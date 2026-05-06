"use client";

import { useState, useRef } from "react";
import { formatRelativeTime } from "@/app/utils/time";
import type { ConversationItem } from "@/app/types/chat";

interface ConversationSidebarProps {
  isOpen: boolean;
  onClose: () => void;
  conversations: ConversationItem[];
  activeConversationId: string | null;
  onNewConversation: () => void;
  onSelectConversation: (id: string) => void;
  onDeleteConversation: (id: string) => void;
  onRenameConversation: (id: string, newTitle: string) => Promise<void>;
}

export default function ConversationSidebar({
  isOpen,
  onClose,
  conversations,
  activeConversationId,
  onNewConversation,
  onSelectConversation,
  onDeleteConversation,
  onRenameConversation,
}: ConversationSidebarProps) {
  const [hoveredConvId, setHoveredConvId] = useState<string | null>(null);
  const hoverHideTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editTitle, setEditTitle] = useState("");
  const commitPendingRef = useRef(false);

  const commitRename = (id: string, newTitle: string) => {
    // Guard against double-commit: Enter fires commitRename then blur fires onBlur,
    // but setEditingId(null) is async so the stale closure still sees editingId === id.
    if (commitPendingRef.current) return;
    commitPendingRef.current = true;
    setEditingId(null);
    const trimmed = newTitle.trim();
    if (trimmed) {
      void onRenameConversation(id, trimmed);
    }
    // Reset after the event loop tick so any pending blur can still see the guard.
    setTimeout(() => { commitPendingRef.current = false; }, 0);
  };

  return (
    <>
      {/* Sidebar overlay on mobile */}
      {isOpen && (
        <div
          className="fixed inset-0 z-10 md:hidden"
          style={{ background: "rgba(0,0,0,0.3)" }}
          onClick={onClose}
        />
      )}

      {/* Sidebar */}
      <aside
        className={`${
          isOpen ? "translate-x-0" : "-translate-x-full"
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
            onClick={onClose}
            className="md:hidden text-lg transition-opacity hover:opacity-70"
            style={{ color: "var(--text-muted)" }}
          >
            ✕
          </button>
        </div>

        {/* New conversation */}
        <div className="px-3 py-2">
          <button
            onClick={onNewConversation}
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
                onClick={() => onSelectConversation(conv.id)}
                onKeyDown={(e) => {
                  if (e.key === "Enter" || e.key === " ") {
                    e.preventDefault();
                    onSelectConversation(conv.id);
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
                  background: conv.id === activeConversationId ? "var(--bg-surface)" : "transparent",
                  border: conv.id === activeConversationId ? "1px solid var(--border)" : "1px solid transparent",
                }}
              >
                {editingId === conv.id ? (
                  <input
                    autoFocus
                    value={editTitle}
                    onChange={(e) => setEditTitle(e.target.value)}
                    onKeyDown={(e) => {
                      if (e.key === "Enter") commitRename(conv.id, editTitle);
                      if (e.key === "Escape") setEditingId(null);
                    }}
                    onBlur={() => {
                      // editingId is already null if commitRename was called via Enter
                      if (editingId === conv.id) commitRename(conv.id, editTitle);
                    }}
                    onClick={(e) => e.stopPropagation()}
                    className="text-sm w-full bg-transparent border-b focus:outline-none"
                    style={{ color: "var(--text-primary)" }}
                  />
                ) : (
                  <div
                    className="text-sm truncate"
                    style={{ color: "var(--text-primary)" }}
                    onDoubleClick={(e) => {
                      e.stopPropagation();
                      setEditingId(conv.id);
                      setEditTitle(conv.title || "");
                    }}
                  >
                    {conv.title || "Untitled"}
                  </div>
                )}
                <div className="text-xs mt-0.5" style={{ color: "var(--text-muted)" }}>
                  {formatRelativeTime(conv.created_at)}
                </div>
                {hoveredConvId === conv.id && (
                  <div
                    className="absolute top-1/2 right-2 -translate-y-1/2 flex items-center gap-1"
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
                  >
                    <button
                      type="button"
                      title="Rename conversation"
                      onClick={(e) => {
                        e.stopPropagation();
                        setEditingId(conv.id);
                        setEditTitle(conv.title || "");
                      }}
                      className="w-6 h-6 flex items-center justify-center text-sm rounded-full transition-opacity hover:opacity-80"
                      style={{ background: "rgba(0,0,0,0.35)", color: "rgba(255,255,255,0.9)", boxShadow: "0 1px 3px rgba(0,0,0,0.3)" }}
                    >
                      ✎
                    </button>
                    <button
                      type="button"
                      title="Delete conversation"
                      onClick={(e) => {
                        e.stopPropagation();
                        onDeleteConversation(conv.id);
                      }}
                      className="w-6 h-6 flex items-center justify-center text-base rounded-full transition-opacity hover:opacity-80"
                      style={{ background: "rgba(0,0,0,0.35)", color: "rgba(255,255,255,0.9)", boxShadow: "0 1px 3px rgba(0,0,0,0.3)" }}
                    >
                      ×
                    </button>
                  </div>
                )}
              </div>
            ))
          )}
        </div>
      </aside>
    </>
  );
}
