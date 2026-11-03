import { useCallback, useEffect, useState } from "react";
import { Menu, X } from "lucide-react";
import { useNavigate } from "react-router-dom";
import { AppHeader } from "../components/AppHeader";
import { ConfirmDialog } from "../components/ConfirmDialog";
import { ChatWindow } from "../components/Chat/ChatWindow";
import { ChatComposer } from "../components/Chat/ChatComposer";
import { ChatPlanCard } from "../components/Chat/ChatPlanCard";
import {
  ChatStatusRegion,
  type ChatStatusKind,
} from "../components/Chat/ChatStatusRegion";
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
  // V6/T3.4: deletion goes through our own dialog instead of window.confirm.
  const [pendingDelete, setPendingDelete] = useState<string | null>(null);

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

  const confirmDelete = useCallback(() => {
    const id = pendingDelete;
    setPendingDelete(null);
    if (id) {
      void removeSession(id);
    }
  }, [pendingDelete, removeSession]);

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

  const ready = status === "ready" && Boolean(planRequest);
  const planning = tripStatus === "planning";
  const hasPlan = Boolean(tripPlan);
  // The three transient states are mutually exclusive; show only the most
  // urgent one (V4/T2.1).
  const statusKind: ChatStatusKind =
    tripStatus === "error"
      ? "error"
      : planning
        ? "planning"
        : pendingMessageId && !hydrating
          ? "pending"
          : null;

  const activeTitle =
    sessions.find((s) => s.session_id === sessionId)?.title?.trim() || "情侣旅行助手";

  const sidebar = (onAfterAction?: () => void) => (
    <SessionList
      sessions={sessions}
      activeId={sessionId}
      loading={hydrating && sessions.length === 0}
      onSelect={handleSelect}
      onNew={() => {
        newSession();
        onAfterAction?.();
      }}
      onRename={(id, title) => void renameSession(id, title)}
      onDelete={setPendingDelete}
      onOpenPlan={(planId) => navigate(`/result?plan_id=${planId}`)}
    />
  );

  return (
    // `h-dvh` (not `h-screen`): on mobile `100vh` includes the browser chrome, so
    // the composer was pushed under the address bar (V6/T3.6).
    <div className="flex h-dvh bg-cream-50 text-ink-900">
      <aside className="hidden w-60 shrink-0 border-r border-cream-200 bg-surface/60 lg:block">
        {sidebar()}
      </aside>

      {sidebarOpen && (
        <div className="fixed inset-0 z-40 flex lg:hidden">
          <div
            className="absolute inset-0 bg-black/45 backdrop-blur-[2px]"
            onClick={() => setSidebarOpen(false)}
          />
          <aside className="relative z-10 h-full w-64 border-r border-cream-200 bg-surface shadow-lift">
            {sidebar(() => setSidebarOpen(false))}
          </aside>
        </div>
      )}

      <div className="flex min-w-0 flex-1 flex-col">
        <AppHeader
          width="chat"
          subtitle={activeTitle}
          leading={
            <button
              type="button"
              aria-label={sidebarOpen ? "关闭对话列表" : "打开对话列表"}
              aria-expanded={sidebarOpen}
              onClick={() => setSidebarOpen((open) => !open)}
              className="ct-btn-quiet h-9 w-9 lg:hidden"
            >
              {sidebarOpen ? <X className="h-5 w-5" /> : <Menu className="h-5 w-5" />}
            </button>
          }
        />

        {/* Message flow — the itinerary card rides at the end of the scroll,
            so "对话 → 行程 → 继续对话" stays one continuous thread (V4/T2.4). */}
        <ChatWindow
          messages={messages}
          sending={status === "sending" || hydrating}
          onQuickStart={handleSend}
          footer={
            tripPlan && !planning ? (
              <ChatPlanCard
                plan={tripPlan}
                expanded={planExpanded}
                onToggle={() => setPlanExpanded((open) => !open)}
                onOpenFull={() => navigate(`/result?plan_id=${tripPlan.plan_id}`)}
              />
            ) : undefined
          }
        />

        {/* Composer — one status bar + collected slots + primary action + input
            collapsed into a single action area (V4/T2.2). */}
        <ChatComposer
          statusRegion={
            <ChatStatusRegion
              kind={statusKind}
              tripError={tripError ?? ""}
              tripStep={tripStep}
              chatBusy={status === "sending"}
              launching={launching}
              onRegenerate={() => void regenerate()}
              onRetry={() => void handleStartPlan()}
            />
          }
          slots={slots}
          ready={ready}
          planning={planning}
          launching={launching}
          hasPlan={hasPlan}
          onStartPlan={handleStartPlan}
          onSend={handleSend}
          inputDisabled={status === "sending" || launching || planning}
        />
      </div>

      <ConfirmDialog
        open={pendingDelete !== null}
        destructive
        title="删除这段对话？"
        description="聊天记录会被清除，已生成的行程会保留。这个操作无法撤销。"
        confirmLabel="删除"
        onConfirm={confirmDelete}
        onCancel={() => setPendingDelete(null)}
      />
    </div>
  );
}
