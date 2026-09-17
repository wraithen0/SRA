import { Link, useLocation } from "react-router-dom";
import type { Match } from "../../api/types";
import { ReasonBars } from "../school/ReasonBars";
import { StaleBadge } from "../layout/StaleBadge";
import { formatNetPrice } from "../../lib/format";

const RING_RADIUS = 17;
const RING_LENGTH = 2 * Math.PI * RING_RADIUS;

export function ResultCard({ match, rank }: { match: Match; rank: number }) {
  const { institution } = match;
  const { search } = useLocation();
  const gapCount = match.gaps.length;
  const score = Math.round(match.score);

  return (
    <li className="result-card">
      <div className="result-card__head">
        <div className="result-card__main">
          <p className="result-card__rank">#{rank}</p>
          <h3 className="result-card__name">
            <Link to={`/schools/${institution.unitid}${search}`}>{institution.name}</Link>
          </h3>
          <p className="result-card__meta">
            {[institution.city, institution.state_abbr].filter(Boolean).join(", ")}
            {" · "}
            Net price {formatNetPrice(institution.avg_net_price)}
          </p>
        </div>
        <span className="result-card__score" aria-label={`Match score ${score} of 100`}>
          <svg className="result-card__ring" viewBox="0 0 40 40" aria-hidden="true">
            <circle className="result-card__ring__track" cx="20" cy="20" r={RING_RADIUS} />
            <circle
              className="result-card__ring__fill"
              cx="20"
              cy="20"
              r={RING_RADIUS}
              style={{ strokeDasharray: `${(RING_LENGTH * score) / 100} ${RING_LENGTH}` }}
            />
          </svg>
          {score}/100
        </span>
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