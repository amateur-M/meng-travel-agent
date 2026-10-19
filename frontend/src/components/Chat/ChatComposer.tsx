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
 * The status bar, the collected-slot chips, the primary "开始规划行程" button and
 * the text input used to be four separate floating blocks stacked down the page.
 * Grouping them into a single bordered region makes the "talk → see what we
 * understood → act → keep talking" loop read as one surface instead of a pile of
 * banners.
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
  const showSlots = Object.values(slots).some((value) => value) || ready;

  return (
    <div className="shrink-0 border-t border-cream-200 bg-surface px-4 py-3 sm:px-6">
      <div className={`mx-auto ${CONTENT_WIDTH.chat} space-y-2`}>
        {statusRegion}

        {showSlots && (
          <div className="space-y-2">
            <SlotPanel slots={slots} />
            {ready && (
              <button
                type="button"
                onClick={onStartPlan}
                disabled={launching || planning}
                className="ct-btn-primary w-full px-4 py-3 text-sm"
              >
                {planning
                  ? "正在规划行程..."
                  : hasPlan
                    ? "按新的要求重新规划"
                    : "开始规划行程"}
                <ArrowRight className="h-4 w-4" />
              </button>
            )}
          </div>
        )}

        <ChatInput onSend={onSend} disabled={inputDisabled} />
      </div>
    </div>
  );
}
