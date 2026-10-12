import { useEffect } from "react";
import { motion } from "framer-motion";
import {
  AlertCircle,
  ArrowLeft,
  CloudSun,
  Compass,
  HeartHandshake,
  MapPinned,
  Plane,
  RotateCcw,
  Wallet,
} from "lucide-react";
import { useNavigate } from "react-router-dom";
import { SSEProgress } from "../components/SSEProgress/SSEProgress";
import { StreamingItinerary } from "../components/StreamingItinerary/StreamingItinerary";
import { useTripStore } from "../stores/tripStore";

function TravelIllustration() {
  return (
    <div className="relative mx-auto h-36 w-36">
      <motion.div
        className="absolute inset-0 rounded-full border border-blush-200 bg-white shadow-soft"
        animate={{ scale: [1, 1.03, 1] }}
        transition={{ duration: 2.6, repeat: Infinity, ease: "easeInOut" }}
      />
      <div className="absolute inset-4 flex items-center justify-center rounded-full bg-blush-50 text-blush-500">
        <HeartHandshake className="h-12 w-12" />
      </div>

      <div className="absolute -left-4 top-2 flex h-10 w-10 animate-float items-center justify-center rounded-lg bg-white text-sky-600 shadow-soft">
        <Plane className="h-5 w-5" />
      </div>
      <div className="absolute -right-4 top-8 flex h-10 w-10 animate-float-delayed items-center justify-center rounded-lg bg-white text-gold-500 shadow-soft">
        <MapPinned className="h-5 w-5" />
      </div>
      <div className="absolute bottom-0 -left-2 flex h-10 w-10 animate-float-delayed items-center justify-center rounded-lg bg-white text-ink-400 shadow-soft">
        <Compass className="h-5 w-5" />
      </div>
      <div className="absolute -bottom-2 right-2 flex h-10 w-10 animate-float items-center justify-center rounded-lg bg-white text-amber-500 shadow-soft">
        <CloudSun className="h-5 w-5" />
      </div>
    </div>
  );
}

/**
 * 规划中页面，用情侣旅行插画和 SSE 进度展示 Agent 的思考过程。
 */
export function Loading() {
  const navigate = useNavigate();
  const status = useTripStore((state) => state.status);
  const currentStep = useTripStore((state) => state.currentStep);
  const progress = useTripStore((state) => state.progress);
  const error = useTripStore((state) => state.error);
  const streamingDays = useTripStore((state) => state.streamingDays);
  const budgetAlert = useTripStore((state) => state.budgetAlert);
  const weatherSwaps = useTripStore((state) => state.weatherSwaps);
  const coupleMessages = useTripStore((state) => state.coupleMessages);
  const beginPlanning = useTripStore((state) => state.beginPlanning);
  const resetPlan = useTripStore((state) => state.resetPlan);

  const hasStreamingContent = streamingDays.length > 0;

  useEffect(() => {
    if (status === "idle") {
      void beginPlanning();
    }
  }, [beginPlanning, status]);

  useEffect(() => {
    if (status === "ready") {
      const timer = window.setTimeout(() => navigate("/result"), 280);
      return () => window.clearTimeout(timer);
    }
  }, [navigate, status]);

  if (status === "error") {
    return (
      <div className="flex min-h-screen items-center justify-center bg-cream-50 px-4 py-10 text-ink-900">
        <div className="flex w-full max-w-sm flex-col items-center text-center">
          <div className="flex h-14 w-14 items-center justify-center rounded-full bg-rose-50 text-rose-600">
            <AlertCircle className="h-7 w-7" />
          </div>
          <h1 className="mt-5 text-xl font-semibold">行程没有生成成功</h1>
          <p className="mt-2 text-sm leading-6 text-ink-500">{error}</p>

          <div className="mt-6 grid w-full gap-2">
            <button
              type="button"
              className="inline-flex h-11 items-center justify-center gap-2 rounded-lg bg-blush-500 px-4 text-sm font-semibold text-white transition hover:bg-blush-600"
              onClick={() => void beginPlanning()}
            >
              <RotateCcw className="h-4 w-4" />
              重试
            </button>
            <button
              type="button"
              className="inline-flex h-11 items-center justify-center gap-2 rounded-lg border border-cream-200 bg-white px-4 text-sm font-medium text-ink-500 transition hover:text-ink-900"
              onClick={() => {
                resetPlan();
                navigate("/");
              }}
            >
              <ArrowLeft className="h-4 w-4" />
              返回首页
            </button>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-cream-50 px-4 py-10 text-ink-900">
      <div className="mx-auto flex w-full max-w-4xl flex-col items-center">
        <TravelIllustration />

        <motion.h1
          className="mt-7 text-2xl font-semibold"
          initial={{ opacity: 0, y: 8 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.4 }}
        >
          正在为你们规划
        </motion.h1>

        <motion.p
          className="mt-2 h-5 text-sm text-ink-500"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ duration: 0.4, delay: 0.1 }}
        >
          {currentStep}
        </motion.p>

        <div className="mt-8 flex w-full justify-center">
          <SSEProgress steps={progress} />
        </div>

        <div className="mt-6 flex w-full flex-col items-center gap-4">
          <StreamingEventBadges
            budgetAlert={budgetAlert}
            weatherSwapCount={weatherSwaps.length}
            messageCount={coupleMessages.length}
          />

          {hasStreamingContent && (
            <div className="mt-2 flex w-full justify-center">
              <StreamingItinerary days={streamingDays} />
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

function StreamingEventBadges({
  budgetAlert,
  weatherSwapCount,
  messageCount,
}: {
  budgetAlert: { warning_level: string; current: number; limit: number } | null;
  weatherSwapCount: number;
  messageCount: number;
}) {
  if (!budgetAlert && weatherSwapCount === 0 && messageCount === 0) {
    return null;
  }

  return (
    <motion.div
      className="flex flex-wrap items-center justify-center gap-2"
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      transition={{ duration: 0.3 }}
    >
      {budgetAlert && (
        <span
          className={`inline-flex items-center gap-1.5 rounded-full px-3 py-1.5 text-xs font-medium ${
            budgetAlert.warning_level === "over"
              ? "bg-rose-50 text-rose-600"
              : budgetAlert.warning_level === "warning"
                ? "bg-amber-50 text-amber-600"
                : "bg-emerald-50 text-emerald-600"
          }`}
        >
          <Wallet className="h-3.5 w-3.5" />
          ¥{budgetAlert.current.toLocaleString("zh-CN")} / ¥{budgetAlert.limit.toLocaleString("zh-CN")}
        </span>
      )}

      {weatherSwapCount > 0 && (
        <span className="inline-flex items-center gap-1.5 rounded-full bg-sky-50 px-3 py-1.5 text-xs font-medium text-sky-600">
          <CloudSun className="h-3.5 w-3.5" />
          天气调整 {weatherSwapCount} 项
        </span>
      )}

      {messageCount > 0 && (
        <span className="inline-flex items-center gap-1.5 rounded-full bg-blush-50 px-3 py-1.5 text-xs font-medium text-blush-600">
          <HeartHandshake className="h-3.5 w-3.5" />
          已生成 {messageCount} 条寄语
        </span>
      )}
    </motion.div>
  );
}
