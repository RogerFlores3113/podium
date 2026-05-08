# CLAUDE.md

## Core principles

1. Don't assume. Don't hide confusion. Surface tradeoffs.
2. Minimum code that solves the problem. Nothing speculative.
3. Touch only what you must. Clean up only your own mess. To clean up
   anything else, propose it during planning — never during implementation.
4. Define success criteria. Loop until verified.

## Two modes of operation

### Planning mode (human in the loop)

Superpowers is installed. Use its brainstorm → plan pipeline for any
non-trivial work. Do not skip phases.

During planning, be thorough and over-communicate:
- When a design decision has multiple valid options, present them all with
  tradeoffs. Don't pick silently.
- Ask clarifying questions early. Exhaust ambiguity before we leave planning.
- Flag risks, unknowns, and things that could go wrong.

Before implementation begins, produce a **design doc** as a markdown file in
`docs/plans/<feature-name>.md`. The design doc must include:
- Problem statement (what and why)
- Key design decisions with tradeoffs considered and choices made
- File-level change list (which files are created, modified, deleted)
- Success criteria as testable assertions
- Risks and mitigations
- Test plan: what is tested, what edge cases are covered

The design doc is the contract. Do not begin implementation until I sign off.

### Execution mode (fully autonomous)

Once I approve the design doc, execute the entire plan without asking
further questions. The design doc has the answers — refer to it.

- If you hit an ambiguity the design doc doesn't cover, make the most
  conservative choice, document it as a comment, and keep going.
- If you hit a blocker that genuinely cannot be resolved without human
  input, write it to `docs/plans/<feature-name>-blockers.md` and continue
  with the rest of the plan.
- Do not stop to ask "should I continue?" — yes, always continue.
- After all tasks are complete, run the full test suite and summarize
  results. Write a completion report to `docs/plans/<feature-name>-done.md`
  covering: what was built, any deviations from the plan, any blockers
  written, and final test status.

## Testing

Write tests before implementation (red-green-refactor). Superpowers enforces
this — follow it. Additionally:

- Every public function gets at least one happy-path and one edge-case test.
- Tests must be runnable in isolation. No test should depend on another.
- Name tests as sentences that describe behavior, not method names.
- If a test is hard to write, the interface is probably wrong. Revisit the
  design before hacking around it.

## Code style

- Prefer clarity over cleverness.
- Functions do one thing. If you need "and" to describe it, split it.
- No dead code. No commented-out code. No TODOs without an issue reference.
- Commit messages: imperative mood, under 72 chars, body explains *why*.

## Git workflow

- One logical change per commit.
- Work on feature branches, never directly on main.
- Superpowers manages worktrees — follow its conventions.

## When compacting

When summarizing this conversation, preserve:
- The current plan and its status
- All files modified and why
- Decisions made and their rationale
- Current test status and any failures

## Subagent cost policy

Default to spawning subagents **sequentially**. Use parallel spawning only when tasks are genuinely independent and parallelism provides clear value. Unnecessary parallel spawning causes cache-read spikes that cost real money; 2x wall time is an acceptable tradeoff.

After a phase is verified complete, delete its RESEARCH.md and all its PLAN.md files immediately. RESEARCH.md files are large web-scraped reference docs needed only during planning. PLAN.md files are execution guides — once a phase is done and summarized in SUMMARY.md, they are dead. GSD itself classifies other phases' PLAN.md files as out-of-scope context (see universal-anti-patterns.md). SUMMARY.md is the permanent record.

## GSD Workflow

This project uses GSD for planning and execution. Planning docs live in `.planning/` (local-only, gitignored).

**Current milestone:** Stabilization & Hardening (6 phases, 27 requirements)
**State:** `.planning/STATE.md` | **Roadmap:** `.planning/ROADMAP.md`

Before starting any phase:
- Run `/gsd-discuss-phase N` to load phase context
- Run `/gsd-plan-phase N` to generate the execution plan
- Run `/gsd-execute-phase N` to execute autonomously (YOLO mode)

Phase order and dependencies:
1. Wire Protocol & Visibility — WIRE-01–04, QUAL-01 (foundation, do first)
2. Agent Reliability — AGENT-01–03, QUAL-02–04 (depends on Phase 1)
3. Destructive UX Paths — CONV-01–02, MEM-01–02 (independent)
4. Loading & Error UX — CHAT-01–06 (depends on Phase 1 + 2)
5. Model Roster & Ollama — MODEL-01–05 (verify model IDs before merge)
6. PR #14 Audit & Smoke Test — AUDIT-01–03 (runs last)

## Alembic migration note

Two migrations share the title "add tool call fields to messages":
- `ca316cd7fec5` — adds `tool_calls` (JSONB) and `tool_call_ids` (String)
- `dc368990e622` — renames `tool_call_ids` → `tool_call_id` (singular)

These are chained (`dc368`'s `down_revision = 'ca316cd7fec5'`). Both are
intentional and must stay.