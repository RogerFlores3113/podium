import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

// ToolCallDisplay is not exported from ChatPage; copy the minimal interface
// here so we can test the rendered output without pulling in the full page.
// If it gets extracted to its own file in the future, update this import.
import { ToolCallDisplay } from "@/app/components/ToolCallDisplay";

describe("ToolCallDisplay", () => {
  const base = {
    id: "tc-1",
    name: "web_search",
    arguments: JSON.stringify({ query: "vitest testing" }),
    status: "done" as const,
    result: "Found 5 results",
  };

  it("renders the tool name", () => {
    render(<ToolCallDisplay toolCall={base} />);
    expect(screen.getByText("web_search")).toBeTruthy();
  });

  it("renders 'done' status", () => {
    render(<ToolCallDisplay toolCall={base} />);
    expect(screen.getByText("done")).toBeTruthy();
  });

  it("renders 'running…' while status is running", () => {
    render(<ToolCallDisplay toolCall={{ ...base, status: "running" }} />);
    expect(screen.getByText("running…")).toBeTruthy();
  });

  it("expands to show arguments and result on click", async () => {
    const user = userEvent.setup();
    render(<ToolCallDisplay toolCall={base} />);

    // Details not visible before expanding
    expect(screen.queryByText("Arguments:")).toBeNull();

    await user.click(screen.getByRole("button"));

    expect(screen.getByText("Arguments:")).toBeTruthy();
    expect(screen.getByText("Result:")).toBeTruthy();
  });

  it("shows error section when status is error", async () => {
    const user = userEvent.setup();
    render(
      <ToolCallDisplay
        toolCall={{ ...base, status: "error", error: "Timeout" }}
      />
    );
    await user.click(screen.getByRole("button"));
    expect(screen.getByText("Error:")).toBeTruthy();
  });
});
