import { Link, useLocation } from "react-router-dom";
import type { Match } from "../../api/types";
import { ReasonBars } from "../school/ReasonBars";
import { StaleBadge } from "../layout/StaleBadge";
import { formatNetPrice } from "../../lib/format";

export function ResultCard({ match }: { match: Match }) {
  const { institution } = match;
  const { search } = useLocation();
  const gapCount = match.gaps.length;

  return (
    <li className="result-card">
      <div className="result-card__head">
        <div>
          <h3 className="result-card__name">
            <Link to={`/schools/${institution.unitid}${search}`}>{institution.name}</Link>
          </h3>
          <p className="result-card__meta">
            {[institution.city, institution.state_abbr].filter(Boolean).join(", ")}
            {" · "}
            Net price {formatNetPrice(institution.avg_net_price)}
          </p>
        </div>
        <p className="result-card__score">{Math.round(match.score)}/100</p>
      </div>
      <ReasonBars reasons={match.why} />
      <div className="result-card__foot">
        <StaleBadge stale={match.stale} />
        <span className={`result-card__gaps${gapCount === 0 ? " result-card__gaps--none" : ""}`}>
          {gapCount === 0 ? "Nothing flagged" : `${gapCount} not verified`}
        </span>
      </div>
    </li>
  );
}