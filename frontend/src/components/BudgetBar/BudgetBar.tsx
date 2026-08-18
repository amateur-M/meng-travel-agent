import { motion } from "framer-motion";
import { AlertTriangle, CircleCheck, WalletCards } from "lucide-react";

interface BudgetBarProps {
  totalBudget: number;
  totalSpent: number;
  overBudget: boolean;
}

/**
 * 预算进度条，实时累计已花费预算，超过总预算时切换为红色告警。
 */
export function BudgetBar({
  totalBudget,
  totalSpent,
  overBudget,
}: BudgetBarProps) {
  const percentage = Math.min(
    100,
    Math.round((totalSpent / Math.max(totalBudget, 1)) * 100),
  );

  const barColor = overBudget
    ? "#e05a68"
    : percentage >= 90
      ? "#ddb866"
      : "#6fbf8d";

  return (
    <div className="rounded-lg border border-cream-200 bg-white p-4 shadow-soft">
      <div className="mb-3 flex items-center justify-between gap-4">
        <div className="flex items-center gap-2">
          <WalletCards className="h-4 w-4 text-blush-400" />
          <span className="text-sm font-medium text-ink-700">预算使用</span>
        </div>
        <span className="text-sm tabular-nums text-ink-500">
          ¥{totalSpent.toLocaleString("zh-CN")} / ¥
          {totalBudget.toLocaleString("zh-CN")}
        </span>
      </div>

      <div className="h-2 overflow-hidden rounded-full bg-cream-200">
        <motion.div
          className="h-full rounded-full"
          initial={{ width: 0 }}
          animate={{ width: `${percentage}%` }}
          transition={{ duration: 0.7, ease: "easeOut" }}
          style={{ backgroundColor: barColor }}
        />
      </div>

      <div className="mt-3 flex items-center justify-between gap-3 text-xs">
        <span className="text-ink-400">{percentage}%</span>
        <span
          className={`inline-flex items-center gap-1.5 font-medium ${
            overBudget ? "text-rose-600" : "text-emerald-600"
          }`}
        >
          {overBudget ? (
            <>
              <AlertTriangle className="h-3.5 w-3.5" />
              已超预算
            </>
          ) : (
            <>
              <CircleCheck className="h-3.5 w-3.5" />
              预算内
            </>
          )}
        </span>
      </div>
    </div>
  );
}
