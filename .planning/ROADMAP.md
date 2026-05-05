# Roadmap: Podium

## Milestones

- ✅ **v1.0 Stabilization & Hardening** — Phases 1-6 (shipped 2026-05-04)
- ✅ **v2.0 Polish, Reliability & AI Upgrade** — Phases 7-10 (shipped 2026-05-04)
- 🚧 **v3.0 Unquestionably Clean** — Phases 11-13 (in progress)

## Phases

<details>
<summary>✅ v1.0 Stabilization & Hardening (Phases 1-6) — SHIPPED 2026-05-04</summary>

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
  4. Sending several messages in rapid succession does not produce duplicate memory extractions or 500s from `get_or_create_user` race conditions.
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
  2. Deleting a memory in settings removes it from the visible list immediately with no silent failure.
  3. Any failed settings action (add/delete memory, add/delete API key) renders a visible status message — no swallowed errors.
**Plans:** 3 plans
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
**Plans:** 3 plans
**UI hint**: yes

### Phase 5: Model Roster & Ollama
**Goal:** Only approved models are user-selectable, guests are locked to gpt-5-nano, and Ollama appears only when a developer opts in via env var.
**Depends on:** External verification of Anthropic and gpt-5.4-nano model IDs
**Requirements:** MODEL-01, MODEL-02, MODEL-03, MODEL-04, MODEL-05
**Success Criteria** (what must be TRUE):
  1. The model picker shows exactly `gpt-5-nano`, `gpt-5.4-nano`, `claude-sonnet-4-6`, `claude-haiku-4-5` (plus Ollama entries only when `OLLAMA_BASE_URL` is set).
  2. A guest user cannot select any model other than gpt-5-nano — the dropdown is disabled for guest sessions, and the backend enforces the same.
  3. With `OLLAMA_BASE_URL` unset, no Ollama models are exposed; with it set, an Ollama model can be selected and used without a BYOK key.
**Plans:** 3 plans
**UI hint**: yes

### Phase 6: PR #14 Audit & Smoke Test
**Goal:** Confirm guest mode, the landing/intro flow, and AWS efficiency changes still work end-to-end after all prior phases.
**Depends on:** Phases 1–5
**Requirements:** AUDIT-01, AUDIT-02, AUDIT-03
**Success Criteria** (what must be TRUE):
  1. A guest session can be created, can send messages up to the cap (and is blocked cleanly past it), can see the demo corpus, and is cleaned up on expiry.
  2. The landing/intro flow renders cleanly for both signed-out and signed-in users with no broken states and the auth gate behaving correctly.
  3. The AWS infrastructure changes shipped in PR #14 are verified against current usage — cost/efficiency claims hold and no regressions observed.
**Plans:** 4 plans
**UI hint**: yes

Coverage (v1.0):

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

</details>

---

## v2.0 Polish, Reliability & AI Upgrade

**Milestone Goal:** Clear code review debt, fix frontend UX bugs, upgrade the agent with actor-critic reasoning and proactive memory, and complete Ollama dynamic model support.

### Phase Checklist

- [x] **Phase 7: Backend Debt & Security** — Eliminate the guest API key leak, harden SSE stream teardown, and fix the Ollama localhost URL rewrite.
- [x] **Phase 8: Frontend Bugs & Polish** — Fix all four UI bugs, surface the BYOK 402 provider-correct message, and ship markdown rendering with in-progress indicators. (completed 2026-05-04)
- [x] **Phase 9: Memory & Agent Core** — Add `memory_save` tool, update system prompt with memory guidance, audit all agent prompts, and implement the actor-critic self-critique pass. (completed 2026-05-04)
- [ ] **Phase 10: Agent UI & Dynamic Ollama** — Expose the Effort slider in the UI and wire up the dynamic Ollama model list in the picker.

## Phase Details

### Phase 7: Backend Debt & Security
**Goal:** The backend is free of the guest API key leak, SSE streams tear down cleanly on error, and Ollama URLs are automatically corrected before use.
**Depends on:** Nothing (pure backend, no frontend deps)
**Requirements:** DEBT-01, DEBT-02, OLL-02
**Success Criteria** (what must be TRUE):
  1. A guest user on the Anthropic or Ollama provider receives the correct system key for that provider — the OpenAI system key is never passed to a non-OpenAI endpoint.
  2. After any chat stream ends (normally or via error), the SSE reader lock is released — no "stream is locked" errors appear in subsequent requests on the same connection.
  3. A developer-supplied Ollama URL containing `localhost` is automatically rewritten to `host.docker.internal` when running in a Docker context, or the UI surfaces clear guidance about the required URL format.
**Plans:** 1/1 plans complete

Plans:
- [x] 07-01-PLAN.md — Implement OLL-02 normalize_ollama_url utility, wire at agent.py and chat.py call sites, and verify pre-done DEBT-01/DEBT-02

### Phase 8: Frontend Bugs & Polish
**Goal:** All four UI bugs are gone, the BYOK 402 error shows the correct provider name, and the chat thread renders markdown with continuous progress feedback.
**Depends on:** Nothing (pure frontend, independent of Phase 7)
**Requirements:** UI-01, UI-02, UI-03, UI-04, DEBT-03, UX-01, UX-02, UX-03
**Success Criteria** (what must be TRUE):
  1. The conversation delete button renders as a circular bubble with correct dark/light mode colors, positioned top-right of the conversation item.
  2. The hamburger toggle is absent on desktop (sidebar permanently pinned) and functions correctly on mobile.
  3. After a guest completes signup and then logs into an existing account, the guest banner disappears and the model picker becomes enabled without requiring a page reload.
  4. The starter prompt suggestions no longer include "Generate images".
  5. When a user hits the BYOK 402 limit, the inline error message names the correct provider (e.g., "Add your Anthropic API key" for Anthropic models), not a hardcoded "OpenAI" string.
  6. A continuously-visible in-progress indicator appears during the synthesis gap — the period after tool results arrive and before the first synthesis token — so the user never sees a blank wait.
  7. Agent processing status is shown as a max-3-word label outside the chat bubble (e.g., "Searching web…", "Thinking…").
  8. Assistant messages render as markdown; links are blue and underline on hover.
**Plans:** 2 plans

**Plans:** 2/2 plans complete

Plans:
- [x] 08-01-PLAN.md — All ChatPage.tsx fixes: UI-01/02/03/04, DEBT-03, UX-01/02 + test suite (Wave 1)
- [x] 08-02-PLAN.md — globals.css markdown link/code styling: UX-03 (Wave 1, parallel)

### Phase 9: Memory & Agent Core
**Goal:** The agent can proactively save memories during conversation, and its reasoning quality is improved through prompt auditing and a self-critique pass.
**Depends on:** Nothing (pure backend, independent of Phase 8)
**Requirements:** MEM-01, MEM-02, AGT-01, AGT-02, AGT-04
**Success Criteria** (what must be TRUE):
  1. During a conversation, the agent can call a `memory_save` tool to persist a fact or preference, and that memory is retrievable in future sessions.
  2. The system prompt instructs the agent on when to proactively save memories vs. search — representative recruiter queries result in appropriate memory saves without explicit user instruction.
  3. All tool descriptions and the system prompt have been reviewed and rewritten — representative recruiter queries produce more complete and accurate answers than before the audit.
  4. When effort level is Balanced or Thorough, the agent performs a self-critique pass before delivering its final answer; when effort is Fast, the self-critique pass is skipped.
**Plans:** 4 plans

Plans:
- [ ] 09-01-PLAN.md — Write all RED failing tests for Phase 9 (Wave 0, TDD baseline)
- [ ] 09-02-PLAN.md — memory_save tool, system prompt rewrite, tool descriptions (Wave 1, MEM-01/02/AGT-01)
- [ ] 09-03-PLAN.md — effort field, _actor_critic helper, both execution path intercepts (Wave 1 parallel, AGT-02/04)
- [ ] 09-04-PLAN.md — GREEN verification gate, full suite must pass (Wave 2)

### Phase 10: Agent UI & Dynamic Ollama
**Goal:** Users can select their desired reasoning depth per query, and the Ollama model picker shows a live list of locally-available models after the base URL is saved.
**Depends on:** Phase 9 (backend must gate actor-critic on effort level before UI exposes it), Phase 7 (Ollama URL rewrite must be in place)
**Requirements:** AGT-03, OLL-01
**Success Criteria** (what must be TRUE):
  1. The chat UI exposes a Fast / Balanced / Thorough effort selector; the selected level is sent with each request and visibly affects response depth (Fast produces quicker, less-elaborated answers; Thorough produces longer, self-critiqued answers).
  2. After a user saves an OLLAMA_BASE_URL in settings, the model picker immediately renders the available Ollama models fetched from that endpoint — no page reload required, and no auth-timing errors on the fetch.
**Plans:** 3 plans
**UI hint**: yes

Plans:
- [ ] 10-01-PLAN.md — Write RED failing tests for AGT-03 and OLL-01; update mockMountFetches to 2-slot order (Wave 1)
- [ ] 10-02-PLAN.md — Implement effort selector and Ollama fetch timing fix in ChatPage.tsx (Wave 2)
- [ ] 10-03-PLAN.md — Full suite verification gate + human UAT checkpoint (Wave 3)

## Coverage

| Requirement | Phase |
|-------------|-------|
| DEBT-01 | Phase 7 |
| DEBT-02 | Phase 7 |
| OLL-02 | Phase 7 |
| UI-01 | Phase 8 |
| UI-02 | Phase 8 |
| UI-03 | Phase 8 |
| UI-04 | Phase 8 |
| DEBT-03 | Phase 8 |
| UX-01 | Phase 8 |
| UX-02 | Phase 8 |
| UX-03 | Phase 8 |
| MEM-01 | Phase 9 |
| MEM-02 | Phase 9 |
| AGT-01 | Phase 9 |
| AGT-02 | Phase 9 |
| AGT-04 | Phase 9 |
| AGT-03 | Phase 10 |
| OLL-01 | Phase 10 |

**Coverage:** 18 / 18 v2.0 requirements mapped — no orphans.

## Progress

| Phase | Milestone | Plans Complete | Status | Completed |
|-------|-----------|----------------|--------|-----------|
| 1. Wire Protocol & Visibility | v1.0 | 3/3 | Complete | 2026-05-03 |
| 2. Agent Reliability | v1.0 | 3/3 | Complete | 2026-05-03 |
| 3. Destructive UX Paths | v1.0 | 3/3 | Complete | 2026-05-03 |
| 4. Loading & Error UX | v1.0 | 3/3 | Complete | 2026-05-03 |
| 5. Model Roster & Ollama | v1.0 | 3/3 | Complete | 2026-05-03 |
| 6. PR #14 Audit & Smoke Test | v1.0 | 4/4 | Complete | 2026-05-04 |
| 7. Backend Debt & Security | v2.0 | 1/1 | Complete    | 2026-05-04 |
| 8. Frontend Bugs & Polish | v2.0 | 2/2 | Complete    | 2026-05-04 |
| 9. Memory & Agent Core | v2.0 | 4/4 | Complete    | 2026-05-04 |
| 10. Agent UI & Dynamic Ollama | v2.0 | 0/TBD | Not started | - |

---

## v3.0 Unquestionably Clean

**Milestone Goal:** Audit and remove test dead weight, extract modules for single-responsibility, split the monolith ChatPage, fix remaining bugs, and ship visual polish.

### Phase Checklist

- [x] **Phase 11: Refactor & Test Audit** — Delete 4 implementation-detail test files, extract critic.py, split ChatPage.tsx into 4 focused components. (completed 2026-05-05)
- [x] **Phase 12: Bug Fixes** — Fix CR-01 actor-critic fallback guard, CR-02 tool message handling, CR-03 handleDeleteConversation error handling, and other review findings. (completed 2026-05-05)
- [ ] **Phase 13: Visual Polish & Deploy** — Final visual polish and production deployment.

## Phase Details (v3.0)

### Phase 11: Refactor & Test Audit
**Goal:** Test suite tests behavior not implementation; each backend module has one clear purpose; ChatPage.tsx is split into focused sub-components.
**Requirements:** REFACTOR-01, REFACTOR-02, REFACTOR-03, REFACTOR-04, REFACTOR-05
**Plans:** 3/3 plans complete

Plans:
- [x] 11-01-PLAN.md — Delete 4 stale test files; remove stale model ID assertions from test_config.py (Wave 1)
- [x] 11-02-PLAN.md — Extract _actor_critic → critic.py; remove dead code from llm.py (Wave 1, parallel)
- [x] 11-03-PLAN.md — Split ChatPage.tsx into ConversationSidebar, MessageThread, ChatComposer + shared types (Wave 2)

### Phase 12: Bug Fixes
**Goal:** Fix all Critical and Warning findings from Phase 11 code review; all backend and frontend tests pass.
**Requirements:** CR-01, CR-02, CR-03, WR-01, WR-02, WR-03, WR-04, WR-05, WR-06, IN-01
**Plans:** 2 plans

Plans:
- [x] 12-01-PLAN.md — Backend fixes: critic double-guard, try/except, standard_messages, tool [no output], LIMIT 200, orphan drop, test rename, prompt fix (Wave 1)
- [x] 12-02-PLAN.md — Frontend fixes: handleDeleteConversation try/catch, loadConversation guard, guest isSignedIn check, remove dead isLoading prop (Wave 2)

### Phase 13: Visual Polish & Deploy
**Goal:** Final visual polish and production deployment.
**Requirements:** TBD
**Plans:** 0 plans (not started)

## Progress (v3.0)

| Phase | Milestone | Plans Complete | Status | Completed |
|-------|-----------|----------------|--------|-----------|
| 11. Refactor & Test Audit | v3.0 | 3/3 | Complete | 2026-05-05 |
| 12. Bug Fixes | v3.0 | 2/2 | Complete | 2026-05-05 |
| 13. Visual Polish & Deploy | v3.0 | 0/TBD | Not started | — |

---
*Roadmap defined: 2026-05-03 (v1.0) / 2026-05-04 (v2.0 phases added) / 2026-05-05 (v3.0 phases added)*
*Last updated: 2026-05-05 — Phase 12 complete. 94 backend + 67 frontend tests passing. 10 bug-fix requirements verified.*
