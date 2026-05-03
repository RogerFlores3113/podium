# Project State

## Project Reference
See: .planning/PROJECT.md (updated 2026-05-03)

**Core value:** A recruiter can ask a question and get a fast, reliable, clearly-presented answer with no silent failures.
**Current focus:** Phase 3 — Destructive UX Paths

## Phase Status
| Phase | Name | Status | Requirements |
|-------|------|--------|--------------|
| 1 | Wire Protocol & Visibility | Complete | WIRE-01–04, QUAL-01 |
| 2 | Agent Reliability | Complete | AGENT-01–03, QUAL-02–04 |
| 3 | Destructive UX Paths | Pending | CONV-01–02, MEM-01–02 |
| 4 | Loading & Error UX | Pending | CHAT-01–06 |
| 5 | Model Roster & Ollama | Pending | MODEL-01–05 |
| 6 | PR #14 Audit & Smoke Test | Pending | AUDIT-01–03 |

## Current Position
- **Phase:** 3 — Destructive UX Paths (next)
- **Last completed:** Phase 2 — Agent Reliability (2026-05-03)
- **Progress:** 2 / 6 phases complete

## Accumulated Context

### Decisions
- One milestone: audit + fix + harden before any new architecture.
- Ollama is dev/power-user only (configurable endpoint), not recruiter-facing.
- Keep `text-embedding-3-small` until retrieval quality is reported as a problem.
- Phase ordering follows research-established dependency chain: wire visibility → agent reliability → destructive UX → loading/error UX → model roster → PR #14 audit last.
- Tavily API key is shared across all users (never blank in prod); Tavily error sanitization UAT skipped as a result.
- Markdown rendering + blue URL links captured as v2 backlog (.planning/todos/pending/v2-markdown-rendering.md).
- All GSD work lives on `stabilization-hardening` branch (branched from main/PR#14). Main stays clean.

### Open Items
- Phase 5 needs external verification of: exact Anthropic dated IDs for `claude-sonnet-4-6` / `claude-haiku-4-5`, whether `gpt-5.4-nano` requires the Responses API path, and litellm version compatibility.
- SSE proxy buffering confirmed not an issue (Vercel proxy passes body stream through directly).
- CR-01 (Phase 2 review): QUAL-03 rollback assertion in test_agent_reliability.py is a tuple expression (always truthy) — real test gap, fix before Phase 6 audit.
- CR-02 (Phase 2 review): BadRequestError handler echoes LLM query into return string — low risk (shared infra, no user keys), fix in Phase 6 audit.

### Blockers
- None.

## Session Continuity
- Roadmap created 2026-05-03.
- Phase 1 complete 2026-05-03: 3 plans, 2 waves, 40/40 tests passing.
- Phase 2 complete 2026-05-03: 3 plans, 2 waves, 51/51 tests passing (11 new).
  - SSE delimiter mismatch (sep="\n" vs \r\n\r\n parsing) fixed in ChatPage.tsx during UAT.
  - Work on `stabilization-hardening` branch.
- Next action: `/gsd-discuss-phase 3` or `/gsd-plan-phase 3`

## Last Updated
2026-05-03 — Phase 2 complete
