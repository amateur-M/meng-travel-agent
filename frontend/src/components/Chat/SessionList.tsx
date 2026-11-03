import { useState } from "react";
import {
  Check,
  Compass,
  MessageSquarePlus,
  Pencil,
  Trash2,
  X,
} from "lucide-react";
import type { SessionSummary } from "../../types/chat";

interface SessionListProps {
  sessions: SessionSummary[];
  activeId: string | null;
  loading?: boolean;
  onSelect: (sessionId: string) => void;
  onNew: () => void;
  onRename: (sessionId: string, title: string) => void;
  onDelete: (sessionId: string) => void;
  onOpenPlan?: (planId: string) => void;
}

function labelFor(session: SessionSummary): string {
  return session.title?.trim() || session.preview?.trim() || "新对话";
}

/** "今天" / "昨天" / "9月12日" — relative dates read faster than timestamps. */
function relativeDate(iso?: string | null): string {
  if (!iso) {
    return "";
  }
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) {
    return "";
  }
  const today = new Date();
  const days = Math.floor(
    (new Date(today.toDateString()).getTime() - new Date(date.toDateString()).getTime()) /
      86_400_000,
  );
  if (days === 0) return "今天";
  if (days === 1) return "昨天";
  if (days < 7) return `${days} 天前`;
  return new Intl.DateTimeFormat("zh-CN", { month: "numeric", day: "numeric" }).format(date);
}

/**
 * Conversation sidebar (V3/P3, reworked in V6/T3.5).
 *
 * Switching conversations is the reason persistence exists at all: without a
 * server-stored transcript there is nothing to switch *to*. Rendered as a fixed
 * column on desktop and a drawer on mobile, driven by the parent.
 *
 * The row actions used to be `opacity-0 group-hover:opacity-100`, i.e. invisible
 * to touch and to keyboard focus — the only way to rename or delete a
 * conversation was with a mouse. They are now always in the layout, dimmed, and
 * come to full contrast on hover/focus; the row also exposes them to screen
 * readers via aria-labels.
 */
export function SessionList({
  sessions,
  activeId,
  loading = false,
  onSelect,
  onNew,
  onRename,
  onDelete,
  onOpenPlan,
}: SessionListProps) {
  const [editingId, setEditingId] = useState<string | null>(null);
  const [draft, setDraft] = useState("");

  const startEditing = (session: SessionSummary) => {
    setEditingId(session.session_id);
    setDraft(labelFor(session));
  };

  const commitEditing = (sessionId: string) => {
    const title = draft.trim();
    if (title) {
      onRename(sessionId, title);
    }
    setEditingId(null);
  };

  return (
    <div className="flex h-full flex-col">
      <div className="flex items-center justify-between px-3 py-3">
        <span className="text-[11px] font-semibold uppercase tracking-wider text-ink-400">
          对话
        </span>
        <button
          type="button"
          onClick={onNew}
          title="新对话"
          aria-label="新对话"
          className="ct-btn-quiet h-7 w-7 hover:text-blush-500"
        >
          <MessageSquarePlus className="h-4 w-4" />
        </button>
      </div>

      <nav className="ct-scroll min-h-0 flex-1 space-y-0.5 overflow-y-auto px-2 pb-3" aria-label="对话列表">
        {loading && sessions.length === 0 && <SessionSkeleton />}

        {!loading && sessions.length === 0 && (
          <p className="px-2 py-4 text-xs leading-5 text-ink-300">
            还没有历史对话。开始聊聊你们的旅行计划吧～
          </p>
        )}

        {sessions.map((session) => {
          const active = session.session_id === activeId;
          return (
            <div
              key={session.session_id}
              className={`group relative rounded-xl px-2.5 py-2 transition ${
                active
                  ? "bg-blush-50 text-ink-900 ring-1 ring-inset ring-blush-200"
                  : "text-ink-600 hover:bg-cream-100"
              }`}
            >
              {editingId === session.session_id ? (
                <div className="flex items-center gap-1">
                  <input
                    autoFocus
                    value={draft}
                    aria-label="对话标题"
                    onChange={(event) => setDraft(event.target.value)}
                    onKeyDown={(event) => {
                      if (event.key === "Enter") commitEditing(session.session_id);
                      if (event.key === "Escape") setEditingId(null);
                    }}
                    className="ct-input min-w-0 flex-1 px-2 py-1 text-xs"
                  />
                  <button
                    type="button"
                    aria-label="保存标题"
                    onClick={() => commitEditing(session.session_id)}
                    className="ct-btn-quiet h-6 w-6 hover:text-blush-500"
                  >
                    <Check className="h-3.5 w-3.5" />
                  </button>
                  <button
                    type="button"
                    aria-label="取消重命名"
                    onClick={() => setEditingId(null)}
                    className="ct-btn-quiet h-6 w-6"
                  >
                    <X className="h-3.5 w-3.5" />
                  </button>
                </div>
              ) : (
                <>
                  <button
                    type="button"
                    onClick={() => onSelect(session.session_id)}
                    aria-current={active ? "page" : undefined}
                    className="block w-full pr-14 text-left"
                  >
                    <span className="line-clamp-1 text-sm font-medium">{labelFor(session)}</span>
                    <span className="mt-0.5 flex items-center gap-1.5 text-[11px] text-ink-300">
                      <span>{relativeDate(session.updated_at)}</span>
                      {session.last_plan_id && (
                        <>
                          <span aria-hidden="true">·</span>
                          <span>已生成行程</span>
                        </>
                      )}
                    </span>
                  </button>

                  {/* Always in the layout (touch + keyboard reachable); dimmed
                      until the row is hovered or focused. */}
                  <div className="absolute right-1.5 top-1/2 flex -translate-y-1/2 items-center gap-0.5 opacity-60 transition group-hover:opacity-100 group-focus-within:opacity-100">
                    {session.last_plan_id && onOpenPlan && (
                      <button
                        type="button"
                        aria-label="查看该对话的行程"
                        title="查看行程"
                        onClick={() => onOpenPlan(session.last_plan_id as string)}
                        className="ct-btn-quiet h-6 w-6 hover:text-blush-500"
                      >
                        <Compass className="h-3 w-3" />
                      </button>
                    )}
                    <button
                      type="button"
                      aria-label="重命名会话"
                      title="重命名"
                      onClick={() => startEditing(session)}
                      className="ct-btn-quiet h-6 w-6"
                    >
                      <Pencil className="h-3 w-3" />
                    </button>
                    <button
                      type="button"
                      aria-label="删除会话"
                      title="删除"
                      onClick={() => onDelete(session.session_id)}
                      className="ct-btn-quiet h-6 w-6 hover:text-tone-rose-strong"
                    >
                      <Trash2 className="h-3 w-3" />
                    </button>
                  </div>
                </>
              )}
            </div>
          );
        })}
      </nav>
    </div>
  );
}

/** Placeholder rows for a cold first paint — the cache usually fills these. */
function SessionSkeleton() {
  return (
    <div className="space-y-2 px-1 py-1" aria-hidden="true">
      {[0, 1, 2].map((index) => (
        <div key={index} className="space-y-1.5 rounded-xl px-2.5 py-2">
          <div className="relative h-3 overflow-hidden rounded bg-cream-100">
            <div className="absolute inset-0 -translate-x-full animate-shimmer bg-gradient-to-r from-transparent via-cream-200/70 to-transparent" />
          </div>
          <div className="relative h-2 w-2/3 overflow-hidden rounded bg-cream-100">
            <div className="absolute inset-0 -translate-x-full animate-shimmer bg-gradient-to-r from-transparent via-cream-200/70 to-transparent" />
          </div>
        </div>
      ))}
    </div>
  );
}
