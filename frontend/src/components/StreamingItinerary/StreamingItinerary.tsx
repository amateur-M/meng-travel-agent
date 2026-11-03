import { AnimatePresence, motion } from "framer-motion";
import { CloudSun, MapPin, Moon, Sun, Sunrise, Utensils } from "lucide-react";
import { TONE } from "../../config/tones";
import type { Activity } from "../../types/trip";

interface StreamingDay {
  day_index: number;
  weather?: string;
  activities: Activity[];
}

const PERIOD_ICONS = {
  上午: Sunrise,
  下午: Sun,
  晚间: Moon,
} as const;

/**
 * 流式行程预览，在 SSE partial 事件到达时逐日逐时段渲染活动卡片。
 *
 * V6/T2.9: the three periods used to share one CloudSun icon, so the rows were
 * indistinguishable; each period now has its own icon matching the timeline, and
 * the day badge uses the fixed brand colour instead of a blush tint.
 */
export function StreamingItinerary({ days }: { days: StreamingDay[] }) {
  return (
    <motion.div
      className="w-full max-w-md space-y-3"
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      transition={{ duration: 0.3 }}
    >
      <AnimatePresence>
        {days.map((day) => (
          <StreamingDayCard key={day.day_index} day={day} />
        ))}
      </AnimatePresence>
    </motion.div>
  );
}

function StreamingDayCard({ day }: { day: StreamingDay }) {
  const periods = ["上午", "下午", "晚间"] as const;
  const groups = periods
    .map((period) => ({
      period,
      activities: day.activities.filter((a) => a.period === period),
    }))
    .filter((g) => g.activities.length > 0);

  return (
    <motion.section
      className="rounded-2xl border border-cream-200 bg-surface/80 p-3 shadow-soft"
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0 }}
      transition={{ duration: 0.35, ease: "easeOut" }}
    >
      <div className="flex items-center gap-2 px-1 pb-2">
        <span className="flex h-7 w-7 items-center justify-center rounded-lg bg-brand text-xs font-bold text-white">
          D{day.day_index + 1}
        </span>
        {day.weather && (
          <span className={`ct-chip gap-1 ${TONE.sky.soft} ${TONE.sky.strong}`}>
            <CloudSun className="h-3.5 w-3.5" />
            {day.weather}
          </span>
        )}
      </div>

      <div className="space-y-2">
        {groups.map((group) => {
          const Icon = PERIOD_ICONS[group.period] ?? MapPin;
          return (
            <div key={group.period}>
              <div className="flex items-center gap-1.5 px-1 pb-1">
                <Icon className="h-3 w-3 text-gold-400" />
                <span className="text-[11px] font-medium uppercase tracking-wide text-ink-400">
                  {group.period}
                </span>
              </div>
              <div className="space-y-1.5">
                {group.activities.map((activity, index) => (
                  <StreamingActivityRow
                    key={`${activity.name}-${index}`}
                    activity={activity}
                  />
                ))}
              </div>
            </div>
          );
        })}
      </div>
    </motion.section>
  );
}

function StreamingActivityRow({ activity }: { activity: Activity }) {
  const isFood = activity.activity_type === "美食";
  const Icon = isFood ? Utensils : MapPin;

  return (
    <motion.div
      className="flex items-center gap-2 rounded-lg bg-cream-50 px-2.5 py-1.5"
      initial={{ opacity: 0, x: -6 }}
      animate={{ opacity: 1, x: 0 }}
      transition={{ duration: 0.22 }}
    >
      <Icon className="h-3.5 w-3.5 shrink-0 text-blush-400" />
      <span className="min-w-0 flex-1 truncate text-xs font-medium text-ink-700">
        {activity.name}
      </span>
      {activity.estimated_cost > 0 && (
        <CostChip cost={activity.estimated_cost} />
      )}
    </motion.div>
  );
}

function CostChip({ cost }: { cost: number }) {
  return (
    <span className="shrink-0 rounded-full bg-surface px-1.5 py-0.5 text-[11px] tabular-nums text-ink-400">
      ¥{cost}
    </span>
  );
}
