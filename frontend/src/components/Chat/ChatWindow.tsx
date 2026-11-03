import { useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { HeartHandshake } from "lucide-react";
import type { ChatMessage } from "../../types/chat";
import { ChatEmptyState } from "./ChatEmptyState";

interface ChatWindowProps {
  messages: ChatMessage[];
  sending: boolean;
  /**
   * Extra content rendered at the end of the scroll flow, after the messages.
   * The itinerary card is passed here so "对话 → 行程 → 继续对话" lives in one
   * continuous scroll instead of the plan being pinned outside it (V4/T2.4).
   */
  footer?: ReactNode;
  /** Sends a suggested opener from the empty state (V4/T3.4). */
  onQuickStart?: (text: string) => void;
}

/** Same-day messages get grouped; a new day starts a new date divider. */
function dayKey(createdAt?: string | null): string | null {
  if (!createdAt) {
    return null;
  }
  const date = new Date(createdAt);
  return Number.isNaN(date.getTime()) ? null : date.toDateString();
}

function formatDivider(createdAt?: string | null): string {
  if (!createdAt) {
    return "";
  }
  const date = new Date(createdAt);
  if (Number.isNaN(date.getTime())) {
    return "";
  }
  const today = new Date();
  if (date.toDateString() === today.toDateString()) {
    return "今天";
  }
  const yesterday = new Date(today);
  yesterday.setDate(today.getDate() - 1);
  if (date.toDateString() === yesterday.toDateString()) {
    return "昨天";
  }
  return new Intl.DateTimeFormat("zh-CN", { month: "long", day: "numeric" }).format(date);
}

/**
 * The message flow (V6/T2.3).
 *
 * Reworked from "every bubble is its own flex row with an avatar" to a grouped
 * thread: consecutive assistant turns share one avatar and one run, so a reply
 * that arrives as several paragraphs no longer looks like several people
 * talking. A date divider appears only when the day actually changes.
 *
 * Two behaviour fixes ride along:
 *  - auto-scroll now respects the reader: it only follows new messages when you
 *    are already near the bottom, instead of yanking you down while you scroll
 *    back through the conversation;
 *  - an explicit "jump to latest" pill appears once you are scrolled away, so
 *    leaving the bottom is recoverable.
 */
export function ChatWindow({ messages, sending, footer, onQuickStart }: ChatWindowProps) {
  const scrollRef = useRef<HTMLDivElement>(null);
  const endRef = useRef<HTMLDivElement>(null);
  const pinnedRef = useRef(true);
  const [showJump, setShowJump] = useState(false);

  // Track whether the reader is at the bottom *before* new content arrives.
  useEffect(() => {
    const el = scrollRef.current;
    if (!el) {
      return;
    }
    const onScroll = () => {
      const distance = el.scrollHeight - el.scrollTop - el.clientHeight;
      pinnedRef.current = distance < 120;
      setShowJump(distance > 240);
    };
    el.addEventListener("scroll", onScroll, { passive: true });
    return () => el.removeEventListener("scroll", onScroll);
  }, []);

  useEffect(() => {
    if (!pinnedRef.current) {
      return;
    }
    endRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [messages, sending, footer]);

  const jumpToLatest = () => {
    pinnedRef.current = true;
    endRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  };

  // Insert a divider whenever the calendar day changes between two messages.
  const rendered = useMemo(() => {
    return messages.map((msg, index) => {
      const current = dayKey(msg.createdAt);
      const previous = index > 0 ? dayKey(messages[index - 1].createdAt) : null;
      return {
        msg,
        index,
        divider: current && current !== previous ? formatDivider(msg.createdAt) : null,
        // Only the first assistant message in a run carries the avatar.
        firstOfRun: msg.role === "assistant" && messages[index - 1]?.role !== "assistant",
      };
    });
  }, [messages]);

  return (
    <div className="relative min-h-0 flex-1">
      <div
        ref={scrollRef}
        className="ct-scroll h-full overflow-y-auto px-4 py-4 sm:px-6"
      >
        <div className="mx-auto flex max-w-2xl flex-col gap-3">
          {messages.length === 0 && <ChatEmptyState onQuickStart={onQuickStart} />}

          {rendered.map(({ msg, index, divider, firstOfRun }) => (
            <div key={msg.messageId ?? index} className="contents">
              {divider && (
                <div className="my-1 flex items-center gap-3">
                  <div className="h-px flex-1 bg-cream-200" />
                  <span className="text-[11px] font-medium text-ink-300">{divider}</span>
                  <div className="h-px flex-1 bg-cream-200" />
                </div>
              )}

              <motion.div
                className={`flex items-end gap-2 ${
                  msg.role === "user" ? "justify-end" : "justify-start"
                }`}
                initial={{ opacity: 0, y: 6 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.22, ease: "easeOut" }}
              >
                {msg.role === "assistant" &&
                  (firstOfRun ? (
                    <div className="mb-0.5 flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-brand text-white">
                      <HeartHandshake className="h-3.5 w-3.5" />
                    </div>
                  ) : (
                    // Spacer keeps a run of replies left-aligned with the first.
                    <div aria-hidden="true" className="w-7 shrink-0" />
                  ))}

                {msg.role === "user" ? (
                  <div className="max-w-[80%] rounded-2xl rounded-br-md bg-brand px-3.5 py-2.5 text-sm leading-relaxed text-white shadow-soft">
                    {msg.content}
                  </div>
                ) : (
                  <div className="max-w-[85%] whitespace-pre-wrap rounded-2xl rounded-bl-md border border-cream-200 bg-surface px-3.5 py-2.5 text-sm leading-relaxed text-ink-800 shadow-soft">
                    {msg.content}
                  </div>
                )}
              </motion.div>
            </div>
          ))}

          <AnimatePresence>
            {sending && (
              <motion.div
                className="flex items-end gap-2"
                initial={{ opacity: 0, y: 6 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0 }}
                transition={{ duration: 0.2 }}
              >
                <div className="mb-0.5 flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-brand text-white">
                  <HeartHandshake className="h-3.5 w-3.5" />
                </div>
                <div
                  role="status"
                  aria-label="正在回复"
                  className="flex items-center gap-1 rounded-2xl rounded-bl-md border border-cream-200 bg-surface px-4 py-3 shadow-soft"
                >
                  <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-blush-300" />
                  <span
                    className="h-1.5 w-1.5 animate-bounce rounded-full bg-blush-300"
                    style={{ animationDelay: "0.15s" }}
                  />
                  <span
                    className="h-1.5 w-1.5 animate-bounce rounded-full bg-blush-300"
                    style={{ animationDelay: "0.3s" }}
                  />
                </div>
              </motion.div>
            )}
          </AnimatePresence>

          {footer}

          <div ref={endRef} className="h-px" />
        </div>
      </div>

      {/* Jump-to-latest pill: only when the reader has scrolled away. */}
      <AnimatePresence>
        {showJump && (
          <motion.button
            type="button"
            onClick={jumpToLatest}
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: 8 }}
            className="absolute bottom-3 left-1/2 -translate-x-1/2 inline-flex items-center gap-1.5 rounded-full border border-cream-200 bg-surface px-3 py-1.5 text-xs font-medium text-ink-600 shadow-lift"
          >
            回到最新
          </motion.button>
        )}
      </AnimatePresence>
    </div>
  );
}
