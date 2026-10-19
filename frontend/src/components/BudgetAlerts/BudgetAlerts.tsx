import { motion } from "framer-motion";
import { AlertTriangle, ArrowDownToLine, ShieldCheck } from "lucide-react";
import type { BudgetBreakdown } from "../../types/trip";

interface BudgetAlertsProps {
  budgetBreakdown: BudgetBreakdown;
}

/**
 * 预算预警与降级说明：超过 90% 给出黄色提醒，超过预算展示自动降级方案。
 */
export function BudgetAlerts({ budgetBreakdown }: BudgetAlertsProps) {
  const {
    total_budget: totalBudget,
    total_spent: totalSpent,
    over_budget: overBudget,
    downgrade_applied: downgradeApplied,
    downgrade_notes: downgradeNotes,
  } = budgetBreakdown;

  const ratio = totalBudget > 0 ? totalSpent / totalBudget : 0;

  if (ratio < 0.9) {
    return (
      <div className="rounded-lg border border-emerald-100 bg-emerald-50 px-4 py-3 shadow-soft">
        <div className="flex items-center gap-2 text-sm font-medium text-emerald-700">
          <ShieldCheck className="h-4 w-4" />
          预算空间充足
        </div>
        <p className="mt-1 text-xs leading-5 text-emerald-600">
          当前花费占预算的 {(ratio * 100).toFixed(0)}%，可以放心安排接下来的体验。
        </p>
      </div>
    );
  }

  const isOver = overBudget || ratio > 1;

  return (
    <motion.section
      className={`rounded-lg border p-4 shadow-soft ${
        isOver
          ? "border-rose-200 bg-rose-50"
          : "border-amber-200 bg-amber-50"
      }`}
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.35, ease: "easeOut" }}
    >
      <div className="flex items-start gap-3">
        <div
          className={`flex h-9 w-9 shrink-0 items-center justify-center rounded-lg ${
            isOver ? "bg-rose-500" : "bg-amber-500"
          } text-white`}
        >
          <AlertTriangle className="h-5 w-5" />
        </div>

        <div className="min-w-0 flex-1">
          <h3
            className={`text-sm font-semibold ${
              isOver ? "text-rose-800" : "text-amber-800"
            }`}
          >
            {isOver ? "已超预算，已生成降级方案" : "预算接近上限"}
          </h3>
          <p
            className={`mt-1 text-xs leading-5 ${
              isOver ? "text-rose-700" : "text-amber-700"
            }`}
          >
            {isOver
              ? `当前 ¥${totalSpent.toLocaleString("zh-CN")}，超出 ¥${totalBudget.toLocaleString("zh-CN")}。`
              : `当前 ¥${totalSpent.toLocaleString("zh-CN")}，已达到预算的 ${(ratio * 100).toFixed(0)}%。`}
          </p>

          {downgradeApplied && downgradeNotes.filter(Boolean).length > 0 && (
            <div className="mt-3 space-y-2">
              <div className="flex items-center gap-1.5 text-xs font-medium text-rose-700">
                <ArrowDownToLine className="h-3.5 w-3.5" />
                已自动降级
              </div>
              <ul className="space-y-1.5">
                {downgradeNotes.filter(Boolean).slice(0, 4).map((note) => (
                  <li
                    key={note}
                    className="rounded-lg bg-surface/70 px-3 py-2 text-xs leading-5 text-ink-600"
                  >
                    {note}
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>
      </div>
    </motion.section>
  );
}
