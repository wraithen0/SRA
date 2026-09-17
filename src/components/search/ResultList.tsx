import type { Match } from "../../api/types";
import { ResultCard } from "./ResultCard";

export function ResultList({ matches, offset = 0 }: { matches: Match[]; offset?: number }) {
  if (matches.length === 0) return null;
  return (
    <ol className="result-list reveal">
      {matches.map((match, index) => (
        <ResultCard key={match.institution.unitid} match={match} rank={offset + index + 1} />
      ))}
    </ol>
  );
}