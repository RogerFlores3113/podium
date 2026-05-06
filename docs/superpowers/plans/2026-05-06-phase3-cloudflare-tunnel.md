# Phase 3 — Cloudflare Tunnel (ALB Elimination) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Eliminate the ALB and its associated public IPv4 charges by routing backend traffic through a Cloudflare Tunnel. Saves ~$23–25/month.

**Architecture:** A `cloudflared` sidecar container runs inside the ECS API task. It dials outbound to Cloudflare's network and proxies traffic to `localhost:8000` (FastAPI). The ALB, its target group, its listener, and the ALB security group are removed from Terraform. The ECS tasks remain in public subnets (they still need outbound internet for OpenAI, Tavily, E2B).

**IMPORTANT — execution order:** Deploy sidecar first → verify tunnel works → destroy ALB. Do not destroy the ALB before the tunnel is verified.

**Tech Stack:** Cloudflare Tunnel (`cloudflared`), Terraform, AWS ECS Fargate, AWS SSM.

---

### Task 1: Create the Cloudflare Tunnel (manual)

*(Performed in the Cloudflare dashboard — dash.cloudflare.com)*

- [ ] **Step 1: Create tunnel**

  - Go to Zero Trust → Networks → Tunnels → Create a tunnel
  - Name: `podium-api`
  - Connector: **Docker** (we'll run cloudflared as a container)
  - Copy the tunnel token shown — it looks like `eyJ...` (a long JWT string)

- [ ] **Step 2: Configure public hostname**

  In the tunnel configuration:
  - Public hostname: `api.podium.rogerflores.dev`
  - Service: `http://localhost:8000`
  - Save the tunnel.

- [ ] **Step 3: Note the tunnel token**

  Store it securely for the next task. Do not commit it.

---

### Task 2: Store tunnel token in AWS SSM

**Files:**
- Modify: `infra/secrets.tf`

- [ ] **Step 1: Add SSM parameter to Terraform**

Add to `infra/secrets.tf`:

```hcl
resource "aws_ssm_parameter" "cloudflare_tunnel_token" {
  name  = "/${var.project_name}/cloudflare-tunnel-token"
  type  = "SecureString"
  value = var.cloudflare_tunnel_token

  tags = {
    Name = "${var.project_name}-cloudflare-tunnel-token"
  }
}
```

- [ ] **Step 2: Add the variable to variables.tf**

Add to `infra/variables.tf`:

```hcl
variable "cloudflare_tunnel_token" {
  description = "Cloudflare Tunnel token for cloudflared sidecar"
  type        = string
  sensitive   = true
}
```

- [ ] **Step 3: Add the value to terraform.tfvars**

```hcl
cloudflare_tunnel_token = "eyJ..."   # paste the token from Task 1 Step 2
```

- [ ] **Step 4: Commit Terraform changes (not the token value)**

```bash
git add infra/secrets.tf infra/variables.tf
git commit -m "feat(tunnel): add SSM parameter and variable for Cloudflare tunnel token"
```

Note: `terraform.tfvars` contains the real token and must NOT be committed. Verify it is in `.gitignore`.

```bash
grep "terraform.tfvars" .gitignore || echo "terraform.tfvars" >> infra/.gitignore
```

---

### Task 3: Add cloudflared sidecar to ECS API task

**Files:**
- Modify: `infra/ecs.tf`

- [ ] **Step 1: Add SSM secret reference for the tunnel token**

In `infra/ecs.tf`, find the `aws_ecs_task_definition.app` resource. In its `secrets` array, add:

```json
{
  "name": "TUNNEL_TOKEN",
  "valueFrom": "${aws_ssm_parameter.cloudflare_tunnel_token.arn}"
}
```

- [ ] **Step 2: Add cloudflared as a second container**

In the `container_definitions` list of `aws_ecs_task_definition.app`, add a second container object after the existing `app` container:

```json
{
  "name": "cloudflared",
  "image": "cloudflare/cloudflared:latest",
  "command": ["tunnel", "--no-autoupdate", "run"],
  "environment": [],
  "secrets": [
    {
      "name": "TUNNEL_TOKEN",
      "valueFrom": "${aws_ssm_parameter.cloudflare_tunnel_token.arn}"
    }
  ],
  "logConfiguration": {
    "logDriver": "awslogs",
    "options": {
      "awslogs-group": "${aws_cloudwatch_log_group.app.name}",
      "awslogs-region": "${var.aws_region}",
      "awslogs-stream-prefix": "cloudflared"
    }
  },
  "essential": false
}
```

`essential: false` means if cloudflared crashes, the API container keeps running (better than taking down the whole task).

- [ ] **Step 3: Commit**

```bash
git add infra/ecs.tf
git commit -m "feat(tunnel): add cloudflared sidecar to ECS API task definition"
```

---

### Task 4: Deploy sidecar and verify tunnel — DO NOT remove ALB yet

- [ ] **Step 1: Apply Terraform (adds sidecar only)**

```bash
cd infra && terraform plan -out=tfplan
```

Review plan: should show modifications to `aws_ecs_task_definition.app` and a new `aws_ssm_parameter.cloudflare_tunnel_token`. Should NOT show any ALB destruction yet.

```bash
terraform apply tfplan
```

- [ ] **Step 2: Force ECS to pick up new task definition**

```bash
aws ecs update-service \
  --cluster podium-cluster \
  --service podium-app \
  --force-new-deployment \
  --region us-east-1

aws ecs wait services-stable \
  --cluster podium-cluster \
  --services podium-app \
  --region us-east-1
```

- [ ] **Step 3: Verify cloudflared is running in the task**

```bash
aws ecs list-tasks --cluster podium-cluster --service-name podium-app --region us-east-1
# Copy a task ARN from the output, then:
aws ecs describe-tasks \
  --cluster podium-cluster \
  --tasks <task-arn> \
  --region us-east-1 \
  | grep -A5 '"name": "cloudflared"'
```

Expected: `lastStatus: "RUNNING"` for the cloudflared container.

- [ ] **Step 4: Check CloudWatch for tunnel connection**

```bash
aws logs tail /ecs/podium --filter-pattern "cloudflared" --since 5m --region us-east-1
```

Expected: log lines showing `"Registered tunnel connection"` or similar from cloudflared.

- [ ] **Step 5: Update Cloudflare DNS — switch api.podium from CNAME to Tunnel**

In the Cloudflare dashboard, the tunnel public hostname (`api.podium.rogerflores.dev`) should now be managed by the tunnel, not the CNAME record. Cloudflare handles this automatically when the tunnel is connected and the hostname is configured — verify in Zero Trust → Networks → Tunnels → your tunnel → Public Hostnames.

- [ ] **Step 6: Verify the tunnel endpoint works**

```bash
curl -s https://api.podium.rogerflores.dev/health
```

Expected: 200 response with health payload (traffic now going through tunnel, not ALB).

```bash
# Full CORS check through tunnel
curl -s -I \
  -H "Origin: https://podium.rogerflores.dev" \
  -X OPTIONS \
  "https://api.podium.rogerflores.dev/chat/" \
  | grep -i "access-control"
```

Expected: `access-control-allow-origin: https://podium.rogerflores.dev`

- [ ] **Step 7: Manual browser smoke test**

  Visit `https://podium.rogerflores.dev`, send a message, verify the response streams. The tunnel is now handling the backend traffic.

---

### Task 5: Remove ALB from Terraform

**Files:**
- Delete: `infra/alb.tf`
- Modify: `infra/ecs.tf` (remove load_balancer block and ALB dependency)
- Modify: `infra/security_groups.tf` (remove ALB security group)
- Modify: `infra/outputs.tf` (remove ALB DNS output if present)

- [ ] **Step 1: Remove load_balancer block from ECS service**

In `infra/ecs.tf`, find `aws_ecs_service.app` and remove:

```hcl
  load_balancer {
    target_group_arn = aws_lb_target_group.app.arn
    container_name   = "app"
    container_port   = 8000
  }

  health_check_grace_period_seconds = 120
```

Also remove from `depends_on`:

```hcl
  depends_on = [aws_lb_listener.http]
```

- [ ] **Step 2: Remove ALB security group from ECS security group ingress**

In `infra/security_groups.tf`, find any ingress rule that references `aws_security_group.alb.id` in the ECS security group and remove it.

- [ ] **Step 3: Remove the ALB security group resource**

In `infra/security_groups.tf`, delete the entire `aws_security_group.alb` resource block.

- [ ] **Step 4: Delete infra/alb.tf**

```bash
git rm infra/alb.tf
```

- [ ] **Step 5: Remove ALB outputs**

In `infra/outputs.tf`, remove any output that references `aws_lb.main` or `aws_lb_target_group.app`.

- [ ] **Step 6: Commit**

```bash
git add infra/ecs.tf infra/security_groups.tf infra/outputs.tf
git commit -m "feat(tunnel): remove ALB — traffic now routed through Cloudflare Tunnel"
```

---

### Task 6: Terraform apply — destroy ALB

- [ ] **Step 1: Plan destruction**

```bash
cd infra && terraform plan -out=tfplan
```

Review carefully. Expected destructions:
- `aws_lb.main`
- `aws_lb_target_group.app`
- `aws_lb_listener.http`
- `aws_security_group.alb`

No unexpected destructions (RDS, ECS tasks, Valkey, VPC should be unaffected).

- [ ] **Step 2: Apply**

```bash
terraform apply tfplan
```

- [ ] **Step 3: Verify ALB is gone**

```bash
aws elbv2 describe-load-balancers --region us-east-1 | grep podium
```

Expected: empty output (no podium ALB found).

- [ ] **Step 4: Final health check through tunnel**

```bash
curl -s https://api.podium.rogerflores.dev/health
```

Expected: still returns 200 — tunnel is the only path now.

- [ ] **Step 5: Commit and open PR**

```bash
git commit --allow-empty -m "chore(tunnel): ALB destroyed, tunnel verified — Phase 3 complete"
```

Open PR to `main`. Title: `feat: eliminate ALB via Cloudflare Tunnel (~$25/month savings)`.
