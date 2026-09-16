import { Link, Navigate, useSearchParams } from "react-router-dom";
import { ArrowRight } from "lucide-react";
import { ProfileCards } from "../components/landing/ProfileCards";
import { HowItWorks } from "../components/landing/HowItWorks";
import { NationalSection } from "../components/landing/NationalSection";

export function LandingPage() {
  const [params] = useSearchParams();
  const search = params.toString();
  if (search !== "") {
    return <Navigate to={`/search?${search}`} replace />;
  }

  return (
    <div className="landing">
      <section className="hero" aria-labelledby="hero-heading">
        <p className="eyebrow">SRA — Student Resource Architecture</p>
        <h1 className="hero__title" id="hero-heading">
          Ranked by what actually pays.
        </h1>
        <p className="hero__sub">
          College and university discovery with financial-aid intelligence for
          students the data usually ignores. Every match shows why it scored,
          its official links, what it costs, and what we could not verify.
        </p>
        <div className="hero__ctas">
          <Link className="button button--primary" to="/search">
            Start your search
            <ArrowRight size={18} aria-hidden="true" />
          </Link>
          <Link className="button button--ghost" to="/search">
            See it in action
          </Link>
        </div>
      </section>

      <ProfileCards />
      <HowItWorks />
      <NationalSection />
    </div>
  );
}
