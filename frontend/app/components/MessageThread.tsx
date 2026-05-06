"use client";

import { useRef, useEffect } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { ToolCallDisplay } from "@/app/components/ToolCallDisplay";
import type { Message } from "@/app/types/chat";

interface CapabilityCard {
  icon: string;
  label: string;
  prompt: string;
  prefill?: true;
}

const CAPABILITY_CARDS: CapabilityCard[] = [
  {
    icon: "🔍",
    label: "Search the web",
    prompt: "Search the web for recent developments in large language model benchmarks and summarize what you find",
  },
  {
    icon: "🧠",
    label: "Remember something",
    prompt: "Remember that I prefer concise, bullet-pointed answers",
  },
  {
    icon: "🐍",
    label: "Run code",
    prompt: "Write and run a Python script that calculates compound interest for a $10,000 investment at 7% over 10 years",
  },
  {
    icon: "📄",
    label: "Search my documents",
    prompt: "What documents have I uploaded? Summarize the key points from the most recent one.",
  },
  {
    icon: "🔗",
    label: "Read a URL",
    prompt: "Read [paste URL here] and summarize the key points",
    prefill: true,
  },
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
  showCapabilityCards: boolean;
  onCardClick: (prompt: string, label: string) => void;
  onCardPrefill?: (prompt: string) => void;
  isGuest?: boolean;
}

export default function MessageThread({
  messages,
  isThinking,
  showCapabilityCards,
  onCardClick,
  onCardPrefill,
  isGuest = false,
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
                        pre: ({ children }) => (
                          <pre
                            style={{
                              background: "var(--bg-elevated)",
                              borderRadius: "6px",
                              padding: "1em",
                              overflowX: "auto",
                              fontFamily: "ui-monospace, SFMono-Regular, monospace",
                              fontSize: "0.875em",
                              lineHeight: "1.5",
                              margin: "0.5em 0",
                            }}
                          >
                            {children}
                          </pre>
                        ),
                        code: ({ className, children, ...props }) => {
                          const isBlock = Boolean(className);
                          if (isBlock) {
                            return (
                              <code style={{ fontFamily: "inherit" }} {...props}>
                                {children}
                              </code>
                            );
                          }
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
          {CAPABILITY_CARDS.filter((card) => !(isGuest && card.label === "Remember something")).map((card) => (
            <button
              key={card.label}
              onClick={() => {
                if (card.prefill && onCardPrefill) {
                  onCardPrefill(card.prompt);
                } else {
                  onCardClick(card.prompt, card.label);
                }
              }}
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
