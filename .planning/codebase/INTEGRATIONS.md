# External Integrations

**Analysis Date:** 2026-05-03

## APIs & External Services

**LLM Providers (via litellm):**
- OpenAI — chat completions (GPT-5 nano, GPT-4o mini, GPT-4o), embeddings (`text-embedding-3-small`), memory extraction (`gpt-4o-mini`)
  - SDK/Client: `litellm` (`acompletion`, `aembedding`) in `app/services/llm.py`, `app/services/ingestion.py`, `app/services/memory.py`
  - Auth: `OPENAI_API_KEY` env var (system key for guests; per-user BYOK keys decrypted from DB)
- Anthropic — Claude 3.5 Haiku, Claude 3.5 Sonnet available as BYOK models
  - SDK/Client: `litellm` abstraction — no direct Anthropic SDK
  - Auth: per-user BYOK key stored encrypted in `api_keys` table
- Ollama — local model support (`ollama/llama3.2`, `ollama/mistral`, `ollama/codellama`; tools disabled for these)
  - SDK/Client: `litellm` abstraction
  - Auth: none (local)
- Model config: `app/config.py` (`AVAILABLE_MODELS`, `MODEL_CAPABILITIES`)

**Web Search:**
- Tavily — web search for the `web_search` agent tool
  - SDK/Client: `tavily-python` (`AsyncTavilyClient`) in `app/tools/web_search.py`
  - Auth: `TAVILY_API_KEY` env var (stored in AWS SSM in prod)
  - Disabled if key not set (returns error string to LLM)

**Code Execution Sandbox:**
- E2B — ephemeral Python sandboxes for the `python_executor` agent tool
  - SDK/Client: `e2b-code-interpreter` (`AsyncSandbox`) in `app/tools/python_executor.py`
  - Auth: `E2B_API_KEY` env var (stored in AWS SSM in prod)
  - Disabled if key not set; sandbox created and killed per tool call (ephemeral)

**URL Reading:**
- Jina AI Reader — proxies URLs to clean markdown text (`https://r.jina.ai/<url>`)
  - SDK/Client: `httpx` (raw HTTP) in `app/tools/url_reader.py`
  - Auth: none (public endpoint)
  - Max content: 8000 chars per fetch

**Frontend Auth:**
- Clerk — user authentication and session management
  - SDK/Client: `@clerk/nextjs ^7.0.6` (frontend), `pyjwt[crypto]` + `httpx` (backend JWKS verification)
  - Auth: `CLERK_SECRET_KEY` + `CLERK_JWKS_URL` env vars; frontend uses `NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY`
  - Backend verifies RS256 JWTs via JWKS endpoint (`app/auth.py`: `verify_clerk_token`)
  - Just-in-time user provisioning: first authenticated request creates a local `User` row (`app/auth.py`: `get_or_create_user`)

## Data Storage

**Databases:**
- PostgreSQL 16 with pgvector extension
  - Dev: `pgvector/pgvector:pg16` Docker image (local docker-compose)
  - Prod: AWS RDS `db.t4g.micro`, engine `16.4`, `db.assistant`, encrypted at rest
  - Connection: `DATABASE_URL` env var (format: `postgresql+asyncpg://...`)
  - Client: SQLAlchemy 2.x async (`create_async_engine`, `AsyncSession`) in `app/database.py`
  - ORM models: `app/models.py` (Document, Chunk, Conversation, Message, User, ApiKey, Memory)
  - Vector column: `pgvector.sqlalchemy.Vector(1536)` on `chunks.embedding`
  - Vector index: HNSW (`m=16`, `ef_construction=64`, `vector_cosine_ops`) in `app/models.py`
  - Migrations: Alembic (`alembic/`, `alembic.ini`)

**File Storage:**
- AWS S3 — document uploads (PDFs)
  - Dev fallback: local filesystem (`uploads/` directory) when `S3_BUCKET_NAME` is empty
  - Prod bucket: `${project_name}-uploads`, versioning enabled, AES256 SSE, all public access blocked
  - Client: `boto3` in `app/services/storage.py`
  - Auth: IAM task role in ECS (no explicit keys in prod)

**Caching / Job Queue:**
- Redis / Valkey — dual purpose
  - Rate limiting storage: `slowapi` uses Redis URI (`app/limiter.py`)
  - Background job queue: `arq` uses Redis for job dispatch and worker polling (`app/services/worker.py`)
  - Dev: `redis:7-alpine` Docker image
  - Prod: Valkey (Redis-compatible) on EC2 `t4g.nano` arm64 (`infra/valkey.tf`)
  - Connection: `REDIS_URL` env var (default: `redis://localhost:6379`)
  - Client: `redis[hiredis]` (arq / slowapi)

## Authentication & Identity

**Primary Auth Provider:**
- Clerk (SaaS) — handles signup, login, session tokens
  - Backend verifies RS256 JWTs via JWKS: `app/auth.py` (`verify_clerk_token`, `get_jwks_client`)
  - JWKS client cached as module-level singleton

**Guest Auth:**
- Custom HS256 JWT — guest sessions without Clerk account
  - Issued by `app/routers/guest.py`, verified by `app/services/guest_auth.py`
  - Secret: `GUEST_JWT_SECRET` env var (required in prod; `openssl rand -hex 32`)
  - Session duration: 24 hours (configurable via `GUEST_SESSION_DURATION_HOURS`)
  - Message limit: 20 per session (`GUEST_MAX_MESSAGES_PER_SESSION`)
  - Guests use system OpenAI key (cost-controlled via rate limits + model restrictions)
  - Expired guest data purged hourly via `cleanup_expired_guests` arq cron job

**Token Verification Flow:**
- `app/auth.py` `verify_token()`: tries Clerk RS256 first, falls back to guest HS256
- FastAPI dependency chain: `get_current_user_id` → `get_or_create_user`

**BYOK (Bring Your Own Key):**
- Authenticated users store API keys per provider in `api_keys` table
- Keys encrypted with AWS KMS before storage (`app/services/encryption.py`)
- Dev fallback: base64 encoding when `KMS_KEY_ID` is empty (NOT secure)
- Decrypted keys cached in-memory for 5 minutes (`_key_cache` dict in `app/services/encryption.py`)
- Guests always use system OpenAI key; authenticated users without BYOK get HTTP 402

## Monitoring & Observability

**Error Tracking:**
- None (no Sentry or equivalent)

**Logs:**
- Python `logging` to stdout (`app/main.py`: `basicConfig(stream=sys.stdout, level=INFO)`)
- Format: `%(asctime)s | %(levelname)s | %(name)s | %(message)s`
- Prod: CloudWatch Logs via ECS `awslogs` log driver, group `/ecs/${project_name}`, 14-day retention (`infra/ecs.tf`)

**Metrics & Alerts:**
- AWS CloudWatch alarms via SNS email notifications (`infra/monitoring.tf`):
  - `high-5xx`: >10 HTTP 5xx errors in 5 minutes (ALB metric)
  - `app-not-running`: ECS running task count < 1

**Health Check:**
- `GET /health` — executes `SELECT 1` against PostgreSQL; returns 200 OK or 503

## CI/CD & Deployment

**Hosting:**
- Backend: AWS ECS Fargate (256 CPU, 512 MB); ALB on port 80 (HTTPS config commented out)
- Frontend: Vercel (`https://podium-beta.vercel.app`)
- Container registry: AWS ECR (`${project_name}-app`), lifecycle keeps last 10 images

**CI Pipeline:**
- Not detected (no `.github/workflows/` or equivalent CI config found)

**Infrastructure:**
- Terraform `>=1.5.0`, state in S3 (`rflores-podium-terraform-state`), locks in DynamoDB
- AWS provider `~> 5.0`, region configurable via `var.aws_region`
- VPC with public/private subnets (`infra/vpc.tf`)
- ECS task: 1 container (`app`), receives env from plaintext + AWS SSM SecureString secrets

## Environment Configuration

**Required env vars (backend):**
- `DATABASE_URL` — PostgreSQL async connection string
- `OPENAI_API_KEY` — system OpenAI key (SSM: `/${project_name}/openai-api-key`)
- `CLERK_SECRET_KEY` — Clerk backend secret (SSM: `/${project_name}/clerk-secret-key`)
- `CLERK_JWKS_URL` — Clerk JWKS endpoint URL
- `GUEST_JWT_SECRET` — guest session signing secret (SSM: `/${project_name}/guest-jwt-secret`)
- `KMS_KEY_ID` — AWS KMS key ID for BYOK encryption
- `S3_BUCKET_NAME` — S3 upload bucket name
- `REDIS_URL` — Redis/Valkey connection string

**Optional env vars (backend):**
- `TAVILY_API_KEY` — enables web search tool (SSM: `/${project_name}/tavily-api-key`)
- `E2B_API_KEY` — enables Python executor tool (SSM: `/${project_name}/e2b-api-key`)
- `AWS_DEFAULT_REGION` — default `us-east-1`

**Secrets location (prod):**
- AWS SSM Parameter Store (SecureString), injected into ECS task containers as `secrets` at runtime
- Defined in `infra/secrets.tf`

## Webhooks & Callbacks

**Incoming:**
- None detected (no Clerk webhook endpoints, no Stripe, no external event receivers)

**Outgoing:**
- None (all external calls are initiated by user requests or background jobs)

---

*Integration audit: 2026-05-03*
