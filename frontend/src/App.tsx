import { useEffect } from "react";
import { MotionConfig } from "framer-motion";
import { BrowserRouter, Route, Routes } from "react-router-dom";
import { Chat } from "./pages/Chat";
import { Home } from "./pages/Home";
import { Loading } from "./pages/Loading";
import { PlanResult } from "./pages/PlanResult";
import { useUIStore, watchSystemTheme } from "./stores/uiStore";

function App() {
  const theme = useUIStore((state) => state.theme);

  // Paint the resolved theme, and animate *only* the switch (V6/T1.2). The
  // `theme-switching` class is added just before the attribute flips and removed
  // once the transition ends, so hovering a button never inherits the 220ms
  // colour transition that keeps a theme switch from looking like a hard cut.
  useEffect(() => {
    const root = document.documentElement;
    if (root.dataset.theme === theme) {
      return;
    }

    const reduce = window.matchMedia?.("(prefers-reduced-motion: reduce)").matches;
    if (!reduce) {
      root.classList.add("theme-switching");
    }
    root.dataset.theme = theme;

    const timer = window.setTimeout(() => root.classList.remove("theme-switching"), 260);
    return () => {
      window.clearTimeout(timer);
      root.classList.remove("theme-switching");
    };
  }, [theme]);

  // Follow the OS while the preference is "system".
  useEffect(() => watchSystemTheme(), []);

  return (
    // V6/T3.3: `reducedMotion="user"` makes every framer-motion animation in the
    // tree honour the OS reduce-motion setting. The store used to carry its own
    // `reducedMotion` flag that nothing ever read — CSS has a media query, but
    // framer-motion animations (stagger, float, layout) ignored it entirely.
    <MotionConfig reducedMotion="user">
      <BrowserRouter>
        <Routes>
          {/* V4/T0.1: the conversation is the single main entry. Everything the
              product does starts here. */}
          <Route path="/" element={<Chat />} />
          {/* /form is intentionally NOT in any navigation: it survives only as a
              direct-URL "batch entry" for power users and the form E2E flow. The
              conversational path (/) is what the product leads with. */}
          <Route path="/form" element={<Home />} />
          {/* /loading resumes an in-flight trip; /result is the full-screen
              itinerary, reached from a chat plan card's "查看完整行程". */}
          <Route path="/loading" element={<Loading />} />
          <Route path="/result" element={<PlanResult />} />
        </Routes>
      </BrowserRouter>
    </MotionConfig>
  );
}

export default App;
