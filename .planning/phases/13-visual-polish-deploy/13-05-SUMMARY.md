---
phase: 13-visual-polish-deploy
plan: "05"
subsystem: frontend-copy-and-polish
tags: [visual-polish, welcome-message, capability-cards, guest-filtering, mobile-sidebar]
dependency_graph:
  requires:
    - 13-03
    - 13-04
  provides:
    - WELCOME_MESSAGE copy (Podium-specific)
    - CAPABILITY_CARDS (5 specific prompts)
    - isGuest prop wired ChatPage→MessageThread
    - memory card filtered for guests
  affects:
    - frontend/app/components/ChatPage.tsx
    - frontend/app/components/MessageThread.tsx
tech_stack:
  added: []
  patterns:
    - prop drilling (isGuest from ChatPage to MessageThread)
    - runtime array filter for guest capability restrictions
key_files:
  created: []
  modified:
    - frontend/app/components/ChatPage.tsx
    - frontend/app/components/MessageThread.tsx
decisions:
  - Filter "Remember something" card at runtime using isGuest flag; backend GUEST_ALLOWED_TOOLS is the enforcement layer (UI filter is UX honesty only)
  - WELCOME_MESSAGE names actual capabilities without over-promising (no "real-time data" claims beyond "search the web")
  - CAPABILITY_CARDS prompts are realistic recruiter/power-user queries, not toy examples
metrics:
  duration: "~10 minutes"
  completed: "2026-05-05"
  tasks_completed: 2
  tasks_blocked: 1
  files_modified: 2
---

# Phase 13 Plan 05: Visual Polish — Copy, Guest Filtering, Mobile Sidebar Summary

One-liner: Rewrote WELCOME_MESSAGE and CAPABILITY_CARDS to Podium-specific copy and wired isGuest prop from ChatPage to MessageThread for guest card filtering.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Rewrite WELCOME_MESSAGE and CAPABILITY_CARDS (POLISH-02) | 0c4aa80 | ChatPage.tsx, MessageThread.tsx |
| 2 | Add isGuest prop to MessageThread for guest card filtering (POLISH-03) | 121bbcd | MessageThread.tsx, ChatPage.tsx |

## Tasks Blocked (Checkpoint)

| Task | Name | Type | Blocked By |
|------|------|------|-----------|
| 3 | Verify mobile sidebar works correctly (D-09) | checkpoint:human-verify | Human must verify mobile sidebar at <768px in browser |

## What Was Built

### Task 1 — Copy Rewrite (POLISH-02 / D-08)

**WELCOME_MESSAGE** (in ChatPage.tsx line 18–19):
- Old: "Hi — I'm Podium, your personal AI assistant. I can search the web, read documents you upload, run code, and remember things you tell me over time. What would you like to work on?"
- New: "Hi — I'm Podium. I can search the web and synthesize results, remember context across our conversations, run Python code in a sandbox, and search documents you upload. What are you working on?"

**CAPABILITY_CARDS** (in MessageThread.tsx lines 9–34):
- Removed "Ask anything" (generic) and "Upload documents" (wrong prompt type)
- Removed "I'll remember this" (replaced with more active framing)
- Added "Read a URL" card (url_reader tool)
- All prompts are specific, realistic recruiter/power-user queries
- Cards: Search the web / Remember something / Run code / Search my documents / Read a URL

### Task 2 — Guest Card Filtering (POLISH-03)

**MessageThreadProps interface** updated:
- Added `isGuest?: boolean` (optional, defaults to false)
- Destructured with `isGuest = false` default

**CAPABILITY_CARDS render** filtered:
- `CAPABILITY_CARDS.filter((card) => !(isGuest && card.label === "Remember something"))`
- Guests see 4 cards instead of 5; memory card hidden (memory_save in GUEST_BLOCKED_TOOLS on backend)

**ChatPage.tsx call site** updated:
- Added `isGuest={isGuest}` to MessageThread component

### Task 3 — Mobile Sidebar Verification (D-09) — PENDING CHECKPOINT

ConversationSidebar already has correct implementation from prior phases:
- `fixed md:relative md:translate-x-0` on aside element
- `-translate-x-full` when closed, `translate-x-0` when open
- Mobile backdrop `fixed inset-0 z-10 md:hidden` that closes on tap
- Hamburger with `md:hidden` in ChatPage header

Human verification required at <768px viewport.

## Deviations from Plan

None — plan executed exactly as written for Tasks 1 and 2.

## Test Results

Frontend: 73 passed (73), 0 failures (run from main repo; worktree has no node_modules).

Note: Test run validates no regressions on base. Tests for isGuest prop already exist in ChatPage test suite (isGuest guard removal tests from Phase 13-03).

## Threat Model Compliance

| Threat ID | Disposition | Status |
|-----------|-------------|--------|
| T-13-10 | mitigate | Applied — guest filter added to CAPABILITY_CARDS render; backend frozenset is enforcement layer |
| T-13-11 | accept | Accepted — WELCOME_MESSAGE is static copy, no user data |

## Known Stubs

None — all capability cards reference real implemented tools.

## Self-Check: PASSED

- [x] `0c4aa80` — Task 1 commit exists
- [x] `121bbcd` — Task 2 commit exists
- [x] `grep "isGuest={isGuest}" ChatPage.tsx` — matches MessageThread call site (line 662)
- [x] `grep "isGuest" MessageThread.tsx | wc -l` — returns 3 (interface, default, filter)
- [x] `grep "Remember something" MessageThread.tsx` — present in CAPABILITY_CARDS definition, filtered at runtime for guests
- [x] WELCOME_MESSAGE no longer contains "personal AI assistant" or "What would you like to work on"
- [x] CAPABILITY_CARDS has no "Ask anything" entry
