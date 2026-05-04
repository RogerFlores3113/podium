# Roadmap: Podium — Stabilization & Hardening

**Milestone:** Stabilization & Hardening
**Phases:** 6
**Requirements:** 27 v1 requirements
**Granularity:** standard
**Defined:** 2026-05-03

## Phases

- [x] **Phase 1: Wire Protocol & Visibility** — Fix SSE delimiter, persistence, redis pool, and remove dead code so failures stop being silent. *(completed 2026-05-03)*
- [x] **Phase 2: Agent Reliability** — Harden the agent loop so tool results are always synthesized and reported to the user. *(completed 2026-05-03)*
- [x] **Phase 3: Destructive UX Paths** — Make conversation and memory deletion actually work end-to-end with clear feedback. *(completed 2026-05-03)*
- [x] **Phase 4: Loading & Error UX** — Surface thinking, tool-in-progress, and error states inline in the chat thread. *(completed 2026-05-03)*
- [x] **Phase 5: Model Roster & Ollama** — Restrict roster to approved models, gate guests, and add Ollama as a dev/power-user opt-in. *(completed 2026-05-03)*
- [x] **Phase 6: PR #14 Audit & Smoke Test** — Verify guest mode, intro flow, and AWS changes still work after all prior phases. *(completed 2026-05-04)*

## Phase Details

### Phase 1: Wire Protocol & Visibility
**Goal:** Backend events reach the frontend reliably, mid-stream disconnects don't lose data, and dead code can't mask real failures.
**Depends on:** Nothing (foundation)
**Requirements:** WIRE-01, WIRE-02, WIRE-03, WIRE-04, QUAL-01
**Success Criteria** (what must be TRUE):
  1. A streamed chat response renders every SSE event the backend emits — no events silently dropped due to delimiter mismatch.
  2. Closing the browser tab mid-stream still results in the assistant message being committed to the DB and visible on reload.
  3. Repeated document uploads do not create or close a new Redis pool per request (pool reused from `app.state`).
  4. A long-running tool call (>60s) does not get severed by the AWS ALB idle timeout.
**Plans:** 3 plans

Plans:
- [x] 01-01-PLAN.md — Write failing test stubs for all 5 fixes (Wave 1, RED baseline)
- [x] 01-02-PLAN.md — Apply SSE delimiter, finally commit, and ping to chat.py (Wave 2, WIRE-01/02/04)
- [x] 01-03-PLAN.md — Fix Redis pool reuse in documents.py and remove dead LLM functions (Wave 2, WIRE-03/QUAL-01)

### Phase 2: Agent Reliability
**Goal:** After any tool call, the agent always synthesizes and returns a user-visible answer; transient empty completions retry once; tool errors are sanitized.
**Depends on:** Phase 1
**Requirements:** AGENT-01, AGENT-02, AGENT-03, QUAL-02, QUAL-03, QUAL-04
**Success Criteria** (what must be TRUE):
  1. Sending a message that triggers `web_search` returns a synthesized answer that references the search results — not an empty bubble.
  2. When the underlying model returns empty assistant text, the agent retries once before yielding `done` (verified on both litellm and Responses API paths).
  3. A Tavily web search failure produces a user-safe error string in the chat with no API key or internal trace leaked.
  4. Sending several messages in rapid succession does not produce duplicate memory extractions or 500s from `get_or_create_user` race conditions, and the user message is not duplicated in the prompt context.
**Plans:** 3 plans

Plans:
- [x] 02-01-PLAN.md — Write failing tests for all 6 fixes (Wave 1, RED baseline)
- [x] 02-02-PLAN.md — Apply AGENT-01/02/03 fixes to agent.py and web_search.py (Wave 2)
- [x] 02-03-PLAN.md — Apply QUAL-02/03/04 fixes to chat.py and auth.py (Wave 2)

### Phase 3: Destructive UX Paths
**Goal:** Users can delete conversations and memories, and every settings-page mutation surfaces a clear status.
**Depends on:** Nothing (independent of agent loop)
**Requirements:** CONV-01, CONV-02, MEM-01, MEM-02
**Success Criteria** (what must be TRUE):
  1. Hovering a conversation in the sidebar reveals a delete affordance; clicking it opens a confirm dialog and, on confirm, removes the conversation from the sidebar immediately and cascades message deletion.
  2. Deleting a memory in settings removes it from the visible list immediately with no silent failure (trailing-slash / filter root cause fixed).
  3. Any failed settings action (add/delete memory, add/delete API key) renders a visible status message — no swallowed errors.
**Plans:** TBD
**UI hint**: yes

### Phase 4: Loading & Error UX
**Goal:** The chat thread always shows what the system is doing (thinking, tool-in-progress, error) — no blank waits, no silent failures.
**Depends on:** Phase 1 (error events flow), Phase 2 (agent reliable)
**Requirements:** CHAT-01, CHAT-02, CHAT-03, CHAT-04, CHAT-05, CHAT-06
**Success Criteria** (what must be TRUE):
  1. Submitting a message renders a thinking indicator within 150ms and stays until the first token arrives.
  2. While a tool runs, the thread shows phased copy ("Searching web…", "Reading source…") driven by `tool_call_start` events; no empty bubbles between submit and final answer.
  3. Both backend SSE `error` events and HTTP-level errors (429 guest cap, 402 BYOK missing, 5xx) render as inline error bubbles with user-readable copy.
  4. The composer is a multi-line textarea where Shift+Enter inserts a newline and Enter submits; upload polling stops after a max-attempts cap and never leaks a timer on fetch failure.
**Plans:** TBD
**UI hint**: yes

### Phase 5: Model Roster & Ollama
**Goal:** Only approved models are user-selectable, guests are locked to gpt-5-nano, and Ollama appears only when a developer opts in via env var.
**Depends on:** External verification of Anthropic and gpt-5.4-nano model IDs (per SUMMARY.md "Verification Required")
**Requirements:** MODEL-01, MODEL-02, MODEL-03, MODEL-04, MODEL-05
**Success Criteria** (what must be TRUE):
  1. The model picker shows exactly `gpt-5-nano`, `gpt-5.4-nano`, `claude-sonnet-4-6`, `claude-haiku-4-5` (plus Ollama entries only when `OLLAMA_BASE_URL` is set), with friendly labels (e.g. "GPT-5 nano · fast").
  2. A guest user cannot select any model other than gpt-5-nano — the dropdown is disabled or locked for guest sessions, and the backend enforces the same.
  3. With `OLLAMA_BASE_URL` unset, no Ollama models are exposed; with it set, an Ollama model can be selected and used without a BYOK key.
**Plans:** TBD
**UI hint**: yes

### Phase 6: PR #14 Audit & Smoke Test
**Goal:** Confirm guest mode, the landing/intro flow, and AWS efficiency changes still work end-to-end after all prior phases.
**Depends on:** Phases 1–5
**Requirements:** AUDIT-01, AUDIT-02, AUDIT-03
**Success Criteria** (what must be TRUE):
  1. A guest session can be created, can send messages up to the cap (and is blocked cleanly past it), can see the demo corpus, and is cleaned up on expiry.
  2. The landing/intro flow renders cleanly for both signed-out and signed-in users with no broken states and the auth gate behaving correctly.
  3. The AWS infrastructure changes shipped in PR #14 are verified against current usage — cost/efficiency claims hold and no regressions are observed in ECS, RDS, or Valkey behavior.
**Plans:** 4 plans

Plans:
**Wave 1**
- [x] 06-01-PLAN.md — Wave 0 RED: write 7 failing tests for AUDIT-01 gaps + CR-02 + CR-04
- [x] 06-02-PLAN.md — Wave 1 GREEN backend: fix CR-01, CR-02, CR-04
- [x] 06-03-PLAN.md — Wave 1 GREEN frontend: fix CR-03 (SSE JSON.parse guard)

**Wave 2** *(blocked on Wave 1 completion)*
- [x] 06-04-PLAN.md — Wave 2: AUDIT-02/03 manual checklist + phase SUMMARY + STATE/ROADMAP close-out
**UI hint**: yes

## Coverage

| Requirement | Phase |
|-------------|-------|
| WIRE-01 | Phase 1 |
| WIRE-02 | Phase 1 |
| WIRE-03 | Phase 1 |
| WIRE-04 | Phase 1 |
| QUAL-01 | Phase 1 |
| AGENT-01 | Phase 2 |
| AGENT-02 | Phase 2 |
| AGENT-03 | Phase 2 |
| QUAL-02 | Phase 2 |
| QUAL-03 | Phase 2 |
| QUAL-04 | Phase 2 |
| CONV-01 | Phase 3 |
| CONV-02 | Phase 3 |
| MEM-01 | Phase 3 |
| MEM-02 | Phase 3 |
| CHAT-01 | Phase 4 |
| CHAT-02 | Phase 4 |
| CHAT-03 | Phase 4 |
| CHAT-04 | Phase 4 |
| CHAT-05 | Phase 4 |
| CHAT-06 | Phase 4 |
| MODEL-01 | Phase 5 |
| MODEL-02 | Phase 5 |
| MODEL-03 | Phase 5 |
| MODEL-04 | Phase 5 |
| MODEL-05 | Phase 5 |
| AUDIT-01 | Phase 6 |
| AUDIT-02 | Phase 6 |
| AUDIT-03 | Phase 6 |

**Coverage:** 27 / 27 v1 requirements mapped — no orphans.

## Progress

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. Wire Protocol & Visibility | 3/3 | Complete | 2026-05-03 |
| 2. Agent Reliability | 3/3 | Complete | 2026-05-03 |
| 3. Destructive UX Paths | 3/3 | Complete | 2026-05-03 |
| 4. Loading & Error UX | 3/3 | Complete | 2026-05-03 |
| 5. Model Roster & Ollama | 3/3 | Complete | 2026-05-03 |
| 6. PR #14 Audit & Smoke Test | 4/4 | Complete | 2026-05-04 |

---
*Roadmap defined: 2026-05-03*
*Last updated: 2026-05-04 — Phase 6 complete (4 plans, 71 tests green). Milestone Stabilization & Hardening: 6/6 phases complete.*
