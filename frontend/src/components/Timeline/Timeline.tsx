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
  /** Tighter cards + spacing for the in-chat itinerary. */
  compact?: boolean;
}

const PERIODS: Period[] = ["上午", "下午", "晚间"];

const PERIOD_META: Record<Period, { Icon: typeof Sun }> = {
  上午: { Icon: Sunrise },
  下午: { Icon: Sun },
  晚间: { Icon: Moon },
};

const timelineVariants: Variants = {
  hidden: {},
  visible: {
    transition: { staggerChildren: 0.08 },
  },
};

const dayVariants: Variants = {
  hidden: { opacity: 0, y: 12 },
  visible: {
    opacity: 1,
    y: 0,
    transition: { duration: 0.35, ease: "easeOut" },
  },
};

/** "9月1日 周二" — the year is redundant inside a 3-day plan. */
function formatDay(tripDate: string): string {
  const date = new Date(`${tripDate}T00:00:00`);
  if (Number.isNaN(date.getTime())) {
    return tripDate;
  }
  return new Intl.DateTimeFormat("zh-CN", {
    month: "long",
    day: "numeric",
    weekday: "short",
  }).format(date);
}

interface TimelineDayProps {
  day: DayPlan;
  weatherSwaps: WeatherSwap[];
  expanded: boolean;
  onToggle: () => void;
  planId?: string;
  compact: boolean;
}

function TimelineDay({
  day,
  weatherSwaps,
  expanded,
  onToggle,
  planId,
  compact,
}: TimelineDayProps) {
  const groups = PERIODS.map((period) => ({
    period,
    activities: day.activities.filter((activity) => activity.period === period),
  })).filter((group) => group.activities.length > 0);

  const adaptations = weatherSwaps
    .filter((swap) => swap.day_index === day.day_index)
    .map((swap) => swap.reason)
    .filter((reason, index, items) => items.indexOf(reason) === index);

  return (
    <motion.section className="relative" variants={dayVariants}>
      {/* Day header — no card chrome. A day is a section of one document, not a
          boxed widget; boxing each day made a 3-day trip read as three separate
          reports (V6/T2.1). */}
      <button
        type="button"
        onClick={onToggle}
        aria-expanded={expanded}
        className="ct-card flex w-full items-center justify-between gap-3 px-4 py-3 text-left transition hover:border-cream-300"
      >
        <div className="flex min-w-0 items-center gap-3">
          <span className="flex h-11 w-11 shrink-0 flex-col items-center justify-center rounded-xl bg-brand text-white">
            <span className="text-[9px] font-medium uppercase leading-none tracking-wide opacity-80">
              Day
            </span>
            <span className="text-base font-bold leading-tight">{day.day_index + 1}</span>
          </span>
          <div className="min-w-0">
            <h2 className="truncate font-semibold text-ink-900">{formatDay(day.trip_date)}</h2>
            <p className="mt-0.5 flex items-center gap-1.5 text-xs text-ink-400">
              <span>{day.activities.length} 个安排</span>
              <span aria-hidden="true">·</span>
              <span className="tabular-nums">¥{day.daily_cost.toLocaleString("zh-CN")}</span>
            </p>
          </div>
        </div>

        <ChevronDown
          className={`h-5 w-5 shrink-0 text-ink-400 transition-transform duration-300 ${
            expanded ? "rotate-180" : ""
          }`}
        />
      </button>

      <div className="mt-2.5 px-1">
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
          <div className={`space-y-5 ${compact ? "pt-3" : "pt-4"}`}>
            {groups.map((group) => {
              const PeriodIcon = PERIOD_META[group.period].Icon;

              return (
                <div key={group.period} className="space-y-2.5">
                  <div className="flex items-center gap-2">
                    <PeriodIcon className="h-3.5 w-3.5 text-gold-400" />
                    <h3 className="text-xs font-semibold uppercase tracking-wide text-ink-400">
                      {group.period}
                    </h3>
                    <div className="h-px flex-1 bg-cream-200" />
                  </div>

                  <div className="grid gap-2.5">
                    {group.activities.map((activity, index) => (
                      <TimelineCard
                        key={`${activity.name}-${index}`}
                        activity={activity}
                        planId={planId}
                        compact={compact}
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
export function Timeline({ days, weatherSwaps = [], planId, compact = false }: TimelineProps) {
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
      className={compact ? "space-y-5" : "space-y-7"}
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
          compact={compact}
        />
      ))}
    </motion.div>
  );
}
