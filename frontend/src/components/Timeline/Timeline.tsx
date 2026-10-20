import { useState } from "react";
import { motion, type Variants } from "framer-motion";
import { ChevronDown, Moon, Sun, Sunrise } from "lucide-react";
import type { DayPlan, Period, WeatherSwap } from "../../types/trip";
import { TimelineCard } from "../TimelineCard/TimelineCard";
import { WeatherBadge } from "../WeatherBadge/WeatherBadge";

interface TimelineProps {
  days: DayPlan[];
  weatherSwaps?: WeatherSwap[];
  planId?: string;
}

const PERIODS: Period[] = ["上午", "下午", "晚间"];

const PERIOD_META: Record<Period, { label: string; Icon: typeof Sun }> = {
  上午: { label: "上午", Icon: Sunrise },
  下午: { label: "下午", Icon: Sun },
  晚间: { label: "晚间", Icon: Moon },
};

const timelineVariants: Variants = {
  hidden: {},
  visible: {
    transition: { staggerChildren: 0.12 },
  },
};

const dayVariants: Variants = {
  hidden: { opacity: 0, y: 16 },
  visible: {
    opacity: 1,
    y: 0,
    transition: { duration: 0.4, ease: "easeOut" },
  },
};

interface TimelineDayProps {
  day: DayPlan;
  weatherSwaps: WeatherSwap[];
  expanded: boolean;
  onToggle: () => void;
  planId?: string;
}

function TimelineDay({
  day,
  weatherSwaps,
  expanded,
  onToggle,
  planId,
}: TimelineDayProps) {
  const dateLabel = new Intl.DateTimeFormat("zh-CN", {
    month: "long",
    day: "numeric",
    weekday: "short",
  }).format(new Date(`${day.trip_date}T00:00:00`));

  const groups = PERIODS.map((period) => ({
    period,
    activities: day.activities.filter((activity) => activity.period === period),
  })).filter((group) => group.activities.length > 0);
  const adaptations = weatherSwaps
    .filter((swap) => swap.day_index === day.day_index)
    .map((swap) => swap.reason)
    .filter((reason, index, items) => items.indexOf(reason) === index);

  return (
    <motion.section
      className="relative ct-card"
      variants={dayVariants}
    >
      <button
        type="button"
        className="flex w-full items-center justify-between gap-3 px-4 py-3 text-left sm:px-5"
        onClick={onToggle}
      >
        <div className="flex min-w-0 items-center gap-3">
          <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-blush-50 text-sm font-bold text-blush-600">
            D{day.day_index + 1}
          </span>
          <div className="min-w-0">
            <h2 className="font-semibold text-ink-900">{dateLabel}</h2>
            <p className="mt-0.5 text-xs text-ink-400">
              当日花费 ¥{day.daily_cost.toLocaleString("zh-CN")}
            </p>
          </div>
        </div>

        <ChevronDown
          className={`h-5 w-5 shrink-0 text-ink-400 transition-transform ${
            expanded ? "rotate-180" : ""
          }`}
        />
      </button>

      <div className="border-t border-cream-100 px-4 py-3 sm:px-5">
        <WeatherBadge
          condition={day.weather_condition}
          kind={day.weather_kind}
          high={day.weather_high}
          low={day.weather_low}
          note={day.day_note}
          adaptations={adaptations}
        />
      </div>

      {/*
        Expand/collapse via CSS grid rows (0fr → 1fr) instead of framer-motion's
        height: "auto": the latter measures content height on mount and collapses
        to 0 on the *second* expand (framer-motion 11), leaving a blank day.
        grid-template-rows needs no measurement and animates reliably both ways.
      */}
      <div
        className={`grid transition-[grid-template-rows] duration-300 ease-in-out ${
          expanded ? "grid-rows-[1fr]" : "grid-rows-[0fr]"
        }`}
      >
        <div className="min-h-0 overflow-hidden">
          <div className="space-y-5 px-4 pb-5 sm:px-5">
            {groups.map((group) => {
              const meta = PERIOD_META[group.period];
              const PeriodIcon = meta.Icon;

              return (
                <div key={group.period} className="space-y-3">
                  <div className="flex items-center gap-2">
                    <PeriodIcon className="h-4 w-4 text-gold-400" />
                    <h3 className="text-sm font-semibold text-ink-700">
                      {meta.label}
                    </h3>
                    <div className="h-px flex-1 bg-cream-200" />
                  </div>

                  <div className="grid gap-3">
                    {group.activities.map((activity, index) => (
                      <TimelineCard
                         key={`${activity.name}-${index}`}
                         activity={activity}
                         planId={planId}
                       />
                    ))}
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      </div>
    </motion.section>
  );
}

/**
 * 行程时间轴，按 Day 1 到 Day N 展开，每天再分为上午、下午和晚间。
 */
export function Timeline({ days, weatherSwaps = [], planId }: TimelineProps) {
  const [expandedDays, setExpandedDays] = useState<Set<number>>(
    () => new Set(days.map((day) => day.day_index)),
  );

  const toggleDay = (dayIndex: number) => {
    setExpandedDays((current) => {
      const next = new Set(current);

      if (next.has(dayIndex)) {
        next.delete(dayIndex);
      } else {
        next.add(dayIndex);
      }

      return next;
    });
  };

  return (
    <motion.div
      className="grid gap-4"
      variants={timelineVariants}
      initial="hidden"
      animate="visible"
    >
      {days.map((day) => (
        <TimelineDay
          key={day.day_index}
          day={day}
          weatherSwaps={weatherSwaps}
          expanded={expandedDays.has(day.day_index)}
          onToggle={() => toggleDay(day.day_index)}
          planId={planId}
        />
      ))}
    </motion.div>
  );
}
