import { motion, type Variants } from "framer-motion";
import {
  Clock3,
  Coffee,
  House,
  Landmark,
  MapPin,
  Mountain,
  Palette,
  TreePine,
  Utensils,
  WalletCards,
} from "lucide-react";
import type { Activity, ActivityType } from "../../types/trip";
import { CoupleMessage } from "../CoupleMessage/CoupleMessage";

interface TimelineCardProps {
  activity: Activity;
}

const TYPE_META: Record<
  ActivityType,
  { Icon: typeof MapPin; className: string }
> = {
  景点: { Icon: Landmark, className: "bg-sky-50 text-sky-700" },
  美食: { Icon: Utensils, className: "bg-amber-50 text-amber-700" },
  室内: { Icon: House, className: "bg-violet-50 text-violet-700" },
  户外: { Icon: TreePine, className: "bg-emerald-50 text-emerald-700" },
  文化: { Icon: Palette, className: "bg-indigo-50 text-indigo-700" },
  冒险: { Icon: Mountain, className: "bg-rose-50 text-rose-700" },
  留白: { Icon: Coffee, className: "bg-cream-100 text-ink-500" },
};

export const timelineCardMotion: Variants = {
  hidden: { opacity: 0, y: 14 },
  visible: {
    opacity: 1,
    y: 0,
    transition: { duration: 0.4, ease: "easeOut" },
  },
};

/**
 * 单个活动卡片，展示类型图标、时间、地点、花费与情侣寄语。
 * M5: 留白活动用虚线边框区分；寄语用 CoupleMessage 按时段差异化展示。
 */
export function TimelineCard({ activity }: TimelineCardProps) {
  const meta = TYPE_META[activity.activity_type] ?? TYPE_META.留白;
  const Icon = meta.Icon;
  const isRest = activity.activity_type === "留白";

  return (
    <motion.article
      className={`relative rounded-lg p-4 shadow-soft ${
        isRest
          ? "border border-dashed border-cream-300 bg-cream-50/40"
          : "border border-cream-200 bg-white"
      }`}
      variants={timelineCardMotion}
    >
      <div className="flex gap-3">
        <div
          className={`flex h-10 w-10 shrink-0 items-center justify-center rounded-lg ${meta.className}`}
        >
          <Icon className="h-5 w-5" />
        </div>

        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-start justify-between gap-2">
            <div className="min-w-0">
              <div className="flex flex-wrap items-center gap-2">
                <h3 className="font-semibold text-ink-900">{activity.name}</h3>
                <span
                  className={`rounded-full px-2 py-0.5 text-xs font-medium ${meta.className}`}
                >
                  {activity.activity_type}
                </span>
              </div>

              <p className="mt-2 text-sm leading-6 text-ink-500">
                {activity.description}
              </p>
            </div>

            {!isRest && (
              <span className="inline-flex items-center gap-1 text-sm font-semibold tabular-nums text-ink-700">
                <WalletCards className="h-3.5 w-3.5 text-gold-400" />¥
                {activity.estimated_cost.toLocaleString("zh-CN")}
              </span>
            )}
          </div>

          <div className="mt-3 flex flex-wrap gap-x-4 gap-y-2 text-xs text-ink-400">
            <span className="inline-flex items-center gap-1">
              <Clock3 className="h-3.5 w-3.5" />
              {activity.start_time ?? "时间待定"} · {activity.duration_min} 分钟
            </span>

            {activity.location && (
              <span className="inline-flex items-center gap-1">
                <MapPin className="h-3.5 w-3.5" />
                {activity.location}
              </span>
            )}
          </div>

          {activity.weather_note && (
            <p className="mt-3 border-l-2 border-sky-200 pl-3 text-sm leading-6 text-sky-700">
              {activity.weather_note}
            </p>
          )}

          {activity.couple_note && (
            <CoupleMessage
              text={activity.couple_note}
              activityType={activity.activity_type}
              period={activity.period}
            />
          )}
        </div>
      </div>
    </motion.article>
  );
}
