"use client";

import { useState, useEffect } from "react";
import { useAuth, UserButton } from "@clerk/nextjs";

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
  const { getToken } = useAuth();

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
    if (res.ok) loadKeys();
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
    }
  };

  const handleDeleteMemory = async (memoryId: string) => {
    const res = await authFetch(`${API_URL}/memories/${memoryId}`, {
      method: "DELETE",
    });
    if (res.ok) loadMemories();
  };

  const handleDeleteAllMemories = async () => {
    if (!confirm("Delete ALL memories? This cannot be undone.")) return;
    const res = await authFetch(`${API_URL}/memories/`, { method: "DELETE" });
    if (res.ok) loadMemories();
  };

  useEffect(() => {
    loadKeys();
    loadMemories();
  // eslint-disable-next-line react-hooks/exhaustive-deps
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
        <h1 className="text-2xl font-semibold">Settings</h1>
        <div className="flex items-center gap-3">
          <a href="/" className="text-sm text-gray-600 hover:text-gray-900">
            Back to Chat
          </a>
          <UserButton />
        </div>
      </div>

      {/* --- API Keys --- */}
      <section className="mb-12">
        <h2 className="text-lg font-medium mb-4">API Keys</h2>
        <p className="text-sm text-gray-500 mb-4">
          Add your own API keys to use your preferred model provider. Keys are
          encrypted at rest and never shown after saving.
        </p>

        <form onSubmit={handleAddKey} className="flex gap-2 mb-4">
          <select
            value={provider}
            onChange={(e) => setProvider(e.target.value)}
            className="border rounded-lg px-3 py-2"
          >
            <option value="openai">OpenAI</option>
            <option value="anthropic">Anthropic</option>
            <option value="ollama">Ollama</option>
          </select>
          <input
            type="password"
            value={apiKey}
            onChange={(e) => setApiKey(e.target.value)}
            placeholder="sk-..."
            className="flex-1 border rounded-lg px-4 py-2"
          />
          <button
            type="submit"
            className="bg-blue-600 text-white px-4 py-2 rounded-lg hover:bg-blue-700"
          >
            Save Key
          </button>
        </form>

        {keyStatus && <p className="text-sm text-gray-500 mb-4">{keyStatus}</p>}

        {keys.length > 0 ? (
          <div className="space-y-2">
            {keys.map((key) => (
              <div
                key={key.id}
                className="flex items-center justify-between border rounded-lg px-4 py-3"
              >
                <div>
                  <span className="font-medium capitalize">{key.provider}</span>
                  <span className="text-gray-400 ml-2 font-mono text-sm">
                    {key.key_hint}
                  </span>
                </div>
                <button
                  onClick={() => handleDeleteKey(key.id)}
                  className="text-red-500 hover:text-red-700 text-sm"
                >
                  Remove
                </button>
              </div>
            ))}
          </div>
        ) : (
          <p className="text-sm text-gray-400">
            No API keys configured. Using system default.
          </p>
        )}
      </section>

      {/* --- Memories --- */}
      <section>
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-lg font-medium">Memories</h2>
          {memories.length > 0 && (
            <button
              onClick={handleDeleteAllMemories}
              className="text-red-500 hover:text-red-700 text-sm"
            >
              Delete all memories
            </button>
          )}
        </div>

        <p className="text-sm text-gray-500 mb-4">
          Things the AI has learned about you. Facts and preferences are always
          included in conversations; context memories are retrieved when relevant.
        </p>

        {/* Filter */}
        <div className="flex gap-2 mb-4">
          {["all", "fact", "preference", "context"].map((cat) => (
            <button
              key={cat}
              onClick={() => setCategoryFilter(cat)}
              className={`px-3 py-1.5 rounded-full text-sm ${
                categoryFilter === cat
                  ? "bg-blue-600 text-white"
                  : "bg-gray-100 text-gray-700 hover:bg-gray-200"
              }`}
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
            className="border rounded-lg px-3 py-2 text-sm"
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
            className="flex-1 border rounded-lg px-4 py-2 text-sm"
          />
          <button
            type="submit"
            className="bg-blue-600 text-white px-4 py-2 rounded-lg hover:bg-blue-700 text-sm"
          >
            Add
          </button>
        </form>

        {memories.length === 0 ? (
          <p className="text-sm text-gray-400">
            No memories yet. They&apos;ll be extracted from your conversations.
          </p>
        ) : (
          <div className="space-y-2">
            {memories.map((mem) => (
              <div key={mem.id} className="border rounded-lg px-4 py-3 bg-white">
                <div className="flex items-start justify-between gap-3">
                  <div className="flex-1">
                    <div className="flex items-center gap-2 mb-1">
                      <span
                        className={`text-xs px-2 py-0.5 rounded ${
                          mem.category === "fact"
                            ? "bg-blue-100 text-blue-700"
                            : mem.category === "preference"
                            ? "bg-green-100 text-green-700"
                            : "bg-purple-100 text-purple-700"
                        }`}
                      >
                        {mem.category}
                      </span>
                      {mem.edited_by_user && (
                        <span className="text-xs text-gray-400">(edited)</span>
                      )}
                    </div>
                    {editingId === mem.id ? (
                      <div className="flex gap-2 mt-2">
                        <input
                          type="text"
                          value={editContent}
                          onChange={(e) => setEditContent(e.target.value)}
                          className="flex-1 border rounded px-2 py-1 text-sm"
                          autoFocus
                        />
                        <button
                          onClick={() => handleUpdateMemory(mem.id)}
                          className="bg-blue-600 text-white px-3 py-1 rounded text-sm hover:bg-blue-700"
                        >
                          Save
                        </button>
                        <button
                          onClick={() => setEditingId(null)}
                          className="bg-gray-100 px-3 py-1 rounded text-sm hover:bg-gray-200"
                        >
                          Cancel
                        </button>
                      </div>
                    ) : (
                      <p className="text-sm text-gray-900">{mem.content}</p>
                    )}
                  </div>
                  {editingId !== mem.id && (
                    <div className="flex gap-2">
                      <button
                        onClick={() => startEditing(mem)}
                        className="text-sm text-gray-500 hover:text-gray-900"
                      >
                        Edit
                      </button>
                      <button
                        onClick={() => handleDeleteMemory(mem.id)}
                        className="text-sm text-red-500 hover:text-red-700"
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
