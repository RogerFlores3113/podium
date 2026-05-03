<!-- refreshed: 2026-05-03 -->
# Architecture

**Analysis Date:** 2026-05-03

## System Overview

```text
┌─────────────────────────────────────────────────────────────────────────┐
│                        Next.js 16 Frontend                              │
│   `frontend/app/page.tsx` → `frontend/app/components/ChatPage.tsx`      │
│   Auth: Clerk SDK  |  Guest: sessionStorage JWT                         │
└──────────┬──────────────────────────────┬───────────────────────────────┘
           │ direct fetch (NEXT_PUBLIC_API_URL)         │ Next.js API proxy
           │                              │  `frontend/app/api/[...proxy]/route.ts`
           ▼                              ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                        FastAPI Backend  `app/main.py`                   │
│   /guest  |  /chat  |  /documents  |  /keys  |  /memories               │
│   `app/routers/`                                                         │
└──────┬──────────────┬─────────────────────────────────────────┬─────────┘
       │              │                                          │
       ▼              ▼                                          ▼
┌────────────┐  ┌─────────────────────────────────────┐  ┌──────────────┐
│  PostgreSQL │  │  Agent Loop  `app/services/agent.py` │  │ Redis (arq)  │
│  +pgvector │  │  litellm / OpenAI Responses API      │  │ Job Queue    │
│  SQLAlchemy│  │  Tool Registry `app/tools/`           │  │             │
│  async     │  └──────────────────────────────────────┘  └──────┬───────┘
└────────────┘                                                    │
                                                                  ▼
                                                       ┌──────────────────┐
                                                       │  arq Worker      │
                                                       │  `app/services/  │
                                                       │   worker.py`     │
                                                       │  - process_doc   │
                                                       │  - extract_mem   │
                                                       │  - cleanup_guests│
                                                       └──────────────────┘
```

## Component Responsibilities

| Component | Responsibility | File |
|-----------|----------------|------|
| FastAPI app | Routing, middleware, lifespan | `app/main.py` |
| Auth layer | Clerk RS256 + guest HS256 JWT verification | `app/auth.py` |
| Config | Pydantic settings, model registry | `app/config.py` |
| ORM models | SQLAlchemy mapped classes | `app/models.py` |
| Pydantic schemas | Request/response validation | `app/schemas.py` |
| Chat router | SSE streaming, conversation lifecycle | `app/routers/chat.py` |
| Documents router | PDF upload, status polling | `app/routers/documents.py` |
| Keys router | BYOK encryption/decryption | `app/routers/keys.py` |
| Memories router | CRUD + soft-delete for memories | `app/routers/memories.py` |
| Guest router | Ephemeral session creation | `app/routers/guest.py` |
| Agent service | Multi-turn tool-calling loop (litellm + Responses API) | `app/services/agent.py` |
| LLM service | History builder, BYOK resolver, raw generation | `app/services/llm.py` |
| Ingestion service | PDF→chunk→embed pipeline | `app/services/ingestion.py` |
| Memory service | Extraction (LLM), persistence, semantic search | `app/services/memory.py` |
| Retrieval service | pgvector cosine similarity search | `app/services/retrieval.py` |
| Encryption service | AWS KMS encrypt/decrypt + in-process cache | `app/services/encryption.py` |
| Guest auth service | HS256 JWT issue + verify | `app/services/guest_auth.py` |
| Storage service | S3 / local filesystem dual-mode | `app/services/storage.py` |
| Tokens service | tiktoken-based token counting | `app/services/tokens.py` |
| Worker | arq background jobs (doc ingestion, memory extraction, guest cleanup) | `app/services/worker.py` |
| Tool registry | Module-level dict, register-on-import | `app/tools/__init__.py` |
| Tool base | Abstract `Tool` class + `ToolContext` dataclass | `app/tools/base.py` |
| Individual tools | document_search, web_search, url_reader, python_executor, memory_search | `app/tools/*.py` |
| Next.js root | Auth gate: signed-in → ChatPage, guest → ChatPage, else → LandingPage | `frontend/app/page.tsx` |
| ChatPage | SSE consumer, message state, upload, model picker | `frontend/app/components/ChatPage.tsx` |
| useAuthFetch | Hook: prefers guest JWT, falls back to Clerk token | `frontend/app/hooks/useAuthFetch.ts` |
| API proxy | Next.js route that relays requests to backend (avoids CORS in prod) | `frontend/app/api/[...proxy]/route.ts` |
| Settings page | BYOK key management + memory CRUD | `frontend/app/settings/page.tsx` |

## Pattern Overview

**Overall:** Layered monolith (backend) + SPA (frontend), async throughout.

**Key Characteristics:**
- FastAPI routers are thin — business logic lives in `app/services/`
- Agent loop is a pure async generator; the router consumes events and writes to DB
- Tools register themselves on module import via a module-level dict; no manual wiring needed
- Two distinct agent execution paths: litellm Chat Completions (most models) and OpenAI Responses API (`gpt-5-nano`)
- Tenant isolation enforced by passing `user_id` (Clerk sub claim) through every DB query — no middleware-level isolation
- Two user types with different key resolution: guests (system key, model locked to gpt-5-nano, tool subset) vs authenticated (BYOK required, 402 if missing)

## Layers

**Routing Layer:**
- Purpose: HTTP contract, input parsing, auth dependency injection, SSE framing
- Location: `app/routers/`
- Contains: FastAPI `APIRouter` modules, rate limit decorators
- Depends on: `app/services/`, `app/auth.py`, `app/schemas.py`
- Used by: Clients (frontend)

**Service Layer:**
- Purpose: All business logic — agent loop, ingestion pipeline, memory extraction, encryption, storage
- Location: `app/services/`
- Contains: Pure async functions and classes
- Depends on: `app/models.py`, `app/config.py`, external SDKs (litellm, boto3, arq)
- Used by: `app/routers/`, `app/services/worker.py`

**Tool Layer:**
- Purpose: Executable capabilities the agent can invoke
- Location: `app/tools/`
- Contains: `Tool` subclasses, a global registry dict
- Depends on: `app/services/retrieval.py`, `app/services/memory.py`, external APIs (Tavily, E2B)
- Used by: `app/services/agent.py` exclusively

**Data Layer:**
- Purpose: Persistence (PostgreSQL + pgvector), schema, migrations
- Location: `app/models.py`, `app/database.py`, `alembic/`
- Contains: SQLAlchemy ORM models with HNSW vector indexes
- Depends on: PostgreSQL with pgvector extension
- Used by: Service layer via `AsyncSession` dependency

**Background Worker:**
- Purpose: Heavy async jobs that shouldn't block HTTP responses
- Location: `app/services/worker.py`
- Contains: arq job functions, cron jobs, startup/shutdown hooks
- Depends on: `app/services/ingestion.py`, `app/services/memory.py`
- Used by: Routers enqueue via Redis; worker runs as a separate process

**Frontend:**
- Purpose: SPA, SSE streaming consumer, auth token management
- Location: `frontend/app/`
- Contains: Next.js App Router pages, React components, a custom fetch hook
- Depends on: Clerk for auth, backend REST/SSE API
- Used by: End users

## Data Flow

### Chat Request (Happy Path)

1. User submits message → `POST /chat/stream` (`app/routers/chat.py:72`)
2. `get_or_create_user` dependency verifies JWT (Clerk or guest), provisions user row if new (`app/auth.py:93`)
3. Guest message cap check (if `user.is_guest`) (`app/routers/chat.py:93`)
4. Conversation created or looked up; user `Message` row flushed (`app/routers/chat.py:110-135`)
5. `build_conversation_history` fetches prior messages within token budget (`app/services/llm.py:30`)
6. `get_user_api_key` + `resolve_api_key` determine which LLM key to use (BYOK or system) (`app/services/llm.py:180-237`)
7. `retrieve_core_memories` injects fact/preference memories into system prompt (`app/services/memory.py:177`)
8. `run_agent` async generator begins (`app/services/agent.py:232`) — dispatches to `_run_responses_agent` (gpt-5-nano) or litellm loop
9. Agent streams events: `token`, `tool_call_start`, `tool_call_result`, `tool_call_error`, `assistant_message`, `tool_message`, `done`
10. Router consumes events, writes `Message` rows for assistant + tool turns, forwards SSE to frontend
11. On `done`: DB committed, `extract_memories_job` enqueued on Redis with a delay (`app/routers/chat.py:229`)
12. arq worker runs `extract_memories_job` after delay → LLM extraction → embedding → `Memory` rows persisted

### Document Ingestion

1. `POST /documents/upload` receives PDF binary (`app/routers/documents.py:23`)
2. File saved to S3 (prod) or local `uploads/` (dev) via `save_file` (`app/services/storage.py`)
3. `Document` row created with `status="processing"`, committed
4. `process_document` job enqueued on Redis
5. arq worker picks up job → `ingest_document_background` (`app/services/ingestion.py:128`)
6. pymupdf extracts text; `chunk_text` splits with overlap (`app/services/ingestion.py:19-46`)
7. `generate_embeddings` batches to OpenAI `text-embedding-3-small` via litellm
8. `Chunk` rows with vector embeddings stored; `Document.status` set to `"ready"`
9. Frontend polls `GET /documents/{id}` until status transitions

### Document Retrieval (within tool execution)

1. `document_search` tool called with a query string
2. `retrieve_relevant_chunks` embeds query → pgvector HNSW cosine similarity search (`app/services/retrieval.py:11`)
3. For guest users, search also includes `seed_user_id="demo_seed"` rows (shared demo corpus)
4. Top-K chunks returned as context string to agent

### Guest Session Creation

1. `POST /guest/session` (no auth required) (`app/routers/guest.py:16`)
2. `create_guest_user` creates a `User` row with `is_guest=True`, `clerk_id="guest_<uuid>"` (`app/services/guest_auth.py:26`)
3. HS256 JWT issued with `GUEST_JWT_SECRET`, expires in `guest_session_duration_hours`
4. Frontend stores token in `sessionStorage`; `useAuthFetch` prefers it over Clerk token
5. arq cron job `cleanup_expired_guests` runs hourly, hard-deletes guest rows past expiry

## Key Abstractions

**Tool (Abstract Base):**
- Purpose: Uniform interface the agent uses to call any capability
- Location: `app/tools/base.py`
- Pattern: ABC with `name`, `description`, `parameters` class attributes + `execute(ctx, args) -> str`; `to_openai_schema()` serializes to LLM-ready JSON

**ToolContext:**
- Purpose: Per-request context passed to every tool — avoids global state
- Location: `app/tools/base.py`
- Pattern: `@dataclass` with `user_id: str`, `db: AsyncSession`, `is_guest: bool`

**Tool Registry:**
- Purpose: Lazy, self-registering collection of tool instances
- Location: `app/tools/__init__.py`
- Pattern: Module-level `_TOOLS: dict[str, Tool]`. Each tool module calls `register_tool(instance)` at import time. Registry is populated by star-importing the tool modules at the bottom of `__init__.py`.

**Agent Event Protocol:**
- Purpose: Typed dict stream that decouples the agent loop from persistence and SSE formatting
- Location: `app/services/agent.py` (generator) consumed by `app/routers/chat.py`
- Pattern: `{"type": "token"|"tool_call_start"|"tool_call_result"|"tool_call_error"|"assistant_message"|"tool_message"|"done"|"error", ...}`

**Dual Auth (Clerk + Guest):**
- Purpose: Single `verify_token()` entry point that handles both user types
- Location: `app/auth.py:48`
- Pattern: Try Clerk RS256 first; on failure, try guest HS256. Both return the same `sub` claim shape. Downstream code uses `User.is_guest` flag for behavioral differences.

**BYOK Resolution:**
- Purpose: Determine which LLM API key to use per request
- Location: `app/services/llm.py:220`
- Pattern: `resolve_api_key(user, user_key)` — guests always use system key; authenticated users must have BYOK (HTTP 402 if missing)

## Entry Points

**FastAPI Application:**
- Location: `app/main.py`
- Triggers: uvicorn process (or Dockerfile CMD)
- Responsibilities: Lifespan (pgvector extension, Redis pool), middleware, router mounting

**arq Worker:**
- Location: `app/services/worker.py` (`WorkerSettings`)
- Triggers: `arq app.services.worker.WorkerSettings` (separate process)
- Responsibilities: Document ingestion, memory extraction, hourly guest cleanup

**Next.js App:**
- Location: `frontend/app/layout.tsx` → `frontend/app/page.tsx`
- Triggers: Next.js runtime (Vercel or local `next dev`)
- Responsibilities: ClerkProvider wrapping, auth gate, route to ChatPage or LandingPage

## Architectural Constraints

- **Threading:** Python backend is single-threaded async (asyncio event loop via uvicorn). All blocking I/O (file writes in dev mode, pymupdf text extraction) happens in the arq worker process, not the API server.
- **Global state:** Two module-level singletons exist: `_TOOLS` dict in `app/tools/__init__.py` and `_jwks_client` in `app/auth.py`. The BYOK in-process cache `_key_cache` in `app/services/encryption.py` is also global (5-minute TTL).
- **Circular imports:** `app/services/worker.py` defers all model and service imports to inside job functions (`from app.services.ingestion import ...` inside `process_document`) to avoid circular import at module load time.
- **Tenant isolation:** Enforced at the query level only — every DB query filters by `user_id`. There is no row-level security in PostgreSQL. A bug that omits the `user_id` filter would leak data across users.
- **SSE persistence coupling:** The router (`app/routers/chat.py`) both forwards SSE events to the client AND writes `Message` rows to the DB inside the same event generator. A mid-stream client disconnect could leave messages partially written before the `done` event triggers `db.commit()`.

## Anti-Patterns

### generate_response / generate_response_stream are unused dead code

**What happens:** `app/services/llm.py` contains `generate_response()` and `generate_response_stream()` which build RAG prompts. The chat router calls `run_agent()` instead — these functions are never invoked.
**Why it's wrong:** Dead code misleads future developers about the data flow. The RAG path (retrieve then answer) is entirely superseded by the tool-calling agent (which uses `document_search` tool on demand).
**Do this instead:** Remove `generate_response` and `generate_response_stream` from `app/services/llm.py`. The agent handles RAG via `app/tools/document_search.py`.

### redis_pool re-created per upload request

**What happens:** `app/routers/documents.py:55` calls `create_pool(...)` to create a new Redis pool, enqueues one job, then closes it — on every document upload request.
**Why it's wrong:** Creating a pool per request is wasteful and slow. The app already has `app.state.redis_pool` created during lifespan.
**Do this instead:** Pass the `Request` object to `upload_document` and use `request.app.state.redis_pool` (as the chat router does at `app/routers/chat.py:229`).

## Error Handling

**Strategy:** FastAPI exception handlers catch at two levels: `RateLimitExceeded` (HTTP 429 with retry-after) and a global catch-all (`app/errors.py`) that returns HTTP 500 and logs with `exc_info=True`. Within the SSE stream, errors are caught and emitted as `{"event": "error", "data": {...}}` events rather than breaking the connection abruptly.

**Patterns:**
- Auth failures: `HTTPException(401)` from `app/auth.py`
- BYOK missing: `HTTPException(402)` from `app/services/llm.py:resolve_api_key`
- Tool failures: caught in agent loop, emitted as `tool_call_error` events; tool result set to error string so LLM can react
- DB not found: `HTTPException(404)` from router layer
- Guest server misconfiguration: `HTTPException(503)` from `app/services/guest_auth.py` if `GUEST_JWT_SECRET` unset

## Cross-Cutting Concerns

**Logging:** `logging.basicConfig` to stdout in `app/main.py`. Format: `"%(asctime)s | %(levelname)s | %(name)s | %(message)s"`. Every module gets its own `logger = logging.getLogger(__name__)`. No structured logging library.

**Validation:** Pydantic v2 for all request/response bodies (`app/schemas.py`). SQLAlchemy typed columns with `Mapped[...]` annotations for DB-layer type safety.

**Authentication:** All routes except `GET /health` and `POST /guest/session` require a `Bearer` JWT. The `get_current_user_id` and `get_or_create_user` FastAPI dependencies are composed via `Depends()`. Guest token is HS256; Clerk token is RS256 with JWKS verification.

**Rate Limiting:** slowapi (`app/limiter.py`) backed by Redis. Per-endpoint limits configured in `app/config.py`: chat stream 5/min, upload 5/min, read endpoints 60/min, guest session creation 5/hour.

---

*Architecture analysis: 2026-05-03*
