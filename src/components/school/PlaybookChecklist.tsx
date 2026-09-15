import type { PlaybookStep } from "../../api/types";
import { Markdown } from "../common/Markdown";
import { formatDate } from "../../lib/format";

export function PlaybookChecklist({ steps }: { steps: PlaybookStep[] }) {
  if (steps.length === 0) return null;
  const ordered = [...steps].sort((a, b) => a.order - b.order);

  return (
    <section className="section" aria-labelledby="playbook-heading">
      <h2 className="section__title" id="playbook-heading">
        Playbook
      </h2>
      <ol className="playbook">
        {ordered.map((step) => (
          <li
            key={step.order}
            className={`playbook-step${step.status === "verify" ? " playbook-step--verify" : ""}`}
          >
            <span className="playbook-step__number" aria-hidden="true">
              {step.order}
            </span>
            <div className="playbook-step__body">
              <h3 className="playbook-step__title">{step.title}</h3>
              <p className="playbook-step__detail">
                <Markdown text={step.detail} />
              </p>
              <p className="playbook-step__meta">
                {step.status === "verify" ? (
                  <span className="playbook-step__tag">Verify on the page</span>
                ) : null}
                {step.deadline ? <span>{formatDate(step.deadline)}</span> : null}
                {step.url ? (
                  <a href={step.url} target="_blank" rel="noopener noreferrer">
                    Open
                  </a>
                ) : null}
              </p>
            </div>
          </li>
        ))}
      </ol>
    </section>
  );
}