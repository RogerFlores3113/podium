import { render, screen } from "@testing-library/react";
import { describe, it, expect, vi } from "vitest";
import ChatComposer from "@/app/components/ChatComposer";

describe("ChatComposer", () => {
  it("populates input when externalValue is set", () => {
    const { rerender } = render(
      <ChatComposer isLoading={false} isGuest={false} onSubmit={vi.fn()} />
    );
    expect((screen.getByRole("textbox") as HTMLTextAreaElement).value).toBe("");

    rerender(
      <ChatComposer
        isLoading={false}
        isGuest={false}
        onSubmit={vi.fn()}
        externalValue="Read [paste URL here] and summarize the key points"
      />
    );
    expect((screen.getByRole("textbox") as HTMLTextAreaElement).value).toBe(
      "Read [paste URL here] and summarize the key points"
    );
  });

  it("does not change input when externalValue is empty string", () => {
    render(
      <ChatComposer
        isLoading={false}
        isGuest={false}
        onSubmit={vi.fn()}
        externalValue=""
      />
    );
    expect((screen.getByRole("textbox") as HTMLTextAreaElement).value).toBe("");
  });
});
