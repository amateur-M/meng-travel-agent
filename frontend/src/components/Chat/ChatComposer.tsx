import type { ReactNode } from "react";
import { ArrowRight } from "lucide-react";
import { CONTENT_WIDTH } from "../../config/layout";
import type { Slots } from "../../types/chat";
import { ChatInput } from "./ChatInput";
import { SlotPanel } from "./SlotPanel";

interface ChatComposerProps {
  /** The single status bar (see ChatStatusRegion), rendered above the action row. */
  statusRegion: ReactNode;
  slots: Slots;
  /** Slots are complete and a plan can be launched. */
  ready: boolean;
  planning: boolean;
  launching: boolean;
  /** A trip already exists, so the primary action reads "重新规划". */
  hasPlan: boolean;
  onStartPlan: () => void;
  onSend: (text: string) => void;
  inputDisabled: boolean;
}

/**
 * The composer: everything below the message flow in one action area (V4/T2.2).
 *
 * V6/T2.6 removed the last of the "pile of boxes" feel: the slot chips no longer
 * sit in their own card, and the primary action only exists when it is actually
 * actionable (no permanent disabled button). What remains is one bordered
 * region: [status] → [slots] → [start plan] → [input].
 */
export function ChatComposer({
  statusRegion,
  slots,
  ready,
  planning,
  launching,
  hasPlan,
  onStartPlan,
  onSend,
  inputDisabled,
}: ChatComposerProps) {
  return (
    <div className="shrink-0 border-t border-cream-200 bg-surface/95 px-3 py-2.5 backdrop-blur sm:px-6">
      <div className={`mx-auto ${CONTENT_WIDTH.chat} space-y-2`}>
        {statusRegion}
        <SlotPanel slots={slots} />

        {ready && (
          <button
            type="button"
            onClick={onStartPlan}
            disabled={launching || planning}
            className="ct-btn-primary w-full px-4 py-2.5 text-sm"
          >
            {planning ? "正在规划行程..." : hasPlan ? "按新的要求重新规划" : "开始规划行程"}
            <ArrowRight className="h-4 w-4" />
          </button>
        )}

        <ChatInput onSend={onSend} disabled={inputDisabled} />

        <p className="text-center text-[11px] text-ink-300">
          行程由 AI 生成，出发前请再核对营业时间与价格
        </p>
      </div>
    </div>
  );
}
