import { AnimatePresence, motion } from "framer-motion";
import { CloudSun, MapPin, Utensils } from "lucide-react";
import type { Activity } from "../../types/trip";

interface StreamingDay {
  day_index: number;
  weather?: string;
  activities: Activity[];
}

interface StreamingItineraryProps {
  days: StreamingDay[];
}

const PERIOD_LABELS: Record<string, string> = {
  上午: "上午",
  下午: "下午",
  晚间: "晚间",
};

const PERIOD_ICONS: Record<string, typeof MapPin> = {
  上午: CloudSun,
  下午: CloudSun,
  晚间: CloudSun,
};

/**
 * 流式行程预览，在 SSE partial 事件到达时逐日逐时段渲染活动卡片。
 */
export function StreamingItinerary({ days }: StreamingItineraryProps) {
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
      className="rounded-lg border border-cream-200 bg-white/80 p-3 shadow-soft"
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0 }}
      transition={{ duration: 0.35, ease: "easeOut" }}
    >
      <div className="flex items-center gap-2 px-1 pb-2">
        <span className="flex h-7 w-7 items-center justify-center rounded-md bg-blush-50 text-xs font-bold text-blush-600">
          D{day.day_index + 1}
        </span>
        {day.weather && (
          <span className="flex items-center gap-1 text-xs text-ink-400">
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
                <span className="text-xs font-medium text-ink-500">
                  {PERIOD_LABELS[group.period] ?? group.period}
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
      className="flex items-center gap-2 rounded-md bg-cream-50 px-2.5 py-1.5"
      initial={{ opacity: 0, x: -8 }}
      animate={{ opacity: 1, x: 0 }}
      transition={{ duration: 0.25 }}
    >
      <Icon className="h-3.5 w-3.5 shrink-0 text-blush-400" />
      <span className="min-w-0 flex-1 truncate text-xs font-medium text-ink-700">
        {activity.name}
      </span>
      {activity.estimated_cost > 0 && (
        <span className="shrink-0 text-xs text-ink-400">
          ¥{activity.estimated_cost}
        </span>
      )}
    </motion.div>
  );
}
