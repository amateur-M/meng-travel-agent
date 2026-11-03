import { useEffect, useRef, useState, type KeyboardEvent } from "react";
import { ArrowUp } from "lucide-react";

interface ChatInputProps {
  onSend: (message: string) => void;
  disabled: boolean;
}

/**
 * Composer input (V6/T3.1).
 *
 * `rows={1}` with `maxHeight: 120px` only *capped* the height — a textarea does
 * not grow on its own, so a multi-line thought scrolled inside a one-line box.
 * It now measures its own scrollHeight and grows to fit, up to a ceiling, then
 * scrolls. Enter sends, Shift+Enter breaks the line (unchanged).
 */
export function ChatInput({ onSend, disabled }: ChatInputProps) {
  const [text, setText] = useState("");
  const ref = useRef<HTMLTextAreaElement>(null);

  // Grow to content, capped. Runs on every text change so deleting also shrinks.
  useEffect(() => {
    const el = ref.current;
    if (!el) {
      return;
    }
    el.style.height = "auto";
    el.style.height = `${Math.min(el.scrollHeight, 160)}px`;
  }, [text]);

  const handleSend = () => {
    const trimmed = text.trim();
    if (!trimmed || disabled) {
      return;
    }
    onSend(trimmed);
    setText("");
  };

  const handleKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  const canSend = Boolean(text.trim()) && !disabled;

  return (
    <div className="ct-input flex items-end gap-2 p-2 focus-within:border-blush-400 focus-within:ring-2 focus-within:ring-blush-100">
      <textarea
        ref={ref}
        value={text}
        onChange={(e) => setText(e.target.value)}
        onKeyDown={handleKeyDown}
        placeholder="说说你们的旅行想法..."
        rows={1}
        aria-label="旅行需求输入框"
        className="ct-scroll max-h-40 flex-1 resize-none bg-transparent px-2 py-1.5 text-sm leading-6 text-ink-900 outline-none placeholder:text-ink-300"
      />
      <button
        type="button"
        onClick={handleSend}
        disabled={!canSend}
        aria-label="发送"
        className="inline-flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-brand text-white transition hover:bg-brand-dark disabled:cursor-not-allowed disabled:opacity-30"
      >
        <ArrowUp className="h-4 w-4" />
      </button>
    </div>
  );
}
