import { api, ApiError } from "./api";
import type {
  ChatReply,
  ProfilePatch,
  Recall,
  SessionDetail,
  SessionSummary,
  StoredMessage,
} from "../types/chat";

export interface PostChatOptions {
  sessionId?: string | null;
  clientId?: string | null;
  /** Client-generated turn id: a retry with the same id cannot duplicate. */
  messageId?: string | null;
}

export async function postChat(
  message: string,
  options: PostChatOptions = {},
): Promise<ChatReply> {
  const response = await api.post("/api/chat", {
    message,
    session_id: options.sessionId ?? null,
    client_id: options.clientId ?? null,
    message_id: options.messageId ?? null,
  });
  return response.data as ChatReply;
}

/** Conversation list for the sidebar, most recently active first. */
export async function listSessions(clientId?: string | null): Promise<SessionSummary[]> {
  const response = await api.get("/api/chat/sessions", {
    params: clientId ? { client_id: clientId } : undefined,
  });
  return (response.data?.items ?? []) as SessionSummary[];
}

/** Session metadata, or `null` when the stored pointer is stale (recovery #4). */
export async function getSession(sessionId: string): Promise<SessionDetail | null> {
  try {
    const response = await api.get(`/api/chat/sessions/${sessionId}`);
    return response.data as SessionDetail;
  } catch (error) {
    if (error instanceof ApiError && error.status === 404) {
      return null;
    }
    throw error;
  }
}

export async function getMessages(sessionId: string): Promise<StoredMessage[]> {
  const response = await api.get(`/api/chat/sessions/${sessionId}/messages`);
  return (response.data?.items ?? []) as StoredMessage[];
}

export async function renameSession(sessionId: string, title: string): Promise<void> {
  await api.patch(`/api/chat/sessions/${sessionId}`, { title });
}

export async function deleteSession(sessionId: string): Promise<void> {
  await api.delete(`/api/chat/sessions/${sessionId}`);
}

/** L3 episodic memory preview (past trips + activity feedback). */
export async function getRecall(): Promise<Recall> {
  const response = await api.get("/api/chat/recall");
  return response.data as Recall;
}

/** L2 durable profile for this browser. */
export async function getProfile(clientId: string): Promise<Record<string, unknown>> {
  const response = await api.get("/api/profile", { params: { client_id: clientId } });
  return (response.data?.profile ?? {}) as Record<string, unknown>;
}

export async function patchProfile(
  clientId: string,
  patch: ProfilePatch,
): Promise<Record<string, unknown>> {
  const response = await api.patch("/api/profile", { client_id: clientId, patch });
  return (response.data?.profile ?? {}) as Record<string, unknown>;
}
