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

export default function SettingsPage() {
  const { getToken } = useAuth();
  const [keys, setKeys] = useState<ApiKeyInfo[]>([]);
  const [provider, setProvider] = useState("openai");
  const [apiKey, setApiKey] = useState("");
  const [status, setStatus] = useState<string | null>(null);

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

  const loadKeys = async () => {
    const res = await authFetch(`${API_URL}/keys/`);
    if (res.ok) {
      setKeys(await res.json());
    }
  };

  useEffect(() => {
    loadKeys();
  }, []);

  const handleAddKey = async (e: React.FormEvent) => {
    e.preventDefault();

    console.log("API_URL:", API_URL);
    if (!apiKey.trim()) return;

    setStatus("Saving...");

    const res = await authFetch(`${API_URL}/keys/`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ provider, api_key: apiKey }),
    });

    if (res.ok) {
      setStatus("Key saved successfully");
      setApiKey("");
      loadKeys();
    } else {
      setStatus("Failed to save key");
    }
  };

  const handleDeleteKey = async (keyId: string) => {
    const res = await authFetch(`${API_URL}/keys/${keyId}`, {
      method: "DELETE",
    });

    if (res.ok) {
      loadKeys();
    }
  };

  return (
    <main className="max-w-2xl mx-auto p-8">
      <div className="flex items-center justify-between mb-8">
        <h1 className="text-2xl font-semibold">Settings</h1>
        <div className="flex items-center gap-3">
          <a href="/" className="text-sm text-gray-600 hover:text-gray-900">
            Back to Chat
          </a>
          <UserButton />
        </div>
      </div>

      {/* Add API Key */}
      <section className="mb-8">
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

        {status && (
          <p className="text-sm text-gray-500 mb-4">{status}</p>
        )}

        {/* Existing Keys */}
        {keys.length > 0 && (
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
        )}

        {keys.length === 0 && (
          <p className="text-sm text-gray-400">
            No API keys configured. Using system default.
          </p>
        )}
      </section>
    </main>
  );
}