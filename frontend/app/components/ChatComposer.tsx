"use client";

import { useState, useEffect } from "react";

interface ChatComposerProps {
  isLoading: boolean;
  isGuest: boolean;
  onSubmit: (message: string) => void;
  externalValue?: string;
}

export default function ChatComposer({ isLoading, isGuest: _isGuest, onSubmit, externalValue }: ChatComposerProps) {
  const [input, setInput] = useState("");

  useEffect(() => {
    if (externalValue) setInput(externalValue);
  }, [externalValue]);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!input.trim() || isLoading) return;
    const message = input.trim();
    setInput("");
    onSubmit(message);
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (
      e.key === "Enter" &&
      !e.shiftKey &&
      !e.nativeEvent.isComposing
    ) {
      e.preventDefault();
      if (!input.trim() || isLoading) return;
      const message = input.trim();
      setInput("");
      onSubmit(message);
    }
  };

  return (
    <form onSubmit={handleSubmit} className="flex gap-2">
      <textarea
        value={input}
        onChange={(e) => {
          setInput(e.target.value);
          const el = e.target;
          el.style.height = "auto";
          el.style.height = `${Math.min(el.scrollHeight, 144)}px`;
        }}
        onKeyDown={handleKeyDown}
        placeholder="Ask me anything…"
        rows={1}
        className="flex-1 rounded-lg px-4 py-2 text-sm focus:outline-none resize-none"
        style={{
          background: "var(--bg-surface)",
          border: "1px solid var(--border)",
          color: "var(--text-primary)",
          minHeight: "40px",
          maxHeight: "144px",
          overflowY: "auto",
        }}
        disabled={isLoading}
      />
      <button
        type="submit"
        disabled={isLoading || !input.trim()}
        className="px-4 py-2 rounded-lg text-sm font-medium transition-opacity hover:opacity-80 disabled:opacity-40 disabled:cursor-not-allowed"
        style={{ background: "var(--accent-warm)", color: "#fff" }}
      >
        {isLoading ? "…" : "Send"}
      </button>
    </form>
  );
}
