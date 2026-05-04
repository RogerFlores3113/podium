# Podium — Stabilization & Hardening Milestone

## What This Is

Podium is an AI-powered assistant for recruiters. It lets users upload documents (resumes, job descriptions), search and query them via a chat interface, and maintain a persistent memory of preferences and facts across sessions. Users authenticate via Clerk or use a guest/demo session. The system runs on AWS (ECS Fargate, RDS, S3, KMS) with a Next.js frontend on Vercel.

## Core Value

A recruiter can paste a link, upload a document, or ask a question and get a fast, reliable, clearly-presented answer — with no silent failures, no UI confusion, and no dead ends.

## Requirements

### Validated

- ✓ Chat streaming via SSE — existing
- ✓ Guest/demo mode (ephemeral sessions with cleanup) — existing
- ✓ Clerk authentication with BYOK API keys — existing
- ✓ Document upload, ingestion, vector search — existing
- ✓ Memory extraction and semantic search — existing
- ✓ Multi-tool agent loop (web search, URL reader, document search, memory search, Python executor) — existing
- ✓ AWS infrastructure (ECS, RDS, S3, KMS, ECR, ALB) — existing
- ✓ Rate limiting, auth middleware, error boundaries — existing
- ✓ Loading/thinking indicators when agent is processing — Phase 4 (CHAT-01)
- ✓ Tool phase copy ("Searching the web…") during tool runs — Phase 4 (CHAT-02)
- ✓ Chat error surface — SSE errors + HTTP 402/429/5xx shown inline — Phase 4 (CHAT-03/04)
- ✓ Conversation deletion — users can delete past conversations — Phase 3 (CONV-01/02)
- ✓ Memory deletion — fix broken delete flow in settings — Phase 3 (MEM-01/02)
- ✓ Agent system prompt hardening — Phase 2 (AGENT-01/02/03)
- ✓ Textarea composer: Enter submits, Shift+Enter newline, IME-safe — Phase 4 (CHAT-05)
- ✓ Upload poll capped at 60 attempts with try/catch — Phase 4 (CHAT-06)

- ✓ Model roster update — GPT-5-nano, GPT-5.4-nano, claude-sonnet-4-6, claude-haiku-4-5; Ollama via OLLAMA_BASE_URL (BYOK bypassed for Ollama); guests locked to gpt-5-nano — Phase 5 (MODEL-01–05)
- ✓ Guest mode verified: session creation, message cap (429), demo corpus, expiry cleanup — Phase 6 (AUDIT-01)
- ✓ Landing/intro flow verified: signed-out landing, "Try as Guest" flow, signed-in redirect, cap enforcement — Phase 6 (AUDIT-02)
- ✓ AWS infra verified: ECS CPU/RAM, RDS t4g.micro, Valkey EC2 t4g.nano (NOT ElastiCache), SSM Parameter Store — Phase 6 (AUDIT-03)
- ✓ SSE JSON.parse hardened with try/catch + continue (CR-03) — Phase 6 (AUDIT-01)
- ✓ BYOK 402 message now provider-aware (CR-04) — Phase 6
- ✓ BadRequestError no longer echoes user query (CR-02) — Phase 6

### Active

- [ ] Fix missing try/catch in handleDeleteConversation (Phase 4 code review debt) — unhandled rejection on network failure
- [ ] `resolve_api_key` always returns openai_api_key for guests regardless of provider — guests on Anthropic/Ollama get wrong key (Phase 6 code review CR-01)
- [ ] SSE reader lock never released — `reader.releaseLock()` missing in ChatPage.tsx (Phase 6 code review WR-02)
- [ ] BYOK 402 frontend still shows hardcoded "OpenAI API key" despite provider-aware backend (Phase 6 code review WR-03)
- [ ] "No results" path in web_search.py echoes raw user query — same pattern as CR-02 fix (Phase 6 code review WR-04)
- [ ] `hoverHideTimeoutRef` not cleaned up on ChatPage unmount (Phase 6 code review WR-05)

### Out of Scope

- Video/audio file ingestion — not recruiter-relevant for v1
- Real-time collaboration — single-user product for now
- Mobile app — web-first
- Ollama in production for recruiters — Ollama is dev/power-user only; recruiters use managed model keys

## Context

- **Milestone complete (2026-05-04):** Stabilization & Hardening — 6/6 phases, 27/27 requirements verified. PR #14 guest mode, intro flow, and AWS changes all confirmed correct.
- **PR #14 cost reality:** ~$35/month savings (NAT Gateway removal + SSM migration). PR claimed ~$65/month — discrepancy noted; reconcile against AWS console.
- **Demo corpus:** `app/services/retrieval.py` references `user_id='demo_seed'` for guest document access. Prod DB seeding unverified — run `SELECT count(*) FROM documents WHERE user_id = 'demo_seed';` to confirm.
- **Code review debt (Phase 6):** 1 critical (guest key leak across providers in resolve_api_key), 5 warnings — all captured in Active requirements above.
- **Agent loop:** Two execution paths — litellm Chat Completions (most models) and OpenAI Responses API (gpt-5-nano). Agent reliability hardened in Phase 2.
- **Embeddings:** Always use system `OPENAI_API_KEY` — even BYOK users get embedding/search without their own OpenAI key.
- **Ollama:** Dev/power-user only via OLLAMA_BASE_URL. Dynamic roster fetched from /api/tags. BYOK check bypassed for Ollama provider.
- **Target audience:** Recruiters. They expect fast, clean, reliable tools. Confusion is unacceptable. Every error must surface clearly.

## Constraints

- **Tech stack:** FastAPI backend, Next.js 16 frontend — no framework changes
- **AWS infra:** ECS Fargate (256 CPU/512 MB), RDS t4g.micro, Valkey on t4g.nano — cost-conscious; no infra upsizing without explicit discussion
- **Embeddings:** text-embedding-3-small (system key) — no upgrade unless retrieval quality becomes a reported issue
- **Models:** Remove all OpenAI models except GPT-5-nano and GPT-5.4-nano; update Anthropic to claude-sonnet-4-6 and claude-haiku-4-5; add Ollama (configurable endpoint, dev/power-user only)

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Ollama as configurable endpoint, dev/power-user only | Prod runs on AWS Fargate; Ollama requires a separately-hosted service. Recruiters use managed keys. | Shipped (Phase 5) — OLLAMA_BASE_URL env var, BYOK bypassed for Ollama |
| Keep text-embedding-3-small | Fast, cheap, accurate enough for recruiter document search. Upgrade not justified until retrieval quality is a reported problem. | Confirmed (Phase 6 audit — no retrieval quality issues reported) |
| One milestone: audit + fix + harden | Fixing reliability issues before adding features. Recruiter-readiness is the gate. | Complete — 6/6 phases, 27/27 requirements. Code review found 1 critical + 5 warnings carried as Active requirements. |
| Valkey is EC2 t4g.nano, NOT ElastiCache | CONTEXT.md D-06 incorrectly described Valkey as ElastiCache — corrected by direct terraform inspection in Phase 6. | Confirmed (infra/valkey.tf:41-43) |
| Dynamic Ollama model roster via /chat/ollama-models | Static AVAILABLE_MODELS excludes Ollama; frontend fetches Ollama models dynamically when OLLAMA_BASE_URL is set. | Shipped (commit 012d769) |

## Evolution

This document evolves at phase transitions and milestone boundaries.

**After each phase transition** (via `/gsd-transition`):
1. Requirements invalidated? → Move to Out of Scope with reason
2. Requirements validated? → Move to Validated with phase reference
3. New requirements emerged? → Add to Active
4. Decisions to log? → Add to Key Decisions
5. "What This Is" still accurate? → Update if drifted

**After each milestone** (via `/gsd-complete-milestone`):
1. Full review of all sections
2. Core Value check — still the right priority?
3. Audit Out of Scope — reasons still valid?
4. Update Context with current state

---
*Last updated: 2026-05-04 after Phase 6 (PR #14 Audit & Smoke Test) — Stabilization & Hardening milestone complete*
