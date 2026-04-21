"use client";

import { useState, useRef, useEffect } from "react";
import { UserButton } from "@clerk/nextjs";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { useAuthFetch } from "@/app/hooks/useAuthFetch";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

const TOOL_ICONS: Record<string, string> = {
  web_search: "🔍",
  document_search: "📄",
  python_executor: "🐍",
  memory_search: "🧠",
  image_generation: "🎨",
};

const CAPABILITY_CARDS = [
  { icon: "💬", label: "Ask anything", prompt: "What can you help me with?" },
  { icon: "🔍", label: "Search the web", prompt: "Search the web for the latest news on AI" },
  { icon: "📄", label: "Upload documents", prompt: "I'll upload a PDF — summarize it for me" },
  { icon: "🐍", label: "Run code", prompt: "Write and run a Python script that prints the Fibonacci sequence" },
  { icon: "🧠", label: "I'll remember this", prompt: "Remember that I prefer concise answers" },
  { icon: "🎨", label: "Generate images", prompt: "Generate an image of a mountain at sunset" },
];

const WELCOME_MESSAGE =
  "Hi — I'm Podium, your personal AI assistant. I can search the web, read documents you upload, run code, and remember things you tell me over time. What would you like to work on?";

interface ToolCall {
  id: string;
  name: string;
  arguments: string;
  result?: string;
  error?: string;
  status: "running" | "done" | "error";
}

interface Message {
  role: "user" | "assistant";
  content: string;
  toolCalls?: ToolCall[];
}

function ToolCallDisplay({ toolCall }: { toolCall: ToolCall }) {
  const [expanded, setExpanded] = useState(false);

  const icon = TOOL_ICONS[toolCall.name] ?? "🔧";

  const statusColor =
    toolCall.status === "running"
      ? "var(--accent-soft)"
      : toolCall.status === "done"
      ? "#15803d"
      : "#b91c1c";

  const statusText = { running: "running…", done: "done", error: "error" }[toolCall.status];

  let argsDisplay = toolCall.arguments;
  try {
    argsDisplay = JSON.stringify(JSON.parse(toolCall.arguments), null, 2);
  } catch {
    // keep as-is while still streaming
  }

  return (
    <div
      className="rounded-lg overflow-hidden"
      style={{ border: "1px solid var(--border)", background: "var(--bg-elevated)" }}
    >
      <button
        onClick={() => setExpanded(!expanded)}
        className="w-full px-4 py-2 flex items-center justify-between text-left"
        style={{ background: "var(--bg-elevated)" }}
      >
        <div className="flex items-center gap-2 text-sm">
          <span>{icon}</span>
          <span className="font-mono" style={{ color: "var(--text-primary)" }}>
            {toolCall.name}
          </span>
          <span style={{ color: statusColor }}>{statusText}</span>
        </div>
        <span className="text-xs" style={{ color: "var(--text-muted)" }}>
          {expanded ? "▼" : "▶"}
        </span>
      </button>
      {expanded && (
        <div
          className="px-4 py-2 border-t text-xs space-y-2"
          style={{ borderColor: "var(--border)" }}
        >
          <div>
            <div className="mb-1" style={{ color: "var(--text-muted)" }}>
              Arguments:
            </div>
            <pre
              className="p-2 rounded overflow-x-auto"
              style={{
                background: "var(--bg-surface)",
                border: "1px solid var(--border)",
                color: "var(--text-primary)",
              }}
            >
              {argsDisplay}
            </pre>
          </div>
          {toolCall.result && (
            <div>
              <div className="mb-1" style={{ color: "var(--text-muted)" }}>
                Result:
              </div>
              <pre
                className="p-2 rounded overflow-x-auto max-h-48 overflow-y-auto whitespace-pre-wrap"
                style={{
                  background: "var(--bg-surface)",
                  border: "1px solid var(--border)",
                  color: "var(--text-primary)",
                }}
              >
                {toolCall.result}
              </pre>
            </div>
          )}
          {toolCall.error && (
            <div>
              <div className="mb-1" style={{ color: "#b91c1c" }}>
                Error:
              </div>
              <pre
                className="p-2 rounded overflow-x-auto"
                style={{ background: "#fef2f2", border: "1px solid #fecaca", color: "#b91c1c" }}
              >
                {toolCall.error}
              </pre>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

export default function ChatPage() {
  const authFetch = useAuthFetch();
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [conversationId, setConversationId] = useState<string | null>(null);
  const [uploadStatus, setUploadStatus] = useState<string | null>(null);
  const [darkMode, setDarkMode] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const hasWelcomed = useRef(false);
  const uploadPollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  useEffect(() => {
    try {
      const stored = localStorage.getItem("theme");
      if (stored === "dark") {
        setDarkMode(true);
        document.documentElement.setAttribute("data-theme", "dark");
      }
    } catch {
      // private browsing
    }
  }, []);

  const toggleDark = () => {
    const next = !darkMode;
    setDarkMode(next);
    document.documentElement.setAttribute("data-theme", next ? "dark" : "");
    try {
      localStorage.setItem("theme", next ? "dark" : "light");
    } catch {
      // private browsing
    }
  };

  // Inject welcome message once per mount
  useEffect(() => {
    if (!hasWelcomed.current) {
      hasWelcomed.current = true;
      setMessages([{ role: "assistant", content: WELCOME_MESSAGE }]);
    }
  }, []);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  // Clean up upload poll on unmount
  useEffect(() => {
    return () => {
      if (uploadPollRef.current) clearInterval(uploadPollRef.current);
    };
  }, []);

  const startNewConversation = () => {
    setMessages([{ role: "assistant", content: WELCOME_MESSAGE }]);
    setConversationId(null);
    hasWelcomed.current = true;
  };

  const handleCardClick = (prompt: string) => {
    setInput(prompt);
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!input.trim() || isLoading) return;

    const userMessage = input.trim();
    setInput("");
    setMessages((prev) => [...prev, { role: "user", content: userMessage }]);
    setIsLoading(true);
    setMessages((prev) => [...prev, { role: "assistant", content: "" }]);

    try {
      const response = await authFetch(`${API_URL}/chat/stream`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message: userMessage, conversation_id: conversationId }),
      });

      const reader = response.body?.getReader();
      const decoder = new TextDecoder();
      if (!reader) throw new Error("No reader available");

      let buffer = "";

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const parts = buffer.split("\r\n\r\n");
        buffer = parts.pop() || "";

        for (const part of parts) {
          if (!part.trim()) continue;
          const lines = part.split("\r\n");
          let currentEvent = "";

          for (const line of lines) {
            if (line.startsWith("event: ")) {
              currentEvent = line.slice(7).trim();
            } else if (line.startsWith("data: ")) {
              const data = JSON.parse(line.slice(6));

              if (currentEvent === "conversation") {
                setConversationId(data.conversation_id);
              } else if (currentEvent === "token") {
                setMessages((prev) => {
                  const updated = [...prev];
                  const last = updated[updated.length - 1];
                  if (last.role === "assistant") {
                    updated[updated.length - 1] = { ...last, content: last.content + data.token };
                  }
                  return updated;
                });
              } else if (currentEvent === "tool_call_start") {
                setMessages((prev) => {
                  const updated = [...prev];
                  const last = updated[updated.length - 1];
                  if (last.role === "assistant") {
                    const newToolCall: ToolCall = {
                      id: data.id,
                      name: data.name,
                      arguments: data.arguments,
                      status: "running",
                    };
                    updated[updated.length - 1] = {
                      ...last,
                      toolCalls: [...(last.toolCalls || []), newToolCall],
                    };
                  }
                  return updated;
                });
              } else if (currentEvent === "tool_call_result") {
                setMessages((prev) => {
                  const updated = [...prev];
                  const last = updated[updated.length - 1];
                  if (last.role === "assistant" && last.toolCalls) {
                    updated[updated.length - 1] = {
                      ...last,
                      toolCalls: last.toolCalls.map((tc) =>
                        tc.id === data.id ? { ...tc, result: data.result, status: "done" as const } : tc
                      ),
                    };
                  }
                  return updated;
                });
                setMessages((prev) => [...prev, { role: "assistant", content: "" }]);
              } else if (currentEvent === "tool_call_error") {
                setMessages((prev) => {
                  const updated = [...prev];
                  const last = updated[updated.length - 1];
                  if (last.role === "assistant" && last.toolCalls) {
                    updated[updated.length - 1] = {
                      ...last,
                      toolCalls: last.toolCalls.map((tc) =>
                        tc.id === data.id ? { ...tc, error: data.error, status: "error" as const } : tc
                      ),
                    };
                  }
                  return updated;
                });
                setMessages((prev) => [...prev, { role: "assistant", content: "" }]);
              }
            }
          }
        }
      }
    } catch (error) {
      console.error("Chat error:", error);
      setMessages((prev) => {
        const updated = [...prev];
        const last = updated[updated.length - 1];
        if (last.role === "assistant") {
          updated[updated.length - 1] = {
            ...last,
            content: "Something went wrong. Please try again.",
          };
        }
        return updated;
      });
    }

    setIsLoading(false);
  };

  const handleUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    setUploadStatus("Uploading…");

    const formData = new FormData();
    formData.append("file", file);

    try {
      const response = await authFetch(`${API_URL}/documents/upload`, {
        method: "POST",
        body: formData,
      });

      if (!response.ok) throw new Error("Upload failed");

      const doc = await response.json();
      setUploadStatus(`Processing: ${doc.filename}`);

      if (uploadPollRef.current) clearInterval(uploadPollRef.current);
      uploadPollRef.current = setInterval(async () => {
        const statusRes = await authFetch(`${API_URL}/documents/${doc.id}`);
        const statusDoc = await statusRes.json();

        if (statusDoc.status === "ready") {
          setUploadStatus(`Ready: ${statusDoc.filename} (${statusDoc.page_count} pages)`);
          if (uploadPollRef.current) clearInterval(uploadPollRef.current);
        } else if (statusDoc.status === "failed") {
          setUploadStatus(`Failed: ${statusDoc.filename}`);
          if (uploadPollRef.current) clearInterval(uploadPollRef.current);
        }
      }, 1000);
    } catch {
      setUploadStatus("Upload failed");
    }

    e.target.value = "";
  };

  const showCapabilityCards =
    messages.length === 1 && messages[0].role === "assistant" && !isLoading;

  return (
    <main className="flex flex-col h-screen max-w-3xl mx-auto p-4">
      {/* Header */}
      <div
        className="flex items-center justify-between mb-4 pb-4"
        style={{ borderBottom: "1px solid var(--border)" }}
      >
        <div className="flex items-center gap-3">
          <h1 className="text-xl font-semibold" style={{ color: "var(--text-primary)" }}>
            Podium
          </h1>
          <button
            onClick={startNewConversation}
            className="w-7 h-7 flex items-center justify-center rounded-full text-lg font-light transition-opacity hover:opacity-70"
            style={{ background: "var(--bg-elevated)", color: "var(--text-muted)" }}
            title="New conversation"
          >
            +
          </button>
        </div>
        <div className="flex items-center gap-3">
          {uploadStatus && (
            <span className="text-sm" style={{ color: "var(--text-muted)" }}>
              {uploadStatus}
            </span>
          )}
          <label
            className="cursor-pointer px-3 py-1.5 rounded text-sm transition-opacity hover:opacity-80"
            style={{ background: "var(--bg-elevated)", color: "var(--text-muted)" }}
          >
            Upload PDF
            <input type="file" accept=".pdf" onChange={handleUpload} className="hidden" />
          </label>
          <a
            href="/settings"
            className="text-sm transition-colors hover:opacity-80"
            style={{ color: "var(--text-muted)" }}
          >
            Settings
          </a>
          <button
            onClick={toggleDark}
            className="text-lg transition-opacity hover:opacity-70"
            title="Toggle dark mode"
          >
            {darkMode ? "☀️" : "🌙"}
          </button>
          <UserButton />
        </div>
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto space-y-4 mb-4">
        {messages.map((msg, i) => (
          <div key={i}>
            {msg.content && (
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
                      <ReactMarkdown remarkPlugins={[remarkGfm]}>
                        {msg.content}
                      </ReactMarkdown>
                    </div>
                  ) : (
                    <p className="whitespace-pre-wrap">{msg.content}</p>
                  )}
                </div>
              </div>
            )}

            {msg.toolCalls && msg.toolCalls.length > 0 && (
              <div className="space-y-2 my-2">
                {msg.toolCalls.map((tc) => (
                  <ToolCallDisplay key={tc.id} toolCall={tc} />
                ))}
              </div>
            )}
          </div>
        ))}

        {/* Capability cards — shown only on fresh conversation */}
        {showCapabilityCards && (
          <div className="grid grid-cols-2 gap-2 mt-4">
            {CAPABILITY_CARDS.map((card) => (
              <button
                key={card.label}
                onClick={() => handleCardClick(card.prompt)}
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

      {/* Input */}
      <form onSubmit={handleSubmit} className="flex gap-2">
        <input
          type="text"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="Ask me anything…"
          className="flex-1 rounded-lg px-4 py-2 text-sm focus:outline-none"
          style={{
            background: "var(--bg-surface)",
            border: "1px solid var(--border)",
            color: "var(--text-primary)",
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
    </main>
  );
}
