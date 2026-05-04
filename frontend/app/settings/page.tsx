"use client";

import { useState, useEffect, useRef } from "react";
import { UserButton } from "@clerk/nextjs";
import { useAuthFetch } from "@/app/hooks/useAuthFetch";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

interface ApiKeyInfo {
  id: string;
  provider: string;
  key_hint: string;
  is_active: boolean;
  created_at: string;
}

interface MemoryInfo {
  id: string;
  category: string;
  content: string;
  is_active: boolean;
  edited_by_user: boolean;
  created_at: string;
  updated_at: string;
}

export default function SettingsPage() {
  const authFetch = useAuthFetch();

  // API keys state
  const [keys, setKeys] = useState<ApiKeyInfo[]>([]);
  const [provider, setProvider] = useState("openai");
  const [apiKey, setApiKey] = useState("");
  const [keyStatus, setKeyStatus] = useState<string | null>(null);

  // Memories state
  const [memories, setMemories] = useState<MemoryInfo[]>([]);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editContent, setEditContent] = useState("");
  const [newCategory, setNewCategory] = useState("preference");
  const [newContent, setNewContent] = useState("");
  const [categoryFilter, setCategoryFilter] = useState<string>("all");
  const [memoryStatus, setMemoryStatus] = useState<string | null>(null);
  const memoryStatusTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  // --- API Keys ---

  const loadKeys = async () => {
    const res = await authFetch(`${API_URL}/keys/`);
    if (res.ok) setKeys(await res.json());
  };

  const handleAddKey = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!apiKey.trim()) return;

    setKeyStatus("Saving...");
    const res = await authFetch(`${API_URL}/keys/`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ provider, api_key: apiKey }),
    });
    if (res.ok) {
      setKeyStatus("Key saved");
      setApiKey("");
      loadKeys();
    } else {
      setKeyStatus("Failed to save key");
    }
  };

  const handleDeleteKey = async (keyId: string) => {
    const res = await authFetch(`${API_URL}/keys/${keyId}`, { method: "DELETE" });
    if (res.ok) {
      loadKeys();
    } else {
      setKeyStatus("Failed to remove key");
    }
  };

  const showMemoryStatus = (msg: string) => {
    if (memoryStatusTimeoutRef.current) clearTimeout(memoryStatusTimeoutRef.current);
    setMemoryStatus(msg);
    memoryStatusTimeoutRef.current = setTimeout(() => setMemoryStatus(null), 3000);
  };

  // --- Memories ---

  const loadMemories = async () => {
    const url =
      categoryFilter === "all"
        ? `${API_URL}/memories/`
        : `${API_URL}/memories/?category=${categoryFilter}`;
    const res = await authFetch(url);
    if (res.ok) setMemories(await res.json());
  };

  const handleAddMemory = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newContent.trim()) return;

    const res = await authFetch(`${API_URL}/memories/`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ category: newCategory, content: newContent }),
    });
    if (res.ok) {
      setNewContent("");
      loadMemories();
      showMemoryStatus("Memory added");
    } else {
      showMemoryStatus("Failed to add memory");
    }
  };

  const handleUpdateMemory = async (memoryId: string) => {
    if (!editContent.trim()) return;
    const res = await authFetch(`${API_URL}/memories/${memoryId}`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ content: editContent }),
    });
    if (res.ok) {
      setEditingId(null);
      setEditContent("");
      loadMemories();
      showMemoryStatus("Memory updated");
    } else {
      showMemoryStatus("Failed to update memory");
    }
  };

  const handleDeleteMemory = async (memoryId: string) => {
    setMemories((prev) => prev.filter((m) => m.id !== memoryId));
    const res = await authFetch(`${API_URL}/memories/${memoryId}`, {
      method: "DELETE",
    });
    if (!res.ok) {
      await loadMemories();
      showMemoryStatus("Failed to delete memory");
    }
  };

  const handleDeleteAllMemories = async () => {
    if (!confirm("Delete ALL memories? This cannot be undone.")) return;
    setMemories([]);
    const res = await authFetch(`${API_URL}/memories/`, { method: "DELETE" });
    if (res.ok) {
      showMemoryStatus("All memories deleted");
    } else {
      await loadMemories();
      showMemoryStatus("Failed to delete memories");
    }
  };

  useEffect(() => {
    loadKeys();
    // loadMemories is called by the categoryFilter effect on mount and on filter changes
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    return () => {
      if (memoryStatusTimeoutRef.current) clearTimeout(memoryStatusTimeoutRef.current);
    };
  }, []);

  useEffect(() => {
    loadMemories();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [categoryFilter]);

  const startEditing = (memory: MemoryInfo) => {
    setEditingId(memory.id);
    setEditContent(memory.content);
  };

  return (
    <main className="max-w-3xl mx-auto p-8">
      <div className="flex items-center justify-between mb-8">
        <h1 className="text-2xl font-semibold" style={{ color: "var(--text-primary)" }}>
          Settings
        </h1>
        <div className="flex items-center gap-3">
          <a
            href="/"
            className="text-sm transition-colors"
            style={{ color: "var(--text-muted)" }}
          >
            Back to Chat
          </a>
          <UserButton />
        </div>
      </div>

      {/* --- API Keys --- */}
      <section className="mb-12">
        <h2 className="text-lg font-medium mb-4" style={{ color: "var(--text-primary)" }}>
          API Keys
        </h2>
        <p className="text-sm mb-4" style={{ color: "var(--text-muted)" }}>
          Add your own API keys to use your preferred model provider. Keys are
          encrypted at rest and never shown after saving.
        </p>

        <form onSubmit={handleAddKey} className="flex gap-2 mb-4">
          <select
            value={provider}
            onChange={(e) => { setProvider(e.target.value); setApiKey(""); }}
            className="rounded-lg px-3 py-2 text-sm"
            style={{
              background: "var(--bg-surface)",
              border: "1px solid var(--border)",
              color: "var(--text-primary)",
            }}
          >
            <option value="openai">OpenAI</option>
            <option value="anthropic">Anthropic</option>
            <option value="ollama">Ollama</option>
          </select>
          <input
            type={provider === "ollama" ? "text" : "password"}
            value={apiKey}
            onChange={(e) => setApiKey(e.target.value)}
            placeholder={provider === "ollama" ? "http://host.docker.internal:11434" : "sk-..."}
            className="flex-1 rounded-lg px-4 py-2 text-sm focus:outline-none"
            style={{
              background: "var(--bg-surface)",
              border: "1px solid var(--border)",
              color: "var(--text-primary)",
            }}
          />
          <button
            type="submit"
            className="px-4 py-2 rounded-lg text-sm font-medium transition-opacity hover:opacity-80"
            style={{ background: "var(--accent-warm)", color: "#fff" }}
          >
            {provider === "ollama" ? "Save URL" : "Save Key"}
          </button>
        </form>

        {provider === "ollama" && (
          <p className="text-xs mb-2" style={{ color: "var(--text-muted)" }}>
            The backend runs in Docker — use <code>host.docker.internal</code> instead of <code>localhost</code>. Models are detected automatically from your Ollama server.
          </p>
        )}

        {keyStatus && (
          <p className="text-sm mb-4" style={{ color: "var(--text-muted)" }}>
            {keyStatus}
          </p>
        )}

        {keys.length > 0 ? (
          <div className="space-y-2">
            {keys.map((key) => (
              <div
                key={key.id}
                className="flex items-center justify-between rounded-lg px-4 py-3"
                style={{
                  background: "var(--bg-surface)",
                  border: "1px solid var(--border)",
                }}
              >
                <div>
                  <span className="font-medium capitalize" style={{ color: "var(--text-primary)" }}>
                    {key.provider}
                  </span>
                  <span className="ml-2 font-mono text-sm" style={{ color: "var(--text-muted)" }}>
                    {key.key_hint}
                  </span>
                </div>
                <button
                  onClick={() => handleDeleteKey(key.id)}
                  className="text-sm transition-opacity hover:opacity-70"
                  style={{ color: "#b91c1c" }}
                >
                  Remove
                </button>
              </div>
            ))}
          </div>
        ) : (
          <p className="text-sm" style={{ color: "var(--text-muted)" }}>
            No API keys configured. Using system default.
          </p>
        )}
      </section>

      {/* --- Memories --- */}
      <section>
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-lg font-medium" style={{ color: "var(--text-primary)" }}>
            Memories
          </h2>
          {memories.length > 0 && (
            <button
              onClick={handleDeleteAllMemories}
              className="text-sm transition-opacity hover:opacity-70"
              style={{ color: "#b91c1c" }}
            >
              Delete all memories
            </button>
          )}
        </div>

        <p className="text-sm mb-4" style={{ color: "var(--text-muted)" }}>
          Things the AI has learned about you. Facts and preferences are always
          included in conversations; context memories are retrieved when relevant.
        </p>

        {/* Filter */}
        <div className="flex gap-2 mb-4">
          {["all", "fact", "preference", "context"].map((cat) => (
            <button
              key={cat}
              onClick={() => setCategoryFilter(cat)}
              className="px-3 py-1.5 rounded-full text-sm transition-colors"
              style={
                categoryFilter === cat
                  ? { background: "var(--accent-warm)", color: "#fff" }
                  : { background: "var(--bg-elevated)", color: "var(--text-muted)" }
              }
            >
              {cat === "all" ? "All" : cat.charAt(0).toUpperCase() + cat.slice(1) + "s"}
            </button>
          ))}
        </div>

        {/* Add new memory */}
        <form onSubmit={handleAddMemory} className="flex gap-2 mb-6">
          <select
            value={newCategory}
            onChange={(e) => setNewCategory(e.target.value)}
            className="rounded-lg px-3 py-2 text-sm"
            style={{
              background: "var(--bg-surface)",
              border: "1px solid var(--border)",
              color: "var(--text-primary)",
            }}
          >
            <option value="fact">Fact</option>
            <option value="preference">Preference</option>
            <option value="context">Context</option>
          </select>
          <input
            type="text"
            value={newContent}
            onChange={(e) => setNewContent(e.target.value)}
            placeholder="e.g., User prefers dark mode"
            className="flex-1 rounded-lg px-4 py-2 text-sm focus:outline-none"
            style={{
              background: "var(--bg-surface)",
              border: "1px solid var(--border)",
              color: "var(--text-primary)",
            }}
          />
          <button
            type="submit"
            className="px-4 py-2 rounded-lg text-sm font-medium transition-opacity hover:opacity-80"
            style={{ background: "var(--accent-warm)", color: "#fff" }}
          >
            Add
          </button>
        </form>

        {memoryStatus && (
          <p
            className="text-sm mt-1"
            style={{
              color: memoryStatus.startsWith("Failed") ? "#b91c1c" : "var(--text-muted)",
            }}
          >
            {memoryStatus}
          </p>
        )}

        {memories.length === 0 ? (
          <p className="text-sm" style={{ color: "var(--text-muted)" }}>
            No memories yet. They&apos;ll be extracted from your conversations.
          </p>
        ) : (
          <div className="space-y-2">
            {memories.map((mem) => (
              <div
                key={mem.id}
                className="rounded-lg px-4 py-3"
                style={{
                  background: "var(--bg-surface)",
                  border: "1px solid var(--border)",
                }}
              >
                <div className="flex items-start justify-between gap-3">
                  <div className="flex-1">
                    <div className="flex items-center gap-2 mb-1">
                      <span
                        className="text-xs px-2 py-0.5 rounded"
                        style={
                          mem.category === "fact"
                            ? { background: "#dbeafe", color: "#1d4ed8" }
                            : mem.category === "preference"
                            ? { background: "#dcfce7", color: "#15803d" }
                            : { background: "#f3e8ff", color: "#7e22ce" }
                        }
                      >
                        {mem.category}
                      </span>
                      {mem.edited_by_user && (
                        <span className="text-xs" style={{ color: "var(--text-muted)" }}>
                          (edited)
                        </span>
                      )}
                    </div>
                    {editingId === mem.id ? (
                      <div className="flex gap-2 mt-2">
                        <input
                          type="text"
                          value={editContent}
                          onChange={(e) => setEditContent(e.target.value)}
                          className="flex-1 rounded px-2 py-1 text-sm focus:outline-none"
                          style={{
                            background: "var(--bg-elevated)",
                            border: "1px solid var(--border)",
                            color: "var(--text-primary)",
                          }}
                          autoFocus
                        />
                        <button
                          onClick={() => handleUpdateMemory(mem.id)}
                          className="px-3 py-1 rounded text-sm font-medium transition-opacity hover:opacity-80"
                          style={{ background: "var(--accent-warm)", color: "#fff" }}
                        >
                          Save
                        </button>
                        <button
                          onClick={() => setEditingId(null)}
                          className="px-3 py-1 rounded text-sm transition-colors"
                          style={{
                            background: "var(--bg-elevated)",
                            color: "var(--text-muted)",
                          }}
                        >
                          Cancel
                        </button>
                      </div>
                    ) : (
                      <p className="text-sm" style={{ color: "var(--text-primary)" }}>
                        {mem.content}
                      </p>
                    )}
                  </div>
                  {editingId !== mem.id && (
                    <div className="flex gap-2">
                      <button
                        onClick={() => startEditing(mem)}
                        className="text-sm transition-colors"
                        style={{ color: "var(--text-muted)" }}
                      >
                        Edit
                      </button>
                      <button
                        onClick={() => handleDeleteMemory(mem.id)}
                        className="text-sm transition-opacity hover:opacity-70"
                        style={{ color: "#b91c1c" }}
                      >
                        Delete
                      </button>
                    </div>
                  )}
                </div>
              </div>
            ))}
          </div>
        )}
      </section>
    </main>
  );
}
