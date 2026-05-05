import { render, fireEvent, screen } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import ConversationSidebar from "@/app/components/ConversationSidebar";
import * as fs from "fs";
import * as path from "path";

const baseProps = {
  isOpen: true,
  onClose: vi.fn(),
  conversations: [{ id: "conv-1", title: "My Conversation", created_at: "2026-01-01T00:00:00Z" }],
  activeConversationId: null,
  onNewConversation: vi.fn(),
  onSelectConversation: vi.fn(),
  onDeleteConversation: vi.fn(),
  onRenameConversation: vi.fn().mockResolvedValue(undefined),
};

beforeEach(() => {
  vi.clearAllMocks();
});

describe("ConversationSidebar", () => {
  it("calls onSelectConversation when a conversation is clicked", () => {
    render(<ConversationSidebar {...baseProps} />);
    const item = screen.getByRole("button", { name: /My Conversation/i });
    fireEvent.click(item);
    expect(baseProps.onSelectConversation).toHaveBeenCalledWith("conv-1");
  });

  it("shows inline input on double-click with title pre-filled", () => {
    render(<ConversationSidebar {...baseProps} />);
    const titleEl = screen.getByText("My Conversation");
    fireEvent.doubleClick(titleEl);
    const input = screen.getByRole("textbox");
    expect(input).toBeDefined();
    expect((input as HTMLInputElement).value).toBe("My Conversation");
  });

  it("calls onRenameConversation with new title on Enter", async () => {
    render(<ConversationSidebar {...baseProps} />);
    const titleEl = screen.getByText("My Conversation");
    fireEvent.doubleClick(titleEl);
    const input = screen.getByRole("textbox");
    fireEvent.change(input, { target: { value: "Renamed Title" } });
    fireEvent.keyDown(input, { key: "Enter" });
    expect(baseProps.onRenameConversation).toHaveBeenCalledWith("conv-1", "Renamed Title");
  });

  it("cancels rename on Escape without calling onRenameConversation", () => {
    render(<ConversationSidebar {...baseProps} />);
    const titleEl = screen.getByText("My Conversation");
    fireEvent.doubleClick(titleEl);
    const input = screen.getByRole("textbox");
    fireEvent.change(input, { target: { value: "Abandoned Title" } });
    fireEvent.keyDown(input, { key: "Escape" });
    expect(baseProps.onRenameConversation).not.toHaveBeenCalled();
    // Input should be gone; original title should be visible again
    expect(screen.getByText("My Conversation")).toBeDefined();
  });

  it("calls onDeleteConversation when delete button is clicked", () => {
    const { container } = render(<ConversationSidebar {...baseProps} hoveredConvId="conv-1" />);
    // The delete button is shown on hover — trigger hover then click
    const item = container.querySelector('[role="button"]') as HTMLElement;
    fireEvent.mouseEnter(item);
    const deleteBtn = screen.getByTitle("Delete conversation");
    fireEvent.click(deleteBtn);
    expect(baseProps.onDeleteConversation).toHaveBeenCalledWith("conv-1");
  });

  it("D-04: ChatComposer is keyed to conversationId (static check)", () => {
    const chatPageContent = fs.readFileSync(
      path.join(__dirname, "../app/components/ChatPage.tsx"),
      "utf8"
    );
    expect(chatPageContent).toContain('key={conversationId ?? "new"}');
  });
});
