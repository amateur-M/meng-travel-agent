import { motion, type Variants } from "framer-motion";
import { Check, LoaderCircle, Sparkles } from "lucide-react";
import type { PlanningStep } from "../../types/trip";

interface SSEProgressProps {
  steps: PlanningStep[];
}

const listVariants: Variants = {
  hidden: {},
  visible: {
    transition: { staggerChildren: 0.14 },
  },
};

const itemVariants: Variants = {
  hidden: { opacity: 0, x: -10 },
  visible: {
    opacity: 1,
    x: 0,
    transition: { duration: 0.35, ease: "easeOut" },
  },
};

/**
 * Agent 思考过程可视化，逐步展示解析、天气、地点、编排与寄语生成进度。
 */
export function SSEProgress({ steps }: SSEProgressProps) {
  return (
    <motion.ol
      className="w-full max-w-sm space-y-3"
      variants={listVariants}
      initial="hidden"
      animate="visible"
    >
      {steps.map((step) => {
        const isDone = step.status === "done";
        const isActive = step.status === "active";

        return (
          <motion.li
            key={step.id}
            className={`flex items-center gap-3 rounded-lg border px-4 py-3 ${
              isActive
                ? "border-blush-200 bg-white shadow-soft"
                : isDone
                  ? "border-cream-200 bg-white/70"
                  : "border-cream-200 bg-white/40"
            }`}
            variants={itemVariants}
          >
            <div
              className={`flex h-8 w-8 shrink-0 items-center justify-center rounded-full ${
                isDone
                  ? "bg-emerald-50 text-emerald-600"
                  : isActive
                    ? "bg-blush-50 text-blush-500"
                    : "bg-cream-100 text-ink-400"
              }`}
            >
              {isDone ? (
                <Check className="h-4 w-4" />
              ) : isActive ? (
                <LoaderCircle className="h-4 w-4 animate-spin" />
              ) : (
                <Sparkles className="h-4 w-4" />
              )}
            </div>

            <div className="min-w-0">
              <p
                className={`text-sm font-semibold ${
                  isActive ? "text-blush-600" : "text-ink-700"
                }`}
              >
                {step.label}
              </p>
              <p className="mt-0.5 text-xs text-ink-400">{step.description}</p>
            </div>
          </motion.li>
        );
      })}
    </motion.ol>
  );
}
