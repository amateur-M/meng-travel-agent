/**
 * Shared layout width tokens (V4/T0.3).
 *
 * Two content widths cover every page. Keeping them here — instead of
 * scattering ad-hoc `max-w-*` classes — is what stops the Chat column and the
 * wide pages from silently drifting apart again.
 *
 * The literal class strings live in this file on purpose: Tailwind's content
 * scanner reads `.ts` sources, so the utilities are still generated.
 */
export const CONTENT_WIDTH = {
  /** Focused single column: the conversation, its status bar, plan card and composer. */
  chat: "max-w-2xl",
  /** Wide multi-column pages: the batch-entry form and the full itinerary detail. */
  page: "max-w-6xl",
} as const;

export type ContentWidth = keyof typeof CONTENT_WIDTH;
