import { useEffect } from "react";
import { BrowserRouter, Route, Routes } from "react-router-dom";
import { Chat } from "./pages/Chat";
import { Home } from "./pages/Home";
import { Loading } from "./pages/Loading";
import { PlanResult } from "./pages/PlanResult";
import { useUIStore } from "./stores/uiStore";

function App() {
  const theme = useUIStore((state) => state.theme);

  useEffect(() => {
    document.documentElement.dataset.theme = theme;
  }, [theme]);

  return (
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
  );
}

export default App;
