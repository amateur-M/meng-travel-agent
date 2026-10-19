import type { ReactNode } from "react";
import { HeartHandshake } from "lucide-react";
import { CONTENT_WIDTH, type ContentWidth } from "../config/layout";
import { ThemeToggle } from "./ThemeToggle";

interface AppHeaderProps {
  /** Small line under the wordmark — the session title on Chat, the tagline elsewhere. */
  subtitle?: string;
  /** Rendered just before the brand (a menu or back button). */
  leading?: ReactNode;
  /** Rendered at the far right edge (a tagline, an action). */
  trailing?: ReactNode;
  /** Which shared width token the inner container uses. */
  width?: ContentWidth;
  /** Pin the header to the top while the page scrolls. */
  sticky?: boolean;
}

/**
 * The one header every page shares (V4/T0.2).
 *
 * Home, Chat and the itinerary detail each used to hand-roll the same
 * wordmark + logo block with slightly different classes, so the product looked
 * like two apps bolted together. This component owns that brand block; pages
 * only pass what is genuinely page-specific (a leading control, a trailing
 * tagline, the content width).
 */
export function AppHeader({
  subtitle = "情侣旅游规划",
  leading,
  trailing,
  width = "page",
  sticky = false,
}: AppHeaderProps) {
  return (
    <header
      className={`shrink-0 border-b border-cream-200 bg-surface/90 ${
        sticky ? "sticky top-0 z-10" : ""
      }`}
    >
      <div
        className={`mx-auto flex ${CONTENT_WIDTH[width]} items-center justify-between px-4 py-3 sm:px-6`}
      >
        <div className="flex min-w-0 items-center gap-2.5">
          {leading}
          <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-brand text-white">
            <HeartHandshake className="h-5 w-5" />
          </div>
          <div className="min-w-0">
            <p className="text-base font-semibold">CoupleTrip</p>
            <p className="line-clamp-1 text-xs text-ink-400">{subtitle}</p>
          </div>
        </div>

        <div className="flex shrink-0 items-center gap-2">
          {trailing}
          <ThemeToggle />
        </div>
      </div>
    </header>
  );
}
