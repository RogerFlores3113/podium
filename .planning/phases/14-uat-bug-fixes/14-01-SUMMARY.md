---
phase: 14-uat-bug-fixes
plan: 01
subsystem: frontend
tags: [proxy, chat, landing, css-vars, bug-fix]
requires: []
provides:
  - "Next.js proxy DELETE/PATCH method support"
  - "Robust hasDocuments null guard"
  - "Composer prefill cleared on new conversation"
  - "Theme-correct banner styling (light/dark)"
  - "Correct View source href"
affects:
  - frontend/app/api/[...proxy]/route.ts
  - frontend/app/components/ChatPage.tsx
  - frontend/app/components/LandingPage.tsx
tech-stack:
  added: []
  patterns:
    - "Per-method proxy handlers mirror existing GET/POST shape"
    - "Inline style theme via CSS custom properties (no hex fallbacks)"
key-files:
  created: []
  modified:
    - frontend/app/api/[...proxy]/route.ts
    - frontend/app/components/ChatPage.tsx
    - frontend/app/components/LandingPage.tsx
decisions:
  - "DELETE handler does NOT forward body (no read), matching GET shape"
  - "PATCH handler mirrors POST exactly, including multipart detection"
  - "Banners use var(--bg-elevated) / var(--text-muted) with NO fallback hex; both vars are defined in :root and [data-theme=dark]"
  - "hasDocuments guard switched to falsy check (!hasDocuments) so initial null state behaves like 'no documents'"
metrics:
  duration: "single wave"
  tasks_completed: 3
  files_modified: 3
  completed: 2026-05-06
---

# Phase 14 Plan 01: UAT Frontend Regressions Summary

Fixed five frontend regressions surfaced in UAT — added DELETE/PATCH to the Next.js proxy, hardened the hasDocuments guard, cleared composer prefill on new conversation, normalized banner CSS variables, and corrected the landing-page GitHub link.

## Tasks Executed

| # | Task                                                | Commit  |
|---|-----------------------------------------------------|---------|
| 1 | Add DELETE and PATCH exports to Next.js proxy       | f8abe3d |
| 2 | Fix hasDocuments guard, prefill clear, banner vars  | 87e6202 |
| 3 | Fix View source href in LandingPage                 | 9e2982d |

## Requirements Closed

- BUG-01 — DELETE /conversations/{id} via proxy now forwards instead of returning 405
- BUG-03 — `Search my documents` shortcut no longer fires API errors when documents state is `null`
- BUG-05 — `+ New conversation` clears the composer textarea
- BUG-06 — Guest banner and BYOK banner render with theme variables in both light and dark mode
- BUG-07 — Hero `View source` link points at `https://github.com/RogerFlores3113`

## Key Changes

**`frontend/app/api/[...proxy]/route.ts`**
- Added `DELETE` (mirrors `GET`, no body) and `PATCH` (mirrors `POST`, multipart-aware) named exports.
- File now exports four methods: GET, POST, DELETE, PATCH.

**`frontend/app/components/ChatPage.tsx`**
- `startNewConversation`: `setPrefillValue("")` added as the first statement.
- Guard `label === "Search my documents" && hasDocuments === false` -> `!hasDocuments`.
- Guest banner and BYOK banner inline `style` switched from `var(--bg-subtle, #...)` / `var(--text-secondary, #...)` to `var(--bg-elevated)` / `var(--text-muted)` with no hex fallback.

**`frontend/app/components/LandingPage.tsx`**
- Hero anchor `href` changed from `https://github.com/RogerFlores3113/podium` to `https://github.com/RogerFlores3113` (other anchor at line 134 already correct, untouched).

## Verification

- `grep "^export async function" frontend/app/api/[...proxy]/route.ts` -> 4 lines (GET, POST, DELETE, PATCH).
- `grep -c "bg-subtle\|text-secondary" frontend/app/components/ChatPage.tsx` -> `0`.
- `grep -c "hasDocuments === false" frontend/app/components/ChatPage.tsx` -> `0`; `grep -c "!hasDocuments"` -> `1`.
- `grep -c 'setPrefillValue("")' frontend/app/components/ChatPage.tsx` -> `1`.
- `grep -c 'var(--bg-elevated)' frontend/app/components/ChatPage.tsx` -> 7; `var(--text-muted)` -> 10 (>= 2 each across both banners plus pre-existing usage).
- `grep -c 'href="https://github.com/RogerFlores3113/podium"' frontend/app/components/LandingPage.tsx` -> `0`; profile href -> `2` (existing footer link plus the corrected hero link).

TypeScript `tsc --noEmit` was not run inside this worktree because frontend `node_modules` is not provisioned in the worktree filesystem. The edits are mechanical and isolated; pre-existing typing on `prefillValue` (string state) and `hasDocuments` (boolean | null) make `setPrefillValue("")` and `!hasDocuments` type-safe by inspection. The orchestrator/main checkout retains node_modules and will run lint/build in CI.

## Deviations from Plan

None. All three tasks executed exactly as specified; no Rule 1/2/3 deviations triggered.

## Self-Check: PASSED

- FOUND: frontend/app/api/[...proxy]/route.ts — DELETE + PATCH exports present
- FOUND: frontend/app/components/ChatPage.tsx — three edits applied, grep contracts satisfied
- FOUND: frontend/app/components/LandingPage.tsx — href corrected
- FOUND commit f8abe3d
- FOUND commit 87e6202
- FOUND commit 9e2982d
