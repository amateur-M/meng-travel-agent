import { WalletCards } from "lucide-react";

interface BudgetSliderProps {
  value: number;
  min?: number;
  max?: number;
  step?: number;
  onChange: (value: number) => void;
}

/**
 * 总预算滑块，用暖粉进度展示预算档位，并同步显示数值。
 */
export function BudgetSlider({
  value,
  min = 1000,
  max = 12000,
  step = 500,
  onChange,
}: BudgetSliderProps) {
  const percentage = Math.min(
    100,
    Math.round(((value - min) / Math.max(max - min, 1)) * 100),
  );

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between gap-3">
        <span className="text-sm font-medium text-ink-700">总预算</span>
        <span className="inline-flex items-center gap-1.5 text-sm font-semibold tabular-nums text-ink-900">
          <WalletCards className="h-4 w-4 text-gold-400" />¥
          {value.toLocaleString("zh-CN")}
        </span>
      </div>

      <input
        className="h-2 w-full cursor-pointer appearance-none rounded-full bg-cream-200 accent-blush-500"
        type="range"
        min={min}
        max={max}
        step={step}
        value={value}
        onChange={(event) => onChange(Number(event.target.value))}
        style={{
          background: `linear-gradient(to right, #e76c8d ${percentage}%, #f9e8d5 ${percentage}%)`,
        }}
      />

      <div className="flex justify-between text-xs text-ink-400">
        <span>¥{min.toLocaleString("zh-CN")}</span>
        <span>¥{max.toLocaleString("zh-CN")}</span>
      </div>
    </div>
  );
}
