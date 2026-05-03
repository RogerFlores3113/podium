"use client";

import { useState } from "react";
import { tryParseImageUrl } from "@/app/utils/image";

const TOOL_ICONS: Record<string, string> = {
  web_search: "🔍",
  document_search: "📄",
  python_executor: "🐍",
  memory_search: "🧠",
  url_reader: "🔗",
};

export interface ToolCall {
  id: string;
  name: string;
  arguments: string;
  result?: string;
  error?: string;
  status: "running" | "done" | "error";
}

export function ToolCallDisplay({ toolCall }: { toolCall: ToolCall }) {
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
              {tryParseImageUrl(toolCall.result) ? (
                // eslint-disable-next-line @next/next/no-img-element
                <img
                  src={tryParseImageUrl(toolCall.result)!}
                  alt="Generated image"
                  className="rounded max-w-full max-h-96 object-contain"
                  style={{ border: "1px solid var(--border)" }}
                />
              ) : (
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
              )}
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
