import { useState } from "react";
import { motion, type Variants } from "framer-motion";
import {
  Clock3,
  Coffee,
  House,
  Landmark,
  MapPin,
  Mountain,
  Palette,
  ThumbsDown,
  ThumbsUp,
  TreePine,
  Utensils,
  WalletCards,
} from "lucide-react";
import { TONE, type Tone } from "../../config/tones";
import type { Activity, ActivityType } from "../../types/trip";
import { CoupleMessage } from "../CoupleMessage/CoupleMessage";
import { ActivityImage } from "./ActivityImage";
import { api } from "../../services/api";

interface TimelineCardProps {
  activity: Activity;
  planId?: string;
  /** Tighter box for the in-chat itinerary where vertical space is scarce. */
  compact?: boolean;
}

const TYPE_META: Record<ActivityType, { Icon: typeof MapPin; tone: Tone }> = {
  景点: { Icon: Landmark, tone: "sky" },
  美食: { Icon: Utensils, tone: "orange" },
  室内: { Icon: House, tone: "violet" },
  户外: { Icon: TreePine, tone: "emerald" },
  文化: { Icon: Palette, tone: "indigo" },
  冒险: { Icon: Mountain, tone: "rose" },
  留白: { Icon: Coffee, tone: "amber" },
};

export const timelineCardMotion: Variants = {
  hidden: { opacity: 0, y: 8 },
  visible: {
    opacity: 1,
    y: 0,
    transition: { duration: 0.3, ease: "easeOut" },
  },
};

/**
 * 单个活动卡片，展示类型图标、时间、地点、花费与情侣寄语。
 * M5: 留白活动用虚线边框区分；寄语用 CoupleMessage 按时段差异化展示。
 *
 * V6/T2.2: layout reworked so the two things a reader actually compares — the
 * name and the cost — sit on one line, with time/place as a quiet meta row
 * underneath. The type icon shrank to a chip-sized badge inside that meta row
 * (it used to be a 40px tile competing with the title for attention), which
 * gives the description the full card width.
 */
export function TimelineCard({ activity, planId, compact = false }: TimelineCardProps) {
  const meta = TYPE_META[activity.activity_type] ?? TYPE_META.留白;
  const Icon = meta.Icon;
  const tone = TONE[meta.tone];
  const isRest = activity.activity_type === "留白";
  // A real photo always shows; otherwise the themed placeholder banner is drawn
  // for substantive activities but skipped for 留白 so rest slots stay light.
  const showBanner = Boolean(activity.image_url) || !isRest;
  const [feedbackState, setFeedbackState] = useState<"none" | "up" | "down">("none");

  const handleFeedback = async (thumbs: "up" | "down") => {
    if (!planId || feedbackState !== "none") {
      return;
    }
    setFeedbackState(thumbs);
    try {
      await api.post(
        `/api/plan/${planId}/feedback?activity_name=${encodeURIComponent(activity.name)}&thumbs=${thumbs}`,
      );
    } catch {
      // silently fail — feedback is best-effort
    }
  };

  return (
    <motion.article
      className={`group relative rounded-2xl transition ${
        isRest
          ? "border border-dashed border-cream-300 bg-cream-50/40 p-4"
          : `border border-cream-200 bg-surface shadow-soft ${compact ? "p-3.5" : "p-4"}`
      }`}
      variants={timelineCardMotion}
    >
      {showBanner && (
        <ActivityImage
          name={activity.name}
          type={activity.activity_type}
          imageUrl={activity.image_url}
          compact={compact}
        />
      )}

      <div className="flex flex-wrap items-start justify-between gap-x-3 gap-y-1">
        <h3 className="min-w-0 flex-1 font-semibold leading-6 text-ink-900">
          {activity.name}
        </h3>

        {!isRest && (
          <span className="inline-flex shrink-0 items-center gap-1 text-sm font-semibold tabular-nums text-ink-700">
            <WalletCards className="h-3.5 w-3.5 text-gold-400" />¥
            {activity.estimated_cost.toLocaleString("zh-CN")}
          </span>
        )}
      </div>

      {/* Meta row: type, time, place — the identifiers, not the content. */}
      <div className="mt-2 flex flex-wrap items-center gap-x-3 gap-y-1.5 text-xs text-ink-400">
        <span className={`ct-chip border font-medium ${tone.chip}`}>
          <Icon className="h-3 w-3" />
          {activity.activity_type}
        </span>
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

      <p className="mt-2.5 text-sm leading-6 text-ink-500">{activity.description}</p>

      {activity.weather_note && (
        <p className="mt-2.5 flex items-start gap-1.5 text-sm leading-6 text-tone-sky-strong">
          <span aria-hidden="true" className="mt-2 h-1.5 w-1.5 shrink-0 rounded-full bg-current" />
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

      {/* Feedback stays hidden until hover/focus on pointer devices, but is
          always visible where hover does not exist (V6/T3.5) — previously
          `opacity-0 group-hover` made it unreachable on touch. */}
      {!isRest && planId && (
        <div className="mt-2.5 flex gap-1 opacity-100 transition sm:opacity-0 sm:group-hover:opacity-100 sm:group-focus-within:opacity-100">
          <button
            type="button"
            onClick={() => handleFeedback("up")}
            disabled={feedbackState !== "none"}
            aria-label={`喜欢「${activity.name}」`}
            aria-pressed={feedbackState === "up"}
            className={`ct-btn-quiet h-7 w-7 ${
              feedbackState === "up" ? `${TONE.emerald.soft} ${TONE.emerald.strong}` : ""
            }`}
          >
            <ThumbsUp className="h-3.5 w-3.5" />
          </button>
          <button
            type="button"
            onClick={() => handleFeedback("down")}
            disabled={feedbackState !== "none"}
            aria-label={`不喜欢「${activity.name}」`}
            aria-pressed={feedbackState === "down"}
            className={`ct-btn-quiet h-7 w-7 ${
              feedbackState === "down" ? `${TONE.rose.soft} ${TONE.rose.strong}` : ""
            }`}
          >
            <ThumbsDown className="h-3.5 w-3.5" />
          </button>
        </div>
      )}
    </motion.article>
  );
}
