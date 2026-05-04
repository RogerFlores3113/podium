import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, waitFor, cleanup } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

// Stable getToken reference — must not be re-created on each useAuth() call
// or authFetch's useCallback dep changes on every render, causing ∞ fetchConversations loop
const stableGetToken = vi.fn().mockResolvedValue("test-token");
vi.mock("@clerk/nextjs", () => ({
  useAuth: () => ({
    getToken: stableGetToken,
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

describe("ChatPage sidebar delete", () => {
  let fetchSpy: ReturnType<typeof vi.spyOn>;

  beforeEach(() => {
    fetchSpy = vi.spyOn(globalThis, "fetch");
  });

  afterEach(() => {
    vi.restoreAllMocks();
    vi.unstubAllGlobals();
    cleanup();
  });

  it("× button is hidden when row is not hovered", async () => {
    mockConversationList(fetchSpy);

    render(<ChatPage />);

    await waitFor(() => screen.getByText("First chat"));

    // The × button (with title="Delete conversation") should NOT be visible
    // before hovering — it does not exist in the DOM yet (Wave 2 adds it)
    expect(document.querySelector('[title="Delete conversation"]')).toBeNull();
  });

  it("× button appears on hover and disappears on leave", async () => {
    const user = userEvent.setup();
    mockConversationList(fetchSpy);

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
    expect(document.querySelector('[title="Delete conversation"]')).toBeNull();
  });

  it("clicking × shows confirm; cancel is a no-op", async () => {
    const user = userEvent.setup();
    mockConversationList(fetchSpy);

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
    mockConversationList(fetchSpy);

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
      ([url, opts]) =>
        typeof url === "string" &&
        url.endsWith(`/chat/c1`) &&
        opts?.method === "DELETE"
    );
    expect(deleteCalls.length).toBeGreaterThan(0);
  });

  it("clicking × on the active conversation calls startNewConversation", async () => {
    const user = userEvent.setup();
    mockConversationList(fetchSpy);

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
    mockConversationList(fetchSpy);

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
      ([url]) =>
        typeof url === "string" && url.match(/\/chat\/c2$/) && !newCalls.find(([, opts]) => opts?.method === "DELETE")
    );
    expect(loadCalls.length).toBe(0);
  });
});
