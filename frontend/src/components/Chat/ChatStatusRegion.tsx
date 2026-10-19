import { RefreshCw } from "lucide-react";

/**
 * The chat's transient states are mutually exclusive, so at most one bar shows.
 * Priority: a failed trip outranks an in-flight one, which outranks the
 * "your last message never got a reply" recovery prompt.
 */
export type ChatStatusKind = "error" | "planning" | "pending" | null;

interface ChatStatusRegionProps {
  kind: ChatStatusKind;
  tripError: string;
  tripStep: string;
  /** Disable "重新生成" while a turn is already in flight. */
  chatBusy: boolean;
  /** Disable "重试" while a plan launch is already running. */
  launching: boolean;
  onRegenerate: () => void;
  onRetry: () => void;
}

/**
 * Single status bar for the composer (V4/T2.1).
 *
 * Chat used to stack three separate banners (regenerate / planning / error)
 * vertically, so a failing trip that was also "planning" painted two bars at
 * once. This collapses them into one region that renders exactly the
 * highest-priority active state — or nothing.
 *
 * The pale amber/rose/blush chips carry their own dark text, so they stay
 * legible against either page theme and are intentionally exempt from the
 * dark-mode surface remap (V4/T2.6).
 */
export function ChatStatusRegion({
  kind,
  tripError,
  tripStep,
  chatBusy,
  launching,
  onRegenerate,
  onRetry,
}: ChatStatusRegionProps) {
  if (kind === "error") {
    return (
      <div className="flex items-center justify-between gap-3 rounded-xl border border-rose-200 bg-rose-50 px-3 py-2 text-xs text-rose-700">
        <span className="truncate">行程没有生成成功：{tripError}</span>
        <button
          type="button"
          onClick={onRetry}
          disabled={launching}
          className="inline-flex shrink-0 items-center gap-1 font-semibold text-rose-900 hover:underline disabled:opacity-50"
        >
          <RefreshCw className="h-3.5 w-3.5" />
          重试
        </button>
      </div>
    );
  }

  if (kind === "planning") {
    return (
      <div className="flex items-center gap-2.5 rounded-xl border border-blush-200 bg-blush-50 px-3 py-2 text-xs text-blush-700">
        <span className="h-3 w-3 shrink-0 animate-spin rounded-full border-2 border-blush-300 border-t-blush-600" />
        <span className="truncate">{tripStep || "正在为你们规划行程..."}</span>
      </div>
    );
  }

  if (kind === "pending") {
    return (
      <div className="flex items-center justify-between gap-3 rounded-xl border border-amber-200 bg-amber-50 px-3 py-2 text-xs text-amber-800">
        <span>上一条消息没有收到回复（可能是断网或中断）。</span>
        <button
          type="button"
          onClick={onRegenerate}
          disabled={chatBusy}
          className="inline-flex shrink-0 items-center gap-1 font-semibold text-amber-900 hover:underline disabled:opacity-50"
        >
          <RefreshCw className="h-3.5 w-3.5" />
          重新生成
        </button>
      </div>
    );
  }

  return null;
}
