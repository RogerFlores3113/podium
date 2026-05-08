# Podium v4 Launch — Milestone Design Spec

**Date:** 2026-05-06  
**Branch:** v3-cleanup → new milestone branch  
**Author:** Roger Flores  

---

## Problem Statement

Podium v3 shipped meaningful improvements (markdown rendering, code blocks, card UX fixes) but UAT Round 2 surfaced two critical regressions and several high-priority bugs before the planned v4 domain launch. Simultaneously, the app is still running on `podium-beta.vercel.app` with a temporary ALB URL as the backend, and monthly AWS spend has room to cut further after the v1 ElastiCache elimination.

This milestone delivers three things in strict sequence:
1. Fix all UAT Round 2 findings
2. Move the app to `podium.rogerflores.dev`
3. Eliminate the ALB via Cloudflare Tunnel to reduce monthly AWS cost

---

## Approach

Four sequential phases, each its own PR. No phase begins until the previous one is merged.

**Why sequenced:** The delete crash (B-N1) must be fixed before the new domain goes live — it's the most visible bug any visitor will hit. The domain migration must be live before the Tunnel PR, because the Tunnel PR updates DNS routing that depends on the new domain being active.

---

## Phase 1 — UAT Bug Fixes

### Sprint 1 (critical — merge before domain)

**B-N1: Delete conversation 405 / page freeze**

- **Root cause:** Unconfirmed from static analysis. The DELETE route is correctly defined in FastAPI (`@router.delete("/{conversation_id}")` in `app/routers/chat.py`), CORS allows all methods, and `authFetch` goes directly to the ALB (not through the Next.js proxy). The 405 cannot be reproduced from code alone.
- **Fix strategy during execution:** First run `curl -X DELETE http://<alb-url>/chat/<valid-uuid> -H "Authorization: Bearer <token>" -v` to isolate backend vs. network. If curl 200s → issue is browser-side (likely HTTP ALB from HTTPS frontend = mixed content); the Phase 2 domain migration (which puts HTTPS on the backend via Cloudflare) may resolve this automatically. If curl 405s → investigate route registration and ALB listener rules.
- **Files:** `app/routers/chat.py` (if backend fix needed), `frontend/app/components/ChatPage.tsx` (if frontend error handling needs hardening)

**B-N2: Web search exceeds 10-iteration limit with no final response**

- **Root cause:** The agentic loop in `app/services/agent.py` runs tool calls up to the model-defined iteration cap but has no forced synthesis step after the last allowed call. The model exhausts its budget searching and reading URLs without ever producing a final text response.
- **Fix:** Add a hard `max_iterations` cap (default 10, configurable). After the final allowed tool result is appended, inject a system/user nudge — `"You've completed your research. Now synthesize what you found into a final answer for the user."` — and run one final non-tool completion pass.
- **Files:** `app/services/agent.py`

**N2: "Search my documents" card auto-submits when no uploads exist**

- **Root cause:** The guard in `ChatPage.tsx` `handleCardClick` checks `hasDocuments === false`, but `hasDocuments` is initialized to `null` and may still be `null` when the card is clicked (document check hasn't resolved yet). The `null` check passes the guard and submits the prompt.
- **Fix:** Change guard to `if (label === "Search my documents" && hasDocuments !== true)` so both `false` and `null` (loading/unknown) show the guidance message instead of submitting.
- **Files:** `frontend/app/components/ChatPage.tsx`

**6.1: Guests can access `/settings`**

- **Fix:** Add an auth gate at the top of `SettingsPage` — if `isLoaded && !isSignedIn`, redirect to `/`. Guests have no API keys to manage and no memories to view.
- **Files:** `frontend/app/settings/page.tsx`

### Sprint 2 (high priority — same PR or immediate follow-up)

**B-N3: Textarea pre-fill persists after "+ New conversation"**

- **Root cause:** `handleNewConversation` (called `startNewConversation` in code) resets messages and conversationId but does not clear `prefillValue`. If a user clicks "Read a URL" (which pre-fills the composer) then clicks "+ New conversation", the stale text remains.
- **Fix:** Add `setPrefillValue("")` to `startNewConversation`.
- **Files:** `frontend/app/components/ChatPage.tsx`

**B-N4: Guest session banner ignores dark mode**

- **Root cause:** The guest session banner has a hardcoded background color instead of a CSS theme variable.
- **Fix:** Replace hardcoded background with `var(--bg-elevated)` or `var(--bg-surface)` on the banner container.
- **Files:** `frontend/app/components/ChatPage.tsx` (wherever the banner is rendered)

**1.1: Hero "View source" link points to repo, not profile**

- **Root cause:** The footer link was fixed in N4 but the hero section `LandingPage.tsx` still has the old repo URL.
- **Fix:** Change `href` to `https://github.com/RogerFlores3113`.
- **Files:** `frontend/app/components/LandingPage.tsx`

### Success criteria — Phase 1
- Conversations can be deleted without error or page freeze
- Web search always produces a final text response (no "Agent exceeded N iterations" with no output)
- Clicking "Search my documents" with no uploads shows in-chat guidance, not an API call
- `/settings` redirects guests to `/`
- New conversation resets the composer completely
- Dark mode themes the guest banner
- Hero "View source" links to the GitHub profile

---

## Phase 2 — Domain Migration

### What changes

| Layer | Change |
|-------|--------|
| Cloudflare DNS | `CNAME podium → cname.vercel-dns.com` (proxied) |
| Cloudflare DNS | `CNAME api.podium → rflores-podium-alb-1333147673.us-east-1.elb.amazonaws.com` (proxied) |
| Cloudflare SSL | Mode: **Flexible** — Cloudflare terminates HTTPS, forwards HTTP to ALB. No ACM cert required. |
| Vercel | Add `podium.rogerflores.dev` as custom domain on the Vercel project |
| `app/config.py` | Add `"https://podium.rogerflores.dev"` to `CORS_ORIGINS` |
| Vercel env vars | Set `NEXT_PUBLIC_API_URL=https://api.podium.rogerflores.dev` in Vercel dashboard |
| Clerk dashboard | Add `podium.rogerflores.dev` to allowed redirect URLs and origins |
| `infra/terraform.tfvars` | Set `domain_name = "api.podium.rogerflores.dev"` (informational only — no HTTPS listener yet) |

### What does NOT change
- ALB stays HTTP-only (Cloudflare Flexible SSL handles termination)
- No new AWS resources provisioned
- `podium-beta.vercel.app` continues working during transition (Vercel supports multiple domains)

### Success criteria — Phase 2
- `https://podium.rogerflores.dev` loads the frontend
- `https://api.podium.rogerflores.dev/health` returns 200
- Sign-in/sign-up flow works (Clerk callback lands correctly)
- Chat works end-to-end on the new domain
- B-N1 (delete 405) re-tested — expected to resolve if root cause was mixed content (HTTP ALB from HTTPS Vercel)

---

## Phase 3 — Cloudflare Tunnel (ALB Elimination)

### What changes

| Layer | Change |
|-------|--------|
| Cloudflare dashboard | Create tunnel, save tunnel token |
| AWS SSM | New parameter: `/<project>/cloudflare-tunnel-token` |
| `infra/secrets.tf` | Add SSM parameter resource for tunnel token |
| `infra/ecs.tf` — API task | Add `cloudflared` sidecar container: `cloudflare/cloudflared:latest`, command `["tunnel", "--no-autoupdate", "run"]`, env var `TUNNEL_TOKEN` from SSM secret, no port mappings needed |
| `infra/ecs.tf` — API service | Remove `load_balancer` block and `depends_on = [aws_lb_listener.http]` |
| `infra/alb.tf` | Delete file entirely (ALB, target group, HTTP listener) |
| `infra/security_groups.tf` | Remove ALB security group resource |
| `infra/ecs.tf` — ECS security group | Remove ALB SG from ingress rules |
| `infra/outputs.tf` | Remove any ALB DNS output |
| Cloudflare DNS | Tunnel takes over `api.podium` routing — remove the CNAME, cloudflared manages the route |

### What does NOT change
- Worker task — untouched
- Frontend (Vercel) — untouched
- RDS, Valkey, VPC subnets — untouched
- ECS tasks stay in public subnets (need outbound internet for OpenAI, Tavily, E2B API calls)
- CORS — origin is still `https://podium.rogerflores.dev`, no change needed

### Expected savings
- ELB eliminated: ~$16–18/month
- 2 ALB public IPv4 IPs eliminated: ~$7/month
- **Total: ~$23–25/month**

### Success criteria — Phase 3
- `https://api.podium.rogerflores.dev/health` returns 200 (via Tunnel)
- Chat works end-to-end
- ALB, target group, and listener confirmed destroyed in Terraform state (`terraform state list` shows no `aws_lb.*`)
- AWS Cost Explorer shows ELB line dropping to $0 following billing cycle

---

## Phase 4 — Worker Cost Audit

### Immediate change — reduce worker memory

- Change worker task `memory` from `"1024"` to `"512"` in `infra/ecs.tf`
- Rationale: worker only does PDF chunking + OpenAI embedding calls + pgvector writes; 512 MB is sufficient
- **Expected savings:** ~$5–7/month on ECS

### Deferred — worker scale-to-zero

ARQ uses a polling loop. Scaling to zero requires replacing the polling model with an event-driven trigger (SQS + Lambda or similar). This is a non-trivial refactor with real operational risk for a portfolio app. **Not in scope for this milestone.**

### Deferred — RDS self-hosting

`db.t4g.micro` is already the minimum managed Postgres instance. Replacing it with self-hosted Postgres on the Valkey EC2 would save ~$10–12/month but sacrifices automated backups, managed upgrades, and introduces a single point of failure for both cache and DB. **Not in scope.**

### Success criteria — Phase 4
- Worker ECS task definition updated to 512 MB
- New task deploying and processing document uploads correctly
- No OOM errors in CloudWatch logs after a document ingestion

---

## File-Level Change Summary

| File | Phase | Change |
|------|-------|--------|
| `app/services/agent.py` | 1 | Add max_iterations cap + forced synthesis turn |
| `app/routers/chat.py` | 1 | Fix delete route if curl confirms backend issue |
| `frontend/app/components/ChatPage.tsx` | 1 | Fix N2 guard, B-N3 prefill reset, B-N4 banner theming |
| `frontend/app/settings/page.tsx` | 1 | Add guest redirect |
| `frontend/app/components/LandingPage.tsx` | 1 | Fix hero "View source" URL |
| `app/config.py` | 2 | Add new domain to CORS_ORIGINS |
| `infra/terraform.tfvars` | 2 | Set domain_name |
| `infra/ecs.tf` | 3, 4 | Add cloudflared sidecar; remove ALB refs; reduce worker memory |
| `infra/alb.tf` | 3 | Delete entirely |
| `infra/security_groups.tf` | 3 | Remove ALB security group |
| `infra/secrets.tf` | 3 | Add tunnel token SSM parameter |
| `infra/outputs.tf` | 3 | Remove ALB outputs |

---

## Risks & Mitigations

| Risk | Mitigation |
|------|-----------|
| B-N1 root cause is environmental and doesn't reproduce locally | Curl test against ALB before writing code; Phase 2 HTTPS migration likely resolves it as a side effect |
| Cloudflare Tunnel outage takes down the API | Tunnel has built-in HA (connects to multiple Cloudflare PoPs); acceptable risk for a portfolio app |
| Worker OOM after memory reduction | CloudWatch OOM kill alert is already in place; roll back to 1024 MB if triggered |
| Clerk callback breaks on new domain | Test sign-in immediately after Phase 2 DNS propagates; Vercel old domain stays live as fallback |
| Terraform plan destroys ALB before Tunnel is verified | Execute Phase 3 as: (1) deploy cloudflared sidecar, (2) verify Tunnel works, (3) then `terraform destroy` ALB resources |

---

## Test Plan

**Phase 1:** Re-run UAT guide sections 3.6 (delete), 7.1 (web search), 2.5 (doc search empty state), 6.1 (settings guest gate), 2.4 (URL card prefill on new conversation), 9.2 (dark mode banner), 1.1 (view source link).

**Phase 2:** Full UAT smoke test on `podium.rogerflores.dev` — landing page, guest flow, sign-in, send a chat message, delete a conversation.

**Phase 3:** Same smoke test after Tunnel cutover. Confirm ALB destroyed in Terraform state.

**Phase 4:** Upload a PDF as authenticated user, confirm ingestion completes, confirm document search returns results. Check CloudWatch for OOM events after 24 hours.
