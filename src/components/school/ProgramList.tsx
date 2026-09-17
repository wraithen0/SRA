import type { Program } from "../../api/types";
import { DeadlineList } from "./DeadlineList";

export function ProgramList({ programs, title = "Programmes" }: { programs: Program[]; title?: string }) {
  if (programs.length === 0) return null;
  const headingId = `programs-${title.replace(/[^a-z0-9]+/gi, "-").toLowerCase()}`;

  return (
    <section className="section reveal" aria-labelledby={headingId}>
      <h2 className="section__title" id={headingId}>
        {title}
      </h2>
      <ul className="program-list">
        {programs.map((program) => (
          <li key={program.program_id} className="program-card">
            <h3 className="program-card__name">{program.name}</h3>
            {program.amount_text ? (
              <p className="program-card__amount">{program.amount_text}</p>
            ) : null}
            {program.official_url ? (
              <a href={program.official_url} target="_blank" rel="noopener noreferrer">
                Official page
              </a>
            ) : null}
            <DeadlineList deadlines={program.deadlines} />
          </li>
        ))}
      </ul>
    </section>
  );
}