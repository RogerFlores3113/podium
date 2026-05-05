# Podium

> A multi-tenant AI assistant platform — BYOK, agentic tools, persistent memory, and a full AWS deployment. Built end-to-end as a portfolio project.

**[Live demo →](https://podium-beta.vercel.app)** · Click "Try as guest" — no sign-up required.

---

## What it does

- **Agentic tool use** — the assistant autonomously chains web search, document retrieval, sandboxed Python execution, and URL reading to answer questions
- **Persistent memory** — extracts facts from conversations in the background; injects relevant context on future messages using pgvector semantic search
- **BYOK** — bring your own OpenAI or Anthropic key, encrypted at rest with AWS KMS; guest sessions use a cost-capped system key

---

## Try it

Visit the live URL and click **"Try as guest"**. You'll land in a working chat session pre-loaded with demo documents you can ask questions about. Guest sessions expire in 24 hours.

To use your own models and keep your data, sign up and add an API key in Settings.

---

## Architecture

```
Browser
  │ HTTPS
  ▼
ALB (AWS) ──► ECS Fargate: API (FastAPI + SSE streaming)
                  │              │
                  │         ECS Fargate: arq worker
                  │              │
              RDS Postgres   Valkey (EC2 t4g.nano)
           + pgvector HNSW
                  │
              S3 (documents)   KMS (key encryption)
                  │
         outbound only ──► OpenAI / Anthropic / Tavily / E2B / Clerk
```

**Stack:** FastAPI · LiteLLM · pgvector · arq · Alembic · Clerk · Next.js 14 · Tailwind · Terraform · GitHub Actions

---

## Why this stack

**FastAPI + SSE streaming** — FastAPI's async-first design pairs naturally with server-sent events. When the agent chains multiple tool calls before responding, the user sees real-time progress rather than a blank wait. A synchronous framework would have required polling or WebSockets with more complexity.

**LiteLLM** — Single interface for OpenAI, Anthropic, and local Ollama models. Adding a new provider is one line of config, not a new integration. The alternative (direct SDK calls per provider) would have meant 3x the API-interaction code to maintain.

**pgvector with HNSW index** — Postgres already handles auth, conversations, and documents — adding pgvector avoids a separate vector database service, reducing infra cost and operational complexity. HNSW (hierarchical navigable small world) gives O(log n) approximate nearest-neighbor search without a full index scan.

**arq (async Redis queue) + Valkey** — Memory extraction runs in the background after each conversation without blocking the SSE stream. arq is a lightweight job queue that runs in the same Python process ecosystem; Valkey is a Redis-compatible open-source fork that replaced ElastiCache at ~10% of the cost on a t4g.nano.

**Clerk** — Auth is the highest-risk surface to hand-roll. Clerk provides JWKS-backed JWT verification, session management, and social login. The tradeoff is a vendor dependency; the mitigation is that the custom HS256 guest JWT path shows the underlying auth mechanics clearly.

**Next.js 14 App Router + Tailwind** — App Router supports React Server Components for static routes (landing, settings) while client components handle streaming chat. Tailwind's utility classes keep the component CSS co-located and avoid stylesheet sprawl.

**E2B sandboxed Python execution** — The alternative (subprocess on the API server) is a security hole. E2B runs user code in an isolated VM with a timeout; the only attack surface is what the agent constructs as a code string, which is already constrained by the system prompt.

**AWS ECS Fargate on public subnets** — Avoids NAT Gateway charges ($32+/mo) by assigning a public IP to each task. The tradeoff is that security groups must be strict (they are: only ports 80/443 from the ALB). This cut infrastructure cost from ~$120/mo to ~$45/mo.

---

## What I built and learned

- Wrote a dual-auth middleware that tries Clerk RS256 first, falls back to HS256 guest JWTs — handles two completely different token shapes in one path cleanly
- Implemented SSE streaming before realizing arq's job model didn't compose with it; separated the agent loop from persistence so streaming works without blocking background work
- Cut AWS cost from ~$120/mo to ~$45/mo by replacing ElastiCache with self-hosted Valkey on a t4g.nano, keeping ECS on public subnets to avoid NAT Gateway charges, and right-sizing Fargate tasks
- pgvector HNSW index with cosine similarity for both memory retrieval and document search — same index type, different query-time filters; guest sessions transparently union their results against a shared seed corpus
- E2B sandboxed Python execution: the agent can write and run code in an isolated VM, return output, and keep the conversation going — the hard part was propagating streaming events back through the SSE channel

---

## Local setup

**Prerequisites:** Docker, Docker Compose, an OpenAI API key.

```bash
git clone https://github.com/RogerFlores3113/podium
cd podium
cp .env.example .env   # fill in OPENAI_API_KEY and GUEST_JWT_SECRET at minimum
docker compose up --build
```

- API: `http://localhost:8000` · Swagger: `http://localhost:8000/docs`
- Frontend: `http://localhost:3000`

Generate a guest JWT secret: `openssl rand -hex 32`

---

## Stack

| Layer | Tech |
|---|---|
| API | FastAPI, SSE streaming, LiteLLM |
| Memory + search | pgvector HNSW, text-embedding-3-small |
| Background jobs | arq + Valkey |
| Auth | Clerk (JWKS RS256) + custom HS256 guest JWTs |
| Key encryption | AWS KMS |
| Storage | S3 (prod), local filesystem (dev) |
| Frontend | Next.js 14 App Router, Tailwind CSS |
| Infra | AWS ECS Fargate, RDS Postgres 16, Terraform |
| CI/CD | GitHub Actions (test on PR, deploy on merge to main) |

---

## Seeding demo documents

Guest sessions can search a shared demo corpus. To load it:

```bash
uv run python -m scripts.seed_demo_corpus path/to/doc1.pdf path/to/doc2.pdf
```

Run once after deploying. The seed user (`demo_seed`) is excluded from the guest cleanup sweep.
