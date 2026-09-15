import { Outlet } from "react-router-dom";
import { Header } from "./components/layout/Header";
import { MockBanner } from "./components/common/MockBanner";

export default function App() {
  return (
    <div className="app-shell">
      <Header />
      <MockBanner />
      <main className="app-main">
        <Outlet />
      </main>
      <footer className="site-footer">
        <p>Provenance is the product. Gaps and stale evidence are always shown.</p>
      </footer>
    </div>
  );
}