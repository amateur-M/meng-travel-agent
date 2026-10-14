import { api } from "./api";
import type { ChatReply } from "../types/chat";

export async function postChat(
  message: string,
  sessionId?: string | null,
): Promise<ChatReply> {
  const response = await api.post("/api/chat", {
    message,
    session_id: sessionId ?? null,
  });
  return response.data as ChatReply;
}
