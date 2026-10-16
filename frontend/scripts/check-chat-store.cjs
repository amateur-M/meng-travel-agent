#!/usr/bin/env node
/**
 * Zero-dependency store checks (V3/P3, T3.7).
 *
 * The project has no frontend test framework, and the Playwright suite cannot
 * run without browsers installed. This script bundles the store with the
 * esbuild that ships with Vite and drives it directly in Node, which is enough
 * to pin the behaviours that are pure client-side logic:
 *
 *   - ensureGreeting() is idempotent (StrictMode double-invokes mount effects,
 *     which used to append the greeting twice in development)
 *   - the client id is stable and persisted
 *   - applyPatch merges into the plan request without erasing fields
 *   - newSession() clears the conversation and re-seeds exactly one greeting
 *   - hydrate() with no stored conversation greets instead of hanging
 *
 * It cannot cover React effect wiring or the network paths — the manual smoke
 * checklist in memory/DEPLOY.md covers those.
 *
 * Usage: node scripts/check-chat-store.cjs [bundle-path]
 */

const path = require("path");

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
    get size() {
      return map.size;
    },
  };
}

globalThis.localStorage = makeStorage();
globalThis.sessionStorage = makeStorage();

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

// ── Run ─────────────────────────────────────────────────────────────

const {
  useChatStore,
  getClientId,
  KEY_ACTIVE,
  KEY_LAST,
  KEY_CLIENT,
} = require(bundlePath);

const state = () => useChatStore.getState();

(async () => {
  section("ensureGreeting() is idempotent");
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
  check("is non-empty", Boolean(first));

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
  check("clears the slots", Object.keys(state().slots).length === 0);
  check("seeds exactly one greeting", state().messages.length === 1,
    `got ${state().messages.length}`);
  check("forgets the active-session pointer",
    globalThis.sessionStorage.getItem(KEY_ACTIVE) === null);
  check("forgets the last-session pointer",
    globalThis.localStorage.getItem(KEY_LAST) === null);

  section("hydrate() with nothing stored");
  state().reset();
  await state().hydrate();
  check("does not hang in the hydrating state", state().hydrating === false);
  check("greets a brand-new conversation", state().messages.length === 1);
  check("has no session id yet", state().sessionId === null);

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
