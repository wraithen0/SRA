import { Link } from "react-router-dom";
import type { Deadline, Program } from "../../api/types";
import { formatDaysLeft } from "../../lib/format";
import { sortDeadlines } from "../../lib/sort";

const MONTHS = [
  "JAN", "FEB", "MAR", "APR", "MAY", "JUN",
  "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"
];

const DEADLINE_CATEGORY_LABELS: Record<string, string> = {
  financial_aid: "Financial aid",
  application: "Application",
  program: "Programme"
};

function deadlineCategoryLabel(category: string): string {
  const label = DEADLINE_CATEGORY_LABELS[category];
  if (label) return label;
  return category.replace(/_/g, " ").replace(/[a-z]/, (letter) => letter.toUpperCase());
}

function splitDate(iso: string): { month: string; day: string; year: string } {
  const [year, month, day] = iso.split("-");
  if (!year || !month || !day) return { month: "", day: "", year: "" };
  const monthLabel = MONTHS[Number(month) - 1];
  if (!monthLabel) return { month: "", day: "", year: "" };
  return { month: monthLabel, day: String(Number(day)), year };
}

function ProgrammeCard({ program }: { program: Program }) {
  return (
    <li className="national-programme">
      <p className="national-programme__kicker">Federal aid</p>
      <h4 className="national-programme__name">{program.name}</h4>
      {program.amount_text ? (
        <p className="national-programme__amount">{program.amount_text}</p>
      ) : null}
      {program.official_url ? (
        <a
          className="national-programme__link"
          href={program.official_url}
          target="_blank"
          rel="noopener noreferrer"
        >
          Official page <span aria-hidden="true">&nearr;</span>
        </a>
      ) : null}
    </li>
  );
}

function DeadlineRow({ deadline }: { deadline: Deadline }) {
  const { month, day, year } = splitDate(deadline.date_iso);
  const className = deadline.is_past
    ? "national-deadline__row national-deadline--past"
    : "national-deadline__row";
  const row = (
    <>
      <span className="national-deadline__main">
        <strong className="national-deadline__label">{deadline.label}</strong>
        <span className="national-deadline__category">
          {deadlineCategoryLabel(deadline.category)}
        </span>
      </span>
      <span className="national-deadline__date">
        {month && day ? (
          <span className="national-deadline__day">
            {month} {day}
          </span>
        ) : null}
        {year ? <span className="national-deadline__year">{year}</span> : null}
      </span>
      <span className="national-deadline__meta">
        <span className="national-deadline__days">
          {formatDaysLeft(deadline.days_left)}
        </span>
        {deadline.url ? (
          <span className="national-deadline__arrow" aria-hidden="true">
            &rarr;
          </span>
        ) : null}
      </span>
    </>
  );

  return (
    <li className="national-deadline">
      {deadline.url ? (
        <a className={className} href={deadline.url} target="_blank" rel="noopener noreferrer">
          {row}
        </a>
      ) : (
        <span className={className}>{row}</span>
      )}
    </li>
  );
}

export function NationalLayer({
  programs,
  deadlines
}: {
  programs: Program[];
  deadlines: Deadline[];
}) {
  if (programs.length === 0 && deadlines.length === 0) return null;

  const combined = sortDeadlines(
    [...programs.flatMap((program) => program.deadlines), ...deadlines].filter(
      (deadline, index, list) =>
        index ===
        list.findIndex(
          (other) => other.label === deadline.label && other.date_iso === deadline.date_iso
        )
    )
  );

  return (
    <section className="national-layer reveal" aria-label="Federal aid reference layer">
      <div className="national-head">
        <div>
          <p className="eyebrow">Federal</p>
          <h2 className="section__title">National aid programs &amp; deadlines</h2>
        </div>
        <Link to="/search">Browse all matches &rarr;</Link>
      </div>
      <p className="national-layer__intro">
        Aid programmes that carry weight nationally, and the deadlines that move them — for any
        school you compare.
      </p>

      {programs.length > 0 ? (
        <section className="national-programmes" aria-labelledby="national-programmes-title">
          <h3 id="national-programmes-title">PROGRAMMES</h3>
          <ul className="national-programmes__list">
            {programs.map((program) => (
              <ProgrammeCard key={program.program_id} program={program} />
            ))}
          </ul>
        </section>
      ) : null}

      {combined.length > 0 ? (
        <section className="national-deadlines" aria-labelledby="national-deadlines-title">
          <h3 id="national-deadlines-title">UPCOMING DEADLINES</h3>
          <ol className="national-deadlines__list">
            {combined.map((deadline) => (
              <DeadlineRow key={`${deadline.label}-${deadline.date_iso}`} deadline={deadline} />
            ))}
          </ol>
        </section>
      ) : null}
    </section>
  );
}