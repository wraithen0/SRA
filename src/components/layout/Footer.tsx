import { Link } from "react-router-dom";
import { GraduationCap } from "lucide-react";
import { resolveConfig } from "../../api/client";
import { useVocabulary } from "../../api/VocabularyContext";
import { profileLabel } from "../../lib/url";
import { useMockActive } from "../../hooks/useMockActive";
import type { ProfileKey } from "../../api/types";

const PROFILE_KEYS: ProfileKey[] = [
  "first_generation",
  "student_with_disability",
  "international_stem"
];

export function Footer() {
  const { profiles } = useVocabulary();
  const label = (key: ProfileKey) => profileLabel(key, profiles);
  const year = new Date().getFullYear();
  const mock = useMockActive(resolveConfig().mock);

  return (
    <footer className="site-footer">
      <div className="site-footer__inner">
        <div className="site-footer__grid">
          <div className="site-footer__brand">
            <Link className="brand" to="/">
              <GraduationCap size={22} aria-hidden="true" />
              <span>SRA</span>
            </Link>
            <p>
              College and university discovery with financial-aid intelligence for
              students the data usually ignores.
            </p>
          </div>
          <nav className="site-footer__col" aria-label="Explore">
            <h3 className="site-footer__heading">Explore</h3>
            <Link to="/">Home</Link>
            <Link to="/search">Search</Link>
            <Link to="/search">School Record Archive</Link>
          </nav>
          <nav className="site-footer__col" aria-label="Profiles">
            <h3 className="site-footer__heading">Profiles</h3>
            {PROFILE_KEYS.map((key) => (
              <Link key={key} to={`/search?profile=${key}`}>
                {label(key)}
              </Link>
            ))}
          </nav>
        </div>
        <div className="site-footer__bar">
          <p className="site-footer__motto">
            Provenance is the product. Gaps and stale evidence are always shown.
          </p>
          <p className="site-footer__meta">
            {`© ${year} SRA · ${mock ? "Mock data" : "Live API"}`}
          </p>
        </div>
      </div>
    </footer>
  );
}