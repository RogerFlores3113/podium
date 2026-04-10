"use client";

import { useState, useRef, useEffect } from "react";
import { useAuth, UserButton } from "@clerk/nextjs";
const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

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

  const icon = {
    web_search: "🔍",
    document_search: "📄",
    python_executor: "🐍",
  }[toolCall.name] || "🔧";

  const statusColor = {
    running: "text-yellow-600",
    done: "text-green-600",
    error: "text-red-600",
  }[toolCall.status];

  const statusText = {
    running: "running...",
    done: "done",
    error: "error",
  }[toolCall.status];

  // Try to parse arguments for display
  let argsDisplay = toolCall.arguments;
  try {
    const parsed = JSON.parse(toolCall.arguments);
    argsDisplay = JSON.stringify(parsed, null, 2);
  } catch {
    // Keep as-is if not valid JSON yet (still streaming)
  }

  return (
    <div className="border rounded-lg bg-gray-50 overflow-hidden">
      <button
        onClick={() => setExpanded(!expanded)}
        className="w-full px-4 py-2 flex items-center justify-between hover:bg-gray-100 text-left"
      >
        <div className="flex items-center gap-2 text-sm">
          <span>{icon}</span>
          <span className="font-mono">{toolCall.name}</span>
          <span className={statusColor}>{statusText}</span>
        </div>
        <span className="text-gray-400 text-xs">{expanded ? "▼" : "▶"}</span>
      </button>
      {expanded && (
        <div className="px-4 py-2 border-t text-xs space-y-2">
          <div>
            <div className="text-gray-500 mb-1">Arguments:</div>
            <pre className="bg-white p-2 rounded border overflow-x-auto">
              {argsDisplay}
            </pre>
          </div>
          {toolCall.result && (
            <div>
              <div className="text-gray-500 mb-1">Result:</div>
              <pre className="bg-white p-2 rounded border overflow-x-auto max-h-48 overflow-y-auto whitespace-pre-wrap">
                {toolCall.result}
              </pre>
            </div>
          )}
          {toolCall.error && (
            <div>
              <div className="text-red-500 mb-1">Error:</div>
              <pre className="bg-red-50 p-2 rounded border border-red-200 overflow-x-auto">
                {toolCall.error}
              </pre>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

export default function Home() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [conversationId, setConversationId] = useState<string | null>(null);
  const [uploadStatus, setUploadStatus] = useState<string | null>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const { getToken } = useAuth();

  const authFetch = async (url: string, options: RequestInit = {}) => {
    const token = await getToken();
    return fetch(url, {
      ...options,
      headers: {
        ...options.headers,
        Authorization: `Bearer ${token}`,
      },
    });
  };

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!input.trim() || isLoading) return;

    const userMessage = input.trim();
    setInput("");
    setMessages((prev) => [...prev, { role: "user", content: userMessage }]);
    setIsLoading(true);

    // Add an empty assistant message that we'll stream into
    setMessages((prev) => [...prev, { role: "assistant", content: "" }]);

try {
  const response = await authFetch(`${API_URL}/chat/stream`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      message: userMessage,
      conversation_id: conversationId,
    }),
  });

  const reader = response.body?.getReader();
  const decoder = new TextDecoder();
  if (!reader) throw new Error("No reader available");

  let buffer = "";

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;

    buffer += decoder.decode(value, { stream: true });

    // Split on \r\n\r\n (the actual delimiter from sse-starlette)
    const parts = buffer.split("\r\n\r\n");
    buffer = parts.pop() || "";

    for (const part of parts) {
      if (!part.trim()) continue;
      const lines = part.split("\r\n");
      let eventType = "";
      let eventData = "";

      let currentEvent = "";
        for (const line of lines) {
          if (line.startsWith("event: ")) {
            currentEvent = line.slice(7).trim();
          } else if (line.startsWith("data: ")) {
            const data = JSON.parse(line.slice(6));

            if (currentEvent === "token") {
              setMessages((prev) => {
                const updated = [...prev];
                const last = updated[updated.length - 1];
                if (last.role === "assistant") {
                  updated[updated.length - 1] = {
                    ...last,
                    content: last.content + data.token,
                  };
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
                  const updatedToolCalls = last.toolCalls.map((tc) =>
                    tc.id === data.id
                      ? { ...tc, result: data.result, status: "done" as const }
                      : tc
                  );
                  updated[updated.length - 1] = {
                    ...last,
                    toolCalls: updatedToolCalls,
                  };
                }
                return updated;
              });
              // Start a new assistant message for the next iteration's text
              setMessages((prev) => [
                ...prev,
                { role: "assistant", content: "" },
              ]);
            } else if (currentEvent === "tool_call_error") {
              setMessages((prev) => {
                const updated = [...prev];
                const last = updated[updated.length - 1];
                if (last.role === "assistant" && last.toolCalls) {
                  const updatedToolCalls = last.toolCalls.map((tc) =>
                    tc.id === data.id
                      ? { ...tc, error: data.error, status: "error" as const }
                      : tc
                  );
                  updated[updated.length - 1] = {
                    ...last,
                    toolCalls: updatedToolCalls,
                  };
                }
                return updated;
              });
              setMessages((prev) => [
                ...prev,
                { role: "assistant", content: "" },
              ]);
            } else if (currentEvent === "done") {
              setConversationId(data.conversation_id);
            } else if (currentEvent === "conversation") {
              setConversationId(data.conversation_id);
            }
          }
        }

      if (!eventData) continue;

      const data = JSON.parse(eventData);

      if (eventType === "token") {
        setMessages((prev) => {
          const updated = [...prev];
          const last = updated[updated.length - 1];
          if (last.role === "assistant") {
            updated[updated.length - 1] = {
              ...last,
              content: last.content + data.token,
            };
          }
          return updated;
        });
      } else if (eventType === "done") {
        setConversationId(data.conversation_id);
      }
    }
  }
}
    
    catch (error) {
      console.error("Chat error:", error);
      setMessages((prev) => {
        const updated = [...prev];
        const last = updated[updated.length - 1];
        if (last.role === "assistant") {
          last.content = "Error: Failed to get response. Is the backend running?";
        }
        return updated;
      });
    }

    setIsLoading(false);
  };

  const handleUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    setUploadStatus("Uploading...");

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

      // Poll for completion
      const pollInterval = setInterval(async () => {
        const statusRes = await authFetch(`${API_URL}/documents/${doc.id}`);
        const statusDoc = await statusRes.json();

        if (statusDoc.status === "ready") {
          setUploadStatus(`Ready: ${statusDoc.filename} (${statusDoc.page_count} pages)`);
          clearInterval(pollInterval);
        } else if (statusDoc.status === "failed") {
          setUploadStatus(`Failed: ${statusDoc.filename}`);
          clearInterval(pollInterval);
        }
      }, 1000);
    } catch (error) {
      setUploadStatus("Upload failed — is the backend running?");
    }

    // Reset file input
    e.target.value = "";
  };

  return (
    <main className="flex flex-col h-screen max-w-3xl mx-auto p-4">
      {/* Header */}
      <div className="flex items-center justify-between mb-4 pb-4 border-b">
        <h1 className="text-xl font-semibold">AI Assistant</h1>
        <div className="flex items-center gap-3">
          {uploadStatus && (
            <span className="text-sm text-gray-500">{uploadStatus}</span>
          )}
          <label className="cursor-pointer bg-gray-100 hover:bg-gray-200 px-3 py-1.5 rounded text-sm">
            Upload PDF
            <input
              type="file"
              accept=".pdf"
              onChange={handleUpload}
              className="hidden"
            />
          </label>
          <a href="/settings" className="text-sm text-gray-600 hover:text-gray-900">
            Settings
          </a>
          <UserButton />
        </div>
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto space-y-4 mb-4">
        {messages.length === 0 && (
          <div className="text-center text-gray-400 mt-20">
            <p className="text-lg">Upload a document and start asking questions.</p>
          </div>
        )}
        {messages.map((msg, i) => (
          <div key={i}>
            {/* Text content */}
            {msg.content && (
              <div
                className={`flex ${
                  msg.role === "user" ? "justify-end" : "justify-start"
                } mb-2`}
              >
                <div
                  className={`max-w-[80%] rounded-lg px-4 py-2 ${
                    msg.role === "user"
                      ? "bg-blue-600 text-white"
                      : "bg-gray-100 text-gray-900"
                  }`}
                >
                  <p className="whitespace-pre-wrap">{msg.content}</p>
                </div>
              </div>
            )}

            {/* Tool calls */}
            {msg.toolCalls && msg.toolCalls.length > 0 && (
              <div className="space-y-2 my-2">
                {msg.toolCalls.map((tc) => (
                  <ToolCallDisplay key={tc.id} toolCall={tc} />
                ))}
              </div>
            )}
          </div>
        ))}
        <div ref={messagesEndRef} />
      </div>

      {/* Input */}
      <form onSubmit={handleSubmit} className="flex gap-2">
        <input
          type="text"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="Ask a question about your documents..."
          className="flex-1 border rounded-lg px-4 py-2 focus:outline-none focus:ring-2 focus:ring-blue-500"
          disabled={isLoading}
        />
        <button
          type="submit"
          disabled={isLoading || !input.trim()}
          className="bg-blue-600 text-white px-4 py-2 rounded-lg hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed"
        >
          Send
        </button>
      </form>
    </main>
  );
}