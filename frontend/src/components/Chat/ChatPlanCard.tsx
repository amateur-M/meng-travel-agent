import { CalendarDays, ChevronDown, ChevronUp, MapPin, Sparkles, WalletCards } from "lucide-react";
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
 */
export function ChatPlanCard({ plan, expanded, onToggle, onOpenFull }: ChatPlanCardProps) {
  const { total_budget, total_spent, over_budget } = plan.budget_breakdown;
  const percentage = Math.round((total_spent / Math.max(total_budget, 1)) * 100);

  return (
    <div
      data-testid="chat-plan-card"
      className="rounded-2xl border border-blush-200 bg-white p-4 shadow-soft"
    >
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <div className="flex items-center gap-2">
            <MapPin className="h-4 w-4 shrink-0 text-blush-500" />
            <p className="truncate text-sm font-semibold text-ink-900">{plan.destination}</p>
          </div>
          <div className="mt-1 flex items-center gap-1.5 text-xs text-ink-500">
            <CalendarDays className="h-3.5 w-3.5 text-gold-400" />
            {plan.start_date} 至 {plan.end_date}
          </div>
        </div>

        <div className="flex flex-wrap items-center gap-2">
          <span className="inline-flex items-center gap-1.5 rounded-full bg-cream-100 px-2.5 py-1 text-xs text-ink-500">
            <Sparkles className="h-3.5 w-3.5 text-gold-400" />
            {plan.days.length} 天
          </span>
          <span className="inline-flex items-center gap-1.5 rounded-full bg-cream-100 px-2.5 py-1 text-xs text-ink-500">
            <WalletCards className="h-3.5 w-3.5 text-blush-400" />¥
            {total_spent.toLocaleString("zh-CN")} / ¥{total_budget.toLocaleString("zh-CN")} · {percentage}%
          </span>
        </div>
      </div>

      <div className="mt-3">
        <BudgetBar
          totalBudget={total_budget}
          totalSpent={total_spent}
          overBudget={over_budget}
        />
      </div>

      <div className="mt-3 flex flex-wrap items-center gap-2">
        <button
          type="button"
          onClick={onToggle}
          data-testid="chat-plan-toggle"
          className="inline-flex items-center gap-1.5 rounded-lg border border-cream-200 px-3 py-1.5 text-xs font-medium text-ink-600 transition hover:bg-cream-100"
        >
          {expanded ? <ChevronUp className="h-3.5 w-3.5" /> : <ChevronDown className="h-3.5 w-3.5" />}
          {expanded ? "收起行程" : "展开行程"}
        </button>
        <button
          type="button"
          onClick={onOpenFull}
          className="inline-flex items-center gap-1.5 rounded-lg bg-cream-100 px-3 py-1.5 text-xs font-medium text-ink-600 transition hover:bg-cream-200"
        >
          查看完整行程
        </button>
        <span className="text-xs text-ink-400">
          想调整就接着说，比如“再加一天”“预算加到八千”
        </span>
      </div>

      {expanded && (
        <div className="mt-3 max-h-[45vh] overflow-y-auto rounded-xl border border-cream-200 bg-cream-50/60 p-3">
          <Timeline days={plan.days} weatherSwaps={plan.weather_swaps} planId={plan.plan_id} />
        </div>
      )}
    </div>
  );
}
