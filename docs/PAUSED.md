# Project paused — 2026-08-01

The live AWS deployment was torn down to stop billing. Everything needed to
bring it back is preserved. This doc is the runbook for restarting.

## What was destroyed

`terraform destroy` ran against `infra/` (backend: S3 bucket
`rflores-podium-terraform-state`, DynamoDB lock table
`rflores-podium-terraform-locks` — both untouched, they live outside the
Terraform-managed state). This removed:

- ECS cluster, services, and task definitions (app + worker)
- RDS instance `rflores-podium-db`
- EC2 Valkey instance
- VPC, subnets, route tables, security groups, IGW
- KMS key `user_keys` (scheduled deletion — see note below)
- SSM parameters (secrets)
- CloudWatch log group, alarms, SNS topic
- ECR repository (images were disposable — rebuilt on redeploy anyway)

## What was preserved

- **All code and Terraform config** — in this repo, on `main`.
- **`infra/terraform.tfvars`** — local, gitignored, holds the variable
  values (db username, project name, alert email, etc.) used for the last
  apply. Needed to `terraform apply` again with the same config.
- **RDS manual snapshot**: `podium-pause-2026-08-01` in `us-east-1`. Manual
  snapshots persist independently of the instance and of Terraform state —
  they are **not** deleted by `terraform destroy` and cost only storage
  (~$0.095/GB-month, roughly $2/month for this DB). Contains all user
  accounts, conversations, memories, and document metadata as of the pause
  date.
- **S3 uploads bucket** (`rflores-podium-uploads`) — `terraform destroy`
  can't delete a non-empty bucket (no `force_destroy` set), so it was left
  in place along with its 16 uploaded documents. Negligible ongoing cost.

## Known tradeoff: KMS key

The `user_keys` KMS key was destroyed (AWS schedules actual deletion 7-30
days out). It encrypted users' BYOK provider API keys at rest. Any BYOK key
in the RDS snapshot is **permanently undecryptable** once the key is gone —
users will need to re-enter their API keys after restart. Guest sessions are
unaffected (they use the cost-capped system key, not BYOK).

## How to restart

1. **Restore the database** from the snapshot instead of letting Terraform
   create a fresh empty one:
   ```bash
   aws rds restore-db-instance-from-db-snapshot \
     --db-instance-identifier rflores-podium-db \
     --db-snapshot-identifier podium-pause-2026-08-01 \
     --region us-east-1
   ```
   Then update `infra/rds.tf` (or import the restored instance into
   Terraform state) so future applies don't try to recreate it.

2. **Re-apply the infra:**
   ```bash
   cd infra
   terraform init
   terraform apply   # uses the existing terraform.tfvars
   ```
   This recreates the VPC, ECS cluster/services, Valkey EC2 instance,
   ECR repo, KMS key (new key — see tradeoff above), SSM parameters, and
   CloudWatch/SNS monitoring.

3. **Push a build** to trigger `.github/workflows/deploy.yml` (build + push
   to ECR, force new ECS deployments), or run `workflow_dispatch` manually.

4. **Turn the frontend back on** — in `frontend/maintenance.config.ts`, set
   `MAINTENANCE_MODE = false`, commit, and push to `main`. Vercel redeploys
   automatically; the maintenance page and its edge redirect
   (`frontend/proxy.ts`) disappear once that flag flips.

## Verifying nothing is still billing

```bash
aws rds describe-db-instances --region us-east-1
aws ecs list-clusters --region us-east-1
aws ec2 describe-instances --region us-east-1 --filters Name=instance-state-name,Values=running
```
All three should come back empty (aside from the untouched Terraform state
bucket/lock table, which cost fractions of a cent).
