import type { Match } from "../../api/types";
import { ResultCard } from "./ResultCard";

export function ResultList({ matches }: { matches: Match[] }) {
  if (matches.length === 0) return null;
  return (
    <ul className="result-list">
      {matches.map((match) => (
        <ResultCard key={match.institution.unitid} match={match} />
      ))}
    </ul>
  );
}