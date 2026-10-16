import { useState } from "react";
import { Check, Compass, MessageSquarePlus, Pencil, Trash2, X } from "lucide-react";
import type { SessionSummary } from "../../types/chat";

interface SessionListProps {
  sessions: SessionSummary[];
  activeId: string | null;
  onSelect: (sessionId: string) => void;
  onNew: () => void;
  onRename: (sessionId: string, title: string) => void;
  onDelete: (sessionId: string) => void;
  onOpenPlan?: (planId: string) => void;
}

function labelFor(session: SessionSummary): string {
  return session.title?.trim() || session.preview?.trim() || "新对话";
}

/**
 * Conversation sidebar (V3/P3).
 *
 * Switching conversations is the reason persistence exists at all: without a
 * server-stored transcript there is nothing to switch *to*. Rendered as a
 * fixed column on desktop and a drawer on mobile, driven by the parent.
 */
export function SessionList({
  sessions,
  activeId,
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
        <span className="text-xs font-semibold uppercase tracking-wide text-ink-400">
          对话
        </span>
        <button
          type="button"
          onClick={onNew}
          title="新对话"
          aria-label="新对话"
          className="inline-flex h-8 w-8 items-center justify-center rounded-lg text-ink-500 transition hover:bg-cream-100 hover:text-blush-500"
        >
          <MessageSquarePlus className="h-4 w-4" />
        </button>
      </div>

      <nav className="min-h-0 flex-1 space-y-1 overflow-y-auto px-2 pb-3">
        {sessions.length === 0 && (
          <p className="px-2 py-4 text-xs text-ink-300">
            还没有历史对话。开始聊聊你们的旅行计划吧～
          </p>
        )}

        {sessions.map((session) => {
          const active = session.session_id === activeId;
          return (
            <div
              key={session.session_id}
              className={`group rounded-lg px-2 py-2 text-sm transition ${
                active ? "bg-blush-50 text-ink-900" : "text-ink-600 hover:bg-cream-100"
              }`}
            >
              {editingId === session.session_id ? (
                <div className="flex items-center gap-1">
                  <input
                    autoFocus
                    value={draft}
                    onChange={(event) => setDraft(event.target.value)}
                    onKeyDown={(event) => {
                      if (event.key === "Enter") commitEditing(session.session_id);
                      if (event.key === "Escape") setEditingId(null);
                    }}
                    className="min-w-0 flex-1 rounded border border-cream-200 bg-white px-2 py-1 text-xs focus:border-blush-400 focus:outline-none"
                  />
                  <button
                    type="button"
                    aria-label="保存标题"
                    onClick={() => commitEditing(session.session_id)}
                    className="text-ink-400 hover:text-blush-500"
                  >
                    <Check className="h-3.5 w-3.5" />
                  </button>
                  <button
                    type="button"
                    aria-label="取消重命名"
                    onClick={() => setEditingId(null)}
                    className="text-ink-400 hover:text-ink-600"
                  >
                    <X className="h-3.5 w-3.5" />
                  </button>
                </div>
              ) : (
                <>
                  <button
                    type="button"
                    onClick={() => onSelect(session.session_id)}
                    className="block w-full text-left"
                  >
                    <span className="line-clamp-1 font-medium">{labelFor(session)}</span>
                    <span className="mt-0.5 flex items-center gap-2 text-[11px] text-ink-300">
                      <span>{session.message_count} 条</span>
                      {session.last_plan_id && <span>· 已生成行程</span>}
                    </span>
                  </button>

                  <div className="mt-1 flex items-center gap-2 opacity-0 transition group-hover:opacity-100">
                    {session.last_plan_id && onOpenPlan && (
                      <button
                        type="button"
                        onClick={() => onOpenPlan(session.last_plan_id as string)}
                        className="inline-flex items-center gap-1 text-[11px] text-blush-500 hover:underline"
                      >
                        <Compass className="h-3 w-3" />
                        查看行程
                      </button>
                    )}
                    <button
                      type="button"
                      aria-label="重命名会话"
                      onClick={() => startEditing(session)}
                      className="text-ink-300 hover:text-ink-600"
                    >
                      <Pencil className="h-3 w-3" />
                    </button>
                    <button
                      type="button"
                      aria-label="删除会话"
                      onClick={() => onDelete(session.session_id)}
                      className="text-ink-300 hover:text-red-500"
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
