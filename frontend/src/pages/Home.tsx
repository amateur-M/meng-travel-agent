import { motion } from "framer-motion";
import {
  ArrowRight,
  CalendarDays,
  HeartHandshake,
  MapPin,
  WalletCards,
} from "lucide-react";
import { useNavigate } from "react-router-dom";
import { CoupleQuote } from "../components/CoupleQuote/CoupleQuote";
import { TripForm } from "../components/TripForm/TripForm";
import { useTripStore } from "../stores/tripStore";

/**
 * 首页，承载情侣行程输入表单，并在桌面端展示当前选择摘要。
 */
export function Home() {
  const navigate = useNavigate();
  const form = useTripStore((state) => state.form);

  return (
    <div className="min-h-screen bg-cream-50 text-ink-900">
      <header className="border-b border-cream-200 bg-white/90">
        <div className="mx-auto flex max-w-6xl items-center justify-between px-4 py-3 sm:px-6">
          <div className="flex items-center gap-2.5">
            <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-blush-500 text-white">
              <HeartHandshake className="h-5 w-5" />
            </div>
            <div>
              <p className="text-base font-semibold">CoupleTrip</p>
              <p className="text-xs text-ink-400">情侣旅游规划</p>
            </div>
          </div>

          <div className="hidden items-center gap-2 text-sm text-ink-400 sm:flex">
            <MapPin className="h-4 w-4 text-blush-400" />
            出发，去喜欢的地方
          </div>
        </div>
      </header>

      <main className="mx-auto max-w-6xl px-4 py-5 sm:px-6 sm:py-8">
        <div className="grid gap-6 lg:grid-cols-[minmax(0,420px)_minmax(0,1fr)]">
          <TripForm onSubmit={() => navigate("/loading")} />

          <motion.aside
            className="hidden lg:block"
            initial={{ opacity: 0, x: 16 }}
            animate={{ opacity: 1, x: 0 }}
            transition={{ duration: 0.5, delay: 0.1 }}
          >
            <div className="sticky top-6 space-y-5">
              <section className="rounded-lg border border-cream-200 bg-white p-6 shadow-soft">
                <div className="flex items-center gap-3">
                  <div className="flex h-11 w-11 items-center justify-center rounded-lg bg-blush-50 text-blush-500">
                    <MapPin className="h-5 w-5" />
                  </div>
                  <div>
                    <p className="text-sm text-ink-400">本次目的地</p>
                    <h2 className="text-2xl font-semibold text-ink-900">
                      {form.destination}
                    </h2>
                  </div>
                </div>

                <div className="mt-5 flex items-center gap-2 text-sm text-ink-500">
                  <span>{form.origin}</span>
                  <ArrowRight className="h-4 w-4 text-blush-400" />
                  <span>{form.destination}</span>
                </div>

                <div className="mt-4 flex flex-wrap gap-x-5 gap-y-3 text-sm text-ink-500">
                  <span className="inline-flex items-center gap-1.5">
                    <CalendarDays className="h-4 w-4 text-gold-400" />
                    {form.start_date} 至 {form.end_date}
                  </span>
                  <span className="inline-flex items-center gap-1.5">
                    <WalletCards className="h-4 w-4 text-gold-400" />¥
                    {form.budget.toLocaleString("zh-CN")}
                  </span>
                </div>

                <div className="mt-4 flex flex-wrap gap-2">
                  {form.preferences.map((preference) => (
                    <span
                      key={preference}
                      className="rounded-full bg-blush-50 px-3 py-1 text-xs text-blush-600"
                    >
                      {preference}
                    </span>
                  ))}
                </div>
              </section>

              <CoupleQuote text="好的旅行，是和喜欢的人把普通的日子过慢。" />
            </div>
          </motion.aside>
        </div>
      </main>
    </div>
  );
}
