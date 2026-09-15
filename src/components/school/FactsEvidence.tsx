import { Info } from "lucide-react";
import type { Fact } from "../../api/types";
import { Confidence } from "../common/Confidence";
import { formatDate } from "../../lib/format";

export function FactsEvidence({ facts }: { facts: Fact[] }) {
  if (facts.length === 0) return null;

  return (
    <section className="section" aria-labelledby="facts-heading">
      <h2 className="section__title" id="facts-heading">
        Evidence
      </h2>
      <ul className="evidence-list">
        {facts.map((fact, index) => (
          <li
            key={`${fact.topic}-${index}`}
            className={`evidence${fact.stale ? " evidence--stale" : ""}`}
          >
            <p className="evidence__value">{fact.value}</p>
            {fact.evidence ? <blockquote className="evidence__quote">{fact.evidence}</blockquote> : null}
            <p className="evidence__meta">
              <span className="evidence__topic">{fact.topic}</span>
              <Confidence value={fact.confidence} />
              {fact.observed_at ? (
                <span className="evidence__date">Observed {formatDate(fact.observed_at)}</span>
              ) : null}
              {fact.extractor === "llm" ? (
                <span className="evidence__llm">
                  <Info size={16} aria-hidden="true" />
                  Model-inferred — verify on the page
                </span>
              ) : null}
            </p>
            {fact.url ? (
              <a
                className="evidence__source"
                href={fact.url}
                target="_blank"
                rel="noopener noreferrer"
              >
                Source
              </a>
            ) : null}
          </li>
        ))}
      </ul>
    </section>
  );
}