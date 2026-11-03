import { Compass, HeartHandshake, Sparkles, Utensils } from "lucide-react";

/**
 * Chat's first impression (V4/T3.4, refined in V6/T2.7).
 *
 * The empty state used to be a lone heart icon and one grey line, which read as
 * a broken page rather than an invitation. Since conversation is now the only
 * front door, this greets the couple, shows what the assistant can do, and
 * offers tappable openers so nobody stares at a blank input wondering what to
 * type.
 *
 * V6: the suggestions carry an icon each, so they read as three different kinds
 * of request rather than three identical rows of text.
 */
const SUGGESTIONS = [
  {
    Icon: Compass,
    text: "想去大理玩三天，预算5000元",
    hint: "有明确目的地",
  },
  {
    Icon: Utensils,
    text: "喜欢自然和美食，推荐个适合情侣的地方",
    hint: "还没有主意",
  },
  {
    Icon: Sparkles,
    text: "杭州周边两天一夜，怎么安排比较轻松？",
    hint: "周边短途",
  },
];

interface ChatEmptyStateProps {
  /** Tapping a suggestion sends it as the first message; hidden when absent. */
  onQuickStart?: (text: string) => void;
}

export function ChatEmptyState({ onQuickStart }: ChatEmptyStateProps) {
  return (
    <div className="flex flex-col items-center justify-center px-2 pb-6 pt-8 text-center sm:pt-12">
      <div className="relative">
        <div
          aria-hidden="true"
          className="absolute inset-0 scale-150 rounded-full bg-blush-200/40 blur-2xl"
        />
        <div className="relative flex h-16 w-16 items-center justify-center rounded-2xl bg-gradient-to-br from-brand to-brand-dark shadow-lift">
          <HeartHandshake className="h-8 w-8 text-white" />
          <span className="absolute -right-1 -top-1 flex h-6 w-6 items-center justify-center rounded-full bg-gold-300 text-white shadow-soft">
            <Sparkles className="h-3.5 w-3.5" />
          </span>
        </div>
      </div>

      <h1 className="mt-5 text-lg font-semibold text-ink-900">你们想去哪儿？</h1>
      <p className="mt-1.5 max-w-xs text-sm leading-6 text-ink-400">
        告诉助手目的地、日期和预算，边聊边把行程定下来。
      </p>

      {onQuickStart && (
        <div className="mt-5 grid w-full max-w-md gap-2">
          {SUGGESTIONS.map(({ Icon, text, hint }) => (
            <button
              key={text}
              type="button"
              onClick={() => onQuickStart(text)}
              className="group flex items-center gap-3 rounded-xl border border-cream-200 bg-surface px-3 py-2.5 text-left transition hover:border-blush-300 hover:shadow-soft"
            >
              <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-blush-50 text-blush-500 transition group-hover:bg-blush-100">
                <Icon className="h-4 w-4" />
              </span>
              <span className="min-w-0 flex-1">
                <span className="block truncate text-sm text-ink-700">{text}</span>
                <span className="mt-0.5 block text-[11px] text-ink-300">{hint}</span>
              </span>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
