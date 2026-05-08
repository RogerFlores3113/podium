# Phase 1 — UAT Bug Fixes Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix all 7 UAT Round 2 findings before the domain migration PR lands.

**Architecture:** Six targeted edits across 4 files (agent loop forced synthesis, frontend guard fix, prefill reset, banner theme, settings auth gate, landing page URL). B-N1 (delete 405) is investigated first via curl — the fix is conditional on what curl returns.

**Tech Stack:** Python/FastAPI backend, Next.js/React frontend, Vitest for frontend tests, pytest for backend tests.

---

### Task 0: Diagnose B-N1 (delete 405) in production

**Files:** none — investigation only

- [ ] **Step 1: Run curl against the live ALB**

```bash
# Replace <uuid> with any real conversation ID from the sidebar
curl -v -X DELETE \
  "http://rflores-podium-alb-1333147673.us-east-1.elb.amazonaws.com/chat/<uuid>" \
  -H "Authorization: Bearer <guest-or-clerk-token>"
```

- [ ] **Step 2: Interpret result**

  - **Returns 200** → backend is fine. Root cause is browser mixed-content (HTTPS Vercel → HTTP ALB). **No code change needed** — Phase 2 domain migration (HTTPS via Cloudflare) will fix it as a side effect. Skip to Task 1.
  - **Returns 405** → backend routing issue. Check `terraform show` to confirm the live ECS image matches the current repo. If the image is stale, redeploy: `aws ecs update-service --cluster podium-cluster --service podium-app --force-new-deployment`. Re-run curl. If still 405, add a debug log to the delete route and redeploy.
  - **Returns 401** → token is invalid. Retry with a fresh token from browser DevTools → Application → sessionStorage.

- [ ] **Step 3: Commit diagnosis notes**

```bash
git commit --allow-empty -m "chore: B-N1 diagnosis — curl result recorded, fix strategy chosen"
```

---

### Task 1: B-N2 — Force synthesis turn after max iterations (litellm path)

**Files:**
- Modify: `app/services/agent.py` (end of `run_agent`, litellm path)
- Test: `tests/test_agent_reliability.py`

- [ ] **Step 1: Write the failing test**

Add to `tests/test_agent_reliability.py`:

```python
def test_run_agent_synthesizes_after_max_iterations():
    """After exhausting all iterations with tool calls, agent must yield 'done' not 'error'."""
    import inspect
    import app.services.agent as agent_module
    source = inspect.getsource(agent_module)
    # Synthesis nudge must exist after the for loop exits
    assert "Synthesize" in source or "synthesize" in source, (
        "agent.py must inject a synthesis nudge after max iterations"
    )
    assert "tools=None" in source or 'tools=None' in source, (
        "Synthesis call must pass tools=None to prevent further tool calls"
    )
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd /home/rflor/podium && python -m pytest tests/test_agent_reliability.py::test_run_agent_synthesizes_after_max_iterations -v
```

Expected: FAIL — "Synthesize" and "tools=None" not yet in source after the loop.

- [ ] **Step 3: Implement — replace the final error yield in the litellm path**

In `app/services/agent.py`, find the last lines of `run_agent` (the litellm for-loop path):

```python
    # BEFORE (remove this):
    logger.warning(f"Agent hit max iterations ({settings.agent_max_iterations})")
    yield {
        "type": "error",
        "detail": f"Agent exceeded {settings.agent_max_iterations} iterations. "
                  "This usually means the task is too complex or the model is confused.",
    }
```

Replace with:

```python
    # Synthesize — force one final text-only response instead of surfacing a raw error
    logger.warning(f"Agent hit max iterations ({settings.agent_max_iterations}) — forcing synthesis")
    synthesis_msgs = messages + [{
        "role": "user",
        "content": "Synthesize everything you found and write a complete answer to the user's original question. Do not make any more tool calls.",
    }]
    try:
        is_ollama = resolved_model.startswith("ollama/")
        synth_response = await acompletion(
            model=resolved_model,
            messages=synthesis_msgs,
            tools=None,
            api_key="" if is_ollama else resolved_api_key,
            api_base=normalize_ollama_url(resolved_api_key) if is_ollama else None,
            max_tokens=1500,
            stream=True,
        )
        final_text = ""
        async for chunk in synth_response:
            if chunk is None:
                break
            delta = chunk.choices[0].delta
            if delta.content:
                final_text += delta.content
                yield {"type": "token", "content": delta.content}
        if final_text.strip():
            yield {"type": "assistant_message", "content": final_text, "tool_calls": None}
            yield {"type": "done"}
            return
    except Exception as e:
        logger.error(f"Synthesis call failed after max iterations: {e}", exc_info=True)
    yield {
        "type": "error",
        "detail": "I wasn't able to produce a final answer after extensive research. Please try a more specific question.",
    }
```

- [ ] **Step 4: Run test to verify it passes**

```bash
python -m pytest tests/test_agent_reliability.py::test_run_agent_synthesizes_after_max_iterations -v
```

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add app/services/agent.py tests/test_agent_reliability.py
git commit -m "fix(B-N2): force synthesis turn after max iterations in litellm agent path"
```

---

### Task 2: B-N2 — Force synthesis turn after max iterations (Responses API path)

**Files:**
- Modify: `app/services/agent.py` (end of `_run_responses_agent`)
- Test: `tests/test_agent_reliability.py`

- [ ] **Step 1: Write the failing test**

Add to `tests/test_agent_reliability.py`:

```python
def test_responses_agent_synthesizes_after_max_iterations():
    """_run_responses_agent must also inject synthesis after max iterations."""
    import inspect
    import app.services.agent as agent_module
    source = inspect.getsource(agent_module._run_responses_agent)
    assert "synthesize" in source.lower() or "Synthesize" in source, (
        "_run_responses_agent must inject a synthesis nudge after max iterations"
    )
```

- [ ] **Step 2: Run to verify it fails**

```bash
python -m pytest tests/test_agent_reliability.py::test_responses_agent_synthesizes_after_max_iterations -v
```

Expected: FAIL

- [ ] **Step 3: Implement — replace the final error yield in `_run_responses_agent`**

Find the last lines of `_run_responses_agent`:

```python
    # BEFORE (remove this):
    logger.warning(f"Responses API agent hit max iterations ({settings.agent_max_iterations})")
    yield {
        "type": "error",
        "detail": f"Agent exceeded {settings.agent_max_iterations} iterations.",
    }
```

Replace with:

```python
    logger.warning(f"Responses API agent hit max iterations ({settings.agent_max_iterations}) — forcing synthesis")
    synthesis_input = input_messages + [{
        "role": "user",
        "content": [{"type": "input_text", "text": "Synthesize everything you found and write a complete answer to the user's original question. Do not make any more tool calls."}],
    }]
    try:
        synth_stream = await client.responses.create(
            model=model,
            input=synthesis_input,
            tools=[],
            store=True,
            stream=True,
        )
        final_text = ""
        async for event in synth_stream:
            if event.type == "response.output_text.delta":
                final_text += event.delta
                yield {"type": "token", "content": event.delta}
        if final_text.strip():
            yield {"type": "assistant_message", "content": final_text, "tool_calls": None}
            yield {"type": "done"}
            return
    except Exception as e:
        logger.error(f"Responses API synthesis call failed: {e}", exc_info=True)
    yield {
        "type": "error",
        "detail": "I wasn't able to produce a final answer after extensive research. Please try a more specific question.",
    }
```

- [ ] **Step 4: Run test to verify it passes**

```bash
python -m pytest tests/test_agent_reliability.py::test_responses_agent_synthesizes_after_max_iterations -v
```

Expected: PASS

- [ ] **Step 5: Run full backend test suite**

```bash
python -m pytest tests/ -v --tb=short
```

Expected: all existing tests pass.

- [ ] **Step 6: Commit**

```bash
git add app/services/agent.py tests/test_agent_reliability.py
git commit -m "fix(B-N2): force synthesis turn after max iterations in Responses API agent path"
```

---

### Task 3: N2 — Fix hasDocuments guard (null treated as no-docs)

**Files:**
- Modify: `frontend/app/components/ChatPage.tsx` (line ~451, `handleCardClick`)
- Test: `frontend/__tests__/ChatPage.test.tsx`

- [ ] **Step 1: Write the failing test**

Add to `frontend/__tests__/ChatPage.test.tsx`:

```typescript
it("shows in-chat guidance for 'Search my documents' when hasDocuments is null (still loading)", async () => {
  const fetchSpy = vi.spyOn(globalThis, "fetch");
  // Slot 1: models
  fetchSpy.mockResolvedValueOnce(
    new Response(JSON.stringify([{ id: "gpt-5-nano", label: "GPT-5 nano" }]), { status: 200 }),
  );
  // Slot 2: conversations
  fetchSpy.mockResolvedValueOnce(new Response(JSON.stringify([]), { status: 200 }));
  // Slot 3: documents check — never resolves (simulates hasDocuments still null)
  fetchSpy.mockReturnValueOnce(new Promise(() => {}));

  render(<ChatPage />);
  await waitFor(() => screen.getByText("Search my documents"));

  await userEvent.click(screen.getByText("Search my documents"));

  await waitFor(() =>
    expect(
      screen.getByText(/haven't uploaded any documents/i),
    ).toBeInTheDocument(),
  );
  cleanup();
});
```

- [ ] **Step 2: Run to verify it fails**

```bash
cd frontend && npx vitest run __tests__/ChatPage.test.tsx 2>&1 | tail -20
```

Expected: FAIL — card click submits the prompt instead of showing guidance.

- [ ] **Step 3: Implement**

In `frontend/app/components/ChatPage.tsx`, find `handleCardClick`:

```typescript
// BEFORE:
if (label === "Search my documents" && hasDocuments === false) {
```

Change to:

```typescript
// AFTER — null (still loading) and false (confirmed empty) both show guidance:
if (label === "Search my documents" && hasDocuments !== true) {
```

- [ ] **Step 4: Run test to verify it passes**

```bash
cd frontend && npx vitest run __tests__/ChatPage.test.tsx 2>&1 | tail -20
```

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add frontend/app/components/ChatPage.tsx frontend/__tests__/ChatPage.test.tsx
git commit -m "fix(N2): show document guidance when hasDocuments is null or false"
```

---

### Task 4: B-N3 — Clear prefill value on new conversation

**Files:**
- Modify: `frontend/app/components/ChatPage.tsx` (`startNewConversation`)
- Test: `frontend/__tests__/ChatPage.test.tsx`

- [ ] **Step 1: Write the failing test**

Add to `frontend/__tests__/ChatPage.test.tsx`:

```typescript
it("clears prefill value when starting a new conversation", async () => {
  const fetchSpy = vi.spyOn(globalThis, "fetch");
  fetchSpy.mockResolvedValueOnce(
    new Response(JSON.stringify([{ id: "gpt-5-nano", label: "GPT-5 nano" }]), { status: 200 }),
  );
  fetchSpy.mockResolvedValueOnce(new Response(JSON.stringify([]), { status: 200 }));
  fetchSpy.mockResolvedValueOnce(new Response(JSON.stringify([]), { status: 200 })); // documents

  render(<ChatPage />);
  await waitFor(() => screen.getByText("Read a URL"));

  // Click the prefill card
  await userEvent.click(screen.getByText("Read a URL"));

  // Composer should have prefill text
  const textarea = screen.getByRole("textbox");
  expect(textarea).toHaveValue(expect.stringContaining("Read [paste URL here]"));

  // Click new conversation
  await userEvent.click(screen.getByText("New conversation"));

  // Prefill should be cleared
  expect(textarea).toHaveValue("");
  cleanup();
});
```

- [ ] **Step 2: Run to verify it fails**

```bash
cd frontend && npx vitest run __tests__/ChatPage.test.tsx 2>&1 | tail -20
```

Expected: FAIL — prefill persists after new conversation.

- [ ] **Step 3: Implement**

In `frontend/app/components/ChatPage.tsx`, find `startNewConversation`:

```typescript
// BEFORE:
const startNewConversation = () => {
  setMessages([{ role: "assistant", content: WELCOME_MESSAGE }]);
  setConversationId(null);
  hasWelcomed.current = true;
};
```

```typescript
// AFTER:
const startNewConversation = () => {
  setMessages([{ role: "assistant", content: WELCOME_MESSAGE }]);
  setConversationId(null);
  setPrefillValue("");
  hasWelcomed.current = true;
};
```

- [ ] **Step 4: Run test to verify it passes**

```bash
cd frontend && npx vitest run __tests__/ChatPage.test.tsx 2>&1 | tail -20
```

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add frontend/app/components/ChatPage.tsx frontend/__tests__/ChatPage.test.tsx
git commit -m "fix(B-N3): clear composer prefill when starting new conversation"
```

---

### Task 5: B-N4 — Fix guest banner dark mode theming

**Files:**
- Modify: `frontend/app/components/ChatPage.tsx` (guest banner style, line ~552)

- [ ] **Step 1: Find the banner**

The banner currently reads:

```tsx
<div className="text-center text-sm py-2 px-4" style={{ background: "var(--bg-subtle, #f0f9ff)", color: "var(--text-secondary, #555)" }}>
```

The `#f0f9ff` (light blue) and `#555` (dark grey) hardcoded fallbacks don't respect dark mode.

- [ ] **Step 2: Implement**

Replace the style with theme variables that have dark-mode-aware fallbacks:

```tsx
<div className="text-center text-sm py-2 px-4" style={{ background: "var(--bg-elevated)", color: "var(--text-muted)" }}>
```

- [ ] **Step 3: Verify visually**

Run the dev server (`cd frontend && npm run dev`) and toggle dark mode. The banner should match the surrounding dark background.

- [ ] **Step 4: Commit**

```bash
git add frontend/app/components/ChatPage.tsx
git commit -m "fix(B-N4): use theme variables on guest session banner for dark mode"
```

---

### Task 6: 6.1 — Redirect guests away from /settings

**Files:**
- Modify: `frontend/app/settings/page.tsx`
- Test: `frontend/__tests__/SettingsPage.test.tsx`

- [ ] **Step 1: Write the failing test**

Open `frontend/__tests__/SettingsPage.test.tsx` and add:

```typescript
it("redirects guest users to / instead of rendering settings", async () => {
  // Mock useAuth to simulate a loaded, unauthenticated session
  vi.mocked(useAuth).mockReturnValue({
    isLoaded: true,
    isSignedIn: false,
    getToken: vi.fn(),
  } as any);

  const pushMock = vi.fn();
  vi.mocked(useRouter).mockReturnValue({ push: pushMock } as any);

  render(<SettingsPage />);

  await waitFor(() => expect(pushMock).toHaveBeenCalledWith("/"));
});
```

Check the existing mock setup in SettingsPage.test.tsx to match the import style already in use.

- [ ] **Step 2: Run to verify it fails**

```bash
cd frontend && npx vitest run __tests__/SettingsPage.test.tsx 2>&1 | tail -20
```

Expected: FAIL — no redirect occurs.

- [ ] **Step 3: Implement**

In `frontend/app/settings/page.tsx`, add router import and redirect effect:

```typescript
// Add to existing imports:
import { useRouter } from "next/navigation";

// Add isSignedIn to the existing useAuth destructure:
const { isLoaded, isSignedIn } = useAuth();
const router = useRouter();

// Add after the existing useAuth line, before any other useEffect:
useEffect(() => {
  if (isLoaded && !isSignedIn) {
    router.push("/");
  }
}, [isLoaded, isSignedIn, router]);
```

- [ ] **Step 4: Run test to verify it passes**

```bash
cd frontend && npx vitest run __tests__/SettingsPage.test.tsx 2>&1 | tail -20
```

Expected: PASS

- [ ] **Step 5: Run full frontend test suite**

```bash
cd frontend && npx vitest run 2>&1 | tail -20
```

Expected: all tests pass.

- [ ] **Step 6: Commit**

```bash
git add frontend/app/settings/page.tsx frontend/__tests__/SettingsPage.test.tsx
git commit -m "fix(6.1): redirect unauthenticated users away from /settings"
```

---

### Task 7: 1.1 — Fix hero "View source" link to point to profile

**Files:**
- Modify: `frontend/app/components/LandingPage.tsx`

- [ ] **Step 1: Find the link**

```bash
grep -n "github\|View source" frontend/app/components/LandingPage.tsx
```

- [ ] **Step 2: Implement**

Find the hero section `<a>` tag with "View source" text. Change its `href` from the repo URL to the profile URL:

```tsx
// BEFORE (exact URL may differ):
href="https://github.com/RogerFlores3113/podium"

// AFTER:
href="https://github.com/RogerFlores3113"
```

- [ ] **Step 3: Verify footer link is still correct**

```bash
grep -n "github" frontend/app/components/LandingPage.tsx
```

Confirm the footer link (fixed in N4) still points to the profile. There should be no repo URL remaining in the file.

- [ ] **Step 4: Commit**

```bash
git add frontend/app/components/LandingPage.tsx
git commit -m "fix(1.1): point hero 'View source' link to GitHub profile not repo"
```

---

### Task 8: Final verification

- [ ] **Step 1: Run all backend tests**

```bash
cd /home/rflor/podium && python -m pytest tests/ -v --tb=short 2>&1 | tail -30
```

Expected: all pass.

- [ ] **Step 2: Run all frontend tests**

```bash
cd frontend && npx vitest run 2>&1 | tail -30
```

Expected: all pass.

- [ ] **Step 3: Open a PR**

Target branch: `main`. Title: `fix: UAT Round 2 — Sprint 1+2 bug fixes`. Body should reference B-N1 diagnosis result, B-N2, N2, B-N3, B-N4, 6.1, 1.1.
