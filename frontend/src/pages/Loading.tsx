import { useEffect } from "react";
import { motion } from "framer-motion";
import {
  CloudSun,
  Compass,
  HeartHandshake,
  MapPinned,
  Plane,
} from "lucide-react";
import { useNavigate } from "react-router-dom";
import { SSEProgress } from "../components/SSEProgress/SSEProgress";
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
  const beginPlanning = useTripStore((state) => state.beginPlanning);

  useEffect(() => {
    void beginPlanning();
  }, [beginPlanning]);

  useEffect(() => {
    if (status === "ready") {
      const timer = window.setTimeout(() => navigate("/result"), 280);
      return () => window.clearTimeout(timer);
    }
  }, [navigate, status]);

  return (
    <div className="flex min-h-screen items-center justify-center bg-cream-50 px-4 py-10 text-ink-900">
      <div className="flex w-full flex-col items-center">
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

        <div className="mt-8 flex justify-center">
          <SSEProgress steps={progress} />
        </div>
      </div>
    </div>
  );
}
