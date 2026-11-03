import { AnimatePresence, motion } from "framer-motion";
import {
  CalendarDays,
  ChevronDown,
  Clock,
  Heart,
  MapPin,
  Sparkles,
  WalletCards,
} from "lucide-react";
import { useState } from "react";
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

/**
 * Collected-slot summary (V6/T2.5).
 *
 * It used to be a bordered card with a title row, which made the composer a
 * three-storey stack (status / slot card / input). Slots are now a single
 * wrapping chip row prefixed by the label — one line of context, collapsible
 * when a trip already exists and the noise is not wanted.
 */
export function SlotPanel({ slots }: SlotPanelProps) {
  const [collapsed, setCollapsed] = useState(false);
  const filled = SLOT_CONFIG.filter((s) => slots[s.key]);
  const prefs = slots.preferences ?? [];
  const empty = filled.length === 0 && prefs.length === 0;

  if (empty) {
    return null;
  }

  return (
    <div className="flex flex-wrap items-center gap-1.5">
      <button
        type="button"
        onClick={() => setCollapsed((value) => !value)}
        aria-expanded={!collapsed}
        className="ct-btn-quiet h-6 gap-1 px-1.5 text-[11px] font-medium text-ink-400"
      >
        <Sparkles className="h-3 w-3 text-gold-400" />
        已收集 {filled.length + (prefs.length ? 1 : 0)} 项
        <ChevronDown
          className={`h-3 w-3 transition-transform ${collapsed ? "" : "rotate-180"}`}
        />
      </button>

      {!collapsed && (
        <AnimatePresence initial={false}>
          {filled.map((slot) => {
            const val = slots[slot.key];
            const display =
              slot.key === "budget" && val
                ? `¥${Number(val).toLocaleString("zh-CN")}`
                : String(val);

            return (
              <motion.span
                key={slot.key}
                layout
                className="ct-chip border border-cream-200 bg-cream-50 text-ink-600"
                initial={{ opacity: 0, scale: 0.92 }}
                animate={{ opacity: 1, scale: 1 }}
                exit={{ opacity: 0, scale: 0.92, transition: { duration: 0.12 } }}
                transition={{ duration: 0.18 }}
              >
                <slot.icon className="h-3 w-3 text-blush-400" />
                <span className="text-ink-400">{slot.label}</span>
                <span className="font-medium text-ink-700">{display}</span>
              </motion.span>
            );
          })}

          {prefs.length > 0 && (
            <motion.span
              key="prefs"
              layout
              className="ct-chip border border-blush-200 bg-blush-50 text-blush-600"
              initial={{ opacity: 0, scale: 0.92 }}
              animate={{ opacity: 1, scale: 1 }}
              transition={{ duration: 0.18 }}
            >
              <Heart className="h-3 w-3" />
              {prefs.join("、")}
            </motion.span>
          )}
        </AnimatePresence>
      )}
    </div>
  );
}
