import { FormEvent } from "react";
import { motion } from "framer-motion";
import { Send, Sparkles } from "lucide-react";
import {
  DESTINATION_OPTIONS,
  ORIGIN_OPTIONS,
  PACE_OPTIONS,
  PREFERENCE_OPTIONS,
} from "../../config/tripOptions";
import { useTripStore } from "../../stores/tripStore";
import { BudgetSlider } from "./BudgetSlider";
import { DateRangePicker } from "./DateRangePicker";
import { DestinationSelect } from "./DestinationSelect";
import { PreferenceTags } from "./PreferenceTags";

interface TripFormProps {
  onSubmit: () => void;
}

/**
 * 行程输入表单，聚合目的地、日期、预算和偏好标签。
 */
export function TripForm({ onSubmit }: TripFormProps) {
  const form = useTripStore((state) => state.form);
  const updateForm = useTripStore((state) => state.updateForm);

  const handleSubmit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    onSubmit();
  };

  return (
    <motion.form
      className="rounded-lg border border-cream-200 bg-white p-5 shadow-soft sm:p-6"
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.4 }}
      onSubmit={handleSubmit}
    >
      <div className="mb-6 flex items-start gap-3">
        <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-blush-50 text-blush-500">
          <Sparkles className="h-5 w-5" />
        </div>
        <div>
          <h1 className="text-xl font-semibold text-ink-900">定制情侣行程</h1>
          <p className="mt-1 text-sm text-ink-500">
            把日期、目的地和心情交给我们。
          </p>
        </div>
      </div>

      <div className="space-y-5">
        <div className="grid gap-3 sm:grid-cols-2">
          <DestinationSelect
            label="出发地"
            value={form.origin}
            options={ORIGIN_OPTIONS}
            onChange={(value) => updateForm({ origin: value })}
          />
          <DestinationSelect
            label="目的地"
            value={form.destination}
            options={DESTINATION_OPTIONS}
            onChange={(value) => updateForm({ destination: value })}
          />
        </div>

        <DateRangePicker
          startDate={form.start_date}
          endDate={form.end_date}
          onChange={(startDate, endDate) =>
            updateForm({ start_date: startDate, end_date: endDate })
          }
        />

        <BudgetSlider
          value={form.budget}
          onChange={(value) => updateForm({ budget: value })}
        />

        <PreferenceTags
          selected={form.preferences}
          options={PREFERENCE_OPTIONS}
          onChange={(preferences) => updateForm({ preferences })}
        />

        <fieldset className="space-y-3">
          <legend className="text-sm font-medium text-ink-700">行程节奏</legend>
          <div className="grid grid-cols-3 gap-2 rounded-lg bg-cream-100 p-1">
            {PACE_OPTIONS.map((pace) => {
              const isSelected = form.pace === pace;

              return (
                <button
                  key={pace}
                  type="button"
                  className={`rounded-md px-2 py-2.5 text-sm font-medium transition ${
                    isSelected
                      ? "bg-white text-blush-600 shadow-soft"
                      : "text-ink-500 hover:text-ink-900"
                  }`}
                  onClick={() => updateForm({ pace })}
                >
                  {pace}
                </button>
              );
            })}
          </div>
        </fieldset>
      </div>

      <button
        type="submit"
        className="mt-7 flex h-12 w-full items-center justify-center gap-2 rounded-lg bg-blush-500 px-4 text-sm font-semibold text-white shadow-soft transition hover:bg-blush-600"
      >
        <Send className="h-4 w-4" />
        生成行程
      </button>
    </motion.form>
  );
}
