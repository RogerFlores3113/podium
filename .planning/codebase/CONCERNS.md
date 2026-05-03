# Codebase Concerns

**Analysis Date:** 2026-05-03

---

## Security Considerations

**Guest JWT secret defaults to empty string:**
- Risk: If `GUEST_JWT_SECRET` is not set in a deployment, `app/config.py:79` defaults to `""`. The code in `app/services/guest_auth.py:17-23` guards against this at call time (returns HTTP 503), and `app/main.py:29-31` logs a CRITICAL warning on startup. However, the configuration field itself (`guest_jwt_secret: str = ""`) does not fail fast at parse time. A misconfigured deploy will start successfully, only failing when a guest session is requested.
- Files: `app/config.py:79`, `app/services/guest_auth.py:17-23`, `app/main.py:29-31`
- Current mitigation: Startup log warning + 503 at request time. Secret is wired through AWS SSM in `infra/secrets.tf:51-59` and `infra/ecs.tf:80-82`, so prod should receive the value correctly.
- Recommendation: Change `guest_jwt_secret: str = ""` to a validator that raises `ValueError` if empty in non-test environments. Alternatively, mark as `guest_jwt_secret: str` (no default) so pydantic-settings fails at startup if the env var is missing.

**KMS fallback uses base64 in dev:**
- Risk: `app/services/encryption.py:25-28` falls back to `base64.b64encode()` when `KMS_KEY_ID` is not set. This is logged as a warning but base64 is not encryption. A developer who forgets to set `KMS_KEY_ID` in a staging environment will silently store API keys in plaintext-equivalent form.
- Files: `app/services/encryption.py:25-28`
- Current mitigation: Warning log is present. KMS is enforced in prod via `infra/ecs.tf:58`.
- Recommendation: Add a comment to the `.env.example` warning developers that staging deployments must set `KMS_KEY_ID`. Consider raising an error (not warning) on write if the environment is not clearly "local dev".

**ALB serves HTTP only — no TLS:**
- Risk: `infra/alb.tf` has an HTTP listener that forwards directly to ECS. The HTTPS listener block is commented out. Traffic between the internet and the ALB is unencrypted. Guest JWTs and Clerk tokens transit over HTTP in production until Phase 4.3 (Cloudflare Tunnel) is completed.
- Files: `infra/alb.tf:39-47`
- Current mitigation: None. The HTTPS block is commented out with a note to uncomment when a domain is set.
- Recommendation: Either complete Phase 4.3 (Cloudflare Tunnel, which terminates TLS at the edge) or uncomment and provision the ACM certificate before considering the deployment production-ready.

**Valkey has no auth configured:**
- Risk: `infra/valkey.tf:54-56` disables protected-mode and binds to `0.0.0.0`. There is no `requirepass` set. Access is restricted only by the VPC security group (`infra/valkey.tf:16-39`), which limits inbound to the ECS security group.
- Files: `infra/valkey.tf`
- Current mitigation: Network isolation via SG is the only control. This is the documented intent and is standard practice for VPC-internal Redis. Acceptable for a portfolio project.
- Recommendation: If the project ever has real user data at scale, add a Valkey password and thread it through the `redis_url` in ECS environment variables.

**CORS origins are hardcoded:**
- Risk: `app/main.py:52-58` lists `http://localhost:3000`, `https://podium-beta.vercel.app`, and `http://localhost:8000` as allowed origins. If the Vercel URL changes or Cloudflare Tunnel is added, CORS will block the frontend silently.
- Files: `app/main.py:52-58`
- Current mitigation: Static list works for the current deploy. No dynamic resolution.
- Recommendation: Move CORS origins to a config field (e.g., `cors_allowed_origins: list[str] = [...]`) so they can be overridden per environment without code changes.

---

## Tech Debt

**`generate_response` and `generate_response_stream` are dead code:**
- Issue: `app/services/llm.py:111-177` defines two functions (`generate_response`, `generate_response_stream`) that are not imported or called anywhere in the application. The chat router uses `run_agent` from `app/services/agent.py` exclusively.
- Files: `app/services/llm.py:111-177`
- Impact: Dead code inflates the file, confuses readers about the actual request path, and adds surface area that could drift out of sync with live code.
- Fix approach: Delete both functions. The file's remaining responsibilities (building conversation history, resolving API keys, fetching user keys) stay.

**Duplicate `from litellm import acompletion` in `llm.py`:**
- Issue: `app/services/llm.py:4` and `app/services/llm.py:20` both import `acompletion` from litellm. The second import is redundant.
- Files: `app/services/llm.py:4,20`
- Impact: Minor — Python deduplicates module imports at runtime. Cosmetic noise in a visible file.
- Fix approach: Remove line 20.

**`scripts/seed_demo_corpus.py` calls `save_file` with wrong arity:**
- Issue: `scripts/seed_demo_corpus.py:47` calls `await save_file(pdf_path.read_bytes(), doc_id, pdf_path.name)` with three arguments. `app/services/storage.py:20` defines `save_file(file_content: bytes, file_key: str) -> str` — only two parameters. Additionally, `save_file` is synchronous (not `async`), so the `await` will error.
- Files: `scripts/seed_demo_corpus.py:47`, `app/services/storage.py:20`
- Impact: `scripts/seed_demo_corpus.py` will fail at runtime with a `TypeError` on the first PDF. The seed corpus (required for the guest demo experience) cannot be provisioned until this is fixed.
- Fix approach: Change the call to `storage_path = save_file(pdf_path.read_bytes(), f"{doc_id}.pdf")` (no `await`, construct the file key explicitly).

**`rate_limit_chat` config field is unused:**
- Issue: `app/config.py:74` defines `rate_limit_chat: str = "30/minute"` but `app/routers/chat.py:71` hardcodes `@limiter.limit("5/minute")` directly. The config field is never referenced.
- Files: `app/config.py:74`, `app/routers/chat.py:71`
- Impact: The config field misleads future readers into thinking the rate limit is 30/minute. Changing the config field has no effect on actual behavior.
- Fix approach: Either use `@limiter.limit(settings.rate_limit_chat_stream)` in the decorator, or delete the unused `rate_limit_chat` config field and keep the hardcoded value with a comment explaining why.

**Naive character-based text chunking:**
- Issue: `app/services/ingestion.py:30-46` implements chunking by character count. The comment on line 37 acknowledges this is a "naive implementation" and defers better approaches. Character boundaries do not align with token boundaries or semantic units, leading to inconsistent chunk sizes by token count and potentially splitting words mid-token at boundaries.
- Files: `app/services/ingestion.py:30-46`
- Impact: Retrieval quality suffers for documents where sentence/paragraph boundaries matter. Not a correctness bug, but a quality ceiling.
- Fix approach: Switch to sentence-boundary or token-count-aware chunking. `tiktoken` is already a transitive dependency via the OpenAI SDK. Use it to split on token count rather than character count.

**Documents router creates a new Redis pool per upload request:**
- Issue: `app/routers/documents.py:55-66` creates a new `arq` Redis pool connection on every upload request and closes it before returning. The chat router correctly reuses `request.app.state.redis_pool` set at startup. The documents router bypasses this shared pool.
- Files: `app/routers/documents.py:55-65`
- Impact: Each document upload opens and closes a TCP connection to Valkey. At low concurrency this is harmless. Under load it wastes connections and adds latency (~5-20ms per upload). Also inconsistent with the pattern established in the chat router.
- Fix approach: Change the documents router to use `request.app.state.redis_pool.enqueue_job(...)` instead of creating its own pool. Requires adding `Request` as a parameter (already imported).

**`app/services/worker.py` sweeps on `User.created_at`, not `User.last_active_at`:**
- Issue: The design doc (PODIUM_CLEANUP.md Phase 3.1) specified adding a `last_active_at` column and using it for the sweep cutoff. The migration (`e7f3a1b9c042`) only added `is_guest`, not `last_active_at`. The sweep in `app/services/worker.py:111-115` uses `User.created_at` as the cutoff. This means a guest who actively chats for 23h59m will still be deleted on schedule — there is no session extension on activity.
- Files: `app/services/worker.py:111-115`, `app/models.py` (no `last_active_at` column), `alembic/versions/e7f3a1b9c042_add_guest_support_to_users.py`
- Impact: Minor behavioral difference from the original design. For a 24h portfolio demo, inactive deletion is acceptable. However, if a recruiter is mid-session at hour 24, their session is deleted without extension. Per the design doc intent, this is a deferred feature.
- Fix approach: Add `last_active_at` column to `users`, update the sweep query, and bump `last_active_at` on each `chat_stream` request for guests.

**Missing sweep index on `(is_guest, created_at)`:**
- Issue: The design doc (PODIUM_CLEANUP.md Phase 3.1) specified creating `Index("ix_users_is_guest_last_active", "is_guest", "last_active_at")` for sweep efficiency. No such index exists in the migration (`e7f3a1b9c042`) or in `app/models.py`. The sweep query does a full table scan on `users` hourly.
- Files: `alembic/versions/e7f3a1b9c042_add_guest_support_to_users.py`, `app/models.py`
- Impact: Negligible at portfolio scale (few hundred users). Matters if the user table grows significantly.
- Fix approach: Add a new migration that creates `Index("ix_users_is_guest_created_at", "is_guest", "created_at")`.

---

## Missing Features from Design Doc

**Seed corpus not provisioned (Phase 3.12 incomplete):**
- Problem: The design doc requires two demo PDFs loaded as the `demo_seed` user so guests can run `document_search` and see results immediately. The retrieval code in `app/services/retrieval.py:29-44` correctly queries `user_id = :seed_user_id` when `include_seed=True`. The seed script exists at `scripts/seed_demo_corpus.py`. But the script has a `save_file` call signature bug (see Tech Debt), and more importantly, no seed documents have been loaded into production.
- Files: `scripts/seed_demo_corpus.py`, `app/services/retrieval.py:29-44`, `app/config.py:84`
- Impact: Guests who try `document_search` get "No relevant documents found in your library." The core demo path — recruiter tries document RAG immediately — returns nothing. This is the single biggest experience gap for the guest demo path.
- Fix approach: (1) Fix `save_file` call signature in `scripts/seed_demo_corpus.py`. (2) Choose two interesting PDFs. (3) Run the seed script against production: `uv run python -m scripts.seed_demo_corpus <file1.pdf> <file2.pdf>`. Requires a one-time connection to the production environment.

**Phase 4.3 (Cloudflare Tunnel) not completed:**
- Problem: `infra/alb.tf` still exists and serves production traffic. The ALB costs ~$16/month and serves only HTTP (no TLS). The HTTPS listener is commented out. Cloudflare Tunnel was the planned replacement but no `cloudflared` sidecar is present in `infra/ecs.tf`.
- Files: `infra/alb.tf`, `infra/ecs.tf`
- Impact: ~$16/month unnecessary spend. HTTP-only traffic (no TLS termination). The architecture diagram referenced in PODIUM_CLEANUP.md Phase 5.2 shows Cloudflare Tunnel but the actual infra does not match.
- Fix approach: Follow PODIUM_CLEANUP.md Phase 4.3 in order. Add cloudflared sidecar to `infra/ecs.tf`, provision tunnel token in SSM, delete `infra/alb.tf` after soak period. Also complete Phase 4.4 (NAT Gateway removal) for the full $32/month savings.

---

## Infra: Single Points of Failure

**Valkey on a single t4g.nano EC2 instance:**
- Problem: `infra/valkey.tf` provisions one EC2 instance. If it reboots, crashes, or is replaced by Terraform (AMI change, user_data change), arq loses all pending jobs and the limiter loses rate limit counters. Memory extraction jobs in flight are silently dropped. Rate limit counters reset (allowing brief rate limit bypass).
- Files: `infra/valkey.tf:41-63`
- Current state: Explicitly acknowledged in PODIUM_CLEANUP.md Phase 4.2: "Single instance = single point of failure. Acceptable for portfolio scope."
- Impact: For the portfolio use case (low traffic, best-effort jobs) this is acceptable. Jobs that fail get retried on the next user request. Rate limits reset briefly on instance restart. No user data is lost (all persistent data is in RDS).
- Fix approach: For robustness beyond portfolio scope, replace with ElastiCache Valkey (managed, Multi-AZ). Not recommended for cost reasons unless the project scales.

**No health check on Valkey:**
- Problem: There is no CloudWatch alarm or ECS health check for the Valkey instance. If it dies silently, the app continues accepting requests but memory extraction fails silently (the `except` in `app/routers/chat.py:229-237` swallows the error with a warning log). Rate limiting also silently fails open (slowapi default behavior on Redis unavailability).
- Files: `app/routers/chat.py:229-237`, `infra/valkey.tf`
- Current mitigation: Warning log on memory extraction failure. No alerting.
- Recommendation: Add a CloudWatch alarm on the EC2 instance `StatusCheckFailed` metric. Optional: add a `/health` endpoint check that includes Redis connectivity.

---

## Fragile Areas

**SSE chat stream and database commit ordering:**
- Files: `app/routers/chat.py:153-258`
- Why fragile: The `event_generator` async generator handles SSE streaming, message persistence, and Redis job scheduling in one tightly coupled function. If the client disconnects mid-stream, the generator may be abandoned mid-commit. FastAPI/Starlette SSE generators are not guaranteed to run `finally` blocks on client disconnect. Messages can be partially persisted (assistant message without tool results, or tool results without the preceding assistant message).
- Safe modification: Do not add more state transitions inside `event_generator`. Any new persistence logic should follow the existing pattern: `db.flush()` inside the stream, `db.commit()` only on `done` or `error`.
- Test coverage: No integration tests cover the partial-disconnect scenario.

**`app/services/agent.py` `_run_responses_agent` accumulates `input_messages` in place:**
- Files: `app/services/agent.py:89-229`
- Why fragile: `input_messages` is mutated across loop iterations (lines 181-222). If the list grows very large (many tool call rounds), subsequent Responses API calls include the full history, increasing token usage and latency each iteration. There is no truncation logic in the Responses API path, unlike the Chat Completions path where `build_conversation_history` applies a token budget.
- Safe modification: Be aware that adding more tool-calling depth increases context window consumption quadratically per session for Responses API models. The `agent_max_iterations` cap (default 10) is the only protection.
- Test coverage: `tests/test_agent.py` covers the agent loop but not multi-iteration context growth.

**Guest token expiry check is client-side only:**
- Files: `frontend/app/page.tsx:17-26`, `frontend/app/hooks/useAuthFetch.ts:27-32`
- Why fragile: The frontend checks `new Date(guestExpires) > new Date()` to decide whether to use the guest token. If the client clock is wrong (common on some devices), a token that expired server-side may still be sent, resulting in a 401. Conversely, a valid token may be discarded early. The backend correctly validates `exp` in the JWT on every request, so incorrect clock on the client causes user-visible auth failures with no recovery path (the guest would need to manually clear sessionStorage or open a new tab).
- Safe modification: The risk is low for the portfolio use case. If adding clock-skew tolerance, the backend is the correct enforcement point (already enforced). The frontend check is only an optimization to avoid sending known-expired tokens.
- Test coverage: `frontend/__tests__/useAuthFetch.test.ts` covers the happy path but not clock-skew edge cases.

---

## Performance Bottlenecks

**Embedding always uses the system OpenAI key:**
- Problem: `app/services/ingestion.py:56-61` calls `aembedding` with `api_key=settings.openai_api_key` (the system key). Document ingestion for authenticated users burns the system key for embeddings even if the user has their own BYOK key. Memory extraction in `app/services/memory.py` similarly uses the system key for the extraction LLM call.
- Files: `app/services/ingestion.py:56-61`, `app/services/memory.py` (uses `acompletion` without an explicit user key)
- Impact: In strict BYOK mode, authenticated users chatting burn the operator's OpenAI key for embedding and memory extraction — not just guests. This is a hidden cost vector. At low traffic it is negligible. At scale it becomes meaningful.
- Fix approach: Thread the user's API key (if available) through to `generate_embeddings` and the memory extraction call. Requires passing the user context into the ingestion pipeline.

**Document poll on every upload creates a new Redis pool:**
- Already noted in Tech Debt above (`app/routers/documents.py:55-66`).

---

## Test Coverage Gaps

**No integration tests for the full guest session flow:**
- What's not tested: `POST /guest/session` → chat with guest token → rate limit enforcement → sweep job deletes the user.
- Files: `tests/test_guest_auth.py` (unit only), `tests/test_byok_and_guest_guards.py` (unit only)
- Risk: A regression in guest JWT verification, the sweep cutoff logic, or the guest cap enforcement would not be caught by the current test suite.
- Priority: Medium. The guest flow is the primary demo path for recruiters.

**No tests for `scripts/seed_demo_corpus.py`:**
- What's not tested: The seed script itself. The `save_file` arity bug (see Tech Debt) was not caught because no test exercises the script.
- Files: `scripts/seed_demo_corpus.py`
- Risk: The script fails silently or with confusing errors when run against production.
- Priority: High. This is a prerequisite for the guest demo experience.

**No tests for the SSE streaming endpoint:**
- What's not tested: `POST /chat/stream` end-to-end. The agent loop, message persistence, and SSE event format are all untested at the HTTP layer.
- Files: `app/routers/chat.py`
- Risk: Changes to the event format or persistence logic could break the frontend without being caught.
- Priority: Medium. The chat path is the core product feature.

**Frontend tests do not cover the guest token expiry path:**
- What's not tested: `useAuthFetch.ts` when the guest token is present but expired.
- Files: `frontend/__tests__/useAuthFetch.test.ts`
- Risk: A regression in the expiry check logic would cause guests to receive 401 errors.
- Priority: Low. Simple edge case, low frequency.

---

## Known Bugs

**`scripts/seed_demo_corpus.py` incorrect `save_file` call:**
- Symptoms: `TypeError: save_file() takes 2 positional arguments but 3 were given` when running the seed script.
- Files: `scripts/seed_demo_corpus.py:47`
- Trigger: `uv run python -m scripts.seed_demo_corpus <file.pdf>`
- Workaround: Manually construct the storage path and call `save_file(content, f"{doc_id}.pdf")` without the third argument. See Tech Debt section for the correct fix.

**Duplicate alembic migration title (cosmetic, not a correctness bug):**
- Symptoms: Two migration files both titled "add tool call fields to messages" (`ca316cd7fec5` and `dc368990e622`). They are intentionally chained: `ca316cd7fec5` adds `tool_calls` + `tool_call_ids`, and `dc368990e622` renames `tool_call_ids` to `tool_call_id` (singular). The chain is correct and applies cleanly.
- Files: `alembic/versions/ca316cd7fec5_add_tool_call_fields_to_messages.py`, `alembic/versions/dc368990e622_add_tool_call_fields_to_messages.py`
- Impact: Cosmetic confusion only. No correctness issue. Both migrations are needed and must stay.
- Note: This is documented in `CLAUDE.md` as intentional.

---

## Dependencies at Risk

**`gpt-5-nano` model availability:**
- Risk: `app/config.py:5-11` lists `gpt-5-nano` as the guest model. It is also hardcoded in `app/services/agent.py:15` as a `RESPONSES_API_MODELS` member and in `app/services/agent.py:286`. `gpt-5-nano` is a very new model (may be renamed, deprecated, or have API surface changes). If OpenAI renames or removes it, guest chat breaks entirely.
- Files: `app/config.py:5-11`, `app/services/agent.py:15,286`
- Current mitigation: `RESPONSES_API_MODELS` frozenset is the dispatch gate — only models in this set use the Responses API path. If `gpt-5-nano` is renamed, update the model ID in `AVAILABLE_MODELS` and `RESPONSES_API_MODELS`.
- Recommendation: Pin the model string to a known stable alias if one is available. Add a startup check that logs a warning if the configured model is not in `AVAILABLE_MODELS`.

**`litellm` version dependency:**
- Risk: `app/services/agent.py` uses `litellm.acompletion` for Chat Completions models while `app/services/agent.py:89-229` uses the raw `openai.AsyncOpenAI` client for Responses API models. The two code paths are not interchangeable. If litellm adds Responses API support and the code is migrated, or if litellm's interface changes, both paths need updating.
- Files: `app/services/agent.py`, `pyproject.toml`
- Impact: Low for a stable portfolio project. A litellm major version bump could break the `acompletion` streaming interface.

---

*Concerns audit: 2026-05-03*
