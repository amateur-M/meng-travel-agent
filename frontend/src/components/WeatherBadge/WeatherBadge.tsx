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
import { TONE, type Tone } from "../../config/tones";
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
  if (/雨|雷/.test(condition)) return "rainy";
  if (/雪/.test(condition)) return "snowy";
  if (/风/.test(condition)) return "windy";
  if (/晴/.test(condition)) return "sunny";
  return "cloudy";
}

/**
 * Icon + hue per weather kind. Every hue comes from the tone ramp, so the
 * `hot` orange and the `rainy` sky stay readable on both themes (V6/T1.4).
 */
const WEATHER_META: Record<WeatherKind, { className: string; tone: Tone }> = {
  sunny: { className: "text-gold-400", tone: "amber" },
  cloudy: { className: "text-ink-400", tone: "sky" },
  rainy: { className: "text-tone-sky-strong", tone: "sky" },
  snowy: { className: "text-tone-sky-strong", tone: "sky" },
  windy: { className: "text-ink-400", tone: "sky" },
  hot: { className: "text-tone-orange-strong", tone: "orange" },
};

function WeatherIcon({ kind }: { kind: WeatherKind }) {
  const className = `h-5 w-5 ${WEATHER_META[kind].className}`;

  if (kind === "rainy") return <CloudRain className={className} />;
  if (kind === "snowy") return <Snowflake className={className} />;
  if (kind === "windy") return <Wind className={className} />;
  if (kind === "hot") return <ThermometerSun className={className} />;
  if (kind === "sunny") return <Sun className={className} />;
  if (kind === "cloudy") return <Cloud className={className} />;
  return <CloudSun className={className} />;
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
  const adaptive = TONE.amber;

  return (
    <div className="flex flex-wrap items-center gap-x-3 gap-y-2">
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
        <span className={`ct-chip border ${TONE.sky.chip}`}>{note}</span>
      )}

      {adaptations.map((reason) => (
        <span key={reason} className={`ct-chip border ${adaptive.chip}`}>
          <RefreshCw className="h-3 w-3" />
          {reason}
        </span>
      ))}
    </div>
  );
}
