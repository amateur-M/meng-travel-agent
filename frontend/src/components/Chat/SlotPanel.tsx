import { motion, AnimatePresence } from "framer-motion";
import {
  CalendarDays,
  MapPin,
  WalletCards,
  Heart,
  Clock,
  Sparkles,
} from "lucide-react";
import type { Slots } from "../../types/chat";

interface SlotPanelProps {
  slots: Slots;
}

const SLOT_CONFIG: {
  key: keyof Slots;
  label: string;
  icon: typeof MapPin;
}[] = [
  { key: "destination", label: "目的地", icon: MapPin },
  { key: "start_date", label: "出发", icon: CalendarDays },
  { key: "end_date", label: "返程", icon: CalendarDays },
  { key: "budget", label: "预算", icon: WalletCards },
  { key: "origin", label: "出发地", icon: MapPin },
  { key: "pace", label: "节奏", icon: Clock },
];

export function SlotPanel({ slots }: SlotPanelProps) {
  const filled = SLOT_CONFIG.filter((s) => slots[s.key]);
  const prefs = slots.preferences ?? [];

  return (
    <div className="ct-card p-4">
      <p className="mb-3 flex items-center gap-1.5 text-xs font-semibold text-ink-400">
        <Sparkles className="h-3.5 w-3.5 text-gold-400" />
        已收集信息
      </p>

      <div className="flex flex-wrap gap-2">
        <AnimatePresence>
          {filled.map((slot) => {
            const val = slots[slot.key];
            const display =
              slot.key === "budget" && val
                ? `¥${Number(val).toLocaleString("zh-CN")}`
                : String(val);

            return (
              <motion.span
                key={slot.key}
                className="inline-flex items-center gap-1 rounded-full bg-cream-50 px-2.5 py-1 text-xs text-ink-600"
                initial={{ opacity: 0, scale: 0.8 }}
                animate={{ opacity: 1, scale: 1 }}
                exit={{ opacity: 0, scale: 0.8 }}
                transition={{ duration: 0.2 }}
              >
                <slot.icon className="h-3 w-3 text-blush-400" />
                {slot.label}: {display}
              </motion.span>
            );
          })}

          {prefs.length > 0 && (
            <motion.span
              className="inline-flex items-center gap-1 rounded-full bg-blush-50 px-2.5 py-1 text-xs text-blush-600"
              initial={{ opacity: 0, scale: 0.8 }}
              animate={{ opacity: 1, scale: 1 }}
              transition={{ duration: 0.2 }}
            >
              <Heart className="h-3 w-3" />
              {prefs.join("、")}
            </motion.span>
          )}
        </AnimatePresence>

        {filled.length === 0 && prefs.length === 0 && (
          <span className="text-xs text-ink-300">还没有收集到信息</span>
        )}
      </div>
    </div>
  );
}
