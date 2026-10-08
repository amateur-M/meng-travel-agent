import { motion } from "framer-motion";
import { Heart, Moon, Sun, Sunrise } from "lucide-react";
import type { ActivityType, Period } from "../../types/trip";

interface CoupleMessageProps {
  text: string;
  activityType: ActivityType;
  period: Period;
}

const PERIOD_ACCENT: Record<
  Period,
  { Icon: typeof Sun; bar: string; chip: string; text: string }
> = {
  上午: {
    Icon: Sunrise,
    bar: "bg-gold-300",
    chip: "bg-gold-50 text-gold-600",
    text: "text-ink-600",
  },
  下午: {
    Icon: Sun,
    bar: "bg-blush-300",
    chip: "bg-blush-50 text-blush-500",
    text: "text-blush-600",
  },
  晚间: {
    Icon: Moon,
    bar: "bg-indigo-300",
    chip: "bg-indigo-50 text-indigo-500",
    text: "text-ink-600",
  },
};

const REST_CHIP = "bg-cream-100 text-ink-500";

/**
 * M5: 情侣寄语气泡，时段差异化的色条与图标，用于 TimelineCard 内联展示。
 */
export function CoupleMessage({
  text,
  activityType,
  period,
}: CoupleMessageProps) {
  const accent = PERIOD_ACCENT[period] ?? PERIOD_ACCENT.下午;
  const isRest = activityType === "留白";
  const chipClass = isRest ? REST_CHIP : accent.chip;
  const Icon = isRest ? Heart : accent.Icon;

  return (
    <motion.div
      className={`mt-3 flex items-start gap-1.5 rounded-md border-l-2 ${accent.bar} bg-cream-50/60 px-3 py-2`}
      initial={{ opacity: 0, y: 4 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.35, ease: "easeOut" }}
    >
      <Icon className={`mt-0.5 h-4 w-4 shrink-0 ${accent.text}`} />
      <span className={`text-sm leading-6 ${accent.text}`}>{text}</span>
      <span
        className={`ml-auto shrink-0 rounded-full px-1.5 py-0.5 text-[10px] font-medium ${chipClass}`}
      >
        {isRest ? "留白" : period}
      </span>
    </motion.div>
  );
}
