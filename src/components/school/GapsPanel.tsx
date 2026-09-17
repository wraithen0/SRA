import { AlertTriangle } from "lucide-react";

export function GapsPanel({ gaps }: { gaps: string[] }) {
  return (
    <section className="section section--pattern gaps-panel reveal" aria-labelledby="gaps-heading">
      <h2 className="section__title" id="gaps-heading">
        Not verified yet
      </h2>
      {gaps.length === 0 ? (
        <p className="gaps-panel__empty">Nothing flagged.</p>
      ) : (
        <ul className="gaps-panel__list">
          {gaps.map((gap) => (
            <li key={gap} className="gap-line">
              <AlertTriangle size={16} aria-hidden="true" />
              <span>{gap}</span>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}