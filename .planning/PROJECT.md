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

### Active

- [ ] Loading/thinking indicators when agent is processing
- [ ] Chat error surface — failures shown in UI, not silently logged to console
- [ ] Conversation deletion — users can delete past conversations
- [ ] Memory deletion — fix broken delete flow in settings
- [ ] Agent system prompt hardening — prevent early termination; ensure web-search results are always reported to user
- [ ] Model roster update — GPT-5-nano, GPT-5.4-nano (OpenAI only); claude-sonnet-4-6, claude-haiku-4-5 (Anthropic); Ollama configurable base URL (dev/power-user)
- [ ] Comprehensive audit of recent PR (guest mode, intro cleanup, AWS efficiency) — verify correctness
- [ ] Full bug hunt — identify and fix all reliability, UX, and correctness gaps targeting recruiter-readiness

### Out of Scope

- Video/audio file ingestion — not recruiter-relevant for v1
- Real-time collaboration — single-user product for now
- Mobile app — web-first
- Ollama in production for recruiters — Ollama is dev/power-user only; recruiters use managed model keys

## Context

- **Recent work (PR #14):** Guest mode added, intro/landing page cleanup, AWS cost/efficiency improvements. Needs verification pass.
- **Agent loop:** Two execution paths — litellm Chat Completions (most models) and OpenAI Responses API (gpt-5-nano). The agent frequently completes a tool call (e.g. web_search) but fails to synthesize and return findings to the user. Root cause is likely in the system prompt or loop termination logic.
- **Embeddings:** Always use system `OPENAI_API_KEY` — even BYOK users get embedding/search without their own OpenAI key.
- **Ollama:** litellm supports Ollama natively via `ollama/model-name` prefix + configurable base URL. Will be added as a dev/power-user setting, not a recruiter-facing feature.
- **Target audience:** Recruiters. They expect fast, clean, reliable tools. Confusion is unacceptable. Every error must surface clearly.

## Constraints

- **Tech stack:** FastAPI backend, Next.js 16 frontend — no framework changes
- **AWS infra:** ECS Fargate (256 CPU/512 MB), RDS t4g.micro, Valkey on t4g.nano — cost-conscious; no infra upsizing without explicit discussion
- **Embeddings:** text-embedding-3-small (system key) — no upgrade unless retrieval quality becomes a reported issue
- **Models:** Remove all OpenAI models except GPT-5-nano and GPT-5.4-nano; update Anthropic to claude-sonnet-4-6 and claude-haiku-4-5; add Ollama (configurable endpoint, dev/power-user only)

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Ollama as configurable endpoint, dev/power-user only | Prod runs on AWS Fargate; Ollama requires a separately-hosted service. Recruiters use managed keys. | — Pending |
| Keep text-embedding-3-small | Fast, cheap, accurate enough for recruiter document search. Upgrade not justified until retrieval quality is a reported problem. | — Pending |
| One milestone: audit + fix + harden | Fixing reliability issues before adding features. Recruiter-readiness is the gate. | — Pending |

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
*Last updated: 2026-05-03 after initialization*
