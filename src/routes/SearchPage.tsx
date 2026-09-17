import { useCallback } from "react";
import { useSearchParams } from "react-router-dom";
import { SearchX } from "lucide-react";
import { search } from "../api/endpoints";
import { useVocabulary } from "../api/VocabularyContext";
import { ErrorBox } from "../components/common/ErrorBox";
import { NationalLayer } from "../components/search/NationalLayer";
import { Pagination } from "../components/search/Pagination";
import { ResultList } from "../components/search/ResultList";
import { ResultSkeleton } from "../components/search/ResultSkeleton";
import { SearchConsole } from "../components/search/SearchConsole";
import { useApi } from "../hooks/useApi";
import { useRevealOnScroll } from "../hooks/useRevealOnScroll";
import { DEFAULT_QUERY, parseSearchQuery, profileLabel, serializeSearchQuery } from "../lib/url";
import type { SearchQuery } from "../api/types";

export function SearchPage() {
  const [params, setParams] = useSearchParams();
  const pageRef = useRevealOnScroll();
  const { profiles } = useVocabulary();
  const query = parseSearchQuery(params);

  const { data, error, loading } = useApi(() => search(query), [params.toString()]);

  const update = useCallback(
    (patch: Partial<SearchQuery>) => {
      const next: SearchQuery = {
        ...parseSearchQuery(params),
        ...patch,
        offset: patch.offset ?? 0
      };
      setParams(serializeSearchQuery(next), { replace: true });
    },
    [params, setParams]
  );

  const results = data?.results ?? [];
  const count = data?.count ?? results.length;
  const universeSize = data?.universe_size;
  const cache = data?.cache;

  return (
    <div className="page" ref={pageRef}>
      <div className="page-head">
        <p className="eyebrow">School Record Archive · Ranked search</p>
        <h1 className="page-title">Ranked by what actually pays.</h1>
        <p className="page-sub">
          Every match shows its reasons, its official links, and the facts we could not verify.
        </p>
      </div>

      <SearchConsole query={query} loading={loading} onCommit={update} />

      <ErrorBox error={error} />

      <div className="results-head">
        <h2 className="section__title" aria-live="polite">
          {loading ? "Ranking schools…" : `${count} ranked match${count === 1 ? "" : "es"}`}
        </h2>
        {loading ? null : (
          <p className="results-sub">
            Best matches first · ranked for the {profileLabel(query.profile, profiles)} profile
          </p>
        )}
      </div>

      {loading ? (
        <ResultSkeleton count={3} />
      ) : !error && results.length === 0 ? (
        <div className="empty-state">
          <span className="empty-state__icon" aria-hidden="true">
            <SearchX size={24} />
          </span>
          <div className="empty-state__body">
            <p>No schools matched these filters. Widen the state or raise the net-price cap.</p>
            <button
              type="button"
              onClick={() => setParams(serializeSearchQuery(DEFAULT_QUERY), { replace: true })}
            >
              Clear filters
            </button>
          </div>
        </div>
      ) : (
        <ResultList matches={results} offset={query.offset} />
      )}

      <Pagination
        limit={query.limit}
        offset={query.offset}
        total={data?.total}
        onChange={(offset) => update({ offset })}
      />

      {!loading && (universeSize !== undefined || cache) ? (
        <p className="results-meta">
          {universeSize !== undefined ? `${universeSize.toLocaleString("en-US")} schools searched` : null}
          {universeSize !== undefined && cache ? " · " : null}
          {cache ? (
            <span className="results-meta__cache">
              cache {cache.hit ? "hit" : "miss"} · <code>{cache.fingerprint.slice(0, 8)}</code>
            </span>
          ) : null}
        </p>
      ) : null}

      <NationalLayer
        programs={data?.national_programs ?? []}
        deadlines={data?.national_deadlines ?? []}
      />
    </div>
  );
}