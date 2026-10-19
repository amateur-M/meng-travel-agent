import {
  Cloud,
  CloudRain,
  CloudSun,
  RefreshCw,
  Snowflake,
  Sun,
  ThermometerSun,
  Wind,
} from "lucide-react";
import type { WeatherKind } from "../../types/trip";

interface WeatherBadgeProps {
  condition: string;
  kind?: WeatherKind | null;
  high?: number | null;
  low?: number | null;
  note?: string | null;
  adaptations?: string[];
}

function resolveKind(condition: string, kind?: WeatherKind | null): WeatherKind {
  if (kind) {
    return kind;
  }

  if (/雨|雷/.test(condition)) {
    return "rainy";
  }

  if (/雪/.test(condition)) {
    return "snowy";
  }

  if (/风/.test(condition)) {
    return "windy";
  }

  if (/晴/.test(condition)) {
    return "sunny";
  }

  return "cloudy";
}

function WeatherIcon({ kind }: { kind: WeatherKind }) {
  const className = "h-5 w-5";

  if (kind === "rainy") {
    return <CloudRain className={`${className} text-sky-600`} />;
  }

  if (kind === "snowy") {
    return <Snowflake className={`${className} text-sky-400`} />;
  }

  if (kind === "windy") {
    return <Wind className={`${className} text-ink-400`} />;
  }

  if (kind === "hot") {
    return <ThermometerSun className={`${className} text-orange-500`} />;
  }

  if (kind === "sunny") {
    return <Sun className={`${className} text-gold-400`} />;
  }

  if (kind === "cloudy") {
    return <Cloud className={`${className} text-ink-400`} />;
  }

  return <CloudSun className={`${className} text-sky-600`} />;
}

/**
 * 天气标识，展示天气类型、体感温度，并在有自适应提示时给出提醒。
 */
export function WeatherBadge({
  condition,
  kind,
  high,
  low,
  note,
  adaptations = [],
}: WeatherBadgeProps) {
  const resolvedKind = resolveKind(condition, kind);

  return (
    <div className="inline-flex flex-wrap items-center gap-x-3 gap-y-2 rounded-lg bg-surface/80 px-3 py-2 shadow-soft">
      <div className="flex items-center gap-2 text-sm font-medium text-ink-700">
        <WeatherIcon kind={resolvedKind} />
        {condition}
      </div>

      {high != null && low != null && (
        <span className="text-xs tabular-nums text-ink-400">
          {low.toFixed(0)}° / {high.toFixed(0)}°
        </span>
      )}

      {note && (
        <span className="rounded-full bg-sky-50 px-2.5 py-1 text-xs text-sky-700">
          {note}
        </span>
      )}

      {adaptations.length > 0 && (
        <span className="flex flex-wrap gap-1.5">
          {adaptations.map((reason) => (
            <span
              key={reason}
              className="inline-flex items-center gap-1 rounded-full bg-amber-50 px-2.5 py-1 text-xs text-amber-700"
            >
              <RefreshCw className="h-3 w-3" />
              {reason}
            </span>
          ))}
        </span>
      )}
    </div>
  );
}
