interface BudgetBarProps {
  totalBudget: number;
  totalSpent: number;
  overBudget: boolean;
}

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
    ? "bg-rose-500"
    : percentage >= 90
      ? "bg-amber-500"
      : "bg-emerald-500";

  return (
    <div className="rounded-lg border border-slate-200 bg-white p-4">
      <div className="mb-2 flex items-center justify-between gap-4">
        <span className="text-sm font-medium text-slate-600">预算使用</span>
        <span className="text-sm tabular-nums text-slate-500">
          ¥{totalSpent.toFixed(0)} / ¥{totalBudget.toFixed(0)}
        </span>
      </div>

      <div className="h-2 overflow-hidden rounded-full bg-slate-100">
        <div
          className={`h-full rounded-full transition-all ${barColor}`}
          style={{ width: `${percentage}%` }}
        />
      </div>

      <div className="mt-2 flex items-center justify-between text-xs text-slate-500">
        <span>{percentage}%</span>
        <span>{overBudget ? "已超预算" : "计划内"}</span>
      </div>
    </div>
  );
}
