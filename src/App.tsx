import { Outlet } from "react-router-dom";
import { Header } from "./components/layout/Header";
import { Footer } from "./components/layout/Footer";
import { MockBanner } from "./components/common/MockBanner";

export default function App() {
  return (
    <div className="app-shell">
      <Header />
      <MockBanner />
      <main className="app-main">
        <Outlet />
      </main>
      <Footer />
    </div>
  );
}