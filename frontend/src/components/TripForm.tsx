import { FormEvent, useState } from "react";
import {
  CalendarDays,
  Heart,
  LoaderCircle,
  MapPin,
  Send,
  WalletCards,
} from "lucide-react";
import type { Pace, TripPlanRequest } from "../types/trip";

const PREFERENCE_OPTIONS = [
  "浪漫",
  "美食",
  "自然",
  "文化",
  "户外",
  "室内",
  "冒险",
];

const PACE_OPTIONS: Pace[] = ["轻松", "适中", "充实"];

interface TripFormProps {
  onSubmit: (request: TripPlanRequest) => void;
  isSubmitting: boolean;
  currentStep: string;
}

const inputClassName =
  "w-full rounded-md border border-slate-200 bg-white px-3 py-2.5 text-sm text-slate-900 outline-none transition focus:border-primary-400 focus:ring-2 focus:ring-primary-100";

export function TripForm({
  onSubmit,
  isSubmitting,
  currentStep,
}: TripFormProps) {
  const [form, setForm] = useState<TripPlanRequest>({
    origin: "北京",
    destination: "大理",
    start_date: "2026-09-01",
    end_date: "2026-09-03",
    budget: 5000,
    preferences: ["浪漫", "美食"],
    pace: "轻松",
  });

  const updateField = <K extends keyof TripPlanRequest>(
    key: K,
    value: TripPlanRequest[K],
  ) => {
    setForm((current) => ({ ...current, [key]: value }));
  };

  const togglePreference = (preference: string) => {
    setForm((current) => ({
      ...current,
      preferences: current.preferences.includes(preference)
        ? current.preferences.filter((item) => item !== preference)
        : [...current.preferences, preference],
    }));
  };

  const handleSubmit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    onSubmit(form);
  };

  return (
    <form
      className="rounded-lg border border-slate-200 bg-white p-4 shadow-sm sm:p-5"
      onSubmit={handleSubmit}
    >
      <div className="mb-5 flex items-center gap-2">
        <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-primary-50 text-primary-700">
          <Heart className="h-5 w-5" />
        </div>
        <div>
          <h2 className="font-semibold text-slate-900">定制情侣行程</h2>
          <p className="text-xs text-slate-500">填写旅行偏好，生成专属计划</p>
        </div>
      </div>

      <div className="grid gap-4 sm:grid-cols-2">
        <label className="space-y-1.5">
          <span className="text-xs font-medium text-slate-600">出发地</span>
          <div className="relative">
            <MapPin className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" />
            <input
              className={`${inputClassName} pl-9`}
              value={form.origin}
              onChange={(event) => updateField("origin", event.target.value)}
              placeholder="例如：北京"
              required
            />
          </div>
        </label>

        <label className="space-y-1.5">
          <span className="text-xs font-medium text-slate-600">目的地</span>
          <div className="relative">
            <MapPin className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" />
            <input
              className={`${inputClassName} pl-9`}
              value={form.destination}
              onChange={(event) => updateField("destination", event.target.value)}
              placeholder="例如：大理"
              required
            />
          </div>
        </label>

        <label className="space-y-1.5">
          <span className="text-xs font-medium text-slate-600">开始日期</span>
          <div className="relative">
            <CalendarDays className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" />
            <input
              className={`${inputClassName} pl-9`}
              type="date"
              value={form.start_date}
              onChange={(event) => updateField("start_date", event.target.value)}
              required
            />
          </div>
        </label>

        <label className="space-y-1.5">
          <span className="text-xs font-medium text-slate-600">结束日期</span>
          <div className="relative">
            <CalendarDays className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" />
            <input
              className={`${inputClassName} pl-9`}
              type="date"
              min={form.start_date}
              value={form.end_date}
              onChange={(event) => updateField("end_date", event.target.value)}
              required
            />
          </div>
        </label>

        <label className="space-y-1.5 sm:col-span-2">
          <span className="text-xs font-medium text-slate-600">总预算（元）</span>
          <div className="relative">
            <WalletCards className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" />
            <input
              className={`${inputClassName} pl-9`}
              type="number"
              min={1}
              step={100}
              value={form.budget}
              onChange={(event) =>
                updateField("budget", Number(event.target.value))
              }
              required
            />
          </div>
        </label>
      </div>

      <fieldset className="mt-5">
        <legend className="text-xs font-medium text-slate-600">偏好标签</legend>
        <div className="mt-2 flex flex-wrap gap-2">
          {PREFERENCE_OPTIONS.map((preference) => {
            const selected = form.preferences.includes(preference);
            return (
              <button
                key={preference}
                type="button"
                className={`rounded-full border px-3 py-1.5 text-xs font-medium transition ${
                  selected
                    ? "border-primary-400 bg-primary-50 text-primary-700"
                    : "border-slate-200 bg-white text-slate-600 hover:border-slate-300"
                }`}
                onClick={() => togglePreference(preference)}
              >
                {preference}
              </button>
            );
          })}
        </div>
      </fieldset>

      <fieldset className="mt-5">
        <legend className="text-xs font-medium text-slate-600">行程节奏</legend>
        <div className="mt-2 grid grid-cols-3 gap-2 rounded-md bg-slate-100 p-1">
          {PACE_OPTIONS.map((pace) => {
            const selected = form.pace === pace;
            return (
              <button
                key={pace}
                type="button"
                className={`rounded-md px-2 py-2 text-xs font-medium transition ${
                  selected
                    ? "bg-white text-primary-700 shadow-sm"
                    : "text-slate-600 hover:text-slate-900"
                }`}
                onClick={() => updateField("pace", pace)}
              >
                {pace}
              </button>
            );
          })}
        </div>
      </fieldset>

      <button
        type="submit"
        disabled={isSubmitting}
        className="mt-5 flex w-full items-center justify-center gap-2 rounded-md bg-primary-600 px-4 py-3 text-sm font-semibold text-white shadow-sm transition hover:bg-primary-700 disabled:cursor-not-allowed disabled:opacity-60"
      >
        {isSubmitting ? (
          <>
            <LoaderCircle className="h-4 w-4 animate-spin" />
            {currentStep || "正在规划..."}
          </>
        ) : (
          <>
            <Send className="h-4 w-4" />
            生成行程
          </>
        )}
      </button>
    </form>
  );
}
