import { CalendarDays } from "lucide-react";

interface DateRangePickerProps {
  startDate: string;
  endDate: string;
  onChange: (startDate: string, endDate: string) => void;
}

/**
 * 旅行日期范围选择器，自动保证结束日期不早于开始日期。
 */
export function DateRangePicker({
  startDate,
  endDate,
  onChange,
}: DateRangePickerProps) {
  return (
    <div className="grid gap-3 sm:grid-cols-2">
      <label className="space-y-2">
        <span className="text-sm font-medium text-ink-700">开始日期</span>
        <div className="relative">
          <CalendarDays className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-blush-400" />
          <input
            className="h-11 w-full rounded-lg border border-cream-200 bg-white pl-10 pr-3 text-sm text-ink-900 outline-none transition focus:border-blush-400 focus:ring-2 focus:ring-blush-100"
            type="date"
            value={startDate}
            onChange={(event) =>
              onChange(event.target.value, endDate)
            }
          />
        </div>
      </label>

      <label className="space-y-2">
        <span className="text-sm font-medium text-ink-700">结束日期</span>
        <div className="relative">
          <CalendarDays className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-blush-400" />
          <input
            className="h-11 w-full rounded-lg border border-cream-200 bg-white pl-10 pr-3 text-sm text-ink-900 outline-none transition focus:border-blush-400 focus:ring-2 focus:ring-blush-100"
            type="date"
            min={startDate}
            value={endDate}
            onChange={(event) =>
              onChange(startDate, event.target.value)
            }
          />
        </div>
      </label>
    </div>
  );
}
