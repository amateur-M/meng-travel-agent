import { create } from "zustand";
import { postChat } from "../services/chat";
import type {
  ChatMessage,
  ChatReply,
  ChatStatus,
  ModifyPatch,
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

/** Rebuild a plan request from complete slots (P1.2 fallback for a patched session). */
function slotsToPlanRequest(slots: Slots): TripPlanRequestPayload | null {
  if (!slots.destination || !slots.start_date || !slots.end_date || !slots.budget) {
    return null;
  }
  return {
    origin: slots.origin ?? "未指定",
    destination: slots.destination,
    start_date: slots.start_date,
    end_date: slots.end_date,
    budget: slots.budget,
    preferences: slots.preferences ?? ["浪漫", "美食"],
    pace: slots.pace ?? "轻松",
  };
}

/** Drop null/undefined patch entries so they never erase untouched fields. */
function omitNullPatch(patch: ModifyPatch): Partial<TripPlanRequestPayload> {
  const out: Record<string, unknown> = {};
  for (const [key, value] of Object.entries(patch)) {
    if (value !== null && value !== undefined) {
      out[key] = value;
    }
  }
  return out as Partial<TripPlanRequestPayload>;
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

      const patch = reply.modify_patch ? omitNullPatch(reply.modify_patch) : null;

      set((state) => ({
        messages: [...state.messages, { role: "assistant", content: reply.reply }],
        sessionId: reply.session_id,
        slots: reply.slots,
        // A modification does not auto-plan; it re-arms the confirm button.
        status: reply.ready ? "ready" : "idle",
        // Keep the current request when the reply has none (greeting/question).
        planRequest: reply.plan_request ?? state.planRequest,
      }));

      if (patch) {
        // P1.2: fold the incremental patch into the request so the user can
        // confirm and re-plan without re-entering everything.
        get().applyPatch(patch);
      }

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
    const base = get().planRequest ?? slotsToPlanRequest(get().slots);
    if (!base) {
      return;
    }
    set({ planRequest: { ...base, ...patch }, status: "ready" });
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
