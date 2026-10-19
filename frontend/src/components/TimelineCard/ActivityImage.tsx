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
import type { ActivityType } from "../../types/trip";

/**
 * Per-type themed placeholder (V4/T3.2).
 *
 * Live POI photos only exist when Amap returns them; curated/offline plans have
 * none. Rather than a broken <img> or an empty grey box, an activity without a
 * photo gets a soft gradient banner keyed to its type with a large icon, so the
 * itinerary still reads as a visual, destination-flavoured card.
 */
const PLACEHOLDER: Record<ActivityType, { Icon: LucideIcon; gradient: string; iconClass: string }> = {
  景点: { Icon: Landmark, gradient: "from-sky-100 to-indigo-100", iconClass: "text-sky-500" },
  美食: { Icon: Utensils, gradient: "from-amber-100 to-orange-100", iconClass: "text-amber-500" },
  室内: { Icon: House, gradient: "from-violet-100 to-fuchsia-100", iconClass: "text-violet-500" },
  户外: { Icon: TreePine, gradient: "from-emerald-100 to-teal-100", iconClass: "text-emerald-500" },
  文化: { Icon: Palette, gradient: "from-indigo-100 to-blue-100", iconClass: "text-indigo-500" },
  冒险: { Icon: Mountain, gradient: "from-rose-100 to-pink-100", iconClass: "text-rose-500" },
  留白: { Icon: Coffee, gradient: "from-cream-100 to-cream-200", iconClass: "text-ink-400" },
};

interface ActivityImageProps {
  name: string;
  type: ActivityType;
  imageUrl?: string | null;
}

export function ActivityImage({ name, type, imageUrl }: ActivityImageProps) {
  const meta = PLACEHOLDER[type] ?? PLACEHOLDER.留白;
  const [failed, setFailed] = useState(false);
  const showPhoto = Boolean(imageUrl) && !failed;

  if (showPhoto) {
    return (
      <div className="relative mb-3 h-36 w-full overflow-hidden rounded-lg bg-cream-100">
        <img
          src={imageUrl as string}
          alt={name}
          loading="lazy"
          onError={() => setFailed(true)}
          className="h-full w-full object-cover"
        />
      </div>
    );
  }

  const { Icon, gradient, iconClass } = meta;
  return (
    <div
      className={`relative mb-3 flex h-24 w-full items-center justify-center overflow-hidden rounded-lg bg-gradient-to-br ${gradient}`}
      aria-hidden="true"
    >
      <Icon className={`h-10 w-10 opacity-70 ${iconClass}`} />
    </div>
  );
}
