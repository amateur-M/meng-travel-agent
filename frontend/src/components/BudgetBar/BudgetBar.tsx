import { motion } from "framer-motion";
import { AlertTriangle, CircleCheck, WalletCards } from "lucide-react";
import { TONE } from "../../config/tones";

interface BudgetBarProps {
  totalBudget: number;
  totalSpent: number;
  overBudget: boolean;
}

/**
 * 预算进度条，实时累计已花费预算，超过总预算时切换为红色告警。
 *
 * V6/T1.4: the bar fill used three hardcoded hexes, which stayed bright green /
 * gold / red on a dark page. It now uses the tone ramp, so the fill and its
 * label share one theme-aware colour.
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

  const isWarning = percentage >= 90 && !overBudget;
  const tone = overBudget ? TONE.rose : isWarning ? TONE.amber : TONE.emerald;
  const statusLabel = overBudget
    ? "已超预算"
    : isWarning
      ? "接近预算上限"
      : "预算内";

  return (
    <div className="ct-card p-4">
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
          className={`h-full rounded-full ${tone.fill}`}
          initial={{ width: 0 }}
          animate={{ width: `${percentage}%` }}
          transition={{ duration: 0.7, ease: "easeOut" }}
        />
      </div>

      <div className="mt-3 flex items-center justify-between gap-3 text-xs">
        <span className="tabular-nums text-ink-400">{percentage}%</span>
        <span className={`inline-flex items-center gap-1.5 font-medium ${tone.strong}`}>
          {overBudget || isWarning ? (
            <AlertTriangle className="h-3.5 w-3.5" />
          ) : (
            <CircleCheck className="h-3.5 w-3.5" />
          )}
          {statusLabel}
        </span>
      </div>
    </div>
  );
}
