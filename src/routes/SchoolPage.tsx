import { Link, useParams, useSearchParams } from "react-router-dom";
import { school } from "../api/endpoints";
import { UnknownSchoolError } from "../api/client";
import { useVocabulary } from "../api/VocabularyContext";
import { ErrorBox } from "../components/common/ErrorBox";
import { useApi } from "../hooks/useApi";
import { parseSearchQuery, profileLabel } from "../lib/url";
import { SchoolHeader } from "../components/school/SchoolHeader";
import { ScorePanel } from "../components/school/ScorePanel";
import { OfficialLinks } from "../components/school/OfficialLinks";
import { FactsEvidence } from "../components/school/FactsEvidence";
import { GapsPanel } from "../components/school/GapsPanel";
import { PlaybookChecklist } from "../components/school/PlaybookChecklist";
import { DeadlineList } from "../components/school/DeadlineList";
import { ProgramList } from "../components/school/ProgramList";

export function SchoolPage() {
  const { key = "" } = useParams();
  const [params] = useSearchParams();
  const query = parseSearchQuery(params);
  const { profiles } = useVocabulary();

  const { data, error, loading } = useApi(() => school(key, query.profile), [key, query.profile]);

  const backTo = `/?${params.toString()}`;

  if (loading) {
    return (
      <div className="page">
        <p className="muted">Loading record…</p>
      </div>
    );
  }

  if (error instanceof UnknownSchoolError) {
    return (
      <div className="page">
        <div className="empty-state">
          <h1 className="page-title">No record for `{key}`.</h1>
          <p>Check the school key, or search by name.</p>
          <Link to={backTo}>Back to search</Link>
        </div>
      </div>
    );
  }

  if (error || !data) {
    return (
      <div className="page">
        <ErrorBox error={error} />
        <Link to={backTo}>Back to search</Link>
      </div>
    );
  }

  return (
    <div className="page page--school">
      <Link className="back-link" to={backTo}>
        Back to search
      </Link>
      <SchoolHeader match={data} />
      <ScorePanel match={data} profileLabelText={profileLabel(query.profile, profiles)} />
      <OfficialLinks links={data.links} />
      <FactsEvidence facts={data.facts} />
      <GapsPanel gaps={data.gaps} />
      <PlaybookChecklist steps={data.playbook} />
      <DeadlineList deadlines={data.deadlines} />
      <ProgramList programs={data.programs} />
    </div>
  );
}