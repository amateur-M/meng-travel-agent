import { useEffect, useState } from "react";
import { HeartHandshake, ArrowRight } from "lucide-react";
import { useNavigate } from "react-router-dom";
import { ChatWindow } from "../components/Chat/ChatWindow";
import { ChatInput } from "../components/Chat/ChatInput";
import { SlotPanel } from "../components/Chat/SlotPanel";
import { useChatStore } from "../stores/chatStore";
import { useTripStore } from "../stores/tripStore";
import { startPlan } from "../services/plan";
import type { TripPlanRequest } from "../types/trip";

export function Chat() {
  const navigate = useNavigate();
  const messages = useChatStore((s) => s.messages);
  const slots = useChatStore((s) => s.slots);
  const status = useChatStore((s) => s.status);
  const planRequest = useChatStore((s) => s.planRequest);
  const send = useChatStore((s) => s.send);
  const ensureGreeting = useChatStore((s) => s.ensureGreeting);
  const [launching, setLaunching] = useState(false);

  // Greet on first visit (idempotent — StrictMode mounts effects twice in dev)
  useEffect(() => {
    ensureGreeting();
  }, [ensureGreeting]);

  const handleSend = (text: string) => {
    void send(text);
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
      const { plan_id } = await startPlan(request);
      useTripStore.setState({ planId: plan_id, status: "planning" });
      navigate(`/loading?plan_id=${plan_id}`);
    } catch {
      setLaunching(false);
    }
  };

  const ready = status === "ready" && planRequest;

  return (
    <div className="flex h-screen flex-col bg-cream-50 text-ink-900">
      {/* Header */}
      <header className="shrink-0 border-b border-cream-200 bg-white/90 px-4 py-3 sm:px-6">
        <div className="mx-auto flex max-w-2xl items-center justify-between">
          <div className="flex items-center gap-2.5">
            <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-blush-500 text-white">
              <HeartHandshake className="h-5 w-5" />
            </div>
            <div>
              <p className="text-base font-semibold">CoupleTrip</p>
              <p className="text-xs text-ink-400">情侣旅行助手</p>
            </div>
          </div>
        </div>
      </header>

      {/* Chat messages */}
      <div className="flex min-h-0 flex-1 flex-col">
        <ChatWindow messages={messages} sending={status === "sending"} />
      </div>

      {/* Slot panel + launch button */}
      {(Object.values(slots).some((v) => v) || ready) && (
        <div className="shrink-0 px-4 pb-2 sm:px-6">
          <div className="mx-auto max-w-2xl space-y-2">
            <SlotPanel slots={slots} />
            {ready && (
              <button
                type="button"
                onClick={handleStartPlan}
                disabled={launching}
                className="inline-flex w-full items-center justify-center gap-2 rounded-xl bg-blush-500 px-4 py-3 text-sm font-semibold text-white transition hover:bg-blush-600 disabled:opacity-50"
              >
                {launching ? "正在创建行程..." : "开始规划行程"}
                <ArrowRight className="h-4 w-4" />
              </button>
            )}
          </div>
        </div>
      )}

      {/* Input */}
      <ChatInput onSend={handleSend} disabled={status === "sending" || launching} />
    </div>
  );
}
