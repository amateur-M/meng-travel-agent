import { useEffect, useState } from "react";
import { motion } from "framer-motion";
import {
  ArrowLeft,
  CalendarDays,
  HeartHandshake,
  MapPin,
  Sparkles,
  WalletCards,
} from "lucide-react";
import { useNavigate, useSearchParams } from "react-router-dom";
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
          navigate("/", { replace: true });
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
      <header className="sticky top-0 z-10 border-b border-cream-200 bg-white/90">
        <div className="mx-auto flex max-w-6xl items-center justify-between px-4 py-3 sm:px-6">
          <button
            type="button"
            className="inline-flex items-center gap-1.5 rounded-lg px-2 py-1.5 text-sm font-medium text-ink-500 transition hover:bg-cream-100 hover:text-ink-900"
            onClick={() => navigate("/")}
          >
            <ArrowLeft className="h-4 w-4" />
            重新规划
          </button>

          <div className="flex items-center gap-2.5">
            <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-blush-500 text-white">
              <HeartHandshake className="h-5 w-5" />
            </div>
            <div>
              <p className="text-base font-semibold">CoupleTrip</p>
              <p className="text-xs text-ink-400">情侣旅游规划</p>
            </div>
          </div>
        </div>
      </header>

      <main className="mx-auto max-w-6xl px-4 py-5 sm:px-6 sm:py-8">
        <motion.section
          className="rounded-lg border border-cream-200 bg-white p-5 shadow-soft sm:p-6"
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.4 }}
        >
          <div className="flex flex-wrap items-start justify-between gap-4">
            <div className="min-w-0">
              <div className="flex items-center gap-2">
                <MapPin className="h-5 w-5 text-blush-500" />
                <h1 className="text-2xl font-semibold">{plan.destination}</h1>
              </div>
              <div className="mt-2 flex items-center gap-1.5 text-sm text-ink-500">
                <CalendarDays className="h-4 w-4 text-gold-400" />
                {plan.start_date} 至 {plan.end_date}
              </div>
            </div>

            <div className="flex flex-wrap items-center gap-2">
              <div className="flex items-center gap-2 rounded-full bg-cream-100 px-3 py-1.5 text-xs text-ink-500">
                <Sparkles className="h-3.5 w-3.5 text-gold-400" />
                {plan.days.length} 天行程
              </div>
              <div className="flex items-center gap-2 rounded-full bg-cream-100 px-3 py-1.5 text-xs text-ink-500">
                <WalletCards className="h-3.5 w-3.5 text-blush-400" />
                ¥{plan.budget_breakdown.total_spent.toLocaleString("zh-CN")} / ¥
                {plan.budget_breakdown.total_budget.toLocaleString("zh-CN")} ·{" "}
                {budgetPercentage}%
              </div>
            </div>
          </div>
        </motion.section>

        <div className="mt-6 grid gap-6 lg:grid-cols-[minmax(0,1fr)_320px]">
          <Timeline days={plan.days} weatherSwaps={plan.weather_swaps} />

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
