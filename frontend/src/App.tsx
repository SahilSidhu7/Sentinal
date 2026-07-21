import { BrowserRouter, Route, Routes } from "react-router-dom";
import { SiteLayout } from "./components/SiteLayout";
import { Home } from "./pages/Home";
import { Docs } from "./pages/Docs";
import { Install } from "./pages/Install";

function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route element={<SiteLayout />}>
          <Route path="/" element={<Home />} />
          <Route path="/docs" element={<Docs />} />
          <Route path="/install" element={<Install />} />
        </Route>
      </Routes>
    </BrowserRouter>
  );
}

export default App;
