import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, waitFor, act } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

vi.mock("@clerk/nextjs", () => ({
  useAuth: () => ({
    getToken: vi.fn().mockResolvedValue("test-token"),
  }),
  UserButton: () => <div data-testid="user-button" />,
}));

import SettingsPage from "@/app/settings/page";

const MEMORY_1 = {
  id: "m1",
  content: "Likes Python",
  category: "fact",
  is_active: true,
  edited_by_user: false,
  created_at: "2025-01-01T00:00:00Z",
  updated_at: "2025-01-01T00:00:00Z",
};

const KEY_1 = {
  id: "k1",
  provider: "openai",
  key_hint: "sk-...abc",
  is_active: true,
  created_at: "2025-01-01T00:00:00Z",
};

/** Returns a Response resolved after `delayMs` milliseconds. */
function delayedResponse(res: Response, delayMs: number): Promise<Response> {
  return new Promise((resolve) => setTimeout(() => resolve(res), delayMs));
}

function mockInitialFetches(
  fetchSpy: ReturnType<typeof vi.spyOn>,
  keys: unknown[] = [],
  memories: unknown[] = []
) {
  fetchSpy
    .mockResolvedValueOnce(
      new Response(JSON.stringify(keys), { status: 200 })
    )
    .mockResolvedValueOnce(
      new Response(JSON.stringify(memories), { status: 200 })
    );
}

describe("SettingsPage", () => {
  let fetchSpy: ReturnType<typeof vi.spyOn>;

  beforeEach(() => {
    fetchSpy = vi.spyOn(globalThis, "fetch");
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("removes memory from list immediately on delete (optimistic)", async () => {
    const user = userEvent.setup();

    // Initial loads: keys=[], memories=[MEMORY_1]
    mockInitialFetches(fetchSpy, [], [MEMORY_1]);

    render(<SettingsPage />);

    // Wait for memory to appear
    await waitFor(() => screen.getByText("Likes Python"));

    // Mock the DELETE as a slow response — proves removal happens optimistically
    fetchSpy.mockReturnValueOnce(
      delayedResponse(new Response(null, { status: 200 }), 50)
    );

    // Click the Delete button within the memory row
    const deleteButtons = screen.getAllByRole("button", { name: /delete/i });
    // The first one is the "Delete all memories" button if visible, but we have only one memory
    // so the pattern is: [Delete (for mem)] — but also "Delete all memories" appears at top
    // We need the button nearest "Likes Python". Use a more specific approach:
    const memoryRow = screen.getByText("Likes Python").closest("div[class]") as HTMLElement;
    // Walk up to find the Delete button in same block
    const deleteBtn = Array.from(document.querySelectorAll("button")).find(
      (btn) => btn.textContent?.toLowerCase() === "delete" && memoryRow?.contains(btn)
    ) ?? deleteButtons[deleteButtons.length - 1];

    await user.click(deleteBtn);

    // "Likes Python" should be gone immediately (before 50ms response resolves)
    expect(screen.queryByText("Likes Python")).toBeNull();
  });

  it("restores list and shows error status on delete failure", async () => {
    const user = userEvent.setup();

    mockInitialFetches(fetchSpy, [], [MEMORY_1]);

    render(<SettingsPage />);

    await waitFor(() => screen.getByText("Likes Python"));

    // DELETE → 500
    fetchSpy.mockResolvedValueOnce(
      new Response(null, { status: 500 })
    );
    // Reload memories on failure → return original list
    fetchSpy.mockResolvedValueOnce(
      new Response(JSON.stringify([MEMORY_1]), { status: 200 })
    );

    const deleteBtn = Array.from(document.querySelectorAll("button")).find(
      (btn) => btn.textContent?.toLowerCase() === "delete"
    )!;

    await user.click(deleteBtn);

    await waitFor(() => screen.getByText("Failed to delete memory"));
    await waitFor(() => screen.getByText("Likes Python"));
  });

  it("memoryStatus auto-clears after 3 seconds", async () => {
    vi.useFakeTimers();
    const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });

    mockInitialFetches(fetchSpy, [], [MEMORY_1]);

    render(<SettingsPage />);

    await waitFor(() => screen.getByText("Likes Python"));

    // Trigger a delete failure so memoryStatus gets set
    fetchSpy.mockResolvedValueOnce(
      new Response(null, { status: 500 })
    );
    // loadMemories on failure
    fetchSpy.mockResolvedValueOnce(
      new Response(JSON.stringify([MEMORY_1]), { status: 200 })
    );

    const deleteBtn = Array.from(document.querySelectorAll("button")).find(
      (btn) => btn.textContent?.toLowerCase() === "delete"
    )!;

    await user.click(deleteBtn);

    await waitFor(() => screen.getByText("Failed to delete memory"));

    // Advance 3 seconds — status should clear
    await act(async () => {
      vi.advanceTimersByTime(3000);
    });

    await waitFor(() =>
      expect(screen.queryByText("Failed to delete memory")).toBeNull()
    );

    vi.useRealTimers();
  });

  it("handleAddMemory sets success status on 200", async () => {
    const user = userEvent.setup();

    mockInitialFetches(fetchSpy, [], []);

    render(<SettingsPage />);

    // Wait for page to settle
    await waitFor(() => screen.getByPlaceholderText(/e\.g\., User prefers dark mode/i));

    // POST /memories → 201 with new memory
    fetchSpy.mockResolvedValueOnce(
      new Response(JSON.stringify({ ...MEMORY_1, id: "m2" }), { status: 201 })
    );
    // loadMemories after add
    fetchSpy.mockResolvedValueOnce(
      new Response(JSON.stringify([MEMORY_1]), { status: 200 })
    );

    const input = screen.getByPlaceholderText(/e\.g\., User prefers dark mode/i);
    await user.type(input, "Likes Python");
    await user.click(screen.getByRole("button", { name: /^add$/i }));

    await waitFor(() => screen.getByText("Memory added"));
  });

  it("handleAddMemory sets failure status on !ok", async () => {
    const user = userEvent.setup();

    mockInitialFetches(fetchSpy, [], []);

    render(<SettingsPage />);

    await waitFor(() => screen.getByPlaceholderText(/e\.g\., User prefers dark mode/i));

    // POST /memories → 500
    fetchSpy.mockResolvedValueOnce(
      new Response(null, { status: 500 })
    );

    const input = screen.getByPlaceholderText(/e\.g\., User prefers dark mode/i);
    await user.type(input, "Likes Python");
    await user.click(screen.getByRole("button", { name: /^add$/i }));

    await waitFor(() => screen.getByText("Failed to add memory"));
  });

  it("handleDeleteKey sets keyStatus on failure (D-09 fix)", async () => {
    const user = userEvent.setup();

    // Initial: keys=[KEY_1], memories=[]
    mockInitialFetches(fetchSpy, [KEY_1], []);

    render(<SettingsPage />);

    // Wait for the key to appear
    await waitFor(() => screen.getByText("openai"));

    // DELETE /keys/k1 → 500
    fetchSpy.mockResolvedValueOnce(
      new Response(null, { status: 500 })
    );

    // The remove button for API keys is labeled "Remove"
    const removeBtn = screen.getByRole("button", { name: /remove/i });
    await user.click(removeBtn);

    await waitFor(() => screen.getByText("Failed to remove key"));
  });
});
