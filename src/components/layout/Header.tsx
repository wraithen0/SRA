import { useEffect, useState } from "react";
import { NavLink } from "react-router-dom";
import { GraduationCap } from "lucide-react";
import { StatusBadge } from "./StatusBadge";

export function Header() {
  const [scrolled, setScrolled] = useState(false);

  useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > 40);
    window.addEventListener("scroll", onScroll, { passive: true });
    onScroll();
    return () => window.removeEventListener("scroll", onScroll);
  }, []);

  return (
    <header className={`site-header${scrolled ? " site-header--scrolled" : ""}`} role="banner">
      <div className="site-header__inner">
        <NavLink to="/" className="brand">
          <GraduationCap size={24} aria-hidden="true" />
          <span>SRA</span>
        </NavLink>
        <nav className="site-nav" aria-label="Main">
          <NavLink to="/" end>
            Search
          </NavLink>
        </nav>
        <StatusBadge />
      </div>
    </header>
  );
}