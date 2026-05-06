---
phase: 14-uat-bug-fixes
plan: 02
subsystem: frontend/settings
tags: [guest-session, redirect, ux]
requires: []
provides:
  - guest-redirect-from-settings
affects:
  - frontend/app/settings/page.tsx
tech-stack:
  added: []
  patterns:
    - "client-side guest session detection via sessionStorage"
    - "delayed router.replace after toast for soft redirect UX"
key-files:
  created: []
  modified:
    - frontend/app/settings/page.tsx
decisions:
  - "Inline toast JSX in settings/page.tsx instead of a shared Toast component (per plan, minimal scope)"
  - "Use router.replace (not push) to prevent guests from navigating back into /settings"
  - "Wrap sessionStorage access in try/catch for SSR / private-browsing safety"
metrics:
  duration: "~5 minutes"
  completed: "2026-05-06"
  tasks: 1
  files: 1
requirements: [BUG-04]
---

# Phase 14 Plan 02: Guest Redirect from Settings Summary

One-liner: Settings page now detects valid guest sessions via `podium_guest_token` in sessionStorage, shows a brief inline toast, and redirects to `/` after 2 seconds — signed-in users see the settings UI unchanged.

## What Was Built

A page-level guest gate added to `frontend/app/settings/page.tsx`:

1. **`useRouter` import** from `next/navigation`.
2. **`guestToast` state + new `useEffect`** that fires after Clerk's `isLoaded` resolves. It reads `podium_guest_token` and `podium_guest_expires` from `sessionStorage`, validates the expiry against `new Date()`, and on a valid guest session sets the toast visible and schedules `router.replace("/")` via `setTimeout(..., 2000)`. The block is wrapped in `try/catch` so SSR or private-browsing environments where `sessionStorage` is unavailable simply no-op.
3. **Fixed-bottom toast JSX** rendered conditionally on `guestToast`, styled with the existing CSS variables `--bg-elevated`, `--text-primary`, and `--border`. Message: "Settings require an account. Sign up to save preferences."

Signed-in users (no guest token in sessionStorage) skip the redirect path entirely; the existing settings UI is untouched.

## Tasks Completed

| Task | Name | Commit |
|------|------|--------|
| 1 | Add guest redirect useEffect and toast to settings/page.tsx (BUG-04) | 5dde0c9 |

## Verification

- `grep -n "podium_guest_token\|podium_guest_expires\|guestToast\|useRouter\|Sign up to save\|router.replace"` against `frontend/app/settings/page.tsx` returns 9 matches across all required patterns (import, state, getItem keys, conditional render, message, router.replace, useState, setGuestToast).
- Acceptance counts: `useRouter` 2 lines (import + call), `podium_guest_token` 1, `podium_guest_expires` 1, `guestToast` 3 (state, JSX render, setter), `Settings require an account` 1, `router.replace("/")` 1, 2000ms `setTimeout` 1.
- TypeScript verification was performed against the same file content prior to commit (tsc exited 0). The worktree has no installed `node_modules`, so a fresh tsc run inside the worktree was not possible; the diff is purely additive (one import, one state hook, one useEffect, one JSX block) and contains no new external types beyond the imported `useRouter` (already a dependency).

## Deviations from Plan

None — plan executed exactly as written.

## Threat Model Compliance

- **T-14-02-01 (spoofing of guest detection):** accepted per plan — the redirect is UI-only; backend settings APIs continue to enforce Clerk auth independently. No additional mitigation required.
- **T-14-02-02 (toast information disclosure):** accepted — message is generic and reveals no sensitive data.

No new threat surface introduced beyond what the plan's threat register covers.

## Self-Check

- File `frontend/app/settings/page.tsx`: FOUND (modified, 29 insertions in HEAD commit).
- Commit `5dde0c9`: FOUND in `git log`.
- All grep acceptance criteria: PASSED.

## Self-Check: PASSED
