import { useState, type KeyboardEvent } from "react";
import { Send } from "lucide-react";

interface ChatInputProps {
  onSend: (message: string) => void;
  disabled: boolean;
}

export function ChatInput({ onSend, disabled }: ChatInputProps) {
  const [text, setText] = useState("");

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

  return (
    <div className="flex items-end gap-2">
      <textarea
        value={text}
        onChange={(e) => setText(e.target.value)}
        onKeyDown={handleKeyDown}
        placeholder="说说你们的旅行想法..."
        rows={1}
        className="flex-1 resize-none rounded-xl border border-cream-200 bg-cream-50 px-4 py-2.5 text-sm text-ink-900 placeholder:text-ink-300 focus:border-blush-400 focus:outline-none focus:ring-1 focus:ring-blush-400"
        style={{ maxHeight: "120px" }}
      />
      <button
        type="button"
        onClick={handleSend}
        disabled={disabled || !text.trim()}
        className="inline-flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-brand text-white transition hover:bg-brand-dark disabled:cursor-not-allowed disabled:opacity-40"
      >
        <Send className="h-4 w-4" />
      </button>
    </div>
  );
}
