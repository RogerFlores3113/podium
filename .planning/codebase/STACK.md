# Technology Stack

**Analysis Date:** 2026-05-03

## Languages

**Primary:**
- Python 3.12 — backend API, services, tools (runtime in Dockerfile; `.python-version` pins 3.10 for local tooling)
- TypeScript 5.x — frontend (strict mode, `target: ES2017`)

**Secondary:**
- HCL (Terraform) — infrastructure as code in `infra/`
- SQL — Alembic migrations in `alembic/`

## Runtime

**Backend:**
- Python 3.12 (docker image: `python:3.12-slim`)
- Package manager: `uv` (astral-sh) — `uv.lock` present, installed via `uv sync --frozen --no-dev`
- ASGI server: Uvicorn (port 8000)

**Frontend:**
- Node.js (version constrained by Next.js 16 requirements)
- Package manager: npm — `package-lock.json` implied (private package)

## Frameworks

**Backend:**
- FastAPI `>=0.128.8` — HTTP API framework (`app/main.py`)
- SQLAlchemy `>=2.0.46` (async) — ORM with `AsyncSession` (`app/database.py`)
- Alembic `>=1.18.4` — database migrations (`alembic/`)
- Pydantic `>=2.12.5` + pydantic-settings `>=2.12.0` — data validation and settings (`app/config.py`)
- sse-starlette `>=3.2.0` — Server-Sent Events for chat streaming
- slowapi `>=0.1.9` — rate limiting middleware (`app/limiter.py`)
- arq `>=0.25.0` — async Redis job queue / background worker (`app/services/worker.py`)

**Frontend:**
- Next.js 16.1.6 — React framework (App Router)
- React 19.2.3 + react-dom 19.2.3
- Tailwind CSS 4.x (via `@tailwindcss/postcss`)
- react-markdown `^10.1.0` + remark-gfm `^4.0.1` — markdown rendering in chat

**Testing:**
- Backend: pytest `>=8.0.0` + pytest-asyncio `>=0.24.0` (`asyncio_mode = "auto"`)
- Frontend: Vitest `^4.1.5` + jsdom `^29.0.2` + @testing-library/react `^16.3.2`

**Build/Dev:**
- Docker + docker-compose (multi-service: `app`, `worker`, `db`, `redis`)
- Terraform `>=1.5.0` with AWS provider `~> 5.0`
- @vitejs/plugin-react `^6.0.1` — Vitest React plugin

## Key Dependencies

**Critical:**
- `litellm>=1.81.10` — LLM abstraction layer used for all model calls (chat completions, embeddings, memory extraction) via `acompletion` / `aembedding` (`app/services/llm.py`, `app/services/ingestion.py`, `app/services/memory.py`)
- `pgvector>=0.4.2` — pgvector SQLAlchemy integration for vector columns (`app/models.py`)
- `asyncpg>=0.31.0` — async PostgreSQL driver (connection string prefix `postgresql+asyncpg://`)
- `pyjwt[crypto]>=2.12.1` — JWT verification for both Clerk (RS256) and guest (HS256) tokens (`app/auth.py`)
- `@clerk/nextjs ^7.0.6` — Clerk authentication SDK for frontend
- `boto3>=1.42.64` — AWS SDK for S3 and KMS (`app/services/storage.py`, `app/services/encryption.py`)

**Infrastructure:**
- `redis[hiredis]>=7.1.1` — Redis client (rate limiting storage, arq job queue)
- `cryptography>=46.0.5` — cryptographic primitives (supports KMS fallback)
- `tiktoken>=0.12.0` — token counting (`app/services/tokens.py`)
- `pymupdf>=1.27.1` — PDF text extraction (`app/services/ingestion.py`)
- `httpx>=0.28.1` — async HTTP client (Jina URL reader in `app/tools/url_reader.py`, test client)
- `tavily-python>=0.7.23` — Tavily web search SDK (`app/tools/web_search.py`)
- `e2b-code-interpreter>=2.6.0` — E2B sandboxed Python execution (`app/tools/python_executor.py`)
- `arc>=1.0` — (dependency of arq ecosystem)
- `python-multipart>=0.0.22` — multipart form uploads (document ingestion)

## Configuration

**Backend Environment (via pydantic-settings, reads `.env`):**
- `DATABASE_URL` — PostgreSQL async URL (required)
- `OPENAI_API_KEY` — system-level OpenAI key for guests and embeddings (required)
- `REDIS_URL` — Redis/Valkey URL (default: `redis://localhost:6379`)
- `CLERK_SECRET_KEY` — Clerk backend secret (required for auth)
- `CLERK_JWKS_URL` — Clerk JWKS endpoint for token verification
- `KMS_KEY_ID` — AWS KMS key ID for BYOK key encryption (empty = base64 dev fallback)
- `S3_BUCKET_NAME` — S3 bucket for uploads (empty = local filesystem dev fallback)
- `GUEST_JWT_SECRET` — HMAC secret for guest session JWTs (required in prod)
- `TAVILY_API_KEY` — Tavily web search key
- `E2B_API_KEY` — E2B sandbox key
- `AWS_DEFAULT_REGION` — default `us-east-1`
- Settings class: `app/config.py` (`Settings(BaseSettings)`)

**Frontend:**
- Clerk publishable key via Next.js environment convention (`NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY`)
- API base URL wired through Next.js env vars

**Build:**
- `pyproject.toml` — Python project manifest and pytest config
- `uv.lock` — pinned dependency lockfile
- `tsconfig.json` — TypeScript config with `@/*` path alias pointing to `frontend/`
- `frontend/vitest.config.ts` — Vitest config (jsdom environment, `@` alias)
- `alembic.ini` — Alembic migration config
- `Dockerfile` — single-stage `python:3.12-slim`, uv-based install
- `docker-compose.yml` — local dev: app + worker + pgvector/pg16 + redis:7-alpine

## Platform Requirements

**Development:**
- Docker + docker-compose for local full-stack (PostgreSQL with pgvector extension, Redis)
- OR: local Python 3.12 + uv, local Node.js, external PostgreSQL with pgvector, local Redis
- `.env` file with required secrets

**Production:**
- AWS ECS Fargate (256 CPU / 512 MB per task)
- AWS RDS PostgreSQL 16.4 (`db.t4g.micro`, pgvector via `CREATE EXTENSION`)
- AWS ElastiCache replacement: Valkey on EC2 `t4g.nano` (self-managed)
- AWS S3 for file storage
- AWS KMS for BYOK encryption
- AWS ALB as load balancer (HTTP; HTTPS config commented out pending domain setup)
- AWS ECR for container image registry
- Frontend deployed to Vercel (`https://podium-beta.vercel.app` in CORS allow list)
- Terraform state: S3 bucket `rflores-podium-terraform-state` + DynamoDB locks

---

*Stack analysis: 2026-05-03*
