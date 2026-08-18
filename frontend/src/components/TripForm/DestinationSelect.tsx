import { MapPin } from "lucide-react";

interface DestinationSelectProps {
  label: string;
  value: string;
  options: readonly string[];
  onChange: (value: string) => void;
}

/**
 * 出发地 / 目的地选择器，支持从预置城市中快速选择。
 */
export function DestinationSelect({
  label,
  value,
  options,
  onChange,
}: DestinationSelectProps) {
  return (
    <label className="space-y-2">
      <span className="text-sm font-medium text-ink-700">{label}</span>
      <div className="relative">
        <MapPin className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-blush-400" />
        <select
          className="h-11 w-full appearance-none rounded-lg border border-cream-200 bg-white pl-10 pr-10 text-sm text-ink-900 outline-none transition focus:border-blush-400 focus:ring-2 focus:ring-blush-100"
          value={value}
          onChange={(event) => onChange(event.target.value)}
        >
          {options.map((option) => (
            <option key={option} value={option}>
              {option}
            </option>
          ))}
        </select>
      </div>
    </label>
  );
}
