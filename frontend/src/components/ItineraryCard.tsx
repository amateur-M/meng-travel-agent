import {
  Cloud,
  CloudRain,
  CloudSun,
  Sun,
  Wind,
} from "lucide-react";
import type { DayPlan, Period } from "../types/trip";
import { ActivityItem } from "./ActivityItem";

const PERIODS: Period[] = ["上午", "下午", "晚间"];

interface ItineraryCardProps {
  day: DayPlan;
}

function WeatherIcon({ condition }: { condition: string }) {
  if (/雨|雪|雷|阵/.test(condition)) {
    return <CloudRain className="h-5 w-5 text-sky-600" />;
  }

  if (/风/.test(condition)) {
    return <Wind className="h-5 w-5 text-slate-500" />;
  }

  if (/云|阴/.test(condition)) {
    return <Cloud className="h-5 w-5 text-slate-500" />;
  }

  if (/晴/.test(condition)) {
    return <Sun className="h-5 w-5 text-amber-500" />;
  }

  return <CloudSun className="h-5 w-5 text-sky-600" />;
}

export function ItineraryCard({ day }: ItineraryCardProps) {
  const tripDate = new Date(`${day.trip_date}T00:00:00`);
  const dateLabel = new Intl.DateTimeFormat("zh-CN", {
    month: "long",
    day: "numeric",
    weekday: "short",
  }).format(tripDate);

  const groupedActivities = PERIODS.map((period) => ({
    period,
    activities: day.activities.filter((activity) => activity.period === period),
  })).filter((group) => group.activities.length > 0);

  return (
    <article className="rounded-lg border border-slate-200 bg-white shadow-sm">
      <header className="flex flex-wrap items-center justify-between gap-3 border-b border-slate-100 px-4 py-3 sm:px-5">
        <div className="flex items-center gap-3">
          <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-primary-50 text-primary-700">
            <span className="text-sm font-bold">D{day.day_index + 1}</span>
          </div>
          <div>
            <h3 className="font-semibold text-slate-900">{dateLabel}</h3>
            <div className="mt-0.5 flex items-center gap-1.5 text-xs text-slate-500">
              <WeatherIcon condition={day.weather_condition} />
              <span>{day.weather_condition}</span>
              {day.weather_high != null && day.weather_low != null && (
                <span>
                  {day.weather_low.toFixed(0)}° / {day.weather_high.toFixed(0)}°
                </span>
              )}
            </div>
          </div>
        </div>

        <div className="text-right">
          <span className="text-xs text-slate-500">当日花费</span>
          <p className="font-semibold tabular-nums text-slate-900">
            ¥{day.daily_cost.toFixed(0)}
          </p>
        </div>
      </header>

      <div className="px-4 sm:px-5">
        {groupedActivities.map((group) => (
          <section key={group.period}>
            <div className="sticky top-0 -mx-1 flex items-center gap-2 bg-white py-3">
              <h4 className="text-xs font-semibold uppercase tracking-wide text-slate-400">
                {group.period}
              </h4>
              <div className="h-px flex-1 bg-slate-100" />
            </div>

            <div>
              {group.activities.map((activity, index) => (
                <ActivityItem
                  key={`${activity.name}-${index}`}
                  activity={activity}
                />
              ))}
            </div>
          </section>
        ))}

        {day.day_note && (
          <p className="border-t border-slate-100 py-4 text-sm leading-6 text-slate-600">
            {day.day_note}
          </p>
        )}
      </div>
    </article>
  );
}
