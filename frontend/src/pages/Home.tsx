import { useState } from "react";
import {
  AlertCircle,
  CalendarDays,
  HeartHandshake,
  MapPin,
  Sparkles,
} from "lucide-react";
import { BudgetBar } from "../components/BudgetBar";
import { ItineraryCard } from "../components/ItineraryCard";
import { TripForm } from "../components/TripForm";
import { createPlan } from "../services/plan";
import type {
  PlanStepEvent,
  TripPlanRequest,
  TripPlanResponse,
} from "../types/trip";

export function Home() {
  const [plan, setPlan] = useState<TripPlanResponse | null>(null);
  const [currentStep, setCurrentStep] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  const handleSubmit = async (request: TripPlanRequest) => {
    setIsSubmitting(true);
    setError(null);
    setPlan(null);
    setCurrentStep("正在解析旅行需求...");

    try {
      const result = await createPlan(request, {
        onStep: (event: PlanStepEvent) => setCurrentStep(event.message),
      });
      setPlan(result);
    } catch (err) {
      setError(err instanceof Error ? err.message : "行程生成失败，请稍后重试");
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="min-h-screen bg-slate-50 text-slate-900">
      <header className="border-b border-slate-200 bg-white">
        <div className="mx-auto flex max-w-7xl items-center justify-between px-4 py-3 sm:px-6">
          <div className="flex items-center gap-2.5">
            <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-primary-600 text-white">
              <HeartHandshake className="h-5 w-5" />
            </div>
            <div>
              <h1 className="text-base font-semibold">CoupleTrip</h1>
              <p className="text-xs text-slate-500">情侣旅游规划</p>
            </div>
          </div>

          <div className="hidden items-center gap-2 text-xs text-slate-500 sm:flex">
            <Sparkles className="h-3.5 w-3.5 text-primary-500" />
            浪漫节奏 · 预算透明 · 天气自适应
          </div>
        </div>
      </header>

      <main className="mx-auto max-w-7xl px-4 py-5 sm:px-6 sm:py-7">
        <div className="grid gap-6 lg:grid-cols-[360px_minmax(0,1fr)]">
          <aside>
            <TripForm
              onSubmit={handleSubmit}
              isSubmitting={isSubmitting}
              currentStep={currentStep}
            />
          </aside>

          <section className="min-w-0 space-y-4">
            {error && (
              <div className="flex items-start gap-2 rounded-lg border border-rose-200 bg-rose-50 p-3 text-sm text-rose-700">
                <AlertCircle className="mt-0.5 h-4 w-4 shrink-0" />
                <span>{error}</span>
              </div>
            )}

            {isSubmitting && (
              <div className="rounded-lg border border-slate-200 bg-white p-6 text-center shadow-sm">
                <div className="mx-auto mb-3 h-2 w-40 overflow-hidden rounded-full bg-slate-100">
                  <div className="h-full w-1/3 animate-pulse rounded-full bg-primary-400" />
                </div>
                <p className="text-sm font-medium text-slate-700">
                  {currentStep || "正在生成行程..."}
                </p>
              </div>
            )}

            {plan && (
              <>
                <div className="rounded-lg border border-slate-200 bg-white p-4 shadow-sm">
                  <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
                    <div>
                      <div className="flex items-center gap-2">
                        <MapPin className="h-4 w-4 text-primary-600" />
                        <h2 className="font-semibold">{plan.destination}</h2>
                      </div>
                      <div className="mt-1 flex items-center gap-1.5 text-xs text-slate-500">
                        <CalendarDays className="h-3.5 w-3.5" />
                        {plan.start_date} 至 {plan.end_date}
                      </div>
                    </div>
                    <span className="rounded-full bg-slate-100 px-2.5 py-1 text-xs text-slate-500">
                      {plan.plan_id}
                    </span>
                  </div>

                  <BudgetBar
                    totalBudget={plan.budget_breakdown.total_budget}
                    totalSpent={plan.budget_breakdown.total_spent}
                    overBudget={plan.budget_breakdown.over_budget}
                  />
                </div>

                <div className="grid gap-4 xl:grid-cols-2">
                  {plan.days.map((day) => (
                    <ItineraryCard key={day.day_index} day={day} />
                  ))}
                </div>
              </>
            )}

            {!plan && !isSubmitting && !error && (
              <div className="flex min-h-[420px] items-center justify-center rounded-lg border border-dashed border-slate-200 bg-white p-8 text-center shadow-sm">
                <div className="max-w-sm">
                  <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-lg bg-primary-50 text-primary-600">
                    <Sparkles className="h-6 w-6" />
                  </div>
                  <h2 className="mt-4 font-semibold text-slate-900">
                    从这里开始规划
                  </h2>
                  <p className="mt-2 text-sm leading-6 text-slate-500">
                    填写出发地、目的地、日期和偏好，生成按上午、下午、晚间组织的情侣行程。
                  </p>
                </div>
              </div>
            )}
          </section>
        </div>
      </main>
    </div>
  );
}
