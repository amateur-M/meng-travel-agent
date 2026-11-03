import { useEffect, useRef } from "react";
import { TONE } from "../config/tones";

interface ConfirmDialogProps {
  open: boolean;
  title: string;
  description?: string;
  confirmLabel?: string;
  cancelLabel?: string;
  /** Paints the confirm button as a destructive action. */
  destructive?: boolean;
  onConfirm: () => void;
  onCancel: () => void;
}

/**
 * One confirmation dialog for the whole app (V6/T3.4).
 *
 * The delete-conversation flow used `window.confirm`, which is a browser chrome
 * element: it ignores the theme, blocks the JS thread, and cannot be styled — so
 * the one truly destructive action in the product looked like it belonged to a
 * different program.
 *
 * Built on the native `<dialog>` element rather than a portal + focus-trap
 * library: `showModal()` already gives us the top layer, an inert background,
 * ESC-to-close and focus containment, so this is ~40 lines and zero dependencies.
 */
export function ConfirmDialog({
  open,
  title,
  description,
  confirmLabel = "确认",
  cancelLabel = "取消",
  destructive = false,
  onConfirm,
  onCancel,
}: ConfirmDialogProps) {
  const ref = useRef<HTMLDialogElement>(null);

  useEffect(() => {
    const dialog = ref.current;
    if (!dialog) {
      return;
    }
    if (open && !dialog.open) {
      dialog.showModal();
    } else if (!open && dialog.open) {
      dialog.close();
    }
  }, [open]);

  // `cancel` fires on ESC; route it through onCancel so state stays in sync
  // (otherwise the dialog closes but the parent still thinks it is open).
  useEffect(() => {
    const dialog = ref.current;
    if (!dialog) {
      return;
    }
    const onCancelEvent = (event: Event) => {
      event.preventDefault();
      onCancel();
    };
    dialog.addEventListener("cancel", onCancelEvent);
    return () => dialog.removeEventListener("cancel", onCancelEvent);
  }, [onCancel]);

  const tone = destructive ? TONE.rose : TONE.sky;

  return (
    <dialog
      ref={ref}
      aria-labelledby="ct-confirm-title"
      className="max-w-sm rounded-2xl border border-cream-200 bg-surface p-0 text-ink-900 shadow-lift backdrop:bg-black/45 backdrop:backdrop-blur-[2px]"
      onClick={(event) => {
        // Clicking the backdrop (the dialog element itself, not its content)
        // dismisses, matching every other dialog on the platform.
        if (event.target === ref.current) {
          onCancel();
        }
      }}
    >
      <div className="p-5">
        <h2 id="ct-confirm-title" className="text-base font-semibold text-ink-900">
          {title}
        </h2>
        {description && (
          <p className="mt-2 text-sm leading-6 text-ink-500">{description}</p>
        )}

        <div className="mt-5 flex justify-end gap-2">
          {/* Cancel takes initial focus, including for destructive actions: the
              browser would otherwise focus the first focusable control, and a
              stray Enter would confirm the deletion. */}
          <button
            type="button"
            onClick={onCancel}
            autoFocus
            className="ct-btn-outline h-9 px-3.5 text-sm"
          >
            {cancelLabel}
          </button>
          <button
            type="button"
            onClick={onConfirm}
            className={
              destructive
                ? `inline-flex h-9 items-center justify-center gap-2 rounded-xl border px-3.5 text-sm font-semibold transition ${tone.panel} ${tone.strong} hover:opacity-80`
                : "ct-btn-primary h-9 px-3.5 text-sm"
            }
          >
            {confirmLabel}
          </button>
        </div>
      </div>
    </dialog>
  );
}
