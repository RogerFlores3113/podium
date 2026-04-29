# Podium Cleanup Plan

**Audience:** Claude Code (and Roger, reviewing).
**Goal:** Minimize Podium's surface area, cost, and demo friction so it can sit live as a portfolio piece for 3–6 months while Roger builds his next project.
**Non-goals:** New features. Tests for new code paths beyond smoke. Refactors that don't serve the above.

---

## How to use this document

Execute phases **in order**. Each phase has acceptance criteria. **Do not start phase N+1 until phase N's acceptance criteria pass.** Phases 1–3 are code-only and reversible. Phase 4 is infra and changes the live deploy. Phase 5 is README/polish.

If something in this doc looks wrong when you (Claude Code) actually inspect the file, **stop and flag it** rather than guessing. Roger has signed off on the *plan*, not on faithful execution of any specific filename or signature that may have drifted since this doc was written.

**Pre-flight (do once, before phase 1):**

- [ ] `git status` clean. New branch: `git checkout -b cleanup-pass-1`.
- [ ] Tag current state: `git tag pre-cleanup-2026-04`. This is the rollback point.
- [ ] Snapshot Terraform state: `cd infra && terraform state pull > /tmp/podium-tfstate-pre-cleanup.json`. Keep this file outside the repo.
- [ ] Verify the live deploy works: hit the deployed URL, sign in, send one chat. If broken before we start, fix that first.
- [ ] Confirm OpenAI API key spending limit is set in OpenAI dashboard. **Hard cap recommended: $20/month.** Guest abuse is the only realistic way Podium burns money.

---

## Phase 1 — Code & Repo Cruft Cleanup

**Risk:** Low. **Reversibility:** Full (git revert).
**Live impact:** None. Code-only changes that don't affect deployed system until next CI deploy.

### 1.1 Delete tracked files that shouldn't be tracked

```bash
git rm __init__.py                           # Empty placeholder at repo root, not a package marker
git rm PoPE_paper.pdf dclm_paper.pdf         # Research PDFs don't belong in code repo
git rm -r uploads/                           # Test PDFs from local dev — should never have been committed
git rm -r podium.egg-info/                   # Build artifact
git rm v5-build-guide.md                     # Build guide in repo root (the one in the project root, not inside docs/)
git rm "v5-build-guide.md:Zone.Identifier"   # Windows download metadata
```

**Notes:**
- The `docs/papers/` move I considered for the PDFs is unnecessary. They're personal research notes, not part of the project. Keep them in a personal Notion/Obsidian instead.
- If `uploads/` doesn't exist as a directory after this, the storage abstraction in `app/services/storage.py` will recreate it at runtime via `os.makedirs(LOCAL_UPLOAD_DIR, exist_ok=True)`. Verified safe.
- `__init__.py` at repo root: confirm with `cat __init__.py` first that it's empty/trivial. If it contains anything substantive, stop and ask.

### 1.2 Update `.gitignore`

Append to `.gitignore`:

```gitignore
# Build artifacts
*.egg-info/
dist/
build/

# Local uploads (S3 in prod)
uploads/

# Windows download metadata
*:Zone.Identifier

# IDE
.vscode/
.idea/

# Environment files (defense in depth — also already covered)
.env
.env.local
.env.production

# Terraform local state files (remote backend in use)
infra/.terraform/
infra/*.tfstate
infra/*.tfstate.backup
infra/.terraform.lock.hcl
```

The `.terraform.lock.hcl` line is a stylistic choice — many projects commit it. For a personal portfolio repo, ignoring it is fine and avoids OS-specific provider hash noise.

### 1.3 Investigate the duplicate alembic migration

**There are two migrations both titled "add tool call fields to messages":**
- `alembic/versions/ca316cd7fec5_add_tool_call_fields_to_messages.py`
- `alembic/versions/dc368990e622_add_tool_call_fields_to_messages.py`

**Do not delete either before running this procedure:**

1. Connect to production RDS (use `aws ecs execute-command` per existing docs).
2. Run: `psql ... -c "SELECT version_num FROM alembic_version;"`
3. Whichever revision is recorded is the one currently applied to prod. Treat the other one as the candidate for deletion.
4. Open both files. Diff them. If they're identical or one is a no-op revision, the unused one is safe to delete.
5. Check `down_revision` chains in BOTH files plus all later migrations. The deletion target must not be referenced as `down_revision` by any other migration.
6. If safe: `git rm alembic/versions/<unused-revision>.py` and update any `down_revision` reference in the chain to point past it.

**If the chain references it and you can't easily fix it: leave both. Cosmetic, not worth breaking migrations over.**

### 1.4 Investigate `frontend/frontend/app/`

Project tree shows a nested `frontend/frontend/app/` directory under `frontend/`. Almost certainly a botched `cp -r` or `mv`.

```bash
# Inspect first:
ls -la frontend/frontend/app/
find frontend/frontend -type f
diff -r frontend/app frontend/frontend/app  # If both exist, see what differs
```

**If contents are a duplicate of `frontend/app/`:** `rm -rf frontend/frontend/`.
**If contents are unique (suggests work-in-progress that was misplaced):** stop and flag to Roger. Do not auto-merge.

### 1.5 Investigate `frontend/proxy.ts` vs `frontend/app/api/[...proxy]/route.ts`

```bash
cat frontend/proxy.ts
```

Two possibilities:
- **Dead code:** unused export from a previous proxy implementation. Delete.
- **Active utility:** imported by something. `grep -r "from.*proxy" frontend/app/` to check.

If unimported and unused: `git rm frontend/proxy.ts`.

### 1.6 Investigate `app/api/`

The tree shows `app/api/` as a directory but lists nothing inside it. Likely empty.

```bash
ls -la app/api/
```

If empty: `rm -rf app/api/` (don't need `git rm` for an empty dir; git ignores them).
If not empty: inspect and decide.

### 1.7 Triage `TODOS.md` and `CLAUDE.md`

- **`CLAUDE.md`:** Keep. Verify it's current. If stale (references old architecture, old tools, old model names), update it as part of phase 5.
- **`TODOS.md`:** Read it. Roll active items into GitHub Issues if you want a backlog. Otherwise delete. **A `TODOS.md` in a portfolio repo signals "I have unfinished work I'm aware of." That's a small but real negative on first impression.**

### Phase 1 acceptance criteria

- [ ] `git status` shows only intentional changes
- [ ] No `*.pdf`, `__pycache__/`, `*.egg-info/`, or `uploads/` content tracked
- [ ] `.gitignore` updated; new commits won't re-add these
- [ ] Duplicate alembic migration investigated; either fixed or explicitly left with a one-line note in `CLAUDE.md` explaining why
- [ ] `frontend/frontend/` resolved
- [ ] `frontend/proxy.ts` and `app/api/` resolved
- [ ] `pyproject.toml`, `frontend/package.json` still parse correctly
- [ ] **Backend tests still pass:** `uv run pytest tests/`
- [ ] **Frontend tests still pass:** `cd frontend && npm test`
- [ ] Local dev still works: `docker compose up -d && uv run uvicorn app.main:app --reload` succeeds

Commit before starting Phase 2.

---

## Phase 2 — Tool Roster Trim

**Risk:** Low. **Reversibility:** Full.
**Decision:** Keep `document_search`, `memory_search`, `web_search`, `url_reader`, `python_executor`. Remove `weather`, `image_generation`.

### 2.1 Delete tool files

```bash
git rm app/tools/weather.py
git rm app/tools/image_generation.py
```

### 2.2 Update tool registry

In `app/tools/__init__.py`, remove these two lines:

```python
from app.tools import weather  # noqa: E402, F401
from app.tools import image_generation  # noqa: E402, F401
```

### 2.3 Remove related dependencies

In `pyproject.toml`, scan the `[project] dependencies` block for entries that exist *only* to support these two tools:
- `image_generation.py` likely depends on the OpenAI SDK directly (already needed for chat — keep) or on something like `pillow` (remove if present and not used elsewhere — `grep -r "from PIL" app/ frontend/` to verify)
- `weather.py` may depend on a weather provider SDK or on `httpx` (already a core dep — keep `httpx`)

**Don't blanket-remove dependencies.** Verify each candidate is unused before removing.

After edits: `uv lock && uv sync` to regenerate `uv.lock`.

### 2.4 Remove environment variables and infra references

If `weather` used a provider API key:
- Remove from `app/config.py` Settings
- Remove from `.env.example`
- Remove from `infra/secrets.tf` (the `aws_ssm_parameter` resource for it)
- Remove from `infra/iam.tf` (the secrets read policy)
- Remove from `infra/ecs.tf` (the `secrets` array entry referencing it)
- Remove from `infra/variables.tf`
- Remove from `infra/terraform.tfvars`

`image_generation` uses the existing OpenAI key — no infra changes needed beyond the file deletion.

### 2.5 Frontend cleanup

Search for any frontend references:

```bash
grep -rn "weather\|image_generation\|imageGeneration\|imageGen" frontend/app/
```

Likely findings:
- A type definition in `ToolCallDisplay` or similar that branches on tool name → just remove those branches; the generic case will handle it
- An icon mapping → remove

The `ToolCallDisplay` component should still gracefully render any tool name it doesn't recognize. Verify with the existing `frontend/__tests__/ToolCallDisplay.test.tsx`.

### Phase 2 acceptance criteria

- [ ] Tool registry imports without error: `uv run python -c "from app.tools import all_tools; print([t.name for t in all_tools()])"`
- [ ] Output shows exactly `['web_search', 'document_search', 'python_executor', 'memory_search', 'url_reader']` (order may vary)
- [ ] Backend tests pass
- [ ] Frontend tests pass
- [ ] Local chat with the agent works using each remaining tool at least once (manual smoke)

Commit.

---

## Phase 3 — Guest Mode + Strict BYOK

**Risk:** Medium. **Reversibility:** Schema migration is reversible if we write a `down`. Code is fully reversible.
**This is the biggest functional change in the cleanup pass.** Take it slow.

### Design summary

| Decision | Choice | Why |
|---|---|---|
| Guest auth | Custom JWT signed with our own secret, validated alongside Clerk JWTs in `app/auth.py` | Avoids Clerk's paid anonymous-users feature; full control |
| Guest identifier | `users.is_guest = TRUE` flag + `clerk_id` filled with synthetic value `guest_<uuid>` | Reuses existing User-keyed code paths; minimal schema change |
| Guest data lifetime | 24 hours from creation | Short enough to limit exposure, long enough for a recruiter session |
| Guest cleanup | Recurring arq cron job, hourly | Already have arq; no new infra |
| Guest model selection | `gpt-5-nano` only (cheapest), forced by backend ignoring any client-supplied model field | Cost containment |
| Guest tool restrictions | Only `document_search`, `memory_search`, `web_search`, `url_reader` (no `python_executor`) | E2B is free for Roger but unbounded resource usage on a public-facing guest path is a bad idea regardless |
| Guest rate limits | 20 messages/session, 10 chat req/min | Aggressive; recruiters won't notice, abusers will |
| Non-guest BYOK behavior | Strict — return 402 if no BYOK key configured. No fallback to system key. | Avoids paying for non-guest usage; consistent with the "BYOK platform" pitch |
| Guest demo data | Seed 2 documents into a shared read-only "demo docs" pool that guests can search via `document_search` | Recruiter sees a working RAG demo immediately |

### 3.1 Schema migration

New migration: `add_guest_support_to_users`.

Columns to add to `users`:

```python
is_guest: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
last_active_at: Mapped[datetime] = mapped_column(
    DateTime, nullable=False, server_default=func.now()
)
```

`server_default` matters — existing rows must get a default value during the migration. **Without `server_default` the migration will fail on RDS with a NOT NULL violation on existing rows.**

Index for sweep efficiency:

```python
Index("ix_users_is_guest_last_active", "is_guest", "last_active_at")
```

Generate, **review the autogenerated file** (autogen sometimes misses `server_default`), apply locally first, then plan for the prod migration in Phase 4.

### 3.2 Guest authentication path

New file: `app/services/guest_auth.py`.

Responsibilities:
- `create_guest_user(db) -> (User, jwt_token)` — creates a User row with `is_guest=True`, `clerk_id="guest_<uuid4>"`, returns a JWT signed with `settings.guest_jwt_secret`, expires in 24h
- `verify_guest_token(token) -> dict` — validates HS256 JWT, returns claims

**Add to `app/config.py`:**

```python
guest_jwt_secret: str  # Required. Generate with `openssl rand -hex 32`
guest_session_duration_hours: int = 24
guest_max_messages_per_session: int = 20
```

**Add to `app/auth.py`:** modify `get_current_user_id` to try guest JWT validation if the token doesn't decode as a Clerk JWT. The flow:

```python
# Pseudocode — adapt to actual auth.py structure
async def get_current_user_id(request: Request) -> str:
    token = extract_bearer(request)
    # Try Clerk first
    try:
        claims = verify_clerk_token(token)
        return claims["sub"]
    except (jwt.InvalidTokenError, ClerkError):
        pass
    # Try guest
    try:
        claims = verify_guest_token(token)
        return claims["sub"]  # "guest_<uuid>" — matches users.clerk_id
    except jwt.InvalidTokenError:
        raise HTTPException(401, "Invalid token")
```

**Why try Clerk first:** Real users are far more common in any sustained use; fast path matters for them.

**Token format for guests:** HS256 JWT with payload `{"sub": "guest_<uuid>", "is_guest": true, "exp": <timestamp>}`. The `is_guest` claim is informational; the source of truth is the `users.is_guest` column.

### 3.3 Guest signup endpoint

New file: `app/routers/guest.py`.

```
POST /guest/session
  → creates ephemeral user, returns { token, user_id, expires_at }
```

No auth required for this endpoint (obviously). Rate-limit it heavily — `slowapi`'s remote-address-based limit at e.g. 5 requests/hour/IP is appropriate. This prevents drive-by guest-spam.

Wire it into `app/main.py`:

```python
from app.routers import documents, chat, keys, memories, guest
app.include_router(guest.router)
```

### 3.4 Strict BYOK enforcement

In `app/services/llm.py`, modify `resolve_api_key`:

```python
def resolve_api_key(user: User, user_key: str | None) -> str:
    if user.is_guest:
        return settings.openai_api_key  # System key, only for guests
    if not user_key:
        raise HTTPException(
            status_code=402,  # Payment Required — semantically appropriate
            detail={
                "error": "byok_required",
                "message": "Add your OpenAI API key in Settings to chat. Or sign out and try Podium as a guest.",
            },
        )
    return user_key
```

Note: `resolve_api_key` currently takes `user_key: str | None` and returns the system key as fallback. This change makes the function require the User object so it can check `is_guest`. Update all call sites accordingly — likely just `app/services/agent.py` and `app/routers/chat.py`.

### 3.5 Guest tool filtering

In `app/services/agent.py`, where `get_tool_schemas()` is called to populate `tools=` for the LLM call:

```python
# Pseudocode
GUEST_ALLOWED_TOOLS = {"document_search", "memory_search", "web_search", "url_reader"}

if user.is_guest:
    tool_schemas = [t for t in get_tool_schemas() if t["function"]["name"] in GUEST_ALLOWED_TOOLS]
else:
    tool_schemas = get_tool_schemas()
```

Pass `user` (or `is_guest: bool`) into the agent loop. Don't reach for `ToolContext` for this — the filter applies at schema selection, before the LLM ever sees a tool. Filtering at the schema level prevents the LLM from even *trying* to call `python_executor`.

### 3.6 Guest model forcing

In `app/services/agent.py`, where `model=` is passed to the Responses API call:

```python
if user.is_guest:
    model_id = "gpt-5-nano"
else:
    model_id = settings.chat_model  # or whatever the user selected
```

This ignores any client-supplied model parameter when the user is a guest.

### 3.7 Guest rate limits

Add per-route limits scoped to guest users. `slowapi` keys on remote IP by default; you can pass a custom key function:

```python
def rate_limit_key(request: Request) -> str:
    user_id = getattr(request.state, "user_id", None)
    return user_id or get_remote_address(request)
```

For chat router on guest:
```python
@limiter.limit("10/minute", key_func=rate_limit_key, condition=lambda req: req.state.user.is_guest if hasattr(req.state, "user") else False)
```

Adapt to actual slowapi version semantics. Acceptable to do a simpler approach: just apply the more-restrictive limit globally on the chat endpoint and accept that authenticated users hit the same cap. 10/minute is plenty for a real user.

Also: enforce `guest_max_messages_per_session` by counting messages where `user.is_guest = True` and `created_at >= user.created_at`. If >= 20, return 429. Done in router, not middleware.

### 3.8 Guest cleanup sweep job

In `app/services/worker.py`, add:

```python
async def cleanup_expired_guests(ctx: dict):
    """Hourly job: delete guest users older than 24h and their cascading data."""
    db_session = ctx["db_session"]
    cutoff = datetime.utcnow() - timedelta(hours=settings.guest_session_duration_hours)

    async with db_session() as db:
        result = await db.execute(
            select(User).where(User.is_guest == True, User.created_at < cutoff)
        )
        expired = result.scalars().all()

        for user in expired:
            await db.delete(user)  # Cascades to documents, conversations, messages, memories
        await db.commit()
        logger.info(f"Deleted {len(expired)} expired guest users")
```

Register it as a cron job in `WorkerSettings`:

```python
from arq.cron import cron

class WorkerSettings:
    functions = [process_document, extract_memories_job, cleanup_expired_guests]
    cron_jobs = [
        cron(cleanup_expired_guests, hour=None, minute=0),  # Every hour at :00
    ]
    # ... existing settings
```

**Important:** cascade deletes must work. Verify your foreign keys have `ondelete="CASCADE"` on `documents.user_id`, `conversations.user_id` (if it exists — current models suggest user_id is a string column on these, not an FK; if so, you need explicit deletes for those tables). Inspect `app/models.py` and either:
- Add proper FKs with cascade, OR
- Explicitly delete documents/conversations/memories where user_id matches before deleting the user

**Don't assume cascade. Check.**

### 3.9 Frontend — guest button

`frontend/app/sign-in/page.tsx` (or wherever the sign-in screen lives):

Add a button below the Clerk sign-in component:

```tsx
<button
  onClick={async () => {
    const res = await fetch(`${API_URL}/guest/session`, { method: "POST" });
    const { token, expires_at } = await res.json();
    sessionStorage.setItem("podium_guest_token", token);
    sessionStorage.setItem("podium_guest_expires", expires_at);
    router.push("/");
  }}
>
  Try as guest
</button>
```

`sessionStorage`, not `localStorage` — clears when the tab closes, prevents lingering guest tokens.

### 3.10 Frontend — auth fetch hook

The existing `frontend/app/hooks/useAuthFetch.ts` (verified by `frontend/__tests__/useAuthFetch.test.ts` existing) should be updated to:

1. First, check `sessionStorage` for `podium_guest_token`. If present and unexpired, use it.
2. Else, fall back to Clerk's `getToken()`.

```typescript
const getAuthToken = async () => {
  const guestToken = sessionStorage.getItem("podium_guest_token");
  const guestExpires = sessionStorage.getItem("podium_guest_expires");

  if (guestToken && guestExpires && new Date(guestExpires) > new Date()) {
    return guestToken;
  }
  return await clerk.session?.getToken();
};
```

**Update `useAuthFetch.test.ts` accordingly** to cover the guest path. This is one of the few places where adding a test is worth the time; the auth path is the highest-risk surface in this whole change.

### 3.11 Frontend — guest banner & BYOK gate

When `is_guest` (decode the JWT client-side, or have the backend return a `/me` endpoint), show a banner:

> 👋 Guest session — your data will be deleted in 24 hours. [Sign up](/sign-up) to keep your work.

When a non-guest user without BYOK key sends their first chat and the backend returns 402:

> Add your OpenAI API key to start chatting. [Settings →](/settings)

**Don't** make the BYOK message scary or transactional. Tone: matter-of-fact, this is how the platform works.

### 3.12 Demo seed data

Two demo documents pre-loaded into a shared pool that all guests see when they search.

**Simplest implementation:** A `SEED_USER_ID = "demo_seed"` constant. On guest user creation, no per-user docs are uploaded. Instead, `app/services/retrieval.py` is modified for guest queries:

```python
# In document_search retrieval, when ctx.user.is_guest:
where_clause = or_(
    Chunk.document_id.in_(select(Document.id).where(Document.user_id == user_id)),
    Chunk.document_id.in_(select(Document.id).where(Document.user_id == SEED_USER_ID)),
)
```

This way guests can search the seed corpus + their own uploads (if any). The seed corpus is owned by a sentinel "demo_seed" user that sweep doesn't touch.

**Provisioning the seed corpus:**

Create `scripts/seed_demo_corpus.py` — a one-shot script that, given paths to 2 PDFs, uploads them as the `demo_seed` user, runs the ingestion pipeline, and prints success. Document this in the `README` so it's reproducible.

**Suggested PDFs:** something genuinely interesting and skimmable. Options:
- A short academic paper (something Roger has actually read)
- A well-known short essay or book chapter
- The Podium architecture writeup itself (meta, but works)

Avoid copyrighted content that would be a takedown risk. The PoPE and DCLM papers Roger had committed (now removed in Phase 1) are good candidates if he likes them as content.

### Phase 3 acceptance criteria

- [ ] Migration generates clean and applies locally without error
- [ ] `POST /guest/session` returns a valid token; can chat with that token
- [ ] Guest can use `document_search`, `memory_search`, `web_search`, `url_reader`
- [ ] Guest gets 4xx error if attempting `python_executor` (or, more precisely, the LLM never sees the tool so it never calls it; verify the schema list excludes it)
- [ ] Non-guest user with no BYOK key gets a clean 402 with the documented payload
- [ ] Adding a BYOK key in settings, then chatting, works
- [ ] Guest session UI shows the banner with countdown
- [ ] Sweep job runs locally (test by manually inserting a guest with `created_at` 25h ago, run `uv run arq app.services.worker.WorkerSettings`, verify deletion)
- [ ] Seed corpus loads and is searchable by a guest
- [ ] All existing tests still pass; `useAuthFetch.test.ts` updated and passing

Commit. Push to main only after Phase 4 is also ready (we want one big deploy, not three).

---

## Phase 4 — Infrastructure Cost Optimization

**Risk:** Medium-high. Touches live infra. **Reversibility:** Each step has an explicit rollback.

**Order matters.** This sequence is designed so you can stop at any step and still have a working deploy. **Do them one at a time, applying Terraform after each, verifying the live URL still works.**

**Target end state:** ~$25–35/mo from current ~$85/mo.

### 4.0 Pre-checks

- [ ] Tag current state: `git tag pre-infra-cleanup`
- [ ] Have AWS Console open in another window
- [ ] Have a 30-minute uninterrupted window — don't try this in 5-min slices

### 4.1 Reduce Fargate task size

**Lowest risk, immediate $5/mo savings.**

In `infra/ecs.tf`:

```hcl
# App task
cpu    = "256"   # was 512
memory = "512"   # was 1024

# Worker task — keep this larger because document ingestion uses memory
cpu    = "256"
memory = "1024"
```

**Why these numbers:** `0.25 vCPU + 0.5 GB` is the smallest Fargate config. Podium's app process is mostly I/O-bound (waiting on LLM/DB). Worker keeps `1 GB` because PDF parsing with PyMuPDF can spike.

**Rollback:** revert the diff, `terraform apply`.

**Verification:** after `terraform apply`, ECS deploys new tasks. Watch CloudWatch logs for OOM kills (`exit code 137`). If you see them on the worker, bump worker memory back up.

### 4.2 Replace ElastiCache Redis with self-hosted Valkey on t4g.nano EC2

**Saves ~$12/mo.**

Valkey is the open-source Redis fork. Drop-in compatible. Free.

**New file: `infra/valkey.tf`:**

```hcl
# Smallest Graviton instance — ~$3/mo
resource "aws_instance" "valkey" {
  ami           = data.aws_ami.amazon_linux_2023_arm.id
  instance_type = "t4g.nano"

  subnet_id              = aws_subnet.private[0].id
  vpc_security_group_ids = [aws_security_group.valkey.id]

  user_data = <<-EOF
    #!/bin/bash
    dnf install -y valkey
    systemctl enable valkey
    sed -i 's/^bind 127.0.0.1.*/bind 0.0.0.0/' /etc/valkey/valkey.conf
    sed -i 's/^protected-mode yes/protected-mode no/' /etc/valkey/valkey.conf
    systemctl start valkey
  EOF

  tags = { Name = "${var.project_name}-valkey" }
}

data "aws_ami" "amazon_linux_2023_arm" {
  most_recent = true
  owners      = ["amazon"]
  filter {
    name   = "name"
    values = ["al2023-ami-*-arm64"]
  }
}

resource "aws_security_group" "valkey" {
  name   = "${var.project_name}-valkey-sg"
  vpc_id = aws_vpc.main.id

  ingress {
    from_port       = 6379
    to_port         = 6379
    protocol        = "tcp"
    security_groups = [aws_security_group.ecs_app.id, aws_security_group.ecs_worker.id]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
}
```

Update the `redis_url` local in `infra/ecs.tf`:

```hcl
locals {
  redis_url = "redis://${aws_instance.valkey.private_ip}:6379"
}
```

**Order of operations:**
1. `terraform apply` — provisions Valkey instance, ECS picks up new redis_url on next deploy
2. Watch worker logs — confirm jobs are processing against the new Valkey
3. Once stable, **delete ElastiCache resources** in `infra/elasticache.tf`:
   ```bash
   git rm infra/elasticache.tf  # Or: comment everything in it out, then delete after a week
   terraform apply
   ```

**Rollback if it breaks:** Restore `infra/elasticache.tf`, revert the `redis_url` local, `terraform apply`. Both can coexist briefly during cutover.

**Caveats:**
- This setup has **no Valkey persistence**. arq jobs in flight at the moment Valkey restarts are lost. For Podium's workload (document ingestion = best-effort, memory extraction = best-effort), this is fine.
- Single instance = single point of failure. Acceptable for portfolio scope. If Valkey crashes, arq retries on next worker poll.
- Security group restricts inbound to ECS SGs only. No `auth` configured on Valkey because it's network-isolated. **Standard practice for VPC-internal Redis.**

### 4.3 Replace ALB with Cloudflare Tunnel

**Saves ~$16/mo. Highest impact and highest care needed.**

**Architecture:**

```
Recruiter browser
   ↓ HTTPS
Cloudflare edge
   ↓ tunneled (no inbound to AWS)
cloudflared sidecar in ECS task
   ↓ localhost
podium API container
```

**Why Cloudflare Tunnel and not Cloudflare Proxy + public IP:**
- Fargate task IPs change on every deploy → DNS rot
- Tunnel is outbound-only → no inbound security group rules → simpler and more secure
- Cloudflare Tunnel is free; no minimum, no card required for the basic feature

**Pre-reqs (manual, in Cloudflare dashboard):**

1. Create a Cloudflare account if needed
2. Add the domain Podium uses (move nameservers from current registrar to Cloudflare — this is a one-time cutover that takes 5–60 minutes to propagate)
3. Cloudflare Zero Trust → Networks → Tunnels → Create tunnel → name it `podium-prod`
4. Copy the tunnel token (looks like `eyJhI...`) — this goes into AWS SSM as a secret
5. Configure tunnel public hostname: `podium.yourdomain.com` → service `http://localhost:8000`

**AWS changes:**

Add to `infra/secrets.tf`:
```hcl
resource "aws_ssm_parameter" "cloudflared_token" {
  name  = "/${var.project_name}/cloudflared-token"
  type  = "SecureString"
  value = var.cloudflared_token
  tags  = { Name = "${var.project_name}-cloudflared" }
}
```

Add to `infra/variables.tf`:
```hcl
variable "cloudflared_token" {
  description = "Cloudflare tunnel token"
  type        = string
  sensitive   = true
}
```

Add to `infra/iam.tf`'s ECS execution secrets policy (the resource ARN list).

In `infra/ecs.tf`, add a sidecar container to the **app** task definition (not worker):

```hcl
container_definitions = jsonencode([
  {
    name = "app"
    # ... existing app config unchanged
  },
  {
    name      = "cloudflared"
    image     = "cloudflare/cloudflared:latest"
    essential = true   # If tunnel dies, restart the whole task
    command   = ["tunnel", "--no-autoupdate", "run", "--token", "$(CLOUDFLARED_TOKEN)"]
    secrets = [
      { name = "CLOUDFLARED_TOKEN", valueFrom = aws_ssm_parameter.cloudflared_token.arn }
    ]
    logConfiguration = {
      logDriver = "awslogs"
      options = {
        "awslogs-group"         = aws_cloudwatch_log_group.app.name
        "awslogs-region"        = var.aws_region
        "awslogs-stream-prefix" = "cloudflared"
      }
    }
  }
])
```

**Cutover procedure:**

1. `terraform apply` adds the sidecar — tunnel starts, but ALB is still serving traffic
2. Verify the tunnel works: `https://podium.yourdomain.com` should reach the API
3. Update `frontend/.env.production` `NEXT_PUBLIC_API_URL` to the Cloudflare hostname (was the ALB DNS name)
4. Redeploy frontend on Vercel
5. **Soak test for 24 hours** with both URLs working
6. Once confident: delete ALB resources

```bash
git rm infra/alb.tf
# Also remove ALB target group references in infra/ecs.tf
terraform apply
```

7. Update CORS origins in `app/main.py` to include the new Cloudflare hostname (and remove the old ALB DNS if it was there)

**Rollback (any step before deleting ALB):** Revert `NEXT_PUBLIC_API_URL`, redeploy frontend. ALB is still running, traffic flows back to it. Tunnel remains up but unused.

**Rollback after deleting ALB:** ~5–10 min to recreate from `git revert` + `terraform apply`. Acceptable downtime for a portfolio project.

### 4.4 Move ECS to public subnets, kill NAT Gateway

**Saves ~$32/mo. Biggest win, biggest infra change.**

**Why this is safe with the tunnel:** With Cloudflare Tunnel (Phase 4.3), no inbound traffic ever needs to reach the ECS task from the internet. The tunnel is outbound-only. So the ECS tasks need outbound internet (for OpenAI, Tavily, etc.) but no inbound. Public subnets give us free outbound; the security group blocks all inbound.

**Changes in `infra/ecs.tf`:**

```hcl
# In aws_ecs_service for app and worker:
network_configuration {
  subnets          = aws_subnet.public[*].id    # was: aws_subnet.private[*].id
  security_groups  = [aws_security_group.ecs_app.id]
  assign_public_ip = true                        # was: false
}
```

**Changes in `infra/security_groups.tf`:** Tighten ECS security groups to allow no inbound. The previous SG allowed inbound from the ALB SG; with no ALB, the ECS SG should have **zero ingress rules**.

```hcl
resource "aws_security_group" "ecs_app" {
  name   = "${var.project_name}-ecs-app"
  vpc_id = aws_vpc.main.id
  # NO ingress rules — tunnel is outbound only
  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
}
```

**Changes in `infra/vpc.tf`:** Remove NAT Gateway resources.

```hcl
# Delete:
# - aws_nat_gateway.main
# - aws_eip.nat
# - aws_route_table.private (the route through NAT)
# - aws_route_table_association.private (associations to private subnets)

# Keep:
# - aws_subnet.private (RDS and Valkey still use them — internal-only resources)
# - aws_internet_gateway.main (still needed for public subnet egress)
```

**Cutover procedure:**

1. **Read the diff carefully.** This is the riskiest change.
2. `terraform plan` — confirm changes match expectations. Should show: NAT Gateway destroyed, EIP destroyed, route tables modified, ECS network config changed.
3. `terraform apply` — provisions new ECS tasks in public subnets. Old tasks in private subnets stop. **There WILL be ~2 minutes of downtime during cutover.**
4. Verify the live site works.
5. Verify outbound from ECS still works: tail logs, send a chat that uses `web_search` (Tavily) and a normal LLM call.

**Rollback:** revert the Terraform changes, `terraform apply`. NAT Gateway recreates (takes ~5 min), tasks move back to private subnets, traffic flows again.

### Phase 4 acceptance criteria

- [ ] Live URL still serves traffic
- [ ] All chat functionality works end-to-end
- [ ] Document upload + ingestion still works (worker → S3 → DB)
- [ ] Memory extraction still works (worker → Valkey → DB)
- [ ] AWS Cost Explorer (after 48h) shows daily spend ≤ $1.20
- [ ] No NAT Gateway, no ALB, no ElastiCache in `terraform state list`

Commit and tag: `git tag post-infra-cleanup`.

---

## Phase 5 — README, Diagram, Demo Polish

**Risk:** None (docs only). **Reversibility:** Trivial.

### 5.1 README rewrite

The current README's structure (per project-knowledge search) is a v0-era document. Rewrite the root `README.md` with this skim path in mind: a recruiter has 30 seconds.

**Suggested structure:**

```markdown
# Podium

> A multi-tenant AI assistant platform with BYOK, agentic tools, persistent memory, and a full AWS deployment. Built end-to-end as a portfolio project.

[**Live demo →**](https://podium.yourdomain.com)  ·  [Architecture](#architecture)  ·  [What I learned](#what-i-learned)

![demo gif or screenshot — 600px wide max]

## What it does

(3 bullets, 1 sentence each. Lead with the most impressive — agentic tool use, persistent memory, multi-tenant with BYOK.)

## Try it as a guest

Click "Try as guest" on the sign-in page. Pre-loaded with two demo documents you can ask questions about. Guest sessions expire in 24 hours.

## Architecture

[diagram]

(One paragraph: stack summary. Backend: FastAPI + Postgres+pgvector + Redis/arq. Frontend: Next.js + Clerk. Infra: AWS via Terraform.)

## What I learned

(Honest list of 4–6 specific things. Not feature list. Examples:
- "Wrote my own JWT verification middleware to integrate Clerk before realizing they ship one — kept mine because debugging is easier when you wrote it"
- "Cut infrastructure cost from $85/mo to $30/mo by replacing the NAT Gateway with public subnets + Cloudflare Tunnel, dropping ALB for the tunnel, and self-hosting Valkey instead of ElastiCache"
- "Implemented streaming with SSE before realizing arq's job model didn't compose with it cleanly — split the agent loop and persistence into different concerns"
)

## Local setup

[5 commands max. The reader should be able to copy-paste and have it running.]

## Stack

[clean table or bullet list]
```

**Don't include:**
- Detailed API documentation (that's what `/docs` Swagger is for)
- Build phases (v0/v1/v2) — they're internal scaffolding, not interesting to readers
- Long lists of features — boring

**Do include:**
- Live URL (working, with guest mode)
- Architecture diagram
- One short demo screenshot or GIF (a recruiter who skims will look at this)
- Honest "what I learned" section — this is the differentiator vs other portfolio repos

### 5.2 Architecture diagram

Tool: [excalidraw.com](https://excalidraw.com). Free, exports clean SVG/PNG, the aesthetic looks intentional.

**Content:**

```
[Recruiter browser]
        │ HTTPS
        ↓
[Cloudflare edge]  ←  free CDN, HTTPS, DDoS protection
        │ tunnel
        ↓
┌────────────────────────────────────┐
│ AWS VPC                            │
│                                    │
│ [ECS Fargate: app + cloudflared]   │
│        ↓             ↓             │
│ [RDS Postgres+pgvector]  [Valkey]  │
│        ↑                  ↑        │
│ [ECS Fargate: arq worker]          │
│        ↓                           │
│  [S3: document storage]            │
│                                    │
│  [KMS: BYOK encryption]            │
└────────────────────────────────────┘
        ↓ outbound only
[OpenAI / Tavily / E2B / Clerk]
```

Save to `docs/architecture.png` (PNG so it renders in GitHub READMEs without setup), embed at the top of the architecture section.

### 5.3 Polish CLAUDE.md

Update with:
- The current model constraint (`gpt-5.4-mini`, `gpt-5.4-nano`, `gpt-5-nano`)
- Note about Responses API
- Reference to this cleanup doc as the most recent architectural state
- Pointer at the architecture diagram

### 5.4 Verify the demo path

Pretend you're a recruiter. From a fresh browser:

1. Visit the live URL → see a clean sign-in page with a prominent "Try as guest" option
2. Click "Try as guest" → land in the chat UI within ~3 seconds
3. See the seeded demo documents in a "Documents" sidebar
4. Ask "What's this document about?" — get a sensible answer with `document_search` tool call visible
5. Ask "What's the latest news on X?" — get an answer with `web_search` tool call visible
6. Banner at the top: "Guest session — data deleted in 24 hours. Sign up to keep your work."

**If any step takes >5 seconds or feels janky, fix it.** First impressions matter more than any other feature work in this project right now.

### Phase 5 acceptance criteria

- [ ] README skim test: someone unfamiliar with Podium understands what it is in <30 seconds
- [ ] Architecture diagram renders inline in GitHub
- [ ] Live demo path works smoothly, no obvious bugs
- [ ] CLAUDE.md is current

---

## Smoke test checklist (run after each phase)

- [ ] `docker compose up -d && uv run uvicorn app.main:app --reload` — backend boots
- [ ] `cd frontend && npm run dev` — frontend boots
- [ ] Sign in via Clerk works
- [ ] Send a chat, get a response
- [ ] Upload a PDF, see it transition to "Ready"
- [ ] Ask a question that triggers `document_search`
- [ ] Ask a question that triggers `web_search`
- [ ] Memory extraction runs after a chat (wait 90s, check `memories` table)
- [ ] (After Phase 3) Guest sign-in works
- [ ] (After Phase 3) Non-guest without BYOK gets clean 402
- [ ] (After Phase 4) Live deploy still works end-to-end

---

## Total cost projection (post-cleanup, monthly)

| Component | Cost |
|---|---|
| RDS db.t4g.micro | ~$15 |
| ECS Fargate (0.25 vCPU app + 0.25 vCPU worker, mostly idle) | ~$8 |
| Valkey on t4g.nano | ~$3 |
| S3 + ECR + CloudWatch + KMS + SSM | ~$3 |
| OpenAI (guest demos + Roger's testing) | ~$5–15 |
| Tavily + E2B | $0 (free tiers) |
| Cloudflare | $0 |
| Vercel (frontend) | $0 |
| **Total** | **~$35–45/mo** |

Comfortably under $75. Below the previous $85 baseline by ~50%, with a stronger architecture story to tell.

---

## Open questions for Roger (if Claude Code hits them)

1. **Domain name for Cloudflare** — does Roger have one currently pointed at the ALB? If yes, that's the one we move to Cloudflare. If no, he needs to register one (Cloudflare Registrar is at-cost; Namecheap or Porkbun are fine).
2. **Demo seed documents** — what 2 PDFs does Roger want loaded? Default: PoPE and DCLM (the two he had committed). If something else, swap them.
3. **Existing user data** — are there real (non-Roger) users with data in production? The strict-BYOK transition will leave them unable to chat until they add a key. If yes, send them an email; if no, no action needed.
4. **`TODOS.md` contents** — keep, integrate, or delete?

---

## Recruiter pitch (to refine in the README)

> Podium is a multi-tenant AI assistant platform. Users authenticate via Clerk, bring their own OpenAI keys (encrypted with AWS KMS), upload documents that get embedded into a pgvector-backed semantic index, and chat with an agent that can autonomously chain web search, document retrieval, sandboxed code execution, and persistent memory across conversations. The full system runs on ECS Fargate behind Cloudflare Tunnel, with Postgres in RDS and a self-hosted Valkey replacing ElastiCache for cost. Deployed via Terraform, with CI/CD through GitHub Actions. Originally cost $85/month; refactored to ~$35/month while improving the architecture.

— end —
