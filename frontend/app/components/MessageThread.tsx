"use client";

import { useRef, useEffect } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { ToolCallDisplay } from "@/app/components/ToolCallDisplay";
import type { Message } from "@/app/types/chat";

const CAPABILITY_CARDS = [
  { icon: "💬", label: "Ask anything", prompt: "What can you help me with?" },
  { icon: "🔍", label: "Search the web", prompt: "Search the web for the latest news on AI" },
  { icon: "📄", label: "Upload documents", prompt: "I'll upload a PDF — summarize it for me" },
  { icon: "🐍", label: "Run code", prompt: "Write and run a Python script that prints the Fibonacci sequence" },
  { icon: "🧠", label: "I'll remember this", prompt: "Remember that I prefer concise answers" },
];

// UX-02 audit passed: all entries ≤3 words (excluding trailing ellipsis)
const TOOL_PHASE_COPY: Record<string, string> = {
  web_search: "Searching the web…",
  document_search: "Reading uploaded documents…",
  url_reader: "Reading source…",
  python_executor: "Running code…",
  memory_search: "Recalling earlier conversations…",
};

const toolPhaseCopy = (name: string): string =>
  TOOL_PHASE_COPY[name] ?? `Working on ${name}…`;

interface MessageThreadProps {
  messages: Message[];
  isThinking: boolean;
  isLoading: boolean;
  showCapabilityCards: boolean;
  onCardClick: (prompt: string) => void;
}

export default function MessageThread({
  messages,
  isThinking,
  isLoading: _isLoading,
  showCapabilityCards,
  onCardClick,
}: MessageThreadProps) {
  const messagesEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  return (
    <div className="flex-1 overflow-y-auto space-y-4 mb-4">
      {messages.map((msg, i) => (
        <div key={i}>
          {msg.role === "error" && (
            <div
              className="flex justify-start mb-2"
              data-testid="error-bubble"
              role="alert"
            >
              <div
                className="max-w-[80%] rounded-lg px-4 py-2 text-sm"
                style={{
                  background: "#fef2f2",
                  border: "1px solid #fecaca",
                  color: "#b91c1c",
                }}
              >
                {msg.content}
              </div>
            </div>
          )}

          {msg.role !== "error" && msg.content && (
            <div className={`flex ${msg.role === "user" ? "justify-end" : "justify-start"} mb-2`}>
              <div
                className="max-w-[80%] rounded-lg px-4 py-2"
                style={
                  msg.role === "user"
                    ? { background: "var(--accent-warm)", color: "#fff" }
                    : { background: "var(--bg-surface)", color: "var(--text-primary)" }
                }
              >
                {msg.role === "assistant" ? (
                  <div className="prose prose-sm max-w-none">
                    <ReactMarkdown
                      remarkPlugins={[remarkGfm]}
                      components={{
                        code: ({ className, children, ...props }) => {
                          const isBlock = Boolean(className);
                          if (isBlock) return <code className={className} {...props}>{children}</code>;
                          return (
                            <code
                              style={{
                                fontFamily: "monospace",
                                background: "var(--bg-elevated)",
                                padding: "0.1em 0.35em",
                                borderRadius: "3px",
                                fontSize: "0.875em",
                              }}
                              {...props}
                            >
                              {children}
                            </code>
                          );
                        },
                      }}
                    >
                      {msg.content}
                    </ReactMarkdown>
                  </div>
                ) : (
                  <p className="whitespace-pre-wrap">{msg.content}</p>
                )}
              </div>
            </div>
          )}

          {msg.role === "assistant" && msg.toolCalls && msg.toolCalls.length > 0 && (
            <div className="space-y-2 my-2">
              {msg.toolCalls.map((tc) => (
                <div key={tc.id}>
                  {tc.status === "running" && (
                    <div
                      className="text-xs italic mb-1"
                      style={{ color: "var(--text-muted)" }}
                    >
                      {toolPhaseCopy(tc.name)}
                    </div>
                  )}
                  <ToolCallDisplay toolCall={tc} />
                </div>
              ))}
            </div>
          )}
        </div>
      ))}

      {isThinking && (
        <div
          className="flex justify-start mb-2"
          data-testid="thinking-indicator"
          role="status"
          aria-label="Thinking"
        >
          <div
            className="rounded-lg px-4 py-2"
            style={{ background: "var(--bg-surface)", color: "var(--text-muted)" }}
          >
            <span className="inline-flex gap-1">
              <span className="animate-pulse">·</span>
              <span className="animate-pulse" style={{ animationDelay: "150ms" }}>·</span>
              <span className="animate-pulse" style={{ animationDelay: "300ms" }}>·</span>
            </span>
          </div>
        </div>
      )}

      {/* Capability cards — shown only on fresh conversation */}
      {showCapabilityCards && (
        <div className="grid grid-cols-2 gap-2 mt-4">
          {CAPABILITY_CARDS.map((card) => (
            <button
              key={card.label}
              onClick={() => onCardClick(card.prompt)}
              className="flex items-center gap-3 rounded-lg px-4 py-3 text-left transition-opacity hover:opacity-80"
              style={{
                background: "var(--bg-surface)",
                border: "1px solid var(--border)",
                color: "var(--text-primary)",
              }}
            >
              <span className="text-xl">{card.icon}</span>
              <span className="text-sm font-medium">{card.label}</span>
            </button>
          ))}
        </div>
      )}

      <div ref={messagesEndRef} />
    </div>
  );
}
