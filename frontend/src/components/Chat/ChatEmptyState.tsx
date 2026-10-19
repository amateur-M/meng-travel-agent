import { HeartHandshake, Sparkles } from "lucide-react";

/**
 * Chat's first impression (V4/T3.4).
 *
 * The empty state used to be a lone heart icon and one grey line, which read as
 * a broken page rather than an invitation. Since conversation is now the only
 * front door, this greets the couple, shows what the assistant can do, and
 * offers tappable openers so nobody stares at a blank input wondering what to
 * type.
 */
const SUGGESTIONS = [
  "五一想去大理，帮我规划 3 天浪漫行程",
  "预算 5000，杭州周边两天一夜怎么走？",
  "喜欢自然和美食，推荐个适合情侣的目的地",
];

interface ChatEmptyStateProps {
  /** Tapping a suggestion sends it as the first message; hidden when absent. */
  onQuickStart?: (text: string) => void;
}

export function ChatEmptyState({ onQuickStart }: ChatEmptyStateProps) {
  return (
    <div className="flex flex-col items-center justify-center px-2 pt-10 text-center sm:pt-16">
      <div className="relative flex h-20 w-20 items-center justify-center rounded-3xl bg-gradient-to-br from-blush-400 to-blush-600 shadow-lift">
        <HeartHandshake className="h-10 w-10 text-white" />
        <span className="absolute -right-1.5 -top-1.5 flex h-7 w-7 items-center justify-center rounded-full bg-gold-300 text-white shadow-soft">
          <Sparkles className="h-4 w-4" />
        </span>
      </div>

      <h2 className="mt-6 text-xl font-semibold text-ink-900">
        你们想去哪儿？
      </h2>
      <p className="mt-2 max-w-sm text-sm leading-6 text-ink-400">
        告诉助手目的地、日期和预算，边聊边把行程定下来。
      </p>

      {onQuickStart && (
        <div className="mt-7 flex w-full max-w-md flex-col gap-2">
          {SUGGESTIONS.map((text) => (
            <button
              key={text}
              type="button"
              onClick={() => onQuickStart(text)}
              className="rounded-xl border border-cream-200 bg-surface px-4 py-2.5 text-left text-sm text-ink-600 shadow-soft transition hover:border-blush-300 hover:text-ink-900"
            >
              {text}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
