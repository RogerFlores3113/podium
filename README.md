# Podium

> A multi-tenant AI assistant platform — BYOK, agentic tools, persistent memory, and a full AWS deployment. Built end-to-end as a portfolio project.

**[Live demo →](https://podium-beta.vercel.app)** · Click "Try as guest" — no sign-up required.

---

## What it does

- **Agentic tool use** — the assistant autonomously chains web search, document retrieval, sandboxed Python execution, and URL reading to answer questions
- **Persistent memory** — extracts facts from conversations in the background; injects relevant context on future messages using pgvector semantic search
- **BYOK** — bring your own OpenAI, Anthropic, or Ollama endpoint, encrypted at rest with AWS KMS; guest sessions use a cost-capped system key

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
Cloudflare Tunnel ──► ECS Fargate: API (FastAPI + SSE streaming)
                          │              │
                          │         ECS Fargate: arq worker
                          │              │
                      RDS Postgres   Valkey (EC2 t4g.nano)
                   + pgvector HNSW
                          │
                      S3 (documents)   KMS (key encryption)
                          │
                 outbound only ──► OpenAI / Anthropic / Ollama / Tavily / E2B / Clerk
```

**Stack:** FastAPI · LiteLLM · pgvector · arq · Alembic · Clerk · Next.js 14 · Tailwind · Terraform · Cloudflare Tunnel · GitHub Actions

---

## Why this stack

**FastAPI + SSE streaming** — FastAPI's async-first design pairs naturally with server-sent events. When the agent chains multiple tool calls before responding, the user sees real-time progress rather than a blank wait. A synchronous framework would have required polling or WebSockets with more complexity.

**LiteLLM** — Single interface for OpenAI, Anthropic, and Ollama. Adding a new provider is one line of config, not a new integration. The alternative (direct SDK calls per provider) would have meant 3× the API-interaction code to maintain.

**pgvector with HNSW index** — Postgres already handles auth, conversations, and documents — adding pgvector avoids a separate vector database service, reducing infra cost and operational complexity. HNSW (hierarchical navigable small world) gives O(log n) approximate nearest-neighbor search without a full index scan.

**arq (async Redis queue) + Valkey** — Memory extraction runs in the background after each conversation without blocking the SSE stream. arq is a lightweight job queue that runs in the same Python process ecosystem; Valkey is a Redis-compatible open-source fork that replaced ElastiCache at roughly 10% of the cost on a t4g.nano.

**Clerk** — Auth is the highest-risk surface to hand-roll. Clerk provides JWKS-backed JWT verification, session management, and social login. The tradeoff is a vendor dependency; the mitigation is that the custom HS256 guest JWT path shows the underlying auth mechanics clearly.

**Next.js 14 App Router + Tailwind** — App Router supports React Server Components for static routes (landing, settings) while client components handle streaming chat. Tailwind's utility classes keep the component CSS co-located and avoid stylesheet sprawl.

**E2B sandboxed Python execution** — The alternative (subprocess on the API server) is a security hole. E2B runs user code in an isolated VM with a timeout; the only attack surface is what the agent constructs as a code string, which is already constrained by the system prompt.

**Cloudflare Tunnel instead of an ALB** — The ALB was the single most expensive line item ($16/mo for traffic this project doesn't have). Cloudflare Tunnel terminates TLS, provides DDoS protection, and routes directly to the ECS task at zero cost. The tradeoff is a Cloudflare dependency for ingress; the mitigation is that the tunnel config lives in Terraform and the cutover is reversible.

**AWS ECS Fargate on public subnets** — Avoids NAT Gateway charges ($32+/mo) by assigning a public IP to each task. Inbound is closed entirely (the tunnel makes outbound connections to Cloudflare); outbound is open for LLM and tool API calls.

---

## What I built and learned

- **Right-sized infra from "tutorial defaults" to actual demand** — started at ~$114/mo and cut to ~$57/mo (≈50%) by removing the ALB in favor of a Cloudflare Tunnel, replacing ElastiCache with self-hosted Valkey on a t4g.nano, halving the worker's Fargate memory after measuring actual usage, and keeping all tasks on public subnets to skip NAT Gateway charges. The architecture handled the cuts cleanly because the boundaries were correct — the lesson was that "production-grade" doesn't mean "expensive by default."
- **Dual-auth middleware** — tries Clerk RS256 first, falls back to HS256 guest JWTs; handles two completely different token shapes in one path without leaking either codepath into the routers.
- **SSE streaming separated from background persistence** — implemented streaming first, then realized arq's job model didn't compose with an open SSE response; split the agent loop from persistence so the stream stays hot while memory extraction queues up behind it.
- **pgvector HNSW for two read patterns from one index** — same cosine-similarity index serves both memory retrieval and document search; guest sessions transparently union their results against a shared seed corpus by changing the WHERE clause, not the index.
- **E2B sandboxed Python via the agent loop** — the agent can write code, run it in an isolated VM, and continue the conversation with the output. The hard part wasn't the sandbox — it was propagating intermediate tool events back through the SSE channel without breaking framing.
- **Working with AI-assisted code on a real codebase** — the codebase was built with heavy AI assistance, but I own every line: I can extend it, debug it, and defend any architectural decision in it. The cost-cutting milestone was the proof — ripping out ALB / ElastiCache / oversized workers required understanding the system end-to-end, not just nudging an agent.

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

### Optional: enable Ollama (local models)

Ollama integration works in two modes:

**Local dev** — easiest path. Install [Ollama](https://ollama.com), `ollama pull <model>`, then add to `.env`:

```
OLLAMA_BASE_URL=http://host.docker.internal:11434
```

Restart `docker compose`. Any model you've pulled will appear in the model dropdown alongside OpenAI/Anthropic.

**Live demo (signed-in user)** — the API decrypts your Ollama URL server-side and calls Ollama from AWS, so the URL has to be reachable from the public internet. Run a tunnel to your local Ollama:

```bash
cloudflared tunnel --url http://localhost:11434
```

Copy the `https://*.trycloudflare.com` URL it prints, paste it into Settings → Ollama, and your local models will appear in the dropdown. Tunnel must stay up while you're using them.

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
| Ingress | Cloudflare Tunnel (TLS termination + DDoS) |
| Infra | AWS ECS Fargate, RDS Postgres 16, Terraform |
| CI/CD | GitHub Actions (test on PR, deploy on merge to main) |

---

## Seeding demo documents

Guest sessions can search a shared demo corpus. To load it:

```bash
uv run python -m scripts.seed_demo_corpus path/to/doc1.pdf path/to/doc2.pdf
```

Run once after deploying. The seed user (`demo_seed`) is excluded from the guest cleanup sweep.
