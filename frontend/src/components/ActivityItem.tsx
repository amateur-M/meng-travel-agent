import {
  Clock3,
  MapPin,
  MessageCircleHeart,
  WalletCards,
} from "lucide-react";
import type { Activity, ActivityType } from "../types/trip";

const typeStyles: Record<ActivityType, string> = {
  景点: "bg-sky-100 text-sky-700",
  美食: "bg-amber-100 text-amber-700",
  室内: "bg-violet-100 text-violet-700",
  户外: "bg-emerald-100 text-emerald-700",
  文化: "bg-indigo-100 text-indigo-700",
  冒险: "bg-rose-100 text-rose-700",
  留白: "bg-slate-100 text-slate-600",
};

interface ActivityItemProps {
  activity: Activity;
}

export function ActivityItem({ activity }: ActivityItemProps) {
  const badgeStyle =
    typeStyles[activity.activity_type] ?? "bg-slate-100 text-slate-600";

  return (
    <div className="border-b border-slate-100 py-4 last:border-b-0">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <h4 className="font-semibold text-slate-900">{activity.name}</h4>
            <span
              className={`rounded-full px-2 py-0.5 text-xs font-medium ${badgeStyle}`}
            >
              {activity.activity_type}
            </span>
          </div>

          <p className="mt-1 text-sm leading-6 text-slate-600">
            {activity.description}
          </p>

          <div className="mt-2 flex flex-wrap gap-x-4 gap-y-1 text-xs text-slate-500">
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

            <span className="inline-flex items-center gap-1 font-medium text-slate-700">
              <WalletCards className="h-3.5 w-3.5" />¥
              {activity.estimated_cost.toFixed(0)}
            </span>
          </div>
        </div>
      </div>

      {activity.weather_note && (
        <p className="mt-3 rounded-md bg-sky-50 px-3 py-2 text-xs text-sky-700">
          {activity.weather_note}
        </p>
      )}

      {activity.couple_note && (
        <p className="mt-2 inline-flex max-w-full items-start gap-1.5 text-sm italic text-rose-700">
          <MessageCircleHeart className="mt-0.5 h-4 w-4 shrink-0" />
          <span>{activity.couple_note}</span>
        </p>
      )}
    </div>
  );
}
