"use client";

import { useClerk } from "@clerk/nextjs";

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

  return (
    <div className="min-h-screen flex flex-col" style={{ background: "var(--bg-base)", color: "var(--text-primary)" }}>
      {/* Nav */}
      <nav className="flex items-center justify-between px-8 py-5" style={{ borderBottom: "1px solid var(--border)" }}>
        <span className="text-lg font-semibold" style={{ color: "var(--text-primary)" }}>Podium</span>
        <div className="flex items-center gap-4">
          <a
            href="https://github.com/RogerFlores3113/podium"
            target="_blank"
            rel="noopener noreferrer"
            className="text-sm transition-opacity hover:opacity-70"
            style={{ color: "var(--text-muted)" }}
          >
            GitHub
          </a>
          <button
            onClick={() => openSignIn()}
            className="px-4 py-2 rounded-lg text-sm font-medium transition-opacity hover:opacity-80"
            style={{ background: "var(--accent-warm)", color: "#fff" }}
          >
            Sign in
          </button>
        </div>
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
        <div className="flex gap-4">
          <button
            onClick={() => openSignIn()}
            className="px-6 py-3 rounded-lg font-medium text-sm transition-opacity hover:opacity-80"
            style={{ background: "var(--accent-warm)", color: "#fff" }}
          >
            Get started
          </button>
          <a
            href="https://github.com/RogerFlores3113/podium"
            target="_blank"
            rel="noopener noreferrer"
            className="px-6 py-3 rounded-lg font-medium text-sm transition-opacity hover:opacity-80"
            style={{
              background: "var(--bg-surface)",
              border: "1px solid var(--border)",
              color: "var(--text-primary)",
            }}
          >
            View source
          </a>
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

      {/* Architecture callout */}
      <section
        className="mx-8 mb-20 max-w-4xl mx-auto w-full rounded-xl px-8 py-6"
        style={{ background: "var(--bg-elevated)", border: "1px solid var(--border)" }}
      >
        <h2 className="text-sm font-semibold uppercase tracking-wide mb-3" style={{ color: "var(--text-muted)" }}>
          Stack
        </h2>
        <p className="text-sm" style={{ color: "var(--text-primary)" }}>
          FastAPI · pgvector (HNSW) · Next.js 14 · AWS ECS Fargate · RDS PostgreSQL · ElastiCache Redis · Clerk Auth · LiteLLM · arq
        </p>
      </section>

      {/* Footer */}
      <footer
        className="mt-auto px-8 py-6 text-center text-sm"
        style={{ borderTop: "1px solid var(--border)", color: "var(--text-muted)" }}
      >
        <a
          href="https://github.com/RogerFlores3113/podium"
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
