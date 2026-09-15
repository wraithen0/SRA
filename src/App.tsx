import { Outlet } from "react-router-dom";

export default function App() {
  return (
    <>
      <header role="banner">
        <a href="/">SRA</a>
      </header>
      <main>
        <Outlet />
      </main>
    </>
  );
}
