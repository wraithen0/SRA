import type { Match } from "../../api/types";
import { formatDate, formatNetPrice } from "../../lib/format";
import { StaleBadge } from "../layout/StaleBadge";

export function SchoolHeader({ match }: { match: Match }) {
  const { institution } = match;
  return (
    <header className="school-header">
      <p className="eyebrow">Unit ID {institution.unitid}</p>
      <h1 className="school-header__name">{institution.name}</h1>
      <p className="school-header__meta">
        {[institution.city, institution.state_abbr].filter(Boolean).join(", ")}
        {institution.control ? ` · ${institution.control.replace(/_/g, " ")}` : ""}
      </p>
      <dl className="school-header__facts">
        <div>
          <dt>Average net price</dt>
          <dd>{formatNetPrice(institution.avg_net_price)}</dd>
        </div>
        <div>
          <dt>Last verified</dt>
          <dd>{formatDate(match.last_verified)}</dd>
        </div>
      </dl>
      <StaleBadge stale={match.stale} />
    </header>
  );
}