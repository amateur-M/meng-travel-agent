#!/usr/bin/env node
/**
 * Zero-dependency store checks (V3/P3, T3.7; extended with recovery paths).
 *
 * The project has no frontend test framework and the Playwright suite cannot
 * run here (no browsers installed). This script bundles the store with the
 * esbuild that ships with Vite and drives it directly in Node, installing
 * localStorage / sessionStorage shims and a stubbed service module so the
 * *recovery* paths — the ones that previously only manual smoke testing could
 * reach — are actually asserted:
 *
 *   local logic:   ensureGreeting() idempotence, client id, applyPatch, newSession, reset
 *   hydration:     restore a conversation; a stale session id (404) starts fresh;
 *                  a trailing unanswered user turn arms "重新生成"
 *   recovery #5/#6: a failed send keeps the user's turn and retries with the
 *                  SAME message_id, so the turn is never duplicated
 *   switching:     switchSession writes the right pointers and hydrates;
 *                  deleting the active session falls back to another one
 *   offline:       loadSessions falls back to the cached list
 *
 * It still cannot cover React effect wiring (which is where the duplicate
 * greeting bug lived) — the manual checklist in memory/DEPLOY.md covers that.
 *
 * Usage: node scripts/check-chat-store.cjs [bundle-path]
 */

const path = require("path");
const Module = require("module");

const bundlePath = path.resolve(
  process.argv[2] || path.join("node_modules", ".cache", "chatStore.cjs"),
);

// ── Browser API shims (installed before the bundle is required) ──────

function makeStorage() {
  const map = new Map();
  return {
    getItem: (key) => (map.has(key) ? map.get(key) : null),
    setItem: (key, value) => void map.set(key, String(value)),
    removeItem: (key) => void map.delete(key),
    clear: () => map.clear(),
  };
}

globalThis.localStorage = makeStorage();
globalThis.sessionStorage = makeStorage();

// ── Stub for ../services/chat ────────────────────────────────────────
//
// The bundle is built with `--external:../services/chat`, so its calls go
// through `require` at call time and can be answered here.

const calls = { postChat: [], listSessions: 0, getSession: [], getMessages: [] };

const stubs = {
  getSession: async () => null,
  getMessages: async () => [],
  postChat: async () => {
    throw new Error("postChat not stubbed");
  },
  listSessions: async () => [],
  renameSession: async () => undefined,
  deleteSession: async () => undefined,
  getRecall: async () => ({ trips: [], feedback: [] }),
  getProfile: async () => ({}),
  patchProfile: async () => ({}),
};

const fakeChat = {
  postChat: async (message, options) => {
    calls.postChat.push({ message, options });
    return stubs.postChat(message, options);
  },
  getSession: async (id) => {
    calls.getSession.push(id);
    return stubs.getSession(id);
  },
  getMessages: async (id) => {
    calls.getMessages.push(id);
    return stubs.getMessages(id);
  },
  listSessions: async (clientId) => {
    calls.listSessions += 1;
    return stubs.listSessions(clientId);
  },
  renameSession: (...args) => stubs.renameSession(...args),
  deleteSession: (...args) => stubs.deleteSession(...args),
  getRecall: (...args) => stubs.getRecall(...args),
  getProfile: (...args) => stubs.getProfile(...args),
  patchProfile: (...args) => stubs.patchProfile(...args),
};

const originalLoad = Module._load;
Module._load = function patchedLoad(request, parent, isMain) {
  if (typeof request === "string" && request.includes("services/chat")) {
    return fakeChat;
  }
  return originalLoad.call(this, request, parent, isMain);
};

// ── Tiny assertion helper ───────────────────────────────────────────

let failures = 0;
let checks = 0;

function check(label, condition, detail) {
  checks += 1;
  if (condition) {
    console.log(`  ok   ${label}`);
  } else {
    failures += 1;
    console.log(`  FAIL ${label}${detail ? ` — ${detail}` : ""}`);
  }
}

function section(title) {
  console.log(`\n${title}`);
}

const {
  useChatStore,
  getClientId,
  KEY_ACTIVE,
  KEY_LAST,
  KEY_SESSIONS,
  KEY_CLIENT,
} = require(bundlePath);

const state = () => useChatStore.getState();

function clearEverything() {
  globalThis.localStorage.clear();
  globalThis.sessionStorage.clear();
  useChatStore.setState({ sessions: [] });
  state().reset();
}

function detail(overrides = {}) {
  return {
    session_id: "s1",
    title: "大理之行",
    summary: null,
    slots: {
      destination: "大理",
      start_date: "2026-09-01",
      end_date: "2026-09-03",
      budget: 5000,
    },
    plan_request: null,
    last_plan_id: "p1",
    message_count: 2,
    ...overrides,
  };
}

(async () => {
  section("ensureGreeting() is idempotent (StrictMode double-invokes effects)");
  state().ensureGreeting();
  state().ensureGreeting();
  state().ensureGreeting();
  check("three calls produce exactly one greeting", state().messages.length === 1,
    `got ${state().messages.length}`);
  check("the greeting is an assistant turn", state().messages[0]?.role === "assistant");

  section("client id");
  const first = getClientId();
  check("is stable across calls", getClientId() === first);
  check("is persisted", globalThis.localStorage.getItem(KEY_CLIENT) === first);

  section("applyPatch()");
  useChatStore.setState({
    planRequest: {
      origin: "北京",
      destination: "大理",
      start_date: "2026-09-01",
      end_date: "2026-09-03",
      budget: 5000,
      preferences: ["浪漫"],
      pace: "轻松",
    },
  });
  state().applyPatch({ budget: 8000 });
  check("merges the patched field", state().planRequest.budget === 8000);
  check("keeps untouched fields", state().planRequest.destination === "大理");
  check("arms the confirm button", state().status === "ready");

  section("newSession()");
  globalThis.sessionStorage.setItem(KEY_ACTIVE, "previous-session");
  globalThis.localStorage.setItem(KEY_LAST, "previous-session");
  state().newSession();
  check("clears the session id", state().sessionId === null);
  check("clears the plan request", state().planRequest === null);
  check("seeds exactly one greeting", state().messages.length === 1);
  check("forgets both session pointers",
    globalThis.sessionStorage.getItem(KEY_ACTIVE) === null &&
      globalThis.localStorage.getItem(KEY_LAST) === null);

  section("hydrate() with nothing stored");
  clearEverything();
  await state().hydrate();
  check("does not hang in the hydrating state", state().hydrating === false);
  check("greets a brand-new conversation", state().messages.length === 1);
  check("has no session id yet", state().sessionId === null);

  // ── Recovery matrix #1/#2/#11: restore a stored conversation ───────
  section("hydrate() restores a stored conversation");
  clearEverything();
  globalThis.sessionStorage.setItem(KEY_ACTIVE, "s1");
  stubs.getSession = async () => detail();
  stubs.getMessages = async () => [
    { role: "user", content: "想去大理", message_id: "m1", created_at: null },
    { role: "assistant", content: "好呀，几天？", message_id: null, created_at: null },
  ];
  await state().hydrate();
  check("restores the session id", state().sessionId === "s1");
  check("restores the transcript", state().messages.length === 2,
    `got ${state().messages.length}`);
  check("keeps the turn id for later retries",
    state().messages[0].messageId === "m1");
  check("restores the slots", state().slots.destination === "大理");
  check("rebuilds the plan request from complete slots",
    state().planRequest?.destination === "大理" && state().planRequest?.budget === 5000);
  check("restores the linked plan", state().lastPlanId === "p1");
  check("does not arm a retry for an answered conversation",
    state().pendingMessageId === null);
  check("marks the session as hydrated", state().hydratedSessionId === "s1");

  section("hydrate() is not repeated for the same session");
  const before = calls.getMessages.length;
  await state().hydrate();
  check("skips a redundant refetch", calls.getMessages.length === before);

  // ── Recovery matrix #4: stale pointer ─────────────────────────────
  section("hydrate() with a stale session id starts fresh (recovery #4)");
  clearEverything();
  globalThis.sessionStorage.setItem(KEY_ACTIVE, "deleted-session");
  globalThis.localStorage.setItem(KEY_LAST, "deleted-session");
  stubs.getSession = async () => null; // 404
  stubs.getMessages = async () => [];
  await state().hydrate();
  check("clears the session id", state().sessionId === null);
  check("drops the stale active-session pointer",
    globalThis.sessionStorage.getItem(KEY_ACTIVE) === null);
  check("drops the stale last-session pointer",
    globalThis.localStorage.getItem(KEY_LAST) === null);
  check("greets instead of showing an empty conversation",
    state().messages.length === 1 && state().messages[0].role === "assistant");
  check("leaves the hydrating flag off", state().hydrating === false);

  // ── Recovery matrix #5: unanswered trailing turn ──────────────────
  section("hydrate() arms a retry for an unanswered turn (recovery #5)");
  clearEverything();
  globalThis.sessionStorage.setItem(KEY_ACTIVE, "s1");
  stubs.getSession = async () => detail({ message_count: 3 });
  stubs.getMessages = async () => [
    { role: "user", content: "想去大理", message_id: "m1" },
    { role: "assistant", content: "好呀" },
    { role: "user", content: "预算加到8千", message_id: "m3" },
  ];
  await state().hydrate();
  check("records the unanswered turn id", state().pendingMessageId === "m3");

  // ── Recovery matrix #5/#6: failed send then retry ─────────────────
  section("send() failure keeps the turn and retries idempotently (#5/#6)");
  clearEverything();
  stubs.getSession = async () => detail();
  stubs.getMessages = async () => [];
  stubs.postChat = async () => {
    throw new Error("网络中断");
  };
  await state().send("我们想去大理");
  check("reports the error", state().status === "error");
  check("keeps the user's message on screen",
    state().messages.at(-1)?.role === "user" &&
      state().messages.at(-1)?.content === "我们想去大理");
  const retryId = state().pendingMessageId;
  check("arms a retry", Boolean(retryId));

  const sentId = calls.postChat.at(-1).options.messageId;
  check("sent a client-generated turn id", sentId === retryId);
  const messageCountBeforeRetry = calls.getMessages.length;

  const messagesBefore = state().messages.length;
  stubs.postChat = async (_message, options) => ({
    session_id: "s1",
    reply: "好呀，预算够的～",
    intent: "planning_intent",
    slots: { destination: "大理" },
    ready: false,
    plan_request: null,
    modify_patch: null,
    __echoedMessageId: options.messageId,
  });
  await state().regenerate();

  check("retry reuses the SAME turn id (no duplicate server write)",
    calls.postChat.at(-1).options.messageId === retryId);
  check("retry does not append a second user bubble",
    state().messages.length === messagesBefore + 1,
    `expected +1, got +${state().messages.length - messagesBefore}`);
  check("retry appends the assistant reply",
    state().messages.at(-1)?.role === "assistant" &&
      state().messages.at(-1)?.content === "好呀，预算够的～");
  check("clears the retry flag after success", state().pendingMessageId === null);
  check("does not refetch the transcript during a retry",
    calls.getMessages.length === messageCountBeforeRetry);

  // ── Switching ─────────────────────────────────────────────────────
  section("switchSession() writes pointers and hydrates");
  clearEverything();
  stubs.getSession = async (id) =>
    detail({ session_id: id, slots: { destination: "三亚" }, last_plan_id: null });
  stubs.getMessages = async () => [
    { role: "user", content: "换成三亚", message_id: "x1" },
    { role: "assistant", content: "好呀" },
  ];
  await state().switchSession("s2");
  check("hydrates the target session", state().sessionId === "s2");
  check("restores its slots", state().slots.destination === "三亚");
  check("remembers it for this tab",
    globalThis.sessionStorage.getItem(KEY_ACTIVE) === "s2");
  check("remembers it for the next tab",
    globalThis.localStorage.getItem(KEY_LAST) === "s2");

  section("removeSession() falls back to another conversation");
  useChatStore.setState({
    sessions: [
      { session_id: "s2", message_count: 2, preview: "换成三亚" },
      { session_id: "s3", message_count: 1, preview: "你好" },
    ],
  });
  stubs.deleteSession = async () => undefined;
  stubs.getSession = async (id) => detail({ session_id: id });
  stubs.getMessages = async () => [{ role: "assistant", content: "你好" }];
  await state().removeSession("s2");
  check("drops the deleted session from the list",
    !state().sessions.some((s) => s.session_id === "s2"));
  check("switches to a remaining session", state().sessionId === "s3");

  // ── Offline ───────────────────────────────────────────────────────
  section("loadSessions() falls back to the cache when offline");
  clearEverything();
  const cached = [{ session_id: "cached-1", message_count: 4, preview: "离线缓存" }];
  globalThis.localStorage.setItem(KEY_SESSIONS, JSON.stringify(cached));
  stubs.listSessions = async () => {
    throw new Error("offline");
  };
  await state().loadSessions();
  check("shows the cached list", state().sessions.length === 1 &&
    state().sessions[0].session_id === "cached-1");

  section("loadSessions() replaces the cache when online");
  const live = [{ session_id: "live-1", message_count: 2, preview: "在线" }];
  stubs.listSessions = async () => live;
  await state().loadSessions();
  check("shows the live list", state().sessions[0]?.session_id === "live-1");
  check("refreshes the cache",
    JSON.parse(globalThis.localStorage.getItem(KEY_SESSIONS))[0].session_id === "live-1");

  section("reset()");
  state().reset();
  check("clears the transcript", state().messages.length === 0);
  check("clears initialized", state().initialized === false);

  console.log(
    `\n${failures === 0 ? "PASS" : "FAIL"}: ${checks - failures}/${checks} checks passed`,
  );
  process.exit(failures === 0 ? 0 : 1);
})().catch((error) => {
  console.error("check-chat-store crashed:", error);
  process.exit(1);
});
