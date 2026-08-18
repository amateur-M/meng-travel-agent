import { useEffect } from "react";
import { BrowserRouter, Route, Routes } from "react-router-dom";
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
        <Route path="/" element={<Home />} />
        <Route path="/loading" element={<Loading />} />
        <Route path="/result" element={<PlanResult />} />
      </Routes>
    </BrowserRouter>
  );
}

export default App;
