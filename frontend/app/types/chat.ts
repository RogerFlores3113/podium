import type { ToolCall } from "@/app/components/ToolCallDisplay";

export interface UserMessage {
  role: "user";
  content: string;
}

export interface AssistantMessage {
  role: "assistant";
  content: string;
  toolCalls?: ToolCall[];
}

export type ErrorKind = "byok" | "limit" | "server" | "stream" | "network";

export interface ErrorMessage {
  role: "error";
  kind: ErrorKind;
  content: string;
}

export type Message = UserMessage | AssistantMessage | ErrorMessage;

export interface ConversationItem {
  id: string;
  title: string | null;
  created_at: string;
}
