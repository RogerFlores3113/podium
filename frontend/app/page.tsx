"use client";

import { useState, useRef, useEffect } from "react";

interface Message {
  role: "user" | "assistant";
  content: string;
}

export default function Home() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [conversationId, setConversationId] = useState<string | null>(null);
  const [uploadStatus, setUploadStatus] = useState<string | null>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);

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
  const response = await fetch("http://localhost:8000/chat/stream", {
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

      for (const line of lines) {
        if (line.startsWith("event: ")) {
          eventType = line.slice(7).trim();
        } else if (line.startsWith("data: ")) {
          eventData = line.slice(6);
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
      const response = await fetch("http://localhost:8000/documents/upload", {
        method: "POST",
        body: formData,
      });

      if (!response.ok) throw new Error("Upload failed");

      const doc = await response.json();
      setUploadStatus(`Processing: ${doc.filename}`);

      // Poll for completion
      const pollInterval = setInterval(async () => {
        const statusRes = await fetch(`http://localhost:8000/documents/${doc.id}`);
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
          <div
            key={i}
            className={`flex ${msg.role === "user" ? "justify-end" : "justify-start"}`}
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