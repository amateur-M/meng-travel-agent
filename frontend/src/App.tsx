import { BrowserRouter, Routes, Route } from "react-router-dom";

function App() {
  return (
    <BrowserRouter>
      <div className="min-h-screen bg-gray-50 text-gray-900">
        <Routes>
          <Route
            path="/"
            element={
              <div className="flex items-center justify-center min-h-screen">
                <h1 className="text-3xl font-bold text-primary-700">
                  CoupleTrip — 情侣旅游规划
                </h1>
              </div>
            }
          />
        </Routes>
      </div>
    </BrowserRouter>
  );
}

export default App;
