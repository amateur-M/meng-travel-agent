#!/usr/bin/env node
/**
 * Zero-dependency checks for the planning store (fixes the "generated an
 * itinerary but cannot view it" bug).
 *
 * Why this exists: `check-chat-store.cjs` only covers the chat store, so nothing
 * guarded the interaction between the Loading page and `tripStore`. That is
 * exactly where the bug lived — the chat POSTs a plan and sets status
 * "planning", the Loading page only ever streamed when status was "idle", so the
 * stream was never consumed and the finished itinerary was unreachable in the UI
 * even though it was sitting in the database.
 *
 * Usage: node scripts/check-trip-store.cjs [bundle-path]
 */

const path = require("path");
const Module = require("module");

const bundlePath = path.resolve(
  process.argv[2] || path.join("node_modules", ".cache", "tripStore.cjs"),
);

// ── Stub for ../services/plan (bundled as external) ──────────────────

const calls = { startPlan: 0, fetchPlan: [], resumeStream: [] };
let stubs = {};

const fakePlan = (planId) => ({
  plan_id: planId,
  destination: "Dali",
  start_date: "2026-09-01",
  end_date: "2026-09-03",
  days: [],
  budget_breakdown: { total_budget: 5000, total_spent: 4000, over_budget: false },
  weather_swaps: [],
  couple_notes: [],
});

const fakePlanService = {
  startPlan: async () => {
    calls.startPlan += 1;
    return { plan_id: "p-new", stream_url: "/api/plan/p-new/stream", status: "processing" };
  },
  fetchPlan: async (planId) => {
    calls.fetchPlan.push(planId);
    return stubs.fetchPlan(planId);
  },
  resumeStream: async (planId, _request, options) => {
    calls.resumeStream.push(planId);
    return stubs.resumeStream(planId, options);
  },
};

const originalLoad = Module._load;
Module._load = function patchedLoad(request, parent, isMain) {
  if (typeof request === "string" && request.includes("services/plan")) {
    return fakePlanService;
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

function reset() {
  calls.startPlan = 0;
  calls.fetchPlan = [];
  calls.resumeStream = [];
  stubs = {};
}

const { useTripStore } = require(bundlePath);
const state = () => useTripStore.getState();

(async () => {
  section("resumeExistingPlan: the chat's already-created plan is consumed");
  reset();
  stubs.fetchPlan = async () => null; // still processing
  stubs.resumeStream = async (planId) => fakePlan(planId);

  await state().resumeExistingPlan("p-chat");

  check("plan is loaded into the store", state().plan?.plan_id === "p-chat");
  check("status becomes ready (which is what advances to /result)", state().status === "ready");
  check("the stream was consumed exactly once", calls.resumeStream.length === 1, JSON.stringify(calls.resumeStream));
  check("it did NOT create a second plan", calls.startPlan === 0);

  section("resumeExistingPlan: a finished plan is read, not re-streamed");
  reset();
  stubs.fetchPlan = async (planId) => fakePlan(planId);
  stubs.resumeStream = async () => {
    throw new Error("must not open a stream for a completed plan");
  };

  await state().resumeExistingPlan("p-done");

  check("plan loaded", state().plan?.plan_id === "p-done");
  check("status ready", state().status === "ready");
  check("no stream was opened", calls.resumeStream.length === 0, JSON.stringify(calls.resumeStream));

  section("resumeExistingPlan: StrictMode double-invoke does not double-consume");
  reset();
  stubs.fetchPlan = async () => null;
  let resolveStream;
  const gate = new Promise((resolve) => {
    resolveStream = resolve;
  });
  stubs.resumeStream = async (planId) => {
    await gate;
    return fakePlan(planId);
  };

  const first = state().resumeExistingPlan("p-double");
  const second = state().resumeExistingPlan("p-double");
  resolveStream();
  await Promise.all([first, second]);

  check(
    "only one stream for the same plan",
    calls.resumeStream.length === 1,
    `opened ${calls.resumeStream.length}`,
  );

  section("resumeExistingPlan: already-loaded plan is a no-op");
  reset();
  stubs.fetchPlan = async () => fakePlan("p-loaded");
  await state().resumeExistingPlan("p-loaded");
  const fetchesAfterFirst = calls.fetchPlan.length;
  await state().resumeExistingPlan("p-loaded");
  check("second call did nothing", calls.fetchPlan.length === fetchesAfterFirst);
  check("plan still loaded", state().plan?.plan_id === "p-loaded");

  section("resumeExistingPlan: failure surfaces the error state");
  reset();
  stubs.fetchPlan = async () => null;
  stubs.resumeStream = async () => {
    throw new Error("stream broke");
  };
  let threw = false;
  try {
    await state().resumeExistingPlan("p-fail");
  } catch {
    threw = true;
  }
  check("the error is propagated to the caller", threw);
  check("status is error so the UI shows the failure", state().status === "error");
  check("the guard is released for a later retry", calls.resumeStream.length === 1);

  section("beginPlanning: the form path still creates and streams a plan");
  reset();
  stubs.fetchPlan = async () => null;
  stubs.resumeStream = async (planId) => fakePlan(planId);

  await state().beginPlanning();

  check("created a plan", calls.startPlan === 1);
  check("streamed it", calls.resumeStream.length === 1 && calls.resumeStream[0] === "p-new");
  check("plan loaded", state().plan?.plan_id === "p-new");
  check("status ready", state().status === "ready");

  section("streaming events feed the progressive UI");
  reset();
  stubs.fetchPlan = async () => null;
  const observed = {};
  stubs.resumeStream = async (planId, options) => {
    options.onStep({ phase: "plan_itinerary", message: "正在编排行程" });
    // sample mid-stream: on completion currentStep deliberately becomes ready
    observed.currentStep = state().currentStep;
    observed.progress = state().progress.map((s) => s.status);
    options.onPartial({ day_index: 0, weather: "sunny", activities: [] });
    options.onPartial({ day_index: 0, weather: "sunny", activities: [] }); // duplicate day
    options.onPartial({ day_index: 1, weather: "rainy", activities: [] });
    options.onBudgetAlert({ current: 5200, limit: 5000, warning_level: "over" });
    options.onWeatherSwap({ original: "outdoor", replacement: "indoor", reason: "rain" });
    options.onMessage({ activity_name: "x", note: "y" });
    return fakePlan(planId);
  };

  await state().resumeExistingPlan("p-events");

  check("progress shows the streamed step", observed.currentStep === "正在编排行程", observed.currentStep);
  check(
    "completed steps are marked done, the active one active",
    observed.progress[0] === "done" && observed.progress[3] === "active",
    JSON.stringify(observed.progress),
  );
  check("currentStep ends as ready", state().currentStep === "行程已就绪", state().currentStep);
  check("days are deduplicated by index", state().streamingDays.length === 2, String(state().streamingDays.length));
  check("budget alert recorded", state().budgetAlert?.current === 5200);
  check("weather swap recorded", state().weatherSwaps.length === 1);
  check("couple message recorded", state().coupleMessages.length === 1);

  section("clearPlan: switching to a conversation with no trip drops the itinerary");
  reset();
  stubs.fetchPlan = async (planId) => fakePlan(planId);
  await state().resumeExistingPlan("p-previous");
  check("plan loaded", state().plan?.plan_id === "p-previous");

  state().clearPlan();

  check("plan is gone", state().plan === null && state().planId === null);
  check("status is idle", state().status === "idle");
  check(
    "the form survives, so the user can plan again",
    state().form.destination === "大理",
    state().form.destination,
  );

  console.log(
    `\n${failures === 0 ? "PASS" : "FAIL"}: ${checks - failures}/${checks} checks passed`,
  );
  process.exit(failures === 0 ? 0 : 1);
})().catch((error) => {
  console.error("check-trip-store crashed:", error);
  process.exit(1);
});
