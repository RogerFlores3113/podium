# Phase 4 — Worker Cost Audit Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Reduce ECS worker task memory from 1024 MB to 512 MB. Saves ~$5–7/month.

**Architecture:** Single Terraform change to the worker task definition. 512 MB is sufficient for PDF chunking + OpenAI embedding calls + pgvector writes. Monitor CloudWatch for OOM kills after deployment.

**Tech Stack:** Terraform, AWS ECS Fargate, CloudWatch.

---

### Task 1: Reduce worker memory in Terraform

**Files:**
- Modify: `infra/ecs.tf`

- [ ] **Step 1: Find the worker task definition**

In `infra/ecs.tf`, find `aws_ecs_task_definition.worker`. It currently reads:

```hcl
resource "aws_ecs_task_definition" "worker" {
  family                   = "${var.project_name}-worker"
  network_mode             = "awsvpc"
  requires_compatibilities = ["FARGATE"]
  cpu                      = "256"
  memory                   = "1024"
```

- [ ] **Step 2: Implement**

Change `memory` from `"1024"` to `"512"`:

```hcl
  cpu    = "256"
  memory = "512"
```

- [ ] **Step 3: Commit**

```bash
git add infra/ecs.tf
git commit -m "feat(cost): reduce worker ECS task memory from 1024 MB to 512 MB"
```

---

### Task 2: Deploy and verify

- [ ] **Step 1: Plan**

```bash
cd infra && terraform plan -out=tfplan
```

Expected: modification to `aws_ecs_task_definition.worker` only. No other resources affected.

- [ ] **Step 2: Apply**

```bash
terraform apply tfplan
```

- [ ] **Step 3: Force worker service to pick up new task definition**

```bash
aws ecs update-service \
  --cluster podium-cluster \
  --service podium-worker \
  --force-new-deployment \
  --region us-east-1

aws ecs wait services-stable \
  --cluster podium-cluster \
  --services podium-worker \
  --region us-east-1
```

Expected: exits 0.

- [ ] **Step 4: Verify worker task is running at 512 MB**

```bash
aws ecs list-tasks --cluster podium-cluster --service-name podium-worker --region us-east-1
# Copy task ARN, then:
aws ecs describe-tasks \
  --cluster podium-cluster \
  --tasks <task-arn> \
  --region us-east-1 \
  | grep memory
```

Expected: `"memory": "512"` in the task definition reference.

---

### Task 3: Monitor for OOM kills

- [ ] **Step 1: Upload a test PDF and trigger ingestion**

  As an authenticated user on `podium.rogerflores.dev`, upload a PDF (any reasonably sized document, 5–20 pages). Watch the upload status indicator — it should complete without hanging.

- [ ] **Step 2: Check CloudWatch for OOM events**

```bash
aws logs filter-log-events \
  --log-group-name /ecs/podium \
  --filter-pattern "OOM\|OutOfMemory\|Killed\|oom_kill" \
  --start-time $(date -d '1 hour ago' +%s000) \
  --region us-east-1
```

Expected: no OOM events.

- [ ] **Step 3: Check ECS task for exit code 137 (OOM kill signal)**

```bash
aws ecs describe-tasks \
  --cluster podium-cluster \
  --tasks <worker-task-arn> \
  --region us-east-1 \
  | grep -i "exitCode\|reason"
```

Expected: no exit code 137. If you see `exitCode: 137` or `reason: "OutOfMemory"`, roll back:

```bash
# Rollback: change memory back to "1024" in infra/ecs.tf and re-apply
terraform apply -target=aws_ecs_task_definition.worker
aws ecs update-service --cluster podium-cluster --service podium-worker --force-new-deployment --region us-east-1
```

- [ ] **Step 4: Open PR**

If no OOM events after 24 hours of normal operation:

Open PR to `main`. Title: `feat: reduce worker memory to 512 MB (~$6/month savings)`.
