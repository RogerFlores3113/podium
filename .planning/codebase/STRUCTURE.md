# Codebase Structure

**Analysis Date:** 2026-05-03

## Directory Layout

```
podium/
├── app/                        # FastAPI backend (Python package)
│   ├── main.py                 # App factory, lifespan, middleware, router mounting
│   ├── config.py               # Pydantic settings, model registry, AVAILABLE_MODELS
│   ├── models.py               # SQLAlchemy ORM: Document, Chunk, Conversation, Message, User, ApiKey, Memory
│   ├── schemas.py              # Pydantic request/response schemas
│   ├── auth.py                 # JWT verification (Clerk RS256 + guest HS256), get_or_create_user
│   ├── database.py             # AsyncEngine, async_session factory, Base, get_db dependency
│   ├── errors.py               # Global exception handler (500 fallback)
│   ├── limiter.py              # slowapi Limiter instance backed by Redis
│   ├── routers/
│   │   ├── __init__.py
│   │   ├── chat.py             # /chat — conversations, SSE stream
│   │   ├── documents.py        # /documents — PDF upload, status polling
│   │   ├── guest.py            # /guest/session — ephemeral session creation
│   │   ├── keys.py             # /keys — BYOK API key CRUD
│   │   └── memories.py         # /memories — memory CRUD + soft delete
│   ├── services/
│   │   ├── __init__.py
│   │   ├── agent.py            # Agent loop (litellm + Responses API), event generator
│   │   ├── encryption.py       # AWS KMS encrypt/decrypt + in-process TTL cache
│   │   ├── guest_auth.py       # HS256 JWT issue/verify for guest sessions
│   │   ├── ingestion.py        # PDF text extract → chunk → embed pipeline
│   │   ├── llm.py              # History builder, BYOK resolver, raw LLM calls (mostly unused)
│   │   ├── memory.py           # Memory extraction (LLM), persistence, semantic search
│   │   ├── retrieval.py        # pgvector cosine similarity search for document chunks
│   │   ├── storage.py          # S3 / local filesystem dual-mode file store
│   │   ├── tokens.py           # tiktoken token counter (cl100k_base)
│   │   └── worker.py           # arq WorkerSettings: process_document, extract_memories_job, cleanup_expired_guests
│   └── tools/
│       ├── __init__.py         # Tool registry dict + self-registration imports
│       ├── base.py             # Tool ABC + ToolContext dataclass
│       ├── document_search.py  # Semantic search over user's chunks
│       ├── memory_search.py    # Semantic search over user's memories
│       ├── python_executor.py  # E2B sandbox Python execution
│       ├── url_reader.py       # Fetch and extract text from a URL
│       └── web_search.py       # Tavily web search
├── alembic/                    # Database migrations
│   ├── alembic.ini             # (root) Migration config
│   ├── env.py                  # Migration environment (async engine setup)
│   └── versions/               # Migration scripts (6 files)
│       ├── b4590ddcd010_initial_schema.py
│       ├── 8210bae2b443_add_users_and_api_keys_tables.py
│       ├── a1b2c3d4e5f6_add_memories_table.py
│       ├── e7f3a1b9c042_add_guest_support_to_users.py
│       ├── ca316cd7fec5_add_tool_call_fields_to_messages.py  # adds tool_calls + tool_call_ids
│       └── dc368990e622_add_tool_call_fields_to_messages.py  # renames to tool_call_id (singular)
├── frontend/                   # Next.js 16 App Router SPA
│   ├── next.config.ts
│   ├── package.json
│   ├── tsconfig.json
│   ├── vitest.config.ts
│   └── app/
│       ├── layout.tsx          # Root layout — ClerkProvider wrapping
│       ├── page.tsx            # Auth gate: signed-in|guest → ChatPage, else → LandingPage
│       ├── globals.css         # CSS custom properties (design tokens: --bg-base, --accent-warm, etc.)
│       ├── components/
│       │   ├── ChatPage.tsx    # Main chat UI — messages, SSE consumer, sidebar, upload
│       │   ├── LandingPage.tsx # Marketing / sign-in landing
│       │   └── ToolCallDisplay.tsx  # Renders tool call status in the message thread
│       ├── hooks/
│       │   └── useAuthFetch.ts # Unified fetch hook: guest JWT > Clerk token
│       ├── utils/
│       │   ├── time.ts         # formatRelativeTime helper
│       │   └── image.ts        # Image utility helpers
│       ├── settings/
│       │   └── page.tsx        # BYOK key management + memory CRUD
│       ├── sign-in/
│       │   └── [[...sign-in]]/page.tsx  # Clerk sign-in
│       ├── sign-up/
│       │   └── [[...sign-up]]/page.tsx  # Clerk sign-up
│       └── api/
│           └── [...proxy]/
│               └── route.ts    # Next.js API route — proxies all backend calls server-side
├── infra/                      # Terraform (AWS)
│   ├── main.tf / terraform.tf / variables.tf / outputs.tf
│   ├── vpc.tf / security_groups.tf
│   ├── ecs.tf / ecr.tf / iam.tf
│   ├── rds.tf                  # PostgreSQL (RDS)
│   ├── s3.tf                   # Document storage bucket
│   ├── kms.tf                  # KMS key for BYOK encryption
│   ├── alb.tf                  # Application load balancer
│   ├── valkey.tf               # Valkey (Redis-compatible) for rate limiting + job queue
│   ├── secrets.tf              # Secrets Manager
│   └── monitoring.tf           # CloudWatch
├── tests/
│   ├── test_agent.py
│   ├── test_byok_and_guest_guards.py
│   ├── test_config.py
│   ├── test_guest_auth.py
│   └── test_schemas.py
├── scripts/                    # Utility scripts (seed data, etc.)
├── uploads/                    # Local dev file storage (gitignored in prod)
├── Dockerfile                  # Multi-stage build for API server
├── docker-compose.yml          # Local dev stack: API + worker + Postgres + Redis
├── pyproject.toml              # Python project metadata + dependencies
├── uv.lock                     # Locked dependency manifest
└── alembic.ini                 # Alembic config (root level)
```

## Directory Purposes

**`app/routers/`:**
- Purpose: HTTP endpoints only — validation, auth dependency injection, response shaping
- Contains: FastAPI `APIRouter` instances, `@limiter.limit()` decorators
- Key files: `chat.py` (SSE streaming), `documents.py` (upload flow)
- Rule: No business logic here. Call services; return schemas.

**`app/services/`:**
- Purpose: All application logic — LLM calls, ingestion pipeline, encryption, memory
- Contains: Async functions, no FastAPI dependencies
- Key files: `agent.py` (core loop), `ingestion.py` (doc pipeline), `memory.py` (extraction)
- Rule: Services are framework-agnostic. They accept typed arguments, not `Request` objects.

**`app/tools/`:**
- Purpose: Pluggable agent capabilities
- Contains: One file per tool, a registry in `__init__.py`
- Key files: `base.py` (interface), `__init__.py` (registry + auto-import)
- Rule: Each tool file must call `register_tool(MyTool())` at module level.

**`alembic/versions/`:**
- Purpose: Sequential DB schema changes
- Contains: Alembic migration scripts
- Note: Two migrations share the title "add tool call fields to messages" (`ca316cd7fec5` and `dc368990e622`). Both are intentional and chained. Do not collapse them.

**`frontend/app/`:**
- Purpose: Next.js App Router pages and components
- Contains: `page.tsx` files for routes, components, hooks, utilities
- Key files: `components/ChatPage.tsx` (entire chat UI), `hooks/useAuthFetch.ts` (auth)

**`infra/`:**
- Purpose: Production infrastructure as code
- Contains: Terraform modules for AWS ECS, RDS, S3, KMS, Valkey, ALB
- Generated: No (hand-authored); Committed: Yes

## Key File Locations

**Entry Points:**
- `app/main.py`: FastAPI application instance, lifespan, all router mounts
- `app/services/worker.py`: arq `WorkerSettings` class (run as: `arq app.services.worker.WorkerSettings`)
- `frontend/app/layout.tsx`: Next.js root layout with `ClerkProvider`
- `frontend/app/page.tsx`: Auth gate — the first thing users see

**Configuration:**
- `app/config.py`: All settings via `AVAILABLE_MODELS`, `MODEL_CAPABILITIES`, `Settings(BaseSettings)` — loaded from `.env`
- `pyproject.toml`: Python dependencies
- `frontend/package.json`: Node dependencies
- `docker-compose.yml`: Local dev stack (Postgres, Redis, API, worker)

**Core Logic:**
- `app/services/agent.py`: The agent loop — read this to understand the full LLM interaction pattern
- `app/tools/__init__.py`: Tool registry — read to understand how tools are discovered
- `app/auth.py`: Dual-auth entry point — `verify_token()` and `get_or_create_user`
- `app/models.py`: Complete data model — all tables and relationships

**Testing:**
- `tests/test_agent.py`: Agent loop unit tests
- `tests/test_byok_and_guest_guards.py`: Auth guard integration tests
- `tests/test_guest_auth.py`: Guest JWT issue/verify tests

## Naming Conventions

**Files (backend):**
- `snake_case.py` — all Python files use snake_case
- Routers named after the resource: `chat.py`, `documents.py`, `keys.py`, `memories.py`
- Services named after the concern: `agent.py`, `ingestion.py`, `memory.py`, `retrieval.py`
- Tools named after the capability: `document_search.py`, `web_search.py`

**Files (frontend):**
- `PascalCase.tsx` for React components: `ChatPage.tsx`, `LandingPage.tsx`, `ToolCallDisplay.tsx`
- `camelCase.ts` for hooks and utilities: `useAuthFetch.ts`, `time.ts`
- Next.js conventions for pages: `page.tsx`, `layout.tsx`, `route.ts`

**Directories:**
- `snake_case` everywhere (Python convention carried through)

**Python identifiers:**
- Classes: `PascalCase` — `Tool`, `ToolContext`, `WorkerSettings`, ORM models
- Functions/variables: `snake_case`
- Constants: `UPPER_SNAKE_CASE` — `AVAILABLE_MODELS`, `AGENT_SYSTEM_PROMPT`, `GUEST_ALLOWED_TOOLS`

**TypeScript identifiers:**
- Components: `PascalCase`
- Hooks: `useX` prefix
- Interfaces: `PascalCase` — `Message`, `ConversationItem`, `ToolCall`
- Constants: `UPPER_SNAKE_CASE` — `API_URL`, `AVAILABLE_MODELS`, `DEFAULT_MODEL`

## Where to Add New Code

**New API endpoint:**
1. Create or add to an `app/routers/<resource>.py` router
2. Mount it in `app/main.py` with `app.include_router(...)`
3. Add request/response schemas to `app/schemas.py`
4. Business logic goes in a new or existing `app/services/<concern>.py`

**New agent tool:**
1. Create `app/tools/<tool_name>.py`
2. Subclass `Tool` from `app/tools/base.py`, define `name`, `description`, `parameters`, `execute()`
3. Call `register_tool(MyTool())` at module level
4. Add a star import to the bottom of `app/tools/__init__.py`
5. Update `AGENT_SYSTEM_PROMPT` in `app/services/agent.py` to describe the tool
6. If the tool should be allowed for guests, add its `name` to `GUEST_ALLOWED_TOOLS` in `app/services/agent.py`

**New background job:**
1. Add an async function to `app/services/worker.py` with signature `async def my_job(ctx: dict, ...)`
2. Add it to `WorkerSettings.functions`
3. Enqueue from a router using `request.app.state.redis_pool.enqueue_job("my_job", ...)`

**New DB model:**
1. Add SQLAlchemy `Mapped` class to `app/models.py` (inheriting `Base`)
2. Generate migration: `alembic revision --autogenerate -m "description"`
3. Review and apply: `alembic upgrade head`

**New frontend page:**
1. Create `frontend/app/<route>/page.tsx`
2. Use `useAuthFetch` from `frontend/app/hooks/useAuthFetch.ts` for all API calls
3. Follow existing CSS custom property tokens from `frontend/app/globals.css`

**New service:**
- Implementation: `app/services/<concern>.py`

**Shared utilities (backend):**
- Token counting: `app/services/tokens.py`
- File I/O: `app/services/storage.py`
- Encryption: `app/services/encryption.py`

## Special Directories

**`uploads/`:**
- Purpose: Local dev file storage for uploaded PDFs
- Generated: At runtime (created by `os.makedirs` in `app/services/ingestion.py` and `app/services/storage.py`)
- Committed: No (should be in `.gitignore`)

**`alembic/versions/`:**
- Purpose: Version-controlled migration history
- Generated: Via `alembic revision` command
- Committed: Yes — all migration files must be committed

**`.planning/`:**
- Purpose: GSD planning documents (codebase maps, phase plans)
- Generated: By GSD tooling
- Committed: Yes

**`infra/`:**
- Purpose: Terraform state and config
- Generated: Hand-authored
- Committed: Yes (excluding `.terraform/` and state files)

**`frontend/.next/`:**
- Purpose: Next.js build output
- Generated: By `next build`
- Committed: No

---

*Structure analysis: 2026-05-03*
