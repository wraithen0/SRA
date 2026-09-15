import type { Match } from "../../api/types";
import { ReasonBars } from "./ReasonBars";

export function ScorePanel({ match, profileLabelText }: { match: Match; profileLabelText: string }) {
  return (
    <section className="score-panel" aria-labelledby="score-heading">
      <p className="score-panel__score" id="score-heading">
        {Math.round(match.score)}/100
      </p>
      <p className="score-panel__subtitle">for {profileLabelText}</p>
      <ReasonBars reasons={match.why} />
    </section>
  );
}