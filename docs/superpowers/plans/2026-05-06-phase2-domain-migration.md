# Phase 2 — Domain Migration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move Podium to `podium.rogerflores.dev` (frontend) and `api.podium.rogerflores.dev` (backend) with zero downtime. Old `podium-beta.vercel.app` continues working during transition.

**Architecture:** Cloudflare DNS proxies both subdomains. Frontend is a Vercel custom domain (CNAME). Backend routes through Cloudflare's proxy to the existing ALB (HTTP, Flexible SSL mode — no ACM cert needed). One backend code change (CORS) + four manual dashboard steps.

**Tech Stack:** Cloudflare DNS, Vercel, Clerk, FastAPI CORS, Terraform (tfvars only).

---

### Task 1: Add new domain to CORS_ORIGINS

**Files:**
- Modify: `app/config.py`
- Test: `tests/test_config.py`

- [ ] **Step 1: Write the failing test**

Add to `tests/test_config.py`:

```python
def test_new_domain_in_cors_origins():
    """podium.rogerflores.dev must be in CORS_ORIGINS for cross-origin chat requests."""
    from app.config import CORS_ORIGINS
    assert "https://podium.rogerflores.dev" in CORS_ORIGINS, (
        "CORS_ORIGINS must include https://podium.rogerflores.dev"
    )
```

- [ ] **Step 2: Run to verify it fails**

```bash
cd /home/rflor/podium && python -m pytest tests/test_config.py::test_new_domain_in_cors_origins -v
```

Expected: FAIL

- [ ] **Step 3: Implement**

In `app/config.py`, add the new domain to `CORS_ORIGINS`:

```python
CORS_ORIGINS = [
    "http://localhost:3000",
    "https://podium-beta.vercel.app",
    "https://podium.rogerflores.dev",
    "http://localhost:8000",
]
```

- [ ] **Step 4: Run test to verify it passes**

```bash
python -m pytest tests/test_config.py::test_new_domain_in_cors_origins -v
```

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add app/config.py tests/test_config.py
git commit -m "feat(domain): add podium.rogerflores.dev to CORS_ORIGINS"
```

---

### Task 2: Update terraform.tfvars with new domain name

**Files:**
- Modify: `infra/terraform.tfvars`

- [ ] **Step 1: Implement**

In `infra/terraform.tfvars`, find the `domain_name` variable and set it:

```hcl
domain_name = "api.podium.rogerflores.dev"
```

(This is informational — no HTTPS listener is being added yet. The ALB stays HTTP-only for now. Cloudflare Flexible SSL handles termination.)

- [ ] **Step 2: Commit**

```bash
git add infra/terraform.tfvars
git commit -m "chore(domain): set domain_name to api.podium.rogerflores.dev in tfvars"
```

---

### Task 3: Deploy updated backend to ECS

- [ ] **Step 1: Build and push new Docker image**

```bash
cd /home/rflor/podium
AWS_ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
AWS_REGION=us-east-1
ECR_REPO="${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com/podium-app"

aws ecr get-login-password --region $AWS_REGION | docker login --username AWS --password-stdin $ECR_REPO
docker build -t podium-app .
docker tag podium-app:latest $ECR_REPO:latest
docker push $ECR_REPO:latest
```

- [ ] **Step 2: Force ECS to pull the new image**

```bash
aws ecs update-service \
  --cluster podium-cluster \
  --service podium-app \
  --force-new-deployment \
  --region us-east-1
```

- [ ] **Step 3: Wait for deployment to stabilize**

```bash
aws ecs wait services-stable \
  --cluster podium-cluster \
  --services podium-app \
  --region us-east-1
```

Expected: command exits 0 (service is stable with new tasks running).

- [ ] **Step 4: Verify CORS is live**

```bash
curl -s -I \
  -H "Origin: https://podium.rogerflores.dev" \
  -X OPTIONS \
  "http://rflores-podium-alb-1333147673.us-east-1.elb.amazonaws.com/chat/" \
  | grep -i "access-control"
```

Expected: `access-control-allow-origin: https://podium.rogerflores.dev` in response headers.

---

### Task 4: Cloudflare DNS — add both subdomains

*(Manual step — performed in the Cloudflare dashboard at dash.cloudflare.com)*

- [ ] **Step 1: Add frontend CNAME**

  - Zone: `rogerflores.dev`
  - Type: `CNAME`
  - Name: `podium`
  - Target: `cname.vercel-dns.com`
  - Proxy status: **Proxied** (orange cloud)
  - TTL: Auto

- [ ] **Step 2: Add backend CNAME**

  - Type: `CNAME`
  - Name: `api.podium`
  - Target: `rflores-podium-alb-1333147673.us-east-1.elb.amazonaws.com`
  - Proxy status: **Proxied** (orange cloud)
  - TTL: Auto

- [ ] **Step 3: Set SSL/TLS mode**

  In Cloudflare dashboard → SSL/TLS → Overview → set mode to **Flexible**.

  (Flexible = Cloudflare terminates HTTPS from users, forwards HTTP to the ALB. No cert needed on the ALB.)

---

### Task 5: Vercel — add custom domain

*(Manual step — performed in the Vercel dashboard)*

- [ ] **Step 1: Add domain to Vercel project**

  - Go to Vercel dashboard → `podium` project → Settings → Domains
  - Add `podium.rogerflores.dev`
  - Vercel will show a CNAME verification record — it should already match what was added in Task 4 Step 1
  - Wait for Vercel to confirm the domain is active (green checkmark)

---

### Task 6: Clerk — add new domain to allowed origins

*(Manual step — performed in the Clerk dashboard at dashboard.clerk.com)*

- [ ] **Step 1: Add allowed redirect URL**

  - Go to Clerk dashboard → your application → Domains
  - Add `https://podium.rogerflores.dev` as an allowed domain / redirect URL

- [ ] **Step 2: Update JWT allowed origins (if shown)**

  Some Clerk plans expose an "Allowed origins" field for JWT verification. Add `https://podium.rogerflores.dev` there too.

---

### Task 7: Vercel — update NEXT_PUBLIC_API_URL

*(Manual step — performed in the Vercel dashboard)*

- [ ] **Step 1: Update environment variable**

  - Vercel dashboard → `podium` project → Settings → Environment Variables
  - Find `NEXT_PUBLIC_API_URL`
  - Change value to `https://api.podium.rogerflores.dev`
  - Apply to: Production

- [ ] **Step 2: Redeploy Vercel project**

  Vercel doesn't automatically redeploy when env vars change. Trigger a new deployment:
  - Vercel dashboard → Deployments → Redeploy latest
  - OR push an empty commit: `git commit --allow-empty -m "chore: trigger Vercel redeploy for new API URL"`

---

### Task 8: Smoke test on new domain

- [ ] **Step 1: Test frontend loads**

```bash
curl -s -o /dev/null -w "%{http_code}" https://podium.rogerflores.dev
```

Expected: `200`

- [ ] **Step 2: Test backend health**

```bash
curl -s https://api.podium.rogerflores.dev/health
```

Expected: `{"status": "ok"}` or similar 200 response.

- [ ] **Step 3: Test CORS from new origin**

```bash
curl -s -I \
  -H "Origin: https://podium.rogerflores.dev" \
  -X OPTIONS \
  "https://api.podium.rogerflores.dev/chat/" \
  | grep -i "access-control"
```

Expected: `access-control-allow-origin: https://podium.rogerflores.dev`

- [ ] **Step 4: Manual browser test**

  Visit `https://podium.rogerflores.dev` in a browser:
  - Landing page loads
  - Click "Try as guest" → chat page loads
  - Send a message → response streams back
  - If B-N1 was previously diagnosed as mixed-content: try deleting a conversation. Should now work (HTTPS → HTTPS).

- [ ] **Step 5: Commit and open PR**

```bash
git add app/config.py infra/terraform.tfvars tests/test_config.py
git commit --allow-empty -m "feat(domain): podium.rogerflores.dev live — smoke test passed"
```

Open PR to `main`. Title: `feat: migrate to podium.rogerflores.dev`.
