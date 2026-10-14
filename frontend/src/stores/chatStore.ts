import { create } from "zustand";
import { postChat } from "../services/chat";
import type {
  ChatMessage,
  ChatReply,
  ChatStatus,
  Slots,
  TripPlanRequestPayload,
} from "../types/chat";

const GREETING =
  "嗨～我是你们的情侣旅行助手。说说想去哪里，我来帮你们安排一段浪漫的旅程吧。";

interface ChatStore {
  messages: ChatMessage[];
  sessionId: string | null;
  slots: Slots;
  status: ChatStatus;
  error: string | null;
  planRequest: TripPlanRequestPayload | null;
  initialized: boolean;
  send: (message: string) => Promise<ChatReply | null>;
  reset: () => void;
  applyPatch: (patch: Partial<TripPlanRequestPayload>) => void;
}

function loadSessionId(): string | null {
  try {
    return sessionStorage.getItem("coupletrip_session_id");
  } catch {
    return null;
  }
}

function saveSessionId(id: string): void {
  try {
    sessionStorage.setItem("coupletrip_session_id", id);
  } catch {
    // ignore
  }
}

export const useChatStore = create<ChatStore>((set, get) => ({
  messages: [],
  sessionId: loadSessionId(),
  slots: {},
  status: "idle",
  error: null,
  planRequest: null,
  initialized: false,

  send: async (message: string) => {
    set((state) => ({
      messages: [...state.messages, { role: "user", content: message }],
      status: "sending",
      error: null,
    }));

    try {
      const reply = await postChat(message, get().sessionId);

      // Persist session_id
      saveSessionId(reply.session_id);

      set((state) => ({
        messages: [...state.messages, { role: "assistant", content: reply.reply }],
        sessionId: reply.session_id,
        slots: reply.slots,
        status: reply.ready ? "ready" : "idle",
        planRequest: reply.plan_request ?? null,
      }));

      return reply;
    } catch (error) {
      const msg = error instanceof Error ? error.message : "发送失败，请重试";
      set((state) => ({
        messages: [...state.messages, { role: "assistant", content: msg }],
        status: "error",
        error: msg,
      }));
      return null;
    }
  },

  applyPatch: (patch) => {
    const current = get().planRequest;
    if (!current) {
      return;
    }
    set({ planRequest: { ...current, ...patch }, status: "ready" });
  },

  reset: () => {
    try {
      sessionStorage.removeItem("coupletrip_session_id");
    } catch {
      // ignore
    }
    set({
      messages: [],
      sessionId: null,
      slots: {},
      status: "idle",
      error: null,
      planRequest: null,
      initialized: false,
    });
  },
}));

export { GREETING };
