"use client";

import { useState, useRef, useEffect, useCallback } from "react";
import { flushSync } from "react-dom";
import { UserButton, useAuth } from "@clerk/nextjs";
import { useAuthFetch } from "@/app/hooks/useAuthFetch";
import { type ToolCall } from "@/app/components/ToolCallDisplay";
import ConversationSidebar from "@/app/components/ConversationSidebar";
import MessageThread from "@/app/components/MessageThread";
import ChatComposer from "@/app/components/ChatComposer";
import type { Message, ConversationItem } from "@/app/types/chat";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

const DEFAULT_MODEL = "gpt-5-nano";
const FALLBACK_MODELS = [{ id: "gpt-5-nano", label: "GPT-5 nano · fast" }];

const WELCOME_MESSAGE =
  "Hi — I'm Podium. I can search the web and synthesize results, remember context across our conversations, run Python code in a sandbox, and search documents you upload. What are you working on?";

type ErrorKind = "byok" | "limit" | "server" | "stream" | "network";

const ERROR_COPY: Record<ErrorKind, string> = {
  byok: "Add your API key in Settings to chat. Or sign out and try Podium as a guest.",
  limit: "You've reached the guest message limit. Sign up to keep chatting.",
  server: "Something went wrong on our end. Please try again in a moment.",
  stream: "", // SSE error fills from data.detail
  network: "Connection lost. Please check your network and try again.",
};

const MAX_POLL_ATTEMPTS = 60;

export default function ChatPage() {
  const authFetch = useAuthFetch();
  const [messages, setMessages] = useState<Message[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [isThinking, setIsThinking] = useState(false);
  const [conversationId, setConversationId] = useState<string | null>(null);
  const [uploadStatus, setUploadStatus] = useState<string | null>(null);
  const [darkMode, setDarkMode] = useState(false);
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [conversations, setConversations] = useState<ConversationItem[]>([]);
  const [selectedModel, setSelectedModel] = useState(DEFAULT_MODEL);
  const [selectedEffort, setSelectedEffort] = useState<"fast" | "balanced" | "thorough">("balanced");
  const [availableModels, setAvailableModels] = useState(FALLBACK_MODELS);
  const [isGuest, setIsGuest] = useState(false);
  const [byokError, setByokError] = useState(false);
  const [byokCopy, setByokCopy] = useState(ERROR_COPY.byok);
  const [showByokModal, setShowByokModal] = useState(false);
  const hasWelcomed = useRef(false);
  const hasShownByokModal = useRef(false);
  const uploadPollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const { isSignedIn, isLoaded } = useAuth();

  useEffect(() => {
    try {
      const stored = localStorage.getItem("theme");
      if (stored === "dark") {
        setDarkMode(true);
        document.documentElement.setAttribute("data-theme", "dark");
      }
      const storedModel = localStorage.getItem("selectedModel");
      if (storedModel) setSelectedModel(storedModel);
      // Phase 10: read persisted effort level
      const storedEffort = localStorage.getItem("selectedEffort");
      if (storedEffort === "fast" || storedEffort === "balanced" || storedEffort === "thorough") {
        setSelectedEffort(storedEffort);
      }
    } catch {
      // private browsing
    }
    // Fetch available base models (unauthenticated). Ollama models are fetched in the
    // isSignedIn effect — authFetch requires Clerk to have hydrated first.
    void (async () => { try {
      const res = await fetch(`${API_URL}/chat/models`);
      if (!res.ok) return;
      const baseModels = await res.json();
      setAvailableModels(baseModels);
      const stored = localStorage.getItem("selectedModel");
      if (stored && baseModels.some((m: { id: string }) => m.id === stored)) {
        setSelectedModel(stored);
      } else if (stored) {
        setSelectedModel(DEFAULT_MODEL);
        try { localStorage.removeItem("selectedModel"); } catch {}
      }
    } catch {} })();
    // Open sidebar by default on wider screens
    if (window.innerWidth >= 768) setSidebarOpen(true);
  }, []);

  // Gate guest detection on isLoaded so we never read isSignedIn while Clerk
  // is still hydrating (at that point isSignedIn === undefined, and !undefined
  // is true, which would incorrectly mark signed-in users as guests).
  useEffect(() => {
    if (!isLoaded) return;
    if (isSignedIn) return;
    try {
      const guestToken = sessionStorage.getItem("podium_guest_token");
      const guestExpires = sessionStorage.getItem("podium_guest_expires");
      if (guestToken && guestExpires && new Date(guestExpires) > new Date()) {
        setIsGuest(true);
      }
    } catch { /* sessionStorage unavailable */ }
  }, [isLoaded, isSignedIn]);

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
    if (isLoaded) fetchConversations();
  }, [isLoaded, fetchConversations]);

  // Reactive guest cleanup: when Clerk confirms sign-in, clear guest state and
  // reload conversation list so sidebar populates without a page refresh.
  useEffect(() => {
    if (isSignedIn) {
      setIsGuest(false);
      try {
        sessionStorage.removeItem("podium_guest_token");
        sessionStorage.removeItem("podium_guest_expires");
      } catch { /* sessionStorage unavailable */ }
      fetchConversations();
      // Phase 10 (OLL-01): fetch Ollama models now that Clerk has confirmed auth.
      // D-03: removed the inner `if (!isGuest)` guard — isGuest may still be true in
      // this closure because setIsGuest(false) is async. The outer `if (isSignedIn)`
      // is the correct and sufficient guard.
      void (async () => {
        try {
          const ollamaRes = await authFetch(`${API_URL}/chat/ollama-models`);
          if (ollamaRes.ok) {
            const ollamaModels = await ollamaRes.json();
            if (ollamaModels.length > 0) {
              setAvailableModels((prev) => {
                const base = prev.filter((m: { id: string }) => !m.id.startsWith("ollama/"));
                return [...base, ...ollamaModels];
              });
            }
          }
        } catch {}
      })();
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isSignedIn, fetchConversations, authFetch]);

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
    try {
      const res = await authFetch(`${API_URL}/chat/${id}`, { method: "DELETE" });
      if (!res.ok) return;
      setConversations((prev) => prev.filter((c) => c.id !== id));
      if (conversationId === id) startNewConversation();
    } catch {
      // sidebar is non-critical — swallow network errors silently
    }
  };

  const handleRenameConversation = async (id: string, newTitle: string) => {
    try {
      const res = await authFetch(`${API_URL}/chat/${id}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ title: newTitle }),
      });
      if (!res.ok) return;
      setConversations((prev) =>
        prev.map((c) => (c.id === id ? { ...c, title: newTitle } : c))
      );
    } catch {
      // rename is non-critical — swallow errors silently
    }
  };

  const loadConversation = async (id: string) => {
    try {
      const res = await authFetch(`${API_URL}/chat/${id}`);
      if (!res.ok) return;
      const data = await res.json();
      const msgs: Message[] = (data.messages as { role: string; content: string }[])
        .filter((m) => m.role === "user" || m.role === "assistant")
        .map((m) => ({ role: m.role as "user" | "assistant", content: m.content }));
      setMessages(msgs.length > 0 ? msgs : [{ role: "assistant", content: WELCOME_MESSAGE }]);
      setConversationId(id);
      // Close sidebar on mobile after selecting
      if (window.innerWidth < 768) setSidebarOpen(false);
    } catch {
      // keep current conversation
    }
  };

  const submitMessage = async (userMessage: string) => {
    if (!userMessage.trim() || isLoading) return;

    // D-05: clear stale 402 error state before each new send attempt
    setByokError(false);

    setMessages((prev) => [...prev, { role: "user", content: userMessage }]);
    setIsLoading(true);
    setIsThinking(true);

    let response: Response;
    try {
      response = await authFetch(`${API_URL}/chat/stream`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message: userMessage, conversation_id: conversationId, model: selectedModel, effort: selectedEffort }),
      });
    } catch {
      setMessages((prev) => [...prev, { role: "error", kind: "network", content: ERROR_COPY.network }]);
      setIsThinking(false);
      setIsLoading(false);
      return;
    }

    if (response.status === 402) {
      let copy = ERROR_COPY.byok;
      try {
        const body = await response.json();
        if (body?.detail?.message) copy = body.detail.message;
      } catch { /* use generic copy */ }
      setByokCopy(copy);
      setMessages((prev) => [...prev, { role: "error", kind: "byok", content: copy }]);
      // D-06: show modal on the FIRST 402 per session; inline banner only for subsequent ones
      if (!hasShownByokModal.current) {
        hasShownByokModal.current = true;
        setShowByokModal(true);
      } else {
        setByokError(true);
      }
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
                // eslint-disable-next-line @typescript-eslint/no-explicit-any
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
                  setIsThinking(true);
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

  const handleCardClick = (prompt: string) => {
    submitMessage(prompt);
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
      <ConversationSidebar
        isOpen={sidebarOpen}
        onClose={() => setSidebarOpen(false)}
        conversations={conversations}
        activeConversationId={conversationId}
        onNewConversation={startNewConversation}
        onSelectConversation={loadConversation}
        onDeleteConversation={handleDeleteConversation}
        onRenameConversation={handleRenameConversation}
      />

      {/* Main area */}
      <div className="flex flex-col flex-1 min-w-0">
        {isGuest && (
          <div className="text-center text-sm py-2 px-4" style={{ background: "var(--bg-subtle, #f0f9ff)", color: "var(--text-secondary, #555)" }}>
            Guest session — your data will be deleted in 24 hours.{" "}
            <a href="/sign-up" className="underline font-medium">Sign up</a> to keep your work.
          </div>
        )}
        {/* D-06: BYOK modal — first 402 per session shows this; subsequent 402s show the banner below */}
        {showByokModal && (
          <div
            className="fixed inset-0 z-50 flex items-center justify-center"
            style={{ background: "rgba(0,0,0,0.4)" }}
            onClick={() => setShowByokModal(false)}
          >
            <div
              className="rounded-xl px-8 py-6 max-w-sm w-full"
              style={{ background: "var(--bg-elevated)" }}
              onClick={(e) => e.stopPropagation()}
            >
              <h2 className="text-lg font-semibold mb-2" style={{ color: "var(--text-primary)" }}>
                Add your API key to continue
              </h2>
              <p className="text-sm mb-4" style={{ color: "var(--text-muted)" }}>
                Podium uses your own API key — nothing is stored on our servers after your messages are processed. Add a key in Settings to start chatting.
              </p>
              <div className="flex gap-3">
                <a
                  href="/settings"
                  className="flex-1 text-center px-4 py-2 rounded-lg text-sm font-medium"
                  style={{ background: "var(--accent-warm)", color: "#fff" }}
                >
                  Go to Settings
                </a>
                <button
                  onClick={() => setShowByokModal(false)}
                  className="px-4 py-2 rounded-lg text-sm"
                  style={{ background: "var(--bg-surface)", color: "var(--text-muted)" }}
                >
                  Dismiss
                </button>
              </div>
            </div>
          </div>
        )}
        {byokError && (
          <div className="text-center text-sm py-2 px-4" style={{ background: "var(--bg-subtle, #fff8e1)", color: "var(--text-secondary, #555)" }}>
            {byokCopy}{" "}
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
                className="md:hidden w-7 h-7 flex items-center justify-center rounded text-sm transition-opacity hover:opacity-70"
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
              <select
                value={selectedEffort}
                onChange={(e) => {
                  setSelectedEffort(e.target.value as "fast" | "balanced" | "thorough");
                  try { localStorage.setItem("selectedEffort", e.target.value); } catch {}
                }}
                disabled={isLoading || isGuest}
                aria-label={isGuest ? "Effort selection unavailable for guest accounts" : "Select effort level"}
                title={isGuest ? "Effort selection unavailable for guest accounts" : undefined}
                className="text-xs rounded px-2 py-1 focus:outline-none transition-opacity disabled:opacity-50"
                style={{
                  background: "var(--bg-elevated)",
                  border: "1px solid var(--border)",
                  color: "var(--text-muted)",
                }}
              >
                <option value="fast">Fast</option>
                <option value="balanced">Balanced</option>
                <option value="thorough">Thorough</option>
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

          <MessageThread
            messages={messages}
            isThinking={isThinking}
            showCapabilityCards={showCapabilityCards}
            onCardClick={handleCardClick}
            isGuest={isGuest}
          />

          <ChatComposer
            key={conversationId ?? "new"}
            isLoading={isLoading}
            isGuest={isGuest}
            onSubmit={submitMessage}
          />
        </main>
      </div>
    </div>
  );
}
