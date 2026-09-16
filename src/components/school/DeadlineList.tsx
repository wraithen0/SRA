import type { Deadline } from "../../api/types";
import { formatDate, formatDaysLeft } from "../../lib/format";
import { sortDeadlines } from "../../lib/sort";

export function DeadlineList({ deadlines, title = "Deadlines" }: { deadlines: Deadline[]; title?: string }) {
  if (deadlines.length === 0) return null;
  const headingId = `deadlines-${title.replace(/[^a-z0-9]+/gi, "-").toLowerCase()}`;

  return (
    <section className="section section--pattern" aria-labelledby={headingId}>
      <h2 className="section__title" id={headingId}>
        {title}
      </h2>
      <ul className="deadline-list">
        {sortDeadlines(deadlines).map((deadline) => (
          <li
            key={`${deadline.label}-${deadline.date_iso}`}
            className={`deadline${deadline.is_past ? " deadline--past" : ""}`}
          >
            <span className="deadline__label">{deadline.label}</span>
            <span className="deadline__date">{formatDate(deadline.date_iso)}</span>
            <span className="deadline__days">{formatDaysLeft(deadline.days_left)}</span>
            <span className="deadline__category">{deadline.category}</span>
          </li>
        ))}
      </ul>
    </section>
  );
}