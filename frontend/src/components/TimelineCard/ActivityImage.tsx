import { useState } from "react";
import {
  Coffee,
  House,
  Landmark,
  Mountain,
  Palette,
  TreePine,
  Utensils,
  type LucideIcon,
} from "lucide-react";
import { TONE, TONE_GRADIENT, type Tone } from "../../config/tones";
import type { ActivityType } from "../../types/trip";

/**
 * Per-type themed placeholder (V4/T3.2, re-toned in V6/T1.4).
 *
 * Live POI photos only exist when Amap returns them; curated/offline plans have
 * none. Rather than a broken <img> or an empty grey box, an activity without a
 * photo gets a soft gradient banner keyed to its type with a large icon, so the
 * itinerary still reads as a visual, destination-flavoured card.
 *
 * The gradients now come from the tone tokens, so they invert with the theme
 * instead of staying pale pastel on a dark page. Both photo and placeholder use
 * the same 4:3 box, so a failed image does not jump the card's height.
 */
const TYPE_TONE: Record<ActivityType, { Icon: LucideIcon; tone: Tone }> = {
  景点: { Icon: Landmark, tone: "sky" },
  美食: { Icon: Utensils, tone: "orange" },
  室内: { Icon: House, tone: "violet" },
  户外: { Icon: TreePine, tone: "emerald" },
  文化: { Icon: Palette, tone: "indigo" },
  冒险: { Icon: Mountain, tone: "rose" },
  留白: { Icon: Coffee, tone: "amber" },
};

interface ActivityImageProps {
  name: string;
  type: ActivityType;
  imageUrl?: string | null;
  /** Compact boxes for the collapsed/inline itinerary. */
  compact?: boolean;
}

export function ActivityImage({ name, type, imageUrl, compact = false }: ActivityImageProps) {
  const meta = TYPE_TONE[type] ?? TYPE_TONE.留白;
  const [failed, setFailed] = useState(false);
  const showPhoto = Boolean(imageUrl) && !failed;

  const box = compact ? "h-24" : "h-40";
  const base = `relative mb-3 w-full overflow-hidden rounded-xl ${box}`;

  if (showPhoto) {
    return (
      <div className={`${base} bg-cream-100`}>
        <img
          src={imageUrl as string}
          alt={name}
          loading="lazy"
          onError={() => setFailed(true)}
          className="h-full w-full object-cover"
        />
        {/* A faint bottom scrim so the badge-ish text above stays readable on
            bright photos without dimming the whole image. */}
        <div
          aria-hidden="true"
          className="pointer-events-none absolute inset-x-0 bottom-0 h-1/3 bg-gradient-to-t from-black/25 to-transparent"
        />
      </div>
    );
  }

  const { Icon, tone } = meta;
  return (
    <div
      className={`${base} flex items-center justify-center bg-gradient-to-br ${TONE_GRADIENT[tone]}`}
      aria-hidden="true"
    >
      <Icon className={`${compact ? "h-8 w-8" : "h-11 w-11"} opacity-60 ${TONE[tone].strong}`} />
    </div>
  );
}
