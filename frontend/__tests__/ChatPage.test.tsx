import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, waitFor, cleanup, fireEvent } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

// Stable getToken reference — must not be re-created on each useAuth() call
// or authFetch's useCallback dep changes on every render, causing ∞ fetchConversations loop
const stableGetToken = vi.fn().mockResolvedValue("test-token");
let mockIsSignedIn: boolean | undefined = undefined;
vi.mock("@clerk/nextjs", () => ({
  useAuth: () => ({
    getToken: stableGetToken,
    isSignedIn: mockIsSignedIn,
  }),
  UserButton: () => <div data-testid="user-button" />,
}));

vi.mock("react-markdown", () => ({
  default: ({ children }: { children: string }) => <span>{children}</span>,
}));

vi.mock("remark-gfm", () => ({
  default: () => null,
}));

vi.mock("@/app/utils/time", () => ({
  formatRelativeTime: () => "just now",
}));

import ChatPage from "@/app/components/ChatPage";

// jsdom does not implement scrollIntoView — stub it so ChatPage renders without errors
window.HTMLElement.prototype.scrollIntoView = vi.fn();

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

const CONV_1 = { id: "c1", title: "First chat", created_at: "2025-01-01T00:00:00Z" };
const CONV_2 = { id: "c2", title: "Second chat", created_at: "2025-01-01T00:00:00Z" };

function mockConversationList(
  fetchSpy: ReturnType<typeof vi.spyOn>,
  convs: unknown[] = [CONV_1, CONV_2]
) {
  fetchSpy.mockResolvedValueOnce(
    new Response(JSON.stringify(convs), { status: 200 })
  );
}

/**
 * Mocks all 3 on-mount fetches so the chat/stream call can receive its own mock.
 * Phase 5 added dynamic model fetching: /chat/models (unauthenticated) fires first,
 * then /chat/ (conversations) and /chat/ollama-models (via authFetch) follow.
 * Tests that submit a message need a 4th mock slot for the chat/stream response.
 */
function mockMountFetches(
  fetchSpy: ReturnType<typeof vi.spyOn>,
  convs: unknown[] = [CONV_1, CONV_2],
) {
  // Slot 1: /chat/models (unauthenticated fetch, fires first in useEffect)
  fetchSpy.mockResolvedValueOnce(
    new Response(JSON.stringify([{ id: "gpt-5-nano", label: "GPT-5 nano · fast" }]), { status: 200 }),
  );
  // Slot 2: /chat/ conversations (authFetch, fires after one getToken microtask)
  fetchSpy.mockResolvedValueOnce(
    new Response(JSON.stringify(convs), { status: 200 }),
  );
  // Slot 3: /chat/ollama-models (authFetch, fires after /chat/models resolves)
  fetchSpy.mockResolvedValueOnce(
    new Response(JSON.stringify([]), { status: 200 }),
  );
}

function makeSSEResponse(
  events: Array<{ event: string; data: object }>,
  status = 200,
): Response {
  const body =
    events
      .map((e) => `event: ${e.event}\ndata: ${JSON.stringify(e.data)}`)
      .join("\n\n") + "\n\n";
  return new Response(body, {
    status,
    headers: { "Content-Type": "text/event-stream" },
  });
}

function streamingResponse(
  headEvents: Array<{ event: string; data: object }>,
  { close = true }: { close?: boolean } = {},
): Response {
  const body =
    headEvents
      .map((e) => `event: ${e.event}\ndata: ${JSON.stringify(e.data)}`)
      .join("\n\n") + "\n\n";
  const stream = new ReadableStream({
    start(controller) {
      controller.enqueue(new TextEncoder().encode(body));
      if (close) controller.close();
      // else leave open — caller must clean up via vi.restoreAllMocks()
    },
  });
  return new Response(stream, {
    status: 200,
    headers: { "Content-Type": "text/event-stream" },
  });
}

describe("ChatPage sidebar delete", () => {
  let fetchSpy: ReturnType<typeof vi.spyOn>;

  beforeEach(() => {
    mockIsSignedIn = undefined;
    fetchSpy = vi.spyOn(globalThis, "fetch");
  });

  afterEach(() => {
    vi.restoreAllMocks();
    vi.unstubAllGlobals();
    cleanup();
  });

  it("× button is hidden when row is not hovered", async () => {
    mockMountFetches(fetchSpy);

    render(<ChatPage />);

    await waitFor(() => screen.getByText("First chat"));

    // The × button (with title="Delete conversation") should NOT be visible
    // before hovering — it does not exist in the DOM yet (Wave 2 adds it)
    expect(document.querySelector('[title="Delete conversation"]')).toBeNull();
  });

  it("× button appears on hover and disappears on leave", async () => {
    const user = userEvent.setup();
    mockMountFetches(fetchSpy);

    render(<ChatPage />);

    await waitFor(() => screen.getByText("First chat"));

    // Hover the conversation row — in Wave 2 this sets hoveredConvId
    // Today this fails because there is no element with title="Delete conversation"
    // Row is <div role="button"> after restructure (fixes nested-button HTML invalidity)
    const row = screen.getByText("First chat").closest('[role="button"], button') as HTMLElement;
    await user.hover(row);

    // Fails today: no × button rendered — RED assertion
    expect(screen.getByTitle("Delete conversation")).toBeTruthy();

    await user.unhover(row);
    // ChatPage.tsx debounces hover-hide via setTimeout(0) on mouseleave so that
    // mouseenter on the child × button can cancel the hide (prevents flicker when
    // jsdom/userEvent fires mouseleave on the parent row when the pointer enters
    // the child button). We must wait for that deferred state update + re-render
    // before asserting the button is gone — a synchronous assertion races the timer.
    await waitFor(() =>
      expect(screen.queryByTitle("Delete conversation")).toBeNull()
    );
  });

  it("clicking × shows confirm; cancel is a no-op", async () => {
    const user = userEvent.setup();
    mockMountFetches(fetchSpy);

    const confirmMock = vi.fn(() => false);
    vi.stubGlobal("confirm", confirmMock);

    render(<ChatPage />);

    await waitFor(() => screen.getByText("First chat"));

    const row = screen.getByText("First chat").closest('[role="button"], button') as HTMLElement;
    await user.hover(row);

    // Fails today: no × button — RED
    // Hover the × button explicitly so hover state is set on the button itself
    // (jsdom fires mouseleave on outer div when pointer moves to child — needs re-entry)
    await user.hover(screen.getByTitle("Delete conversation"));
    const deleteBtn = screen.getByTitle("Delete conversation"); // fresh ref after re-render
    await user.click(deleteBtn);

    expect(confirmMock).toHaveBeenCalledOnce();
    expect(confirmMock).toHaveBeenCalledWith(
      "Delete this conversation? This cannot be undone."
    );

    // Record fetch count before — confirm returns false so no DELETE should fire
    const fetchCallsBefore = fetchSpy.mock.calls.length;
    // Give a tick for any async side effects
    await new Promise((r) => setTimeout(r, 10));
    expect(fetchSpy.mock.calls.length).toBe(fetchCallsBefore);
  });

  it("clicking × → confirm OK → DELETE /chat/{id} → row removed from sidebar", async () => {
    const user = userEvent.setup();
    mockMountFetches(fetchSpy);

    const confirmMock = vi.fn(() => true);
    vi.stubGlobal("confirm", confirmMock);

    render(<ChatPage />);

    await waitFor(() => screen.getByText("First chat"));

    // Mock the DELETE response
    fetchSpy.mockResolvedValueOnce(
      new Response(JSON.stringify({ detail: "Conversation deleted" }), {
        status: 200,
      })
    );

    const row = screen.getByText("First chat").closest('[role="button"], button') as HTMLElement;
    await user.hover(row);

    // Fails today: no × button — RED
    await user.hover(screen.getByTitle("Delete conversation"));
    const deleteBtn = screen.getByTitle("Delete conversation"); // fresh ref after re-render
    await user.click(deleteBtn);

    // Wait for the row to leave the DOM
    await waitFor(() =>
      expect(screen.queryByText("First chat")).toBeNull()
    );

    // Verify DELETE was called with the correct URL and method
    const deleteCalls = fetchSpy.mock.calls.filter(
      ([url, opts]: [unknown, RequestInit | undefined]) =>
        typeof url === "string" &&
        url.endsWith(`/chat/c1`) &&
        opts?.method === "DELETE"
    );
    expect(deleteCalls.length).toBeGreaterThan(0);
  });

  it("clicking × on the active conversation calls startNewConversation", async () => {
    const user = userEvent.setup();
    mockMountFetches(fetchSpy);

    const confirmMock = vi.fn(() => true);
    vi.stubGlobal("confirm", confirmMock);

    render(<ChatPage />);

    await waitFor(() => screen.getByText("First chat"));

    // First, load conversation c1 to make it the active conversation
    fetchSpy.mockResolvedValueOnce(
      new Response(
        JSON.stringify({
          id: "c1",
          messages: [
            { role: "user", content: "Hello" },
            { role: "assistant", content: "Hi there" },
          ],
        }),
        { status: 200 }
      )
    );

    // Activate c1 by clicking the row
    const row = screen.getByText("First chat");
    await user.click(row);

    // Wait for messages to load
    await waitFor(() => screen.getByText("Hello"));

    // Now mock the DELETE for c1
    fetchSpy.mockResolvedValueOnce(
      new Response(JSON.stringify({ detail: "Conversation deleted" }), {
        status: 200,
      })
    );

    // Reload conversation list after delete
    fetchSpy.mockResolvedValueOnce(
      new Response(JSON.stringify([CONV_2]), { status: 200 })
    );

    const convRow = screen.getByText("First chat").closest('[role="button"], button') as HTMLElement;
    await user.hover(convRow);

    // Fails today: no × button — RED
    await user.hover(screen.getByTitle("Delete conversation"));
    const deleteBtn = screen.getByTitle("Delete conversation"); // fresh ref after re-render
    await user.click(deleteBtn);

    // After deleting the active conversation, startNewConversation resets state
    // The chat area should show no user messages (welcome message only)
    await waitFor(() =>
      expect(screen.queryByText("Hello")).toBeNull()
    );
  });

  it("clicking × propagation does NOT trigger loadConversation", async () => {
    const user = userEvent.setup();
    mockMountFetches(fetchSpy);

    const confirmMock = vi.fn(() => false);
    vi.stubGlobal("confirm", confirmMock);

    render(<ChatPage />);

    await waitFor(() => screen.getByText("Second chat"));

    // Record fetch calls before hovering/clicking
    const fetchCallsBefore = fetchSpy.mock.calls.length;

    const row = screen.getByText("Second chat").closest('[role="button"], button') as HTMLElement;
    await user.hover(row);

    // Fails today: no × button — RED
    await user.hover(screen.getByTitle("Delete conversation"));
    const deleteBtn = screen.getByTitle("Delete conversation"); // fresh ref after re-render
    await user.click(deleteBtn);

    // e.stopPropagation() prevents loadConversation — no GET to /chat/c2
    await new Promise((r) => setTimeout(r, 20));

    const newCalls = fetchSpy.mock.calls.slice(fetchCallsBefore);
    const loadCalls = newCalls.filter(
      ([url]: [unknown, RequestInit | undefined]) =>
        typeof url === "string" && url.match(/\/chat\/c2$/) && !newCalls.find(([, opts]: [unknown, RequestInit | undefined]) => opts?.method === "DELETE")
    );
    expect(loadCalls.length).toBe(0);
  });
});

describe("ChatPage thinking indicator", () => {
  let fetchSpy: ReturnType<typeof vi.spyOn>;

  beforeEach(() => {
    mockIsSignedIn = undefined;
    fetchSpy = vi.spyOn(globalThis, "fetch");
  });

  afterEach(() => {
    vi.restoreAllMocks();
    vi.unstubAllGlobals();
    cleanup();
  });

  it("shows thinking indicator immediately after submit, before any SSE event lands", async () => {
    const user = userEvent.setup();
    mockMountFetches(fetchSpy, []);

    // /chat/stream returns a stream that never emits — locks open
    fetchSpy.mockResolvedValueOnce(
      new Response(
        new ReadableStream({
          start() {
            /* never enqueue, never close */
          },
        }),
        { status: 200, headers: { "Content-Type": "text/event-stream" } },
      ),
    );

    render(<ChatPage />);

    const composer = await screen.findByPlaceholderText(/Ask me anything/i);
    await user.click(composer);
    await user.keyboard("Hello");

    // Submit the form (works for input or textarea)
    const form = composer.closest("form") as HTMLFormElement;
    fireEvent.submit(form);

    expect(await screen.findByTestId("thinking-indicator")).toBeTruthy();
  });

  it("hides thinking indicator on first token event", async () => {
    const user = userEvent.setup();
    mockMountFetches(fetchSpy, []);

    // Stream stays open after one token so indicator presence can be observed
    // pre-event and the indicator-cleared assertion lands once Wave 2 ships.
    fetchSpy.mockResolvedValueOnce(
      streamingResponse(
        [
          { event: "conversation", data: { conversation_id: "c-new" } },
          { event: "token", data: { token: "Hi" } },
        ],
        { close: false },
      ),
    );

    render(<ChatPage />);

    const composer = await screen.findByPlaceholderText(/Ask me anything/i);
    await user.click(composer);
    await user.keyboard("Hello");
    const form = composer.closest("form") as HTMLFormElement;
    fireEvent.submit(form);

    // Today: no indicator ever exists — this assertion fails (RED).
    // Wave 2: indicator briefly exists before the token branch clears it.
    await screen.findByTestId("thinking-indicator");
    await waitFor(() =>
      expect(screen.queryByTestId("thinking-indicator")).toBeNull(),
    );
  });

  it("hides thinking indicator on first tool_call_start event (tool-first flow)", async () => {
    const user = userEvent.setup();
    mockMountFetches(fetchSpy, []);

    fetchSpy.mockResolvedValueOnce(
      streamingResponse(
        [
          { event: "conversation", data: { conversation_id: "c-new" } },
          {
            event: "tool_call_start",
            data: { id: "t1", name: "web_search", arguments: {} },
          },
        ],
        { close: false },
      ),
    );

    render(<ChatPage />);

    const composer = await screen.findByPlaceholderText(/Ask me anything/i);
    await user.click(composer);
    await user.keyboard("Hello");
    const form = composer.closest("form") as HTMLFormElement;
    fireEvent.submit(form);

    // Today: no indicator ever exists — fails (RED).
    // Wave 2: indicator briefly exists then tool_call_start clears it.
    await screen.findByTestId("thinking-indicator");
    await waitFor(() =>
      expect(screen.queryByTestId("thinking-indicator")).toBeNull(),
    );
  });
});

describe("ChatPage tool phase copy", () => {
  let fetchSpy: ReturnType<typeof vi.spyOn>;

  beforeEach(() => {
    mockIsSignedIn = undefined;
    fetchSpy = vi.spyOn(globalThis, "fetch");
  });

  afterEach(() => {
    vi.restoreAllMocks();
    vi.unstubAllGlobals();
    cleanup();
  });

  it("renders 'Searching the web…' while web_search is running", async () => {
    const user = userEvent.setup();
    mockMountFetches(fetchSpy, []);

    // Stream emits start but no result — leave open so the running state persists
    fetchSpy.mockResolvedValueOnce(
      streamingResponse(
        [
          { event: "conversation", data: { conversation_id: "c-new" } },
          {
            event: "tool_call_start",
            data: { id: "t1", name: "web_search", arguments: {} },
          },
        ],
        { close: false },
      ),
    );

    render(<ChatPage />);

    const composer = await screen.findByPlaceholderText(/Ask me anything/i);
    await user.click(composer);
    await user.keyboard("Hello");
    const form = composer.closest("form") as HTMLFormElement;
    fireEvent.submit(form);

    expect(await screen.findByText(/Searching the web…/i)).toBeTruthy();
  });

  it("removes the tool phase copy once tool_call_result lands", async () => {
    const user = userEvent.setup();
    mockMountFetches(fetchSpy, []);

    // Open stream — emit start (running), then result (done), then close.
    fetchSpy.mockResolvedValueOnce(
      streamingResponse(
        [
          { event: "conversation", data: { conversation_id: "c-new" } },
          {
            event: "tool_call_start",
            data: { id: "t1", name: "web_search", arguments: {} },
          },
          { event: "tool_call_result", data: { id: "t1", result: "ok" } },
          { event: "done", data: { conversation_id: "c-new" } },
        ],
        { close: true },
      ),
    );

    render(<ChatPage />);

    const composer = await screen.findByPlaceholderText(/Ask me anything/i);
    await user.click(composer);
    await user.keyboard("Hello");
    const form = composer.closest("form") as HTMLFormElement;
    fireEvent.submit(form);

    // Today: phase copy is never rendered — this assertion fails (RED).
    // Wave 2: copy renders briefly while running, then disappears on result.
    // Note: with all events queued at once we can't reliably observe the
    // running state, so this test asserts the copy was visible at any point
    // by checking the "stably absent" condition AFTER drain. To make it
    // RED today, we first assert presence at any point during the stream.
    await waitFor(() => {
      // At some point during the stream the copy must have rendered.
      // Use the test's own fetchSpy timing: if Wave 2 is wired, the start
      // event flips status to "running" and the copy is present synchronously
      // with that state update.
      expect(screen.queryByText(/Searching the web…/i)).toBeTruthy();
    });
    await waitFor(() =>
      expect(screen.queryByText(/Searching the web…/i)).toBeNull(),
    );
  });
});

describe("ChatPage SSE error event", () => {
  let fetchSpy: ReturnType<typeof vi.spyOn>;

  beforeEach(() => {
    mockIsSignedIn = undefined;
    fetchSpy = vi.spyOn(globalThis, "fetch");
  });

  afterEach(() => {
    vi.restoreAllMocks();
    vi.unstubAllGlobals();
    cleanup();
  });

  it("renders an error bubble when backend emits event: error", async () => {
    const user = userEvent.setup();
    mockMountFetches(fetchSpy, []);

    fetchSpy.mockResolvedValueOnce(
      makeSSEResponse([
        { event: "conversation", data: { conversation_id: "c-new" } },
        { event: "error", data: { detail: "Tavily search unavailable" } },
      ]),
    );

    render(<ChatPage />);

    const composer = await screen.findByPlaceholderText(/Ask me anything/i);
    await user.click(composer);
    await user.keyboard("Hello");
    const form = composer.closest("form") as HTMLFormElement;
    fireEvent.submit(form);

    const bubble = await screen.findByTestId("error-bubble");
    expect(bubble.textContent || "").toContain("Tavily search unavailable");
  });

  it("preserves partial assistant content when error arrives after tokens", async () => {
    const user = userEvent.setup();
    mockMountFetches(fetchSpy, []);

    fetchSpy.mockResolvedValueOnce(
      makeSSEResponse([
        { event: "conversation", data: { conversation_id: "c-new" } },
        { event: "token", data: { token: "Based on the search resul" } },
        { event: "error", data: { detail: "Stream interrupted" } },
      ]),
    );

    render(<ChatPage />);

    const composer = await screen.findByPlaceholderText(/Ask me anything/i);
    await user.click(composer);
    await user.keyboard("Hello");
    const form = composer.closest("form") as HTMLFormElement;
    fireEvent.submit(form);

    const bubble = await screen.findByTestId("error-bubble");
    expect(bubble.textContent || "").toContain("Stream interrupted");
    // Partial assistant content must remain visible
    expect(screen.getByText(/Based on the search resul/)).toBeTruthy();
  });
});

describe("ChatPage HTTP error responses", () => {
  let fetchSpy: ReturnType<typeof vi.spyOn>;

  beforeEach(() => {
    mockIsSignedIn = undefined;
    fetchSpy = vi.spyOn(globalThis, "fetch");
  });

  afterEach(() => {
    vi.restoreAllMocks();
    vi.unstubAllGlobals();
    cleanup();
  });

  it("renders BYOK error bubble on HTTP 402", async () => {
    const user = userEvent.setup();
    mockMountFetches(fetchSpy, []);

    fetchSpy.mockResolvedValueOnce(
      new Response(
        JSON.stringify({ detail: { code: "byok_required" } }),
        { status: 402, headers: { "Content-Type": "application/json" } },
      ),
    );

    render(<ChatPage />);

    const composer = await screen.findByPlaceholderText(/Ask me anything/i);
    await user.click(composer);
    await user.keyboard("hi");
    const form = composer.closest("form") as HTMLFormElement;
    fireEvent.submit(form);

    const bubble = await screen.findByTestId("error-bubble");
    expect(bubble.textContent || "").toMatch(/key/i);
  });

  it("renders guest-limit error bubble on HTTP 429 using backend message when present", async () => {
    const user = userEvent.setup();
    mockMountFetches(fetchSpy, []);

    fetchSpy.mockResolvedValueOnce(
      new Response(
        JSON.stringify({
          detail: {
            code: "guest_limit_reached",
            message: "You hit the cap of 5 messages.",
          },
        }),
        { status: 429, headers: { "Content-Type": "application/json" } },
      ),
    );

    render(<ChatPage />);

    const composer = await screen.findByPlaceholderText(/Ask me anything/i);
    await user.click(composer);
    await user.keyboard("hi");
    const form = composer.closest("form") as HTMLFormElement;
    fireEvent.submit(form);

    const bubble = await screen.findByTestId("error-bubble");
    expect(bubble.textContent || "").toMatch(/cap of 5 messages/);
  });

  it("renders generic server error bubble on HTTP 500", async () => {
    const user = userEvent.setup();
    mockMountFetches(fetchSpy, []);

    // Note: NOT JSON — exercises the path where backend returns plain text.
    fetchSpy.mockResolvedValueOnce(
      new Response("Internal Server Error", { status: 500 }),
    );

    render(<ChatPage />);

    const composer = await screen.findByPlaceholderText(/Ask me anything/i);
    await user.click(composer);
    await user.keyboard("hi");
    const form = composer.closest("form") as HTMLFormElement;
    fireEvent.submit(form);

    const bubble = await screen.findByTestId("error-bubble");
    expect(bubble.textContent || "").toMatch(/something went wrong|server/i);
  });
});

describe("ChatPage multi-line composer", () => {
  let fetchSpy: ReturnType<typeof vi.spyOn>;

  beforeEach(() => {
    mockIsSignedIn = undefined;
    fetchSpy = vi.spyOn(globalThis, "fetch");
  });

  afterEach(() => {
    vi.restoreAllMocks();
    vi.unstubAllGlobals();
    cleanup();
  });

  it("Enter submits the message", async () => {
    const user = userEvent.setup();
    mockMountFetches(fetchSpy, []);

    fetchSpy.mockResolvedValueOnce(
      makeSSEResponse([
        { event: "conversation", data: { conversation_id: "c1" } },
        { event: "token", data: { token: "ok" } },
        { event: "done", data: { conversation_id: "c1" } },
      ]),
    );

    render(<ChatPage />);

    const composer = await screen.findByPlaceholderText(/Ask me anything/i);
    await user.click(composer);
    await user.keyboard("Hello");
    await user.keyboard("{Enter}");

    await waitFor(() => {
      const submitCalls = fetchSpy.mock.calls.filter(([url]: [unknown]) =>
        String(url).includes("/chat/stream"),
      );
      expect(submitCalls.length).toBeGreaterThan(0);
    });
  });

  it("Shift+Enter inserts newline and does NOT submit", async () => {
    const user = userEvent.setup();
    mockMountFetches(fetchSpy, []);

    render(<ChatPage />);

    const composer = (await screen.findByPlaceholderText(
      /Ask me anything/i,
    )) as HTMLTextAreaElement;
    await user.click(composer);
    await user.keyboard("Line 1");
    await user.keyboard("{Shift>}{Enter}{/Shift}");
    await user.keyboard("Line 2");

    // Today: composer is <input type="text"> — \n is silently dropped.
    // Wave 2: composer is <textarea> — value preserves the newline.
    expect(composer.value).toBe("Line 1\nLine 2");

    const submitCalls = fetchSpy.mock.calls.filter(([url]: [unknown]) =>
      String(url).includes("/chat/stream"),
    );
    expect(submitCalls.length).toBe(0);
  });

  it("Enter during IME composition does NOT submit", async () => {
    mockMountFetches(fetchSpy, []);

    render(<ChatPage />);

    const composer = await screen.findByPlaceholderText(/Ask me anything/i);
    // fireEvent.keyDown lets us pass isComposing on the synthetic event;
    // userEvent does not expose this flag.
    fireEvent.keyDown(composer, {
      key: "Enter",
      code: "Enter",
      isComposing: true,
    });

    await new Promise((r) => setTimeout(r, 20));

    const submitCalls = fetchSpy.mock.calls.filter(([url]: [unknown]) =>
      String(url).includes("/chat/stream"),
    );
    expect(submitCalls.length).toBe(0);
    // Today: <input type="text"> has no onKeyDown for Enter and no submit
    // wiring through keyDown either, so this passes vacuously. Wave 2 ships
    // the textarea + IME guard; this test prevents regression.
    // To make it RED today, we additionally require the composer be a textarea.
    expect(composer.tagName.toLowerCase()).toBe("textarea");
  });
});

describe("ChatPage upload poll cap", () => {
  let fetchSpy: ReturnType<typeof vi.spyOn>;

  beforeEach(() => {
    mockIsSignedIn = undefined;
    fetchSpy = vi.spyOn(globalThis, "fetch");
  });

  afterEach(() => {
    vi.useRealTimers();
    vi.restoreAllMocks();
    vi.unstubAllGlobals();
    cleanup();
  });

  it("stops polling after MAX_POLL_ATTEMPTS", async () => {
    vi.useFakeTimers();
    const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
    mockMountFetches(fetchSpy, []);

    // Upload POST → 200
    fetchSpy.mockResolvedValueOnce(
      new Response(
        JSON.stringify({ id: "d1", filename: "a.pdf" }),
        { status: 200 },
      ),
    );
    // Every poll returns processing
    fetchSpy.mockResolvedValue(
      new Response(
        JSON.stringify({
          id: "d1",
          filename: "a.pdf",
          status: "processing",
        }),
        { status: 200 },
      ),
    );

    render(<ChatPage />);

    // Wait for mount
    await screen.findByPlaceholderText(/Ask me anything/i);

    const fileInput = document.querySelector(
      'input[type="file"]',
    ) as HTMLInputElement;
    expect(fileInput).toBeTruthy();

    await user.upload(
      fileInput,
      new File(["dummy"], "a.pdf", { type: "application/pdf" }),
    );

    // > 60 attempts at 1s each
    await vi.advanceTimersByTimeAsync(70_000);
    const callsAfterCap = fetchSpy.mock.calls.length;
    await vi.advanceTimersByTimeAsync(5_000);
    expect(fetchSpy.mock.calls.length).toBe(callsAfterCap);
  });

  it("stops polling and surfaces a status when fetch rejects", async () => {
    vi.useFakeTimers();
    const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
    mockMountFetches(fetchSpy, []);

    // Upload POST → 200
    fetchSpy.mockResolvedValueOnce(
      new Response(
        JSON.stringify({ id: "d1", filename: "a.pdf" }),
        { status: 200 },
      ),
    );
    // First poll tick rejects
    fetchSpy.mockRejectedValueOnce(new Error("Network down"));

    render(<ChatPage />);

    await screen.findByPlaceholderText(/Ask me anything/i);

    const fileInput = document.querySelector(
      'input[type="file"]',
    ) as HTMLInputElement;

    await user.upload(
      fileInput,
      new File(["dummy"], "a.pdf", { type: "application/pdf" }),
    );

    await vi.advanceTimersByTimeAsync(2_000);

    // Today: rejection bubbles up inside the interval callback unhandled —
    // no user-readable status is set. Wave 2 wraps the callback in try/catch
    // and surfaces a failure status.
    expect(
      screen.queryByText(/upload.*(failed|error)/i),
    ).toBeTruthy();

    const callsAfter = fetchSpy.mock.calls.length;
    await vi.advanceTimersByTimeAsync(10_000);
    expect(fetchSpy.mock.calls.length).toBe(callsAfter);
  });
});

describe("hamburger button", () => {
  let fetchSpy: ReturnType<typeof vi.spyOn>;

  beforeEach(() => {
    mockIsSignedIn = undefined;
    fetchSpy = vi.spyOn(globalThis, "fetch");
  });

  afterEach(() => {
    vi.restoreAllMocks();
    vi.unstubAllGlobals();
    cleanup();
  });

  it("has md:hidden class so it is invisible on desktop", async () => {
    mockMountFetches(fetchSpy);
    render(<ChatPage />);
    await waitFor(() => expect(fetchSpy).toHaveBeenCalled());
    const hamburger = screen.getByTitle("Toggle sidebar");
    expect(hamburger.className).toContain("md:hidden");
  });
});

describe("guest banner reactive cleanup", () => {
  let fetchSpy: ReturnType<typeof vi.spyOn>;

  beforeEach(() => {
    mockIsSignedIn = undefined;
    fetchSpy = vi.spyOn(globalThis, "fetch");
  });

  afterEach(() => {
    vi.restoreAllMocks();
    vi.unstubAllGlobals();
    cleanup();
    sessionStorage.clear();
  });

  it("clears guest state when isSignedIn becomes true", async () => {
    mockIsSignedIn = undefined;
    // Simulate a guest session via sessionStorage
    sessionStorage.setItem("podium_guest_token", "tok");
    sessionStorage.setItem("podium_guest_expires", new Date(Date.now() + 86400000).toISOString());
    mockMountFetches(fetchSpy);
    // Need an extra slot for fetchConversations triggered by isSignedIn effect
    fetchSpy.mockResolvedValueOnce(
      new Response(JSON.stringify([]), { status: 200 }),
    );
    const { rerender } = render(<ChatPage />);
    await waitFor(() => expect(screen.queryByText(/Guest session/)).toBeInTheDocument());

    // Simulate Clerk confirming sign-in
    mockIsSignedIn = true;
    rerender(<ChatPage />);
    await waitFor(() => expect(screen.queryByText(/Guest session/)).not.toBeInTheDocument());
  });
});

describe("capability cards", () => {
  let fetchSpy: ReturnType<typeof vi.spyOn>;

  beforeEach(() => {
    mockIsSignedIn = undefined;
    fetchSpy = vi.spyOn(globalThis, "fetch");
  });

  afterEach(() => {
    vi.restoreAllMocks();
    vi.unstubAllGlobals();
    cleanup();
  });

  it("does not include Generate images card", async () => {
    mockMountFetches(fetchSpy);
    render(<ChatPage />);
    await waitFor(() => expect(fetchSpy).toHaveBeenCalled());
    expect(screen.queryByText("Generate images")).not.toBeInTheDocument();
  });
});

describe("ChatPage BYOK provider-correct copy", () => {
  let fetchSpy: ReturnType<typeof vi.spyOn>;

  beforeEach(() => {
    mockIsSignedIn = undefined;
    fetchSpy = vi.spyOn(globalThis, "fetch");
  });

  afterEach(() => {
    vi.restoreAllMocks();
    vi.unstubAllGlobals();
    cleanup();
  });

  it("shows provider-correct copy from 402 detail.message", async () => {
    mockMountFetches(fetchSpy, []);
    const byokBody = JSON.stringify({
      detail: {
        error: "byok_required",
        message: "Add your Anthropic API key in Settings to chat. Or sign out and try Podium as a guest.",
      },
    });
    fetchSpy.mockResolvedValueOnce(
      new Response(byokBody, { status: 402, headers: { "Content-Type": "application/json" } }),
    );
    render(<ChatPage />);
    await waitFor(() => expect(fetchSpy).toHaveBeenCalled());
    const user = userEvent.setup();
    await user.type(screen.getByRole("textbox"), "hello");
    await user.keyboard("{Enter}");
    await waitFor(() =>
      expect(screen.getByText(/Anthropic API key/)).toBeInTheDocument()
    );
  });
});

describe("synthesis gap indicator", () => {
  let fetchSpy: ReturnType<typeof vi.spyOn>;

  beforeEach(() => {
    mockIsSignedIn = undefined;
    fetchSpy = vi.spyOn(globalThis, "fetch");
  });

  afterEach(() => {
    vi.restoreAllMocks();
    vi.unstubAllGlobals();
    cleanup();
  });

  it("shows thinking indicator after tool_call_result SSE event", async () => {
    mockMountFetches(fetchSpy, []);
    const sseBody = [
      'event: conversation\ndata: {"conversation_id":"c-new"}\n\n',
      'event: tool_call_start\ndata: {"id":"tc1","name":"web_search","arguments":"{}"}\n\n',
      'event: tool_call_result\ndata: {"id":"tc1","result":"done"}\n\n',
    ].join("");
    fetchSpy.mockResolvedValueOnce(
      new Response(sseBody, {
        status: 200,
        headers: { "Content-Type": "text/event-stream" },
      }),
    );
    render(<ChatPage />);
    await waitFor(() => expect(fetchSpy).toHaveBeenCalled());
    const user = userEvent.setup();
    await user.type(screen.getByRole("textbox"), "search this");
    await user.keyboard("{Enter}");
    await waitFor(() =>
      expect(screen.getByTestId("thinking-indicator")).toBeInTheDocument()
    );
  });
});
