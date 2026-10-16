import { create } from "zustand";
import {
  deleteSession as apiDeleteSession,
  getMessages,
  getSession,
  listSessions as apiListSessions,
  postChat,
  renameSession as apiRenameSession,
} from "../services/chat";
import type {
  ChatMessage,
  ChatReply,
  ChatStatus,
  ModifyPatch,
  SessionSummary,
  Slots,
  StoredMessage,
  TripPlanRequestPayload,
} from "../types/chat";

const GREETING =
  "嗨～我是你们的情侣旅行助手。说说想去哪里，我来帮你们安排一段浪漫的旅程吧。";

/**
 * Storage layout (V3/P3 — recovery matrix #2 and #7).
 *
 * The *active* session is per-tab (sessionStorage): two tabs open on the same
 * conversation would otherwise interleave their turns into one transcript.
 * localStorage only carries the seed a brand-new tab opens with, the sidebar
 * cache for a fast first paint, and the stable client id that scopes both
 * conversations and the L2 profile.
 */
const KEY_ACTIVE = "coupletrip.active_session";
const KEY_LAST = "coupletrip.last_session";
const KEY_SESSIONS = "coupletrip.sessions_cache";
const KEY_CLIENT = "coupletrip.client_id";

function readString(storage: Storage | undefined, key: string): string | null {
  try {
    return storage?.getItem(key) ?? null;
  } catch {
    return null;
  }
}

function writeString(storage: Storage | undefined, key: string, value: string | null): void {
  try {
    if (value === null) {
      storage?.removeItem(key);
    } else {
      storage?.setItem(key, value);
    }
  } catch {
    // storage disabled — the app still works, it just will not remember
  }
}

function readJSON<T>(storage: Storage | undefined, key: string): T | null {
  const raw = readString(storage, key);
  if (!raw) {
    return null;
  }
  try {
    return JSON.parse(raw) as T;
  } catch {
    return null;
  }
}

function writeJSON(storage: Storage | undefined, key: string, value: unknown): void {
  try {
    writeString(storage, key, JSON.stringify(value));
  } catch {
    // ignore
  }
}

function browserSessionStorage(): Storage | undefined {
  return typeof sessionStorage === "undefined" ? undefined : sessionStorage;
}

function browserLocalStorage(): Storage | undefined {
  return typeof localStorage === "undefined" ? undefined : localStorage;
}

/** Stable per-browser id: scopes conversations and the L2 profile. */
export function getClientId(): string {
  const storage = browserLocalStorage();
  const existing = readString(storage, KEY_CLIENT);
  if (existing) {
    return existing;
  }
  const created = newMessageId();
  writeString(storage, KEY_CLIENT, created);
  return created;
}

function newMessageId(): string {
  const cryptoObj = typeof crypto === "undefined" ? undefined : crypto;
  if (cryptoObj?.randomUUID) {
    return cryptoObj.randomUUID();
  }
  return `m-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 10)}`;
}

/** Rebuild a plan request from complete slots (used when hydrating). */
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

function toChatMessages(stored: StoredMessage[]): ChatMessage[] {
  return stored.map((message) => ({
    role: message.role,
    content: message.content,
    messageId: message.message_id ?? null,
    createdAt: message.created_at ?? null,
  }));
}

interface SendOptions {
  /** Reuse an existing turn id so a retry cannot duplicate the message. */
  messageId?: string;
  /** False when the user bubble is already on screen (regenerate). */
  appendUserMessage?: boolean;
}

interface ChatStore {
  messages: ChatMessage[];
  sessionId: string | null;
  slots: Slots;
  planRequest: TripPlanRequestPayload | null;
  status: ChatStatus;
  error: string | null;
  initialized: boolean;

  sessions: SessionSummary[];
  hydrating: boolean;
  /** Which session the in-memory transcript belongs to. */
  hydratedSessionId: string | null;
  lastPlanId: string | null;
  /** A user turn that never received a reply — offers "重新生成" (recovery #5). */
  pendingMessageId: string | null;

  ensureGreeting: () => void;
  hydrate: () => Promise<void>;
  loadSessions: () => Promise<void>;
  newSession: () => void;
  switchSession: (sessionId: string) => Promise<void>;
  renameSession: (sessionId: string, title: string) => Promise<void>;
  removeSession: (sessionId: string) => Promise<void>;
  send: (message: string, options?: SendOptions) => Promise<ChatReply | null>;
  regenerate: () => Promise<void>;
  applyPatch: (patch: Partial<TripPlanRequestPayload>) => void;
  reset: () => void;
}

export const useChatStore = create<ChatStore>((set, get) => ({
  messages: [],
  sessionId: null,
  slots: {},
  planRequest: null,
  status: "idle",
  error: null,
  initialized: false,

  sessions: readJSON<SessionSummary[]>(browserLocalStorage(), KEY_SESSIONS) ?? [],
  hydrating: false,
  hydratedSessionId: null,
  lastPlanId: null,
  pendingMessageId: null,

  /**
   * Seed the opening assistant message exactly once.
   *
   * The guard reads live store state (not the render closure), so repeated
   * calls are no-ops — React StrictMode double-invokes mount effects in dev,
   * which previously appended the greeting twice.
   */
  ensureGreeting: () => {
    if (get().initialized || get().messages.length > 0) {
      return;
    }
    set((state) => ({
      messages: [{ role: "assistant", content: GREETING }, ...state.messages],
      initialized: true,
    }));
  },

  /**
   * Restore the conversation this browser was last on (recovery #1/#2/#11).
   *
   * Runs once per session per page load: navigating Chat → loading → result →
   * back keeps the in-memory transcript, so refetching would only add latency
   * and risk clobbering newer local state.
   */
  hydrate: async () => {
    // Guards StrictMode's double mount and any concurrent call: without this the
    // two invocations would both fetch the transcript.
    if (get().hydrating) {
      return;
    }

    const target =
      readString(browserSessionStorage(), KEY_ACTIVE) ??
      readString(browserLocalStorage(), KEY_LAST);

    if (!target) {
      set({ hydrating: false });
      get().ensureGreeting();
      return;
    }
    if (get().hydratedSessionId === target) {
      return;
    }

    set({ hydrating: true, error: null });
    try {
      const [detail, transcript] = await Promise.all([
        getSession(target),
        getMessages(target),
      ]);

      if (!detail) {
        // Stale pointer: the session was deleted or the database was reset
        // (recovery #4). Start clean instead of showing a broken conversation.
        writeString(browserSessionStorage(), KEY_ACTIVE, null);
        writeString(browserLocalStorage(), KEY_LAST, null);
        set({
          hydrating: false,
          hydratedSessionId: null,
          sessionId: null,
          messages: [],
          slots: {},
          planRequest: null,
          lastPlanId: null,
          pendingMessageId: null,
          initialized: false,
          status: "idle",
        });
        get().ensureGreeting();
        return;
      }

      const messages = toChatMessages(transcript);
      // A trailing user turn means the reply never arrived: offer a retry
      // instead of silently leaving the conversation hanging (recovery #5).
      const trailing = messages[messages.length - 1];
      const pending = trailing?.role === "user" ? trailing.messageId ?? null : null;

      writeString(browserSessionStorage(), KEY_ACTIVE, detail.session_id);
      writeString(browserLocalStorage(), KEY_LAST, detail.session_id);

      set({
        sessionId: detail.session_id,
        slots: detail.slots ?? {},
        planRequest: detail.plan_request ?? slotsToPlanRequest(detail.slots ?? {}),
        lastPlanId: detail.last_plan_id ?? null,
        messages,
        hydrating: false,
        hydratedSessionId: detail.session_id,
        pendingMessageId: pending,
        initialized: true,
        status: "idle",
      });

      if (messages.length === 0) {
        set({ initialized: false });
        get().ensureGreeting();
      }
    } catch (error) {
      // Network failure: keep whatever is already on screen.
      const message = error instanceof Error ? error.message : "会话恢复失败";
      set({ hydrating: false, error: message });
      get().ensureGreeting();
    }
  },

  loadSessions: async () => {
    try {
      const sessions = await apiListSessions(getClientId());
      writeJSON(browserLocalStorage(), KEY_SESSIONS, sessions);
      set({ sessions });
    } catch {
      const cached = readJSON<SessionSummary[]>(browserLocalStorage(), KEY_SESSIONS);
      if (Array.isArray(cached)) {
        set({ sessions: cached });
      }
    }
  },

  newSession: () => {
    writeString(browserSessionStorage(), KEY_ACTIVE, null);
    writeString(browserLocalStorage(), KEY_LAST, null);
    set({
      sessionId: null,
      messages: [],
      slots: {},
      planRequest: null,
      lastPlanId: null,
      pendingMessageId: null,
      hydratedSessionId: null,
      initialized: false,
      status: "idle",
      error: null,
    });
    get().ensureGreeting();
  },

  switchSession: async (sessionId) => {
    if (sessionId === get().sessionId) {
      return;
    }
    writeString(browserSessionStorage(), KEY_ACTIVE, sessionId);
    writeString(browserLocalStorage(), KEY_LAST, sessionId);
    // Clear the view first so the previous conversation cannot flash.
    set({
      sessionId: null,
      messages: [],
      slots: {},
      planRequest: null,
      lastPlanId: null,
      pendingMessageId: null,
      hydratedSessionId: null,
      initialized: false,
      status: "idle",
      error: null,
    });
    await get().hydrate();
  },

  renameSession: async (sessionId, title) => {
    await apiRenameSession(sessionId, title);
    set((state) => ({
      sessions: state.sessions.map((session) =>
        session.session_id === sessionId ? { ...session, title } : session,
      ),
    }));
  },

  removeSession: async (sessionId) => {
    await apiDeleteSession(sessionId);
    const remaining = get().sessions.filter((s) => s.session_id !== sessionId);
    set({ sessions: remaining });

    if (get().sessionId === sessionId) {
      const next = remaining[0]?.session_id;
      if (next) {
        await get().switchSession(next);
      } else {
        get().newSession();
      }
    }
  },

  send: async (message, options = {}) => {
    const appendUserMessage = options.appendUserMessage !== false;
    const messageId = options.messageId ?? newMessageId();

    set((state) => ({
      messages: appendUserMessage
        ? [...state.messages, { role: "user", content: message, messageId }]
        : state.messages,
      status: "sending",
      error: null,
    }));

    try {
      const reply = await postChat(message, {
        sessionId: get().sessionId,
        clientId: getClientId(),
        messageId,
      });

      const patch = reply.modify_patch ? omitNullPatch(reply.modify_patch) : null;

      writeString(browserSessionStorage(), KEY_ACTIVE, reply.session_id);
      writeString(browserLocalStorage(), KEY_LAST, reply.session_id);

      set((state) => ({
        messages: [...state.messages, { role: "assistant", content: reply.reply }],
        sessionId: reply.session_id,
        hydratedSessionId: reply.session_id,
        slots: reply.slots,
        status: reply.ready ? "ready" : "idle",
        planRequest: reply.plan_request ?? state.planRequest,
        pendingMessageId: null,
        initialized: true,
      }));

      if (patch) {
        // P1.2: fold the incremental patch into the request so the user can
        // confirm and re-plan without re-entering everything.
        get().applyPatch(patch);
      }

      void get().loadSessions();
      return reply;
    } catch (error) {
      const msg = error instanceof Error ? error.message : "发送失败，请重试";
      // The user's turn is persisted server-side before the model is called, so
      // it is not lost — surface a retry with the same id instead (recovery #5).
      set({ status: "error", error: msg, pendingMessageId: messageId });
      return null;
    }
  },

  regenerate: async () => {
    const { messages, pendingMessageId } = get();
    const lastUser = [...messages].reverse().find((m) => m.role === "user");
    if (!lastUser) {
      return;
    }
    await get().send(lastUser.content, {
      messageId: pendingMessageId ?? lastUser.messageId ?? undefined,
      appendUserMessage: false,
    });
  },

  applyPatch: (patch) => {
    const base = get().planRequest ?? slotsToPlanRequest(get().slots);
    if (!base) {
      return;
    }
    set({ planRequest: { ...base, ...patch }, status: "ready" });
  },

  reset: () => {
    writeString(browserSessionStorage(), KEY_ACTIVE, null);
    writeString(browserLocalStorage(), KEY_LAST, null);
    set({
      messages: [],
      sessionId: null,
      slots: {},
      planRequest: null,
      status: "idle",
      error: null,
      initialized: false,
      hydrating: false,
      hydratedSessionId: null,
      lastPlanId: null,
      pendingMessageId: null,
    });
  },
}));

export { GREETING, KEY_ACTIVE, KEY_LAST, KEY_SESSIONS, KEY_CLIENT };
