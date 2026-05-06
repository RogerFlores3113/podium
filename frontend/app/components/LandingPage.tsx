"use client";

import { useClerk } from "@clerk/nextjs";
import { useState } from "react";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

const CAPABILITIES = [
  { icon: "🧠", title: "Memory", desc: "Learns your preferences and remembers facts across every conversation." },
  { icon: "🔍", title: "Web Search", desc: "Searches the web in real time to answer questions with current information." },
  { icon: "📄", title: "Document RAG", desc: "Ingests PDFs and retrieves relevant passages with pgvector semantic search." },
  { icon: "🐍", title: "Code Execution", desc: "Writes and runs Python in a sandboxed environment, returning real output." },
  { icon: "🔑", title: "BYOK", desc: "Bring your own API key — OpenAI, Anthropic, or Ollama. Encrypted at rest with AWS KMS." },
  { icon: "☁️", title: "Multi-model", desc: "Switch between providers without changing a line of code, powered by LiteLLM." },
];

export default function LandingPage() {
  const { openSignIn } = useClerk();
  const [guestLoading, setGuestLoading] = useState(false);

  const handleGuestSession = async () => {
    if (guestLoading) return;
    try {
      // Reuse existing valid session without hitting the API
      const existingToken = sessionStorage.getItem("podium_guest_token");
      const existingExpires = sessionStorage.getItem("podium_guest_expires");
      if (existingToken && existingExpires && new Date(existingExpires) > new Date()) {
        window.location.href = "/";
        return;
      }
      setGuestLoading(true);
      const res = await fetch(`${API_URL}/guest/session`, { method: "POST" });
      if (!res.ok) throw new Error("Failed to create guest session");
      const { token, expires_at } = await res.json();
      sessionStorage.setItem("podium_guest_token", token);
      sessionStorage.setItem("podium_guest_expires", expires_at);
      window.location.href = "/";
    } catch (err) {
      console.error("Guest session error:", err);
      setGuestLoading(false);
    }
  };

  return (
    <div className="min-h-screen flex flex-col" style={{ background: "var(--bg-base)", color: "var(--text-primary)" }}>
      {/* Nav */}
      <nav className="flex items-center justify-between px-8 py-5" style={{ borderBottom: "1px solid var(--border)" }}>
        <span className="text-lg font-semibold" style={{ color: "var(--text-primary)" }}>Podium</span>
        <button
          onClick={() => openSignIn()}
          className="px-4 py-2 rounded-lg text-sm font-medium transition-opacity hover:opacity-80"
          style={{ background: "var(--bg-surface)", border: "1px solid var(--border)", color: "var(--text-primary)" }}
        >
          Sign in
        </button>
      </nav>

      {/* Hero */}
      <section className="flex flex-col items-center text-center px-8 py-24 max-w-3xl mx-auto">
        <h1 className="text-5xl font-bold mb-4 leading-tight" style={{ color: "var(--text-primary)" }}>
          Podium.
        </h1>
        <p className="text-2xl font-medium mb-3" style={{ color: "var(--text-primary)" }}>
          Your personal AI, built the right way.
        </p>
        <p className="text-lg mb-10" style={{ color: "var(--text-muted)" }}>
          Memory-first. Document-aware. Runs on your models.
        </p>
        <div className="flex flex-col items-center gap-3">
          <div className="flex gap-3">
            <button
              onClick={handleGuestSession}
              disabled={guestLoading}
              className="px-6 py-3 rounded-lg font-medium text-sm transition-opacity hover:opacity-80 disabled:opacity-50 disabled:cursor-not-allowed"
              style={{ background: "var(--accent-warm)", color: "#fff" }}
            >
              {guestLoading ? "Starting session…" : "Try as guest"}
            </button>
            <button
              onClick={() => openSignIn()}
              className="px-6 py-3 rounded-lg font-medium text-sm transition-opacity hover:opacity-80"
              style={{ background: "var(--bg-surface)", border: "1px solid var(--border)", color: "var(--text-primary)" }}
            >
              Get started
            </button>
          </div>
          <div className="flex items-center gap-4 text-sm" style={{ color: "var(--text-muted)" }}>
            <span>No sign-up required · Guest sessions expire in 24h</span>
            <a
              href="https://github.com/RogerFlores3113/podium"
              target="_blank"
              rel="noopener noreferrer"
              className="transition-opacity hover:opacity-70 underline underline-offset-2"
            >
              View source
            </a>
          </div>
        </div>
      </section>

      {/* Capabilities */}
      <section className="px-8 pb-20 max-w-4xl mx-auto w-full">
        <h2 className="text-xl font-semibold text-center mb-8" style={{ color: "var(--text-primary)" }}>
          What it can do
        </h2>
        <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-4">
          {CAPABILITIES.map((cap) => (
            <div
              key={cap.title}
              className="rounded-xl px-5 py-4"
              style={{
                background: "var(--bg-surface)",
                border: "1px solid var(--border)",
              }}
            >
              <div className="text-2xl mb-2">{cap.icon}</div>
              <div className="font-semibold text-sm mb-1" style={{ color: "var(--text-primary)" }}>
                {cap.title}
              </div>
              <p className="text-sm leading-relaxed" style={{ color: "var(--text-muted)" }}>
                {cap.desc}
              </p>
            </div>
          ))}
        </div>
      </section>

      {/* Footer */}
      <footer
        className="mt-auto px-8 py-6 text-center text-sm"
        style={{ borderTop: "1px solid var(--border)", color: "var(--text-muted)" }}
      >
        <a
          href="https://github.com/RogerFlores3113"
          target="_blank"
          rel="noopener noreferrer"
          className="transition-opacity hover:opacity-70"
        >
          GitHub
        </a>
      </footer>
    </div>
  );
}
