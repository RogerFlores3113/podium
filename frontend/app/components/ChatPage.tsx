"use client";

import { useState, useRef, useEffect, useCallback } from "react";
import { flushSync } from "react-dom";
import { UserButton } from "@clerk/nextjs";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { useAuthFetch } from "@/app/hooks/useAuthFetch";
import { formatRelativeTime } from "@/app/utils/time";
import { ToolCallDisplay, type ToolCall } from "@/app/components/ToolCallDisplay";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

const DEFAULT_MODEL = "gpt-5-nano";
const FALLBACK_MODELS = [{ id: "gpt-5-nano", label: "GPT-5 nano · fast" }];

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

const TOOL_PHASE_COPY: Record<string, string> = {
  web_search: "Searching the web…",
  document_search: "Reading uploaded documents…",
  url_reader: "Reading source…",
  python_executor: "Running code…",
  memory_search: "Recalling earlier conversations…",
};
const toolPhaseCopy = (name: string): string =>
  TOOL_PHASE_COPY[name] ?? `Working on ${name}…`;

type ErrorKind = "byok" | "limit" | "server" | "stream" | "network";

const ERROR_COPY: Record<ErrorKind, string> = {
  byok: "Add your OpenAI API key in Settings to chat. Or sign out and try Podium as a guest.",
  limit: "You've reached the guest message limit. Sign up to keep chatting.",
  server: "Something went wrong on our end. Please try again in a moment.",
  stream: "", // SSE error fills from data.detail
  network: "Connection lost. Please check your network and try again.",
};

const MAX_POLL_ATTEMPTS = 60;

interface UserMessage { role: "user"; content: string }
interface AssistantMessage { role: "assistant"; content: string; toolCalls?: ToolCall[] }
interface ErrorMessage { role: "error"; kind: ErrorKind; content: string }
type Message = UserMessage | AssistantMessage | ErrorMessage;

interface ConversationItem {
  id: string;
  title: string | null;
  created_at: string;
}

export default function ChatPage() {
  const authFetch = useAuthFetch();
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [isThinking, setIsThinking] = useState(false);
  const [conversationId, setConversationId] = useState<string | null>(null);
  const [uploadStatus, setUploadStatus] = useState<string | null>(null);
  const [darkMode, setDarkMode] = useState(false);
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [conversations, setConversations] = useState<ConversationItem[]>([]);
  const [selectedModel, setSelectedModel] = useState(DEFAULT_MODEL);
  const [availableModels, setAvailableModels] = useState(FALLBACK_MODELS);
  const [isGuest, setIsGuest] = useState(false);
  const [byokError, setByokError] = useState(false);
  const [hoveredConvId, setHoveredConvId] = useState<string | null>(null);
  const hoverHideTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);
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
      const storedModel = localStorage.getItem("selectedModel");
      if (storedModel) setSelectedModel(storedModel);
    } catch {
      // private browsing
    }
    // Detect guest session
    try {
      const guestToken = sessionStorage.getItem("podium_guest_token");
      const guestExpires = sessionStorage.getItem("podium_guest_expires");
      if (guestToken && guestExpires && new Date(guestExpires) > new Date()) {
        setIsGuest(true);
      }
    } catch {
      // sessionStorage unavailable
    }
    // Fetch available models from backend (base list + dynamic Ollama models)
    void (async () => { try {
      const res = await fetch(`${API_URL}/chat/models`);
      if (!res.ok) return;
      const baseModels = await res.json();
      let allModels = baseModels;
      try {
        const ollamaRes = await authFetch(`${API_URL}/chat/ollama-models`);
        if (ollamaRes.ok) {
          const ollamaModels = await ollamaRes.json();
          if (ollamaModels.length > 0) allModels = [...baseModels, ...ollamaModels];
        }
      } catch {}
      setAvailableModels(allModels);
      const stored = localStorage.getItem("selectedModel");
      if (stored && allModels.some((m: { id: string }) => m.id === stored)) {
        setSelectedModel(stored);
      } else if (stored) {
        setSelectedModel(DEFAULT_MODEL);
        try { localStorage.removeItem("selectedModel"); } catch {}
      }
    } catch {} })();
    // Open sidebar by default on wider screens
    if (window.innerWidth >= 768) setSidebarOpen(true);
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

  const fetchConversations = useCallback(async () => {
    try {
      const res = await authFetch(`${API_URL}/chat/`);
      if (!res.ok) return;
      const data = await res.json();
      if (Array.isArray(data)) {
        setConversations(data);
      }
    } catch {
      // sidebar is non-critical
    }
  }, [authFetch]);

  // Inject welcome message once per mount
  useEffect(() => {
    if (!hasWelcomed.current) {
      hasWelcomed.current = true;
      setMessages([{ role: "assistant", content: WELCOME_MESSAGE }]);
    }
  }, []);

  useEffect(() => {
    fetchConversations();
  }, [fetchConversations]);

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

  const handleDeleteConversation = async (id: string) => {
    if (!window.confirm("Delete this conversation? This cannot be undone.")) return;
    const res = await authFetch(`${API_URL}/chat/${id}`, { method: "DELETE" });
    if (!res.ok) return; // sidebar silent per D-05
    setConversations((prev) => prev.filter((c) => c.id !== id));
    if (conversationId === id) startNewConversation();
  };

  const loadConversation = async (id: string) => {
    try {
      const res = await authFetch(`${API_URL}/chat/${id}`);
      if (!res.ok) return;
      const data = await res.json();
      const msgs: Message[] = (data.messages as { role: string; content: string }[])
        .filter((m) => (m.role === "user" || m.role === "assistant") && m.content)
        .map((m) => ({ role: m.role as "user" | "assistant", content: m.content }));
      setMessages(msgs.length > 0 ? msgs : [{ role: "assistant", content: WELCOME_MESSAGE }]);
      setConversationId(id);
      // Close sidebar on mobile after selecting
      if (window.innerWidth < 768) setSidebarOpen(false);
    } catch {
      // keep current conversation
    }
  };

  const handleCardClick = (prompt: string) => {
    setInput(prompt);
  };

  const submitMessage = async () => {
    if (!input.trim() || isLoading) return;

    const userMessage = input.trim();
    setInput("");
    setMessages((prev) => [...prev, { role: "user", content: userMessage }]);
    setIsLoading(true);
    setIsThinking(true);

    let response: Response;
    try {
      response = await authFetch(`${API_URL}/chat/stream`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message: userMessage, conversation_id: conversationId, model: selectedModel }),
      });
    } catch {
      setMessages((prev) => [...prev, { role: "error", kind: "network", content: ERROR_COPY.network }]);
      setIsThinking(false);
      setIsLoading(false);
      return;
    }

    if (response.status === 402) {
      setByokError(true);
      setMessages((prev) => [...prev, { role: "error", kind: "byok", content: ERROR_COPY.byok }]);
      setIsThinking(false);
      setIsLoading(false);
      return;
    }
    if (response.status === 429) {
      let copy = ERROR_COPY.limit;
      try {
        const body = await response.json();
        if (body?.detail?.message) copy = body.detail.message;
      } catch { /* generic copy */ }
      setMessages((prev) => [...prev, { role: "error", kind: "limit", content: copy }]);
      setIsThinking(false);
      setIsLoading(false);
      return;
    }
    if (!response.ok) {
      // 5xx (or any other non-2xx). DO NOT read body — Pitfall 2 + V7.
      setMessages((prev) => [...prev, { role: "error", kind: "server", content: ERROR_COPY.server }]);
      setIsThinking(false);
      setIsLoading(false);
      return;
    }

    setMessages((prev) => [...prev, { role: "assistant", content: "" }]);

    try {
      const reader = response.body?.getReader();
      const decoder = new TextDecoder();
      if (!reader) throw new Error("No reader available");

      let buffer = "";

      try {
        while (true) {
          const { done, value } = await reader.read();
          if (done) break;

          buffer += decoder.decode(value, { stream: true }).replace(/\r\n/g, "\n");
          const parts = buffer.split("\n\n");
          buffer = parts.pop() || "";

          for (const part of parts) {
            if (!part.trim()) continue;
            const lines = part.split("\n");
            let currentEvent = "";

            for (const line of lines) {
              if (line.startsWith("event: ")) {
                currentEvent = line.slice(7).trim();
              } else if (line.startsWith("data: ")) {
                let data: any;
                try {
                  data = JSON.parse(line.slice(6));
                } catch {
                  continue; // skip malformed frames, don't abort the stream
                }

                if (currentEvent === "conversation") {
                  setConversationId(data.conversation_id);
                } else if (currentEvent === "token") {
                  // flushSync ensures each token renders immediately (visible streaming).
                  flushSync(() => {
                    setIsThinking(false);
                    setMessages((prev) => {
                      const updated = [...prev];
                      const last = updated[updated.length - 1];
                      if (last.role === "assistant") {
                        updated[updated.length - 1] = { ...last, content: last.content + data.token };
                      }
                      return updated;
                    });
                  });
                } else if (currentEvent === "tool_call_start") {
                  // flushSync ensures the "running" phase copy renders before the result arrives.
                  flushSync(() => {
                    setIsThinking(false);
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
                } else if (currentEvent === "done") {
                  // Refresh sidebar after new conversation completes
                  fetchConversations();
                } else if (currentEvent === "error") {
                  setIsThinking(false);
                  setMessages((prev) => {
                    const updated = [...prev];
                    const last = updated[updated.length - 1];
                    // Preserve partial assistant content (Pitfall 6) — only pop empty placeholders.
                    if (
                      last &&
                      last.role === "assistant" &&
                      !last.content &&
                      (!last.toolCalls || last.toolCalls.length === 0)
                    ) {
                      updated.pop();
                    }
                    updated.push({
                      role: "error",
                      kind: "stream",
                      content: data.detail || "The response was interrupted. Please try again.",
                    });
                    return updated;
                  });
                }
              }
            }
          }
        }
      } finally {
        reader.releaseLock();
      }
    } catch {
      setMessages((prev) => [...prev, { role: "error", kind: "network", content: ERROR_COPY.network }]);
    }

    setIsThinking(false);
    setIsLoading(false);
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    submitMessage();
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
      let attempts = 0;
      uploadPollRef.current = setInterval(async () => {
        attempts += 1;
        if (attempts > MAX_POLL_ATTEMPTS) {
          if (uploadPollRef.current) clearInterval(uploadPollRef.current);
          uploadPollRef.current = null;
          setUploadStatus(`Upload taking too long: ${doc.filename}`);
          return;
        }
        try {
          const statusRes = await authFetch(`${API_URL}/documents/${doc.id}`);
          // Stale-tick guard (Pitfall 4): another tick may have cleared the interval while we awaited.
          if (uploadPollRef.current === null) return;
          if (!statusRes.ok) throw new Error(`status ${statusRes.status}`);
          const statusDoc = await statusRes.json();
          if (uploadPollRef.current === null) return;
          if (statusDoc.status === "ready") {
            setUploadStatus(
              `Ready: ${statusDoc.filename} (${statusDoc.page_count} pages)`,
            );
            clearInterval(uploadPollRef.current);
            uploadPollRef.current = null;
          } else if (statusDoc.status === "failed") {
            setUploadStatus(`Failed: ${statusDoc.filename}`);
            clearInterval(uploadPollRef.current);
            uploadPollRef.current = null;
          }
        } catch {
          if (uploadPollRef.current) clearInterval(uploadPollRef.current);
          uploadPollRef.current = null;
          setUploadStatus("Upload status check failed");
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
    <div className="flex h-screen" style={{ background: "var(--bg-base)" }}>
      {/* Sidebar overlay on mobile */}
      {sidebarOpen && (
        <div
          className="fixed inset-0 z-10 md:hidden"
          style={{ background: "rgba(0,0,0,0.3)" }}
          onClick={() => setSidebarOpen(false)}
        />
      )}

      {/* Sidebar */}
      <aside
        className={`${
          sidebarOpen ? "translate-x-0" : "-translate-x-full"
        } fixed md:relative md:translate-x-0 z-20 md:z-auto flex-shrink-0 flex flex-col h-full transition-transform duration-200`}
        style={{
          width: "240px",
          background: "var(--bg-elevated)",
          borderRight: "1px solid var(--border)",
        }}
      >
        {/* Sidebar header */}
        <div
          className="flex items-center justify-between px-4 py-4"
          style={{ borderBottom: "1px solid var(--border)" }}
        >
          <span className="text-sm font-semibold" style={{ color: "var(--text-primary)" }}>
            Conversations
          </span>
          <button
            onClick={() => setSidebarOpen(false)}
            className="md:hidden text-lg transition-opacity hover:opacity-70"
            style={{ color: "var(--text-muted)" }}
          >
            ✕
          </button>
        </div>

        {/* New conversation */}
        <div className="px-3 py-2">
          <button
            onClick={startNewConversation}
            className="w-full flex items-center gap-2 px-3 py-2 rounded-lg text-sm transition-opacity hover:opacity-80"
            style={{ background: "var(--accent-warm)", color: "#fff" }}
          >
            <span className="text-base font-light">+</span>
            New conversation
          </button>
        </div>

        {/* Conversation list */}
        <div className="flex-1 overflow-y-auto px-2 py-1">
          {conversations.length === 0 ? (
            <p className="text-xs px-2 py-3" style={{ color: "var(--text-muted)" }}>
              No conversations yet
            </p>
          ) : (
            conversations.map((conv) => (
              <div
                key={conv.id}
                role="button"
                tabIndex={0}
                onClick={() => loadConversation(conv.id)}
                onKeyDown={(e) => {
                  if (e.key === "Enter" || e.key === " ") {
                    e.preventDefault();
                    loadConversation(conv.id);
                  }
                }}
                onMouseEnter={() => {
                  if (hoverHideTimeoutRef.current) {
                    clearTimeout(hoverHideTimeoutRef.current);
                    hoverHideTimeoutRef.current = null;
                  }
                  setHoveredConvId(conv.id);
                }}
                onMouseLeave={() => {
                  // Defer hide so mouseenter on the × button child can cancel it
                  hoverHideTimeoutRef.current = setTimeout(
                    () => setHoveredConvId(null),
                    0
                  );
                }}
                className="relative w-full text-left px-3 py-2 rounded-lg mb-0.5 transition-opacity hover:opacity-80 cursor-pointer"
                style={{
                  background: conv.id === conversationId ? "var(--bg-surface)" : "transparent",
                  border: conv.id === conversationId ? "1px solid var(--border)" : "1px solid transparent",
                }}
              >
                <div
                  className="text-sm truncate"
                  style={{ color: "var(--text-primary)" }}
                >
                  {conv.title || "Untitled"}
                </div>
                <div className="text-xs mt-0.5" style={{ color: "var(--text-muted)" }}>
                  {formatRelativeTime(conv.created_at)}
                </div>
                {hoveredConvId === conv.id && (
                  <button
                    type="button"
                    title="Delete conversation"
                    onMouseEnter={() => {
                      if (hoverHideTimeoutRef.current) {
                        clearTimeout(hoverHideTimeoutRef.current);
                        hoverHideTimeoutRef.current = null;
                      }
                      setHoveredConvId(conv.id);
                    }}
                    onMouseLeave={() => {
                      hoverHideTimeoutRef.current = setTimeout(
                        () => setHoveredConvId(null),
                        0
                      );
                    }}
                    onClick={(e) => {
                      e.stopPropagation();
                      handleDeleteConversation(conv.id);
                    }}
                    className="absolute right-2 top-1/2 -translate-y-1/2 w-6 h-6 flex items-center justify-center text-sm transition-opacity hover:opacity-70"
                    style={{ color: "#b91c1c" }}
                  >
                    ×
                  </button>
                )}
              </div>
            ))
          )}
        </div>
      </aside>

      {/* Main area */}
      <div className="flex flex-col flex-1 min-w-0">
        {isGuest && (
          <div className="text-center text-sm py-2 px-4" style={{ background: "var(--bg-subtle, #f0f9ff)", color: "var(--text-secondary, #555)" }}>
            Guest session — your data will be deleted in 24 hours.{" "}
            <a href="/sign-up" className="underline font-medium">Sign up</a> to keep your work.
          </div>
        )}
        {byokError && (
          <div className="text-center text-sm py-2 px-4" style={{ background: "var(--bg-subtle, #fff8e1)", color: "var(--text-secondary, #555)" }}>
            Add your OpenAI API key to start chatting.{" "}
            <a href="/settings" className="underline font-medium">Settings →</a>
          </div>
        )}
        <main className="flex flex-col h-full max-w-3xl w-full mx-auto p-4">
          {/* Header */}
          <div
            className="flex items-center justify-between mb-4 pb-4"
            style={{ borderBottom: "1px solid var(--border)" }}
          >
            <div className="flex items-center gap-3">
              <button
                onClick={() => setSidebarOpen(!sidebarOpen)}
                className="w-7 h-7 flex items-center justify-center rounded text-sm transition-opacity hover:opacity-70"
                style={{ background: "var(--bg-elevated)", color: "var(--text-muted)" }}
                title="Toggle sidebar"
              >
                ☰
              </button>
              <h1 className="text-xl font-semibold" style={{ color: "var(--text-primary)" }}>
                Podium
              </h1>
              <select
                value={selectedModel}
                onChange={(e) => {
                  setSelectedModel(e.target.value);
                  try { localStorage.setItem("selectedModel", e.target.value); } catch {}
                }}
                disabled={isLoading || isGuest}
                aria-label={isGuest ? "Model selection unavailable for guest accounts" : "Select model"}
                title={isGuest ? "Model selection unavailable for guest accounts" : undefined}
                className="text-xs rounded px-2 py-1 focus:outline-none transition-opacity disabled:opacity-50"
                style={{
                  background: "var(--bg-elevated)",
                  border: "1px solid var(--border)",
                  color: "var(--text-muted)",
                }}
              >
                {availableModels.map((m) => (
                  <option key={m.id} value={m.id}>{m.label}</option>
                ))}
              </select>
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
            <textarea
              value={input}
              onChange={(e) => {
                setInput(e.target.value);
                const el = e.target;
                el.style.height = "auto";
                el.style.height = `${Math.min(el.scrollHeight, 144)}px`;
              }}
              onKeyDown={(e) => {
                if (
                  e.key === "Enter" &&
                  !e.shiftKey &&
                  !e.nativeEvent.isComposing
                ) {
                  e.preventDefault();
                  submitMessage();
                }
              }}
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
        </main>
      </div>
    </div>
  );
}
