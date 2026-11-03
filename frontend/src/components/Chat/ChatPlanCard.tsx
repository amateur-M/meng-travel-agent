import {
  CalendarDays,
  ChevronDown,
  ChevronUp,
  MapPin,
  Sparkles,
  WalletCards,
} from "lucide-react";
import { BudgetBar } from "../BudgetBar/BudgetBar";
import { Timeline } from "../Timeline/Timeline";
import type { TripPlanResponse } from "../../types/trip";

interface ChatPlanCardProps {
  plan: TripPlanResponse;
  expanded: boolean;
  onToggle: () => void;
  onOpenFull: () => void;
}

/**
 * The itinerary, shown inside the conversation.
 *
 * Generating a trip used to navigate away to /result, which hid the itinerary
 * from the chat that produced it — and since adjusting a trip happens by
 * talking, the user had to walk back to the conversation to change anything.
 * Keeping the itinerary here (and the input right below it) makes
 * "再加一天" / "预算加到八千" the obvious next move.
 *
 * V6/T2.4: the hero header now states the destination/date/budget as one
 * summary line with the budget ratio as a small meter, instead of three pills of
 * equal weight — the destination is the headline, budget is the status.
 */
export function ChatPlanCard({ plan, expanded, onToggle, onOpenFull }: ChatPlanCardProps) {
  const { total_budget, total_spent, over_budget } = plan.budget_breakdown;
  const percentage = Math.round((total_spent / Math.max(total_budget, 1)) * 100);

  return (
    <div
      data-testid="chat-plan-card"
      className="overflow-hidden rounded-2xl border border-cream-200 bg-surface shadow-lift"
    >
      <div className="relative overflow-hidden bg-gradient-to-br from-brand to-brand-dark px-4 py-3.5 text-white">
        <div
          aria-hidden="true"
          className="pointer-events-none absolute -right-8 -top-10 h-32 w-32 rounded-full bg-gold-300/25 blur-2xl"
        />
        <div className="relative flex flex-wrap items-start justify-between gap-3">
          <div className="min-w-0">
            <div className="flex items-center gap-1.5">
              <MapPin className="h-4 w-4 shrink-0" />
              <p className="truncate text-base font-semibold">{plan.destination}</p>
              <span className="inline-flex shrink-0 items-center gap-1 rounded-full bg-white/15 px-2 py-0.5 text-[11px] backdrop-blur-sm">
                <Sparkles className="h-3 w-3" />
                {plan.days.length} 天
              </span>
            </div>
            <p className="mt-1 flex items-center gap-1.5 text-xs text-white/80">
              <CalendarDays className="h-3.5 w-3.5" />
              {plan.start_date} 至 {plan.end_date}
            </p>
          </div>

          <div className="text-right">
            <p className="text-[11px] text-white/70">预算使用</p>
            <p className="text-sm font-semibold tabular-nums">
              ¥{total_spent.toLocaleString("zh-CN")}
              <span className="text-white/70"> / ¥{total_budget.toLocaleString("zh-CN")}</span>
            </p>
          </div>
        </div>

        {/* A hairline meter inside the hero: the ratio without a second widget. */}
        <div className="relative mt-2.5 h-1 overflow-hidden rounded-full bg-white/20">
          <div
            className={`h-full rounded-full ${over_budget ? "bg-white" : "bg-white/85"}`}
            style={{ width: `${Math.min(100, percentage)}%` }}
          />
        </div>
      </div>

      <div className="space-y-3 p-3.5">
        <BudgetBar
          totalBudget={total_budget}
          totalSpent={total_spent}
          overBudget={over_budget}
        />

        <div className="flex flex-wrap items-center gap-2">
          <button
            type="button"
            onClick={onToggle}
            data-testid="chat-plan-toggle"
            aria-expanded={expanded}
            className="ct-btn-outline h-8 px-3 text-xs"
          >
            {expanded ? <ChevronUp className="h-3.5 w-3.5" /> : <ChevronDown className="h-3.5 w-3.5" />}
            {expanded ? "收起行程" : "展开行程"}
          </button>
          <button
            type="button"
            onClick={onOpenFull}
            className="ct-btn-quiet h-8 border border-cream-200 px-3 text-xs"
          >
            <WalletCards className="h-3.5 w-3.5" />
            查看完整行程
          </button>
        </div>

        {expanded && (
          <div className="ct-scroll max-h-[45vh] overflow-y-auto rounded-xl bg-cream-50/70 p-3">
            <Timeline
              days={plan.days}
              weatherSwaps={plan.weather_swaps}
              planId={plan.plan_id}
              compact
            />
          </div>
        )}

        {!expanded && (
          <p className="text-xs leading-5 text-ink-400">
            想调整就接着说，比如“再加一天”“预算加到八千”。
          </p>
        )}
      </div>
    </div>
  );
}
