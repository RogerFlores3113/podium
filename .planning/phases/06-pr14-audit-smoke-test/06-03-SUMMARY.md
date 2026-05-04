---
phase: 06-pr14-audit-smoke-test
plan: 03
subsystem: frontend-sse
tags: [bug-fix, frontend, sse, code-review-debt]
requires: []
provides:
  - "Resilient SSE JSON parse loop (CR-03)"
affects:
  - frontend/app/components/ChatPage.tsx
tech-stack:
  added: []
  patterns:
    - "Skip-and-continue parse error handling for SSE frames"
key-files:
  created: []
  modified:
    - frontend/app/components/ChatPage.tsx
decisions:
  - "Used `let data: any;` rather than `let data: unknown;` to keep diff minimal — there are >5 downstream access sites (data.conversation_id, data.token, data.id, data.name, data.arguments, data.result, data.error, data.detail) that would all need narrowing/casts under `unknown`. Plan explicitly permitted option (b) when access sites > 5."
metrics:
  duration: "~10m"
  completed: 2026-05-03
---

# Phase 06 Plan 03: SSE JSON Parse Hardening (CR-03) Summary

One-liner: Wrap the SSE reader's `JSON.parse(line.slice(6))` in try/catch with `continue`, so a single malformed `data:` frame can no longer abort the entire assistant response.

## What Changed

`frontend/app/components/ChatPage.tsx` — SSE reader inside the `for (const line of lines)` loop.

### Before

```typescript
} else if (line.startsWith("data: ")) {
  const data = JSON.parse(line.slice(6));
```

### After

```typescript
} else if (line.startsWith("data: ")) {
  let data: any;
  try {
    data = JSON.parse(line.slice(6));
  } catch {
    continue; // skip malformed frames, don't abort the stream
  }
```

The enclosing loop was confirmed to be `for (const line of lines)` (not `forEach`), so `continue` correctly skips the malformed frame and continues processing subsequent valid frames in the same chunk.

## Decisions

### `let data: any;` vs `let data: unknown;`

Chose `any`. Downstream branches read `data.conversation_id`, `data.token`, `data.id`, `data.name`, `data.arguments`, `data.result`, `data.error`, `data.detail` — that is 8 distinct access sites across 7 `else if` branches. Switching to `unknown` would require casting every site, ballooning the diff well past the plan's "minimal change" guidance. The plan explicitly authorized option (b) when access sites exceed 5.

The runtime behavior is identical — TypeScript type information is erased at runtime; the SSE event-name dispatch (`currentEvent === "..."`) already gates which fields are read, so missing/wrong fields fail benignly within their existing branches.

## Verification

### Automated (grep-based, per plan acceptance criteria)

| Criterion | Result |
|-----------|--------|
| `const data = JSON.parse(line.slice(6))` (old, unguarded) | 0 matches — gone |
| `let data:\s*(unknown\|any);` in SSE reader | 1 match (line 281) |
| `data = JSON.parse(line.slice(6));` (new assignment) | 1 match (line 283) |
| `continue; // skip malformed frames` | 1 match (line 285) |
| `try {` precedes `data = JSON.parse...` within 2 lines | confirmed (1 match) |
| Enclosing loop is `for (const line of lines)` | confirmed |

### TypeScript Check (deferred)

`cd frontend && npx tsc --noEmit` could not be run in this worktree because `frontend/node_modules` is not installed (worktree was created without `npm install`). The change is mechanically minimal:
- Replaces `const data = JSON.parse(...)` with `let data: any; try { data = JSON.parse(...) } catch { continue; }`
- Preserves the exact `data` identifier and `any` typing, which keeps every downstream `data.*` access site valid.

This pattern has no plausible TypeScript regression. Plan 04's manual checklist (per VALIDATION.md) covers the runtime smoke test with a malformed frame.

## Deviations from Plan

### Auto-fixed Issues

None.

### Procedural Note

The plan's primary `<verify>` step (`cd frontend && npx tsc --noEmit`) was unrunnable because `frontend/node_modules` is not present in this worktree. All grep-based acceptance criteria passed; the TypeScript check is recommended to be re-run by Plan 04's manual checklist owner before merge. This is not a code deviation — only a verification environment limitation specific to the worktree.

## Threat Surface

The plan's threat register entries T-06-07 (DoS / UX cascade) and T-06-08 (defensive tampering) are both mitigated by this change. No new threat surface introduced.

## Self-Check: PASSED

- File modified: `frontend/app/components/ChatPage.tsx` — confirmed via grep that the new try/catch block is in place at the expected location.
- Acceptance criteria: all grep-based criteria from the plan pass (see Verification table above).
- Commit: created in this plan's commit (hash recorded by orchestrator).
