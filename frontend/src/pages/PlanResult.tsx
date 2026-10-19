import { useEffect, useState } from "react";
import { motion } from "framer-motion";
import {
  ArrowLeft,
  CalendarDays,
  MapPin,
  Sparkles,
  WalletCards,
} from "lucide-react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { AppHeader } from "../components/AppHeader";
import { BudgetAlerts } from "../components/BudgetAlerts/BudgetAlerts";
import { BudgetBar } from "../components/BudgetBar/BudgetBar";
import { CoupleQuote } from "../components/CoupleQuote/CoupleQuote";
import { Timeline } from "../components/Timeline/Timeline";
import { useTripStore } from "../stores/tripStore";

/**
 * 行程展示页，以可折叠时间轴呈现每日活动，并汇总预算与情侣寄语。
 */
export function PlanResult() {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const planIdParam = searchParams.get("plan_id");
  const plan = useTripStore((state) => state.plan);
  const loadPlan = useTripStore((state) => state.loadPlan);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!plan && planIdParam) {
      setLoading(true);
      loadPlan(planIdParam).then((ok) => {
        if (!ok) {
          // Not finished yet (or the id is gone). Send it to /loading, which
          // resumes an in-flight plan and comes back here when it is ready —
          // and shows an explanatory error for an id that no longer exists,
          // which is better than silently dropping the user on the chat page.
          navigate(`/loading?plan_id=${planIdParam}`, { replace: true });
        }
        setLoading(false);
      });
    } else if (!plan && !planIdParam) {
      navigate("/", { replace: true });
    }
  }, [navigate, plan, planIdParam, loadPlan]);

  if (loading) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-cream-50 text-ink-500">
        <p className="text-sm">正在恢复行程...</p>
      </div>
    );
  }

  if (!plan) {
    return null;
  }

  const budgetPercentage = Math.round(
    (plan.budget_breakdown.total_spent /
      Math.max(plan.budget_breakdown.total_budget, 1)) *
      100,
  );

  return (
    <div className="min-h-screen bg-cream-50 text-ink-900">
      <AppHeader
        sticky
        leading={
          <button
            type="button"
            className="inline-flex items-center gap-1.5 rounded-lg px-2 py-1.5 text-sm font-medium text-ink-500 transition hover:bg-cream-100 hover:text-ink-900"
            onClick={() => navigate("/")}
          >
            <ArrowLeft className="h-4 w-4" />
            重新规划
          </button>
        }
      />

      <main className="mx-auto max-w-6xl px-4 py-5 sm:px-6 sm:py-8">
        <motion.section
          className="relative overflow-hidden rounded-2xl bg-gradient-to-br from-brand to-brand-dark p-6 text-white shadow-lift sm:p-8"
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.4 }}
        >
          {/* Decorative glow — a fixed gold accent so it reads the same in both themes. */}
          <div
            aria-hidden="true"
            className="pointer-events-none absolute -right-10 -top-12 h-48 w-48 rounded-full bg-gold-300/30 blur-2xl"
          />
          <div className="relative flex flex-wrap items-start justify-between gap-4">
            <div className="min-w-0">
              <div className="flex items-center gap-2">
                <MapPin className="h-6 w-6" />
                <h1 className="text-3xl font-semibold tracking-tight">{plan.destination}</h1>
              </div>
              <div className="mt-3 flex items-center gap-1.5 text-sm text-white/85">
                <CalendarDays className="h-4 w-4" />
                {plan.start_date} 至 {plan.end_date}
              </div>
            </div>

            <div className="flex flex-wrap items-center gap-2">
              <div className="flex items-center gap-2 rounded-full bg-white/15 px-3 py-1.5 text-xs text-white backdrop-blur-sm">
                <Sparkles className="h-3.5 w-3.5" />
                {plan.days.length} 天行程
              </div>
              <div className="flex items-center gap-2 rounded-full bg-white/15 px-3 py-1.5 text-xs text-white backdrop-blur-sm">
                <WalletCards className="h-3.5 w-3.5" />
                ¥{plan.budget_breakdown.total_spent.toLocaleString("zh-CN")} / ¥
                {plan.budget_breakdown.total_budget.toLocaleString("zh-CN")} ·{" "}
                {budgetPercentage}%
              </div>
            </div>
          </div>
        </motion.section>

        <div className="mt-6 grid gap-6 lg:grid-cols-[minmax(0,1fr)_320px]">
          <Timeline days={plan.days} weatherSwaps={plan.weather_swaps} planId={plan.plan_id} />

          <aside className="space-y-4 lg:sticky lg:top-20 lg:self-start">
            <BudgetAlerts budgetBreakdown={plan.budget_breakdown} />
            <BudgetBar
              totalBudget={plan.budget_breakdown.total_budget}
              totalSpent={plan.budget_breakdown.total_spent}
              overBudget={plan.budget_breakdown.over_budget}
            />

            {plan.couple_notes.map((note, index) => (
              <CoupleQuote
                key={note}
                text={note}
                label={index === 0 ? "今日寄语" : "旅途注脚"}
              />
            ))}
          </aside>
        </div>
      </main>
    </div>
  );
}
