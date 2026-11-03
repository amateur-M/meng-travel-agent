import { motion } from "framer-motion";
import { Heart, Moon, Sun, Sunrise } from "lucide-react";
import { TONE, type Tone } from "../../config/tones";
import type { ActivityType, Period } from "../../types/trip";

interface CoupleMessageProps {
  text: string;
  activityType: ActivityType;
  period: Period;
}

/**
 * Each period gets one accent hue from the tone ramp. The left rule and the icon
 * share it, so the message reads as belonging to morning/afternoon/evening at a
 * glance without a second colour competing with the card (V6/T1.4).
 */
const PERIOD_TONE: Record<Period, Tone> = {
  上午: "amber",
  下午: "rose",
  晚间: "indigo",
};

/**
 * M5: 情侣寄语气泡，时段差异化的色条与图标，用于 TimelineCard 内联展示。
 */
export function CoupleMessage({
  text,
  activityType,
  period,
}: CoupleMessageProps) {
  const isRest = activityType === "留白";
  const tone = TONE[isRest ? "sky" : PERIOD_TONE[period] ?? "rose"];
  const Icon = isRest ? Heart : period === "上午" ? Sunrise : period === "晚间" ? Moon : Sun;

  return (
    <motion.div
      className={`mt-3 flex items-start gap-2 rounded-r-xl border-l-2 py-2 pl-3 pr-2 ${tone.line} ${tone.soft}`}
      initial={{ opacity: 0, y: 4 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.35, ease: "easeOut" }}
    >
      <Icon className={`mt-0.5 h-4 w-4 shrink-0 ${tone.strong}`} />
      <span className={`min-w-0 flex-1 text-sm leading-6 ${tone.strong}`}>{text}</span>
      <span
        className={`ml-auto shrink-0 rounded-full bg-surface/60 px-1.5 py-0.5 text-[10px] font-medium ${tone.strong}`}
      >
        {isRest ? "留白" : period}
      </span>
    </motion.div>
  );
}
