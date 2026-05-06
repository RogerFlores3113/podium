---
status: partial
phase: 14-uat-bug-fixes
source: [14-VERIFICATION.md]
started: 2026-05-06T00:00:00Z
updated: 2026-05-06T00:00:00Z
---

## Current Test

[awaiting human testing]

## Tests

### 1. Guest redirect from /settings
expected: When logged in as a guest (valid podium_guest_token + podium_guest_expires in sessionStorage), navigating to /settings shows a toast notification for ~2 seconds then redirects to /
result: [pending]

### 2. Conversation delete end-to-end
expected: Clicking "Delete conversation" sends a DELETE request through the proxy, returns HTTP 200 (not 405), and removes the conversation from the list
result: [pending]

### 3. Dark mode banner rendering
expected: Guest banner and BYOK error banner display with correct contrast using var(--bg-elevated) and var(--text-muted) in both light and dark mode — no invisible or low-contrast text
result: [pending]

### 4. BUG-02 forced synthesis regression
expected: An agent run that previously looped 10 tool-only iterations (web search producing no answer) now produces a synthesized text answer instead of an empty or silent response
result: [pending]

## Summary

total: 4
passed: 0
issues: 0
pending: 4
skipped: 0
blocked: 0

## Gaps
