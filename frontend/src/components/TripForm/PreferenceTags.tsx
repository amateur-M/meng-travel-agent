import { Heart } from "lucide-react";

interface PreferenceTagsProps {
  selected: string[];
  options: readonly string[];
  onChange: (selected: string[]) => void;
}

/**
 * 偏好标签多选器，选中的标签会切换为暖粉高亮。
 */
export function PreferenceTags({
  selected,
  options,
  onChange,
}: PreferenceTagsProps) {
  const toggle = (option: string) => {
    if (selected.includes(option)) {
      onChange(selected.filter((item) => item !== option));
      return;
    }

    onChange([...selected, option]);
  };

  return (
    <div className="space-y-3">
      <span className="text-sm font-medium text-ink-700">偏好标签</span>
      <div className="flex flex-wrap gap-2">
        {options.map((option) => {
          const isSelected = selected.includes(option);

          return (
            <button
              key={option}
              type="button"
              className={`inline-flex items-center gap-1 rounded-full border px-3 py-2 text-sm font-medium transition ${
                isSelected
                  ? "border-blush-300 bg-blush-50 text-blush-600"
                  : "border-cream-200 bg-white text-ink-500 hover:border-blush-200 hover:text-ink-700"
              }`}
              onClick={() => toggle(option)}
            >
              {isSelected && <Heart className="h-3.5 w-3.5 fill-current" />}
              {option}
            </button>
          );
        })}
      </div>
    </div>
  );
}
