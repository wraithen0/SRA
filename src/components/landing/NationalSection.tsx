import { Link } from "react-router-dom";
import { search } from "../../api/endpoints";
import { useApi } from "../../hooks/useApi";
import { DEFAULT_QUERY } from "../../lib/url";
import { ProgramList } from "../school/ProgramList";
import { DeadlineList } from "../school/DeadlineList";

export function NationalSection() {
  const { data } = useApi(() => search({ ...DEFAULT_QUERY, limit: 1 }), []);

  if (!data) return null;

  return (
    <section className="section section--pattern reveal" aria-labelledby="national-heading">
      <div className="national-head">
        <div>
          <p className="eyebrow">Federal</p>
          <h2 className="section__title" id="national-heading">
            National aid programs and deadlines
          </h2>
        </div>
        <Link to="/search">Browse all matches</Link>
      </div>
      <ProgramList programs={data.national_programs ?? []} title="National programmes" />
      <DeadlineList deadlines={data.national_deadlines ?? []} title="National deadlines" />
    </section>
  );
}
