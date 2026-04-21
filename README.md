# Podium

A personal AI assistant with long-term memory, document search, code execution, and web search. Runs on your own API keys. Deployed on AWS.

**Live:** [podium-beta.vercel.app](https://podium-beta.vercel.app)

---

## Features

| Capability | How it works |
|---|---|
| **Memory** | Extracts facts and preferences from conversations via background job (arq + Redis). Retrieves relevant memories at prompt time using pgvector HNSW semantic search. |
| **Web search** | Tavily API, invoked as an agent tool. |
| **Document RAG** | Upload PDFs → chunked, embedded, stored in pgvector. Retrieved at query time with cosine similarity. |
| **Code execution** | Python runs in an E2B sandbox. Output is returned to the agent. |
| **BYOK** | Bring your own OpenAI / Anthropic / Ollama key. Encrypted at rest with AWS KMS. |
| **Multi-model** | LiteLLM routing. Switch providers without changing application code. |
| **Conversation history** | Full sidebar with paginated history. Conversations persist in PostgreSQL. |

---

## Stack

**Backend**
- FastAPI — async API, SSE streaming
- LiteLLM — model-agnostic LLM routing
- pgvector (HNSW) — semantic search for memories and document chunks
- arq + Redis — background memory extraction with debounce
- Alembic — database migrations
- Clerk — JWT auth

**Frontend**
- Next.js 14 (App Router)
- Tailwind CSS + CSS custom properties (warm parchment design system, dark mode)
- Clerk — auth routing

**Infrastructure**
- AWS ECS Fargate — API + worker containers
- RDS PostgreSQL 16 + pgvector
- ElastiCache Redis 7
- S3 — document storage
- AWS KMS — API key encryption
- Terraform — all infra as code
- GitHub Actions — CI/CD (build → ECR push → ECS deploy)

---

## Local Development

**Prerequisites:** Docker, Docker Compose, an OpenAI API key.

```bash
git clone https://github.com/RogerFlores3113/podium
cd podium
cp .env.example .env   # fill in required values
docker compose up --build
```

The API runs at `http://localhost:8000`. Swagger UI at `http://localhost:8000/docs`.

For the frontend:
```bash
cd frontend
cp .env.local.example .env.local   # set NEXT_PUBLIC_API_URL and Clerk keys
npm install
npm run dev
```

Runs at `http://localhost:3000`.

### Required environment variables

| Variable | Description |
|---|---|
| `DATABASE_URL` | PostgreSQL connection string (asyncpg) |
| `REDIS_URL` | Redis connection string |
| `OPENAI_API_KEY` | Default LLM + embeddings key |
| `CLERK_SECRET_KEY` | Clerk backend secret |
| `CLERK_JWKS_URL` | Clerk JWKS endpoint for JWT verification |
| `TAVILY_API_KEY` | Web search |
| `E2B_API_KEY` | Code execution sandbox |
| `KMS_KEY_ID` | AWS KMS key ARN for BYOK encryption |
| `S3_BUCKET_NAME` | S3 bucket for document storage (leave empty for local filesystem) |

---

## API

| Method | Path | Description |
|---|---|---|
| `POST` | `/chat/stream` | Send a message, get SSE-streamed agent response |
| `GET` | `/chat/` | List conversations (paginated, newest first) |
| `GET` | `/chat/{id}` | Fetch a conversation with all messages |
| `POST` | `/documents/upload` | Upload a PDF for RAG |
| `GET` | `/documents/` | List uploaded documents |
| `GET` | `/documents/{id}` | Get document status |
| `POST` | `/keys/` | Store an encrypted API key |
| `GET` | `/keys/` | List stored key hints |
| `DELETE` | `/keys/{id}` | Delete a key |
| `GET` | `/memories/` | List extracted memories |
| `PATCH` | `/memories/{id}` | Edit a memory |
| `DELETE` | `/memories/{id}` | Delete a memory |

### SSE event types (`POST /chat/stream`)

```
conversation   — first event, carries conversation_id
token          — streaming text chunk
tool_call_start / tool_call_result / tool_call_error
done           — agent finished, conversation committed
error          — unrecoverable failure
```

---

## Project Structure

```
podium/
├── app/
│   ├── routers/         # FastAPI route handlers
│   ├── services/
│   │   ├── agent.py     # Tool-calling agent loop
│   │   ├── memory.py    # Memory extraction + retrieval
│   │   ├── ingestion.py # PDF chunking + embedding
│   │   ├── retrieval.py # pgvector similarity search
│   │   ├── llm.py       # Conversation history builder
│   │   └── worker.py    # arq background worker
│   ├── models.py        # SQLAlchemy ORM models
│   ├── schemas.py       # Pydantic request/response schemas
│   ├── config.py        # Settings (pydantic-settings)
│   └── auth.py          # Clerk JWT verification
├── frontend/
│   └── app/
│       ├── components/
│       │   ├── ChatPage.tsx     # Main chat UI with sidebar
│       │   └── LandingPage.tsx  # Marketing landing page
│       ├── hooks/
│       │   └── useAuthFetch.ts  # Clerk-authenticated fetch
│       └── settings/            # BYOK settings page
├── infra/               # Terraform — VPC, ECS, RDS, Redis, S3, KMS
├── alembic/             # Database migrations
└── docker-compose.yml   # Local dev stack
```

---

## Deployment

Infrastructure is managed with Terraform. CI/CD runs on GitHub Actions.

```bash
cd infra
terraform init
terraform apply
```

On every push to `main`, GitHub Actions:
1. Builds the Docker image and pushes to ECR
2. Runs `aws ecs update-service --force-new-deployment`
3. Waits for the service to stabilize

Required GitHub Actions secrets: `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `AWS_ACCOUNT_ID`.

---

## Roadmap

- [ ] Model picker UI (switch providers per conversation)
- [ ] Additional tools: URL reader, weather, image generation
- [ ] Frontend unit tests (vitest)
- [ ] Model capability flags (config-driven tool support per model)
