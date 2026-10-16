import { useEffect, useState } from "react";
import { HeartHandshake, ArrowRight, Menu, RefreshCw, X } from "lucide-react";
import { useNavigate } from "react-router-dom";
import { ChatWindow } from "../components/Chat/ChatWindow";
import { ChatInput } from "../components/Chat/ChatInput";
import { ChatPlanCard } from "../components/Chat/ChatPlanCard";
import { SlotPanel } from "../components/Chat/SlotPanel";
import { SessionList } from "../components/Chat/SessionList";
import { useChatStore, KEY_LAST } from "../stores/chatStore";
import { useTripStore } from "../stores/tripStore";
import { startPlan } from "../services/plan";
import type { TripPlanRequest } from "../types/trip";

export function Chat() {
  const navigate = useNavigate();
  const messages = useChatStore((s) => s.messages);
  const slots = useChatStore((s) => s.slots);
  const status = useChatStore((s) => s.status);
  const planRequest = useChatStore((s) => s.planRequest);
  const sessions = useChatStore((s) => s.sessions);
  const sessionId = useChatStore((s) => s.sessionId);
  const hydrating = useChatStore((s) => s.hydrating);
  const pendingMessageId = useChatStore((s) => s.pendingMessageId);
  const send = useChatStore((s) => s.send);
  const hydrate = useChatStore((s) => s.hydrate);
  const loadSessions = useChatStore((s) => s.loadSessions);
  const newSession = useChatStore((s) => s.newSession);
  const switchSession = useChatStore((s) => s.switchSession);
  const renameSession = useChatStore((s) => s.renameSession);
  const removeSession = useChatStore((s) => s.removeSession);
  const regenerate = useChatStore((s) => s.regenerate);
  const lastPlanId = useChatStore((s) => s.lastPlanId);
  const tripPlan = useTripStore((s) => s.plan);
  const tripStatus = useTripStore((s) => s.status);
  const tripStep = useTripStore((s) => s.currentStep);
  const tripError = useTripStore((s) => s.error);
  const resumeExistingPlan = useTripStore((s) => s.resumeExistingPlan);
  const clearPlan = useTripStore((s) => s.clearPlan);
  const [launching, setLaunching] = useState(false);
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [planExpanded, setPlanExpanded] = useState(false);

  // Restore this browser's conversation. hydrate() is idempotent (it guards on
  // already-hydrated sessions and on in-flight work), so StrictMode's double
  // mount is harmless. It also seeds the greeting when there is nothing to
  // restore — no separate greeting effect needed.
  useEffect(() => {
    void hydrate();
    void loadSessions();
  }, [hydrate, loadSessions]);

  // Another tab switching or deleting a conversation refreshes this sidebar
  // (recovery #7). The active conversation itself stays tab-local.
  useEffect(() => {
    const onStorage = (event: StorageEvent) => {
      if (event.key === KEY_LAST || event.key === null) {
        void loadSessions();
      }
    };
    window.addEventListener("storage", onStorage);
    return () => window.removeEventListener("storage", onStorage);
  }, [loadSessions]);

  // Show this conversation's itinerary on the chat page itself. Covers both a
  // trip generated here and one restored after a refresh (the session's
  // last_plan_id). Switching to a conversation without a trip clears the card,
  // so one chat never shows another chat's itinerary.
  useEffect(() => {
    if (!lastPlanId) {
      if (useTripStore.getState().plan) {
        clearPlan();
      }
      return;
    }

    const state = useTripStore.getState();
    if (state.planId === lastPlanId && state.plan) {
      return; // already on screen
    }
    if (state.status === "planning") {
      return; // already streaming it
    }
    void resumeExistingPlan(lastPlanId);
  }, [clearPlan, lastPlanId, resumeExistingPlan]);

  const handleSend = (text: string) => {
    void send(text);
  };

  const handleSelect = (id: string) => {
    setSidebarOpen(false);
    if (id !== sessionId) {
      void switchSession(id);
    }
  };

  const handleDelete = (id: string) => {
    if (window.confirm("删除这段对话？聊天记录会被清除，已生成的行程保留。")) {
      void removeSession(id);
    }
  };

  const handleStartPlan = async () => {
    if (!planRequest || launching) {
      return;
    }
    setLaunching(true);

    // Sync plan_request into tripStore form, then start plan
    const request: TripPlanRequest = {
      origin: planRequest.origin,
      destination: planRequest.destination,
      start_date: planRequest.start_date,
      end_date: planRequest.end_date,
      budget: planRequest.budget,
      preferences: planRequest.preferences,
      pace: planRequest.pace as TripPlanRequest["pace"],
    };

    useTripStore.getState().updateForm(request);

    try {
      // session_id links the finished trip back to this conversation (V3/P3).
      const { plan_id } = await startPlan(request, sessionId ?? undefined);
      // Record the link so a refresh on this page can bring the itinerary back.
      useChatStore.setState({ lastPlanId: plan_id });
      setPlanExpanded(false);
      // Consume the stream *here* rather than navigating to /loading: the
      // itinerary then lands in this conversation with the input still below it,
      // which is what makes conversational tweaks the obvious next step.
      await useTripStore.getState().resumeExistingPlan(plan_id);
    } catch {
      // tripStore already exposes the failure through its error state.
    } finally {
      setLaunching(false);
    }
  };

  const ready = status === "ready" && planRequest;
  const planning = tripStatus === "planning";
  const hasPlan = Boolean(tripPlan);

  return (
    <div className="flex h-screen bg-cream-50 text-ink-900">
      {/* Conversation sidebar — fixed on desktop, drawer on mobile */}
      <aside className="hidden w-60 shrink-0 border-r border-cream-200 bg-white/70 lg:block">
        <SessionList
          sessions={sessions}
          activeId={sessionId}
          onSelect={handleSelect}
          onNew={newSession}
          onRename={(id, title) => void renameSession(id, title)}
          onDelete={handleDelete}
          onOpenPlan={(planId) => navigate(`/result?plan_id=${planId}`)}
        />
      </aside>

      {sidebarOpen && (
        <div className="fixed inset-0 z-40 flex lg:hidden">
          <div
            className="absolute inset-0 bg-ink-900/30"
            onClick={() => setSidebarOpen(false)}
          />
          <aside className="relative z-10 h-full w-64 border-r border-cream-200 bg-white">
            <SessionList
              sessions={sessions}
              activeId={sessionId}
              onSelect={handleSelect}
              onNew={() => {
                newSession();
                setSidebarOpen(false);
              }}
              onRename={(id, title) => void renameSession(id, title)}
              onDelete={handleDelete}
              onOpenPlan={(planId) => navigate(`/result?plan_id=${planId}`)}
            />
          </aside>
        </div>
      )}

      <div className="flex min-w-0 flex-1 flex-col">
        {/* Header */}
        <header className="shrink-0 border-b border-cream-200 bg-white/90 px-4 py-3 sm:px-6">
          <div className="mx-auto flex max-w-2xl items-center justify-between">
            <div className="flex items-center gap-2.5">
              <button
                type="button"
                aria-label="打开对话列表"
                onClick={() => setSidebarOpen((open) => !open)}
                className="inline-flex h-9 w-9 items-center justify-center rounded-lg text-ink-500 transition hover:bg-cream-100 lg:hidden"
              >
                {sidebarOpen ? <X className="h-5 w-5" /> : <Menu className="h-5 w-5" />}
              </button>
              <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-blush-500 text-white">
                <HeartHandshake className="h-5 w-5" />
              </div>
              <div className="min-w-0">
                <p className="text-base font-semibold">CoupleTrip</p>
                <p className="line-clamp-1 text-xs text-ink-400">
                  {sessions.find((s) => s.session_id === sessionId)?.title?.trim() ||
                    "情侣旅行助手"}
                </p>
              </div>
            </div>
          </div>
        </header>

        {/* Chat messages */}
        <div className="flex min-h-0 flex-1 flex-col">
          <ChatWindow messages={messages} sending={status === "sending" || hydrating} />
        </div>

        {/* Recovery: a user turn that never got a reply (recovery #5) */}
        {pendingMessageId && !hydrating && (
          <div className="shrink-0 px-4 pt-2 sm:px-6">
            <div className="mx-auto flex max-w-2xl items-center justify-between gap-3 rounded-xl border border-amber-200 bg-amber-50 px-3 py-2 text-xs text-amber-800">
              <span>上一条消息没有收到回复（可能是断网或中断）。</span>
              <button
                type="button"
                onClick={() => void regenerate()}
                disabled={status === "sending"}
                className="inline-flex shrink-0 items-center gap-1 font-semibold text-amber-900 hover:underline disabled:opacity-50"
              >
                <RefreshCw className="h-3.5 w-3.5" />
                重新生成
              </button>
            </div>
          </div>
        )}

        {/* Planning progress, in place (no navigation away from the chat) */}
        {planning && (
          <div className="shrink-0 px-4 pt-2 sm:px-6">
            <div className="mx-auto flex max-w-2xl items-center gap-2.5 rounded-xl border border-blush-200 bg-blush-50 px-3 py-2 text-xs text-blush-700">
              <span className="h-3 w-3 shrink-0 animate-spin rounded-full border-2 border-blush-300 border-t-blush-600" />
              <span className="truncate">{tripStep || "正在为你们规划行程..."}</span>
            </div>
          </div>
        )}

        {tripStatus === "error" && (
          <div className="shrink-0 px-4 pt-2 sm:px-6">
            <div className="mx-auto flex max-w-2xl items-center justify-between gap-3 rounded-xl border border-rose-200 bg-rose-50 px-3 py-2 text-xs text-rose-700">
              <span className="truncate">行程没有生成成功：{tripError}</span>
              <button
                type="button"
                onClick={() => void handleStartPlan()}
                disabled={launching}
                className="inline-flex shrink-0 items-center gap-1 font-semibold text-rose-900 hover:underline disabled:opacity-50"
              >
                <RefreshCw className="h-3.5 w-3.5" />
                重试
              </button>
            </div>
          </div>
        )}

        {/* The itinerary itself, so it can be adjusted by talking right below it */}
        {tripPlan && !planning && (
          <div className="shrink-0 px-4 pt-2 sm:px-6">
            <div className="mx-auto max-w-2xl">
              <ChatPlanCard
                plan={tripPlan}
                expanded={planExpanded}
                onToggle={() => setPlanExpanded((open) => !open)}
                onOpenFull={() => navigate(`/result?plan_id=${tripPlan.plan_id}`)}
              />
            </div>
          </div>
        )}

        {/* Slot panel + launch button */}
        {(Object.values(slots).some((v) => v) || ready) && (
          <div className="shrink-0 px-4 pb-2 sm:px-6">
            <div className="mx-auto max-w-2xl space-y-2">
              <SlotPanel slots={slots} />
              {ready && (
                <button
                  type="button"
                  onClick={handleStartPlan}
                  disabled={launching || planning}
                  className="inline-flex w-full items-center justify-center gap-2 rounded-xl bg-blush-500 px-4 py-3 text-sm font-semibold text-white transition hover:bg-blush-600 disabled:opacity-50"
                >
                  {planning
                    ? "正在规划行程..."
                    : hasPlan
                      ? "按新的要求重新规划"
                      : "开始规划行程"}
                  <ArrowRight className="h-4 w-4" />
                </button>
              )}
            </div>
          </div>
        )}

        {/* Input */}
        <ChatInput onSend={handleSend} disabled={status === "sending" || launching || planning} />
      </div>
    </div>
  );
}
