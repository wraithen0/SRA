import { useCallback } from "react";
import { useSearchParams } from "react-router-dom";
import { search } from "../api/endpoints";
import { ErrorBox } from "../components/common/ErrorBox";
import { FilterBar, type FilterValues } from "../components/search/FilterBar";
import { Pagination } from "../components/search/Pagination";
import { ResultList } from "../components/search/ResultList";
import { SearchForm } from "../components/search/SearchForm";
import { useApi } from "../hooks/useApi";
import { DEFAULT_QUERY, parseSearchQuery, serializeSearchQuery } from "../lib/url";
import type { SearchQuery } from "../api/types";

export function SearchPage() {
  const [params, setParams] = useSearchParams();
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

  const filterValues: FilterValues = {
    profile: query.profile,
    state: query.state ?? "",
    control: query.control ?? "",
    level: query.level ?? "",
    stemOnly: query.stem_only === true,
    maxNetPrice: query.max_net_price !== undefined ? String(query.max_net_price) : ""
  };

  const onFilterChange = (next: Partial<FilterValues>) => {
    const patch: Partial<SearchQuery> = {};
    if (next.profile !== undefined) patch.profile = next.profile;
    if (next.state !== undefined) patch.state = next.state || undefined;
    if (next.control !== undefined) patch.control = next.control || undefined;
    if (next.level !== undefined) patch.level = next.level || undefined;
    if (next.stemOnly !== undefined) patch.stem_only = next.stemOnly || undefined;
    if (next.maxNetPrice !== undefined) {
      patch.max_net_price = next.maxNetPrice ? Number(next.maxNetPrice) : undefined;
    }
    update(patch);
  };

  const results = data?.results ?? [];

  return (
    <div className="page">
      <div className="page-head">
        <p className="eyebrow">School Record Archive</p>
        <h1 className="page-title">Ranked by what actually pays.</h1>
        <p className="page-sub">
          Every match shows its reasons, its official links, and the facts we could not verify.
        </p>
      </div>

      <SearchForm value={query.q ?? ""} onChange={(q) => update({ q: q || undefined })} />
      <FilterBar values={filterValues} onChange={onFilterChange} />

      <ErrorBox error={error} />

      <h2 className="section__title">
        {loading
          ? "Ranking schools…"
          : `${results.length} ranked match${results.length === 1 ? "" : "es"}`}
        {data?.total !== undefined ? ` of ${data.total}` : ""}
      </h2>

      {!loading && !error && results.length === 0 ? (
        <div className="empty-state">
          <p>No schools matched these filters. Widen the state or raise the net-price cap.</p>
          <button
            type="button"
            onClick={() => setParams(serializeSearchQuery(DEFAULT_QUERY), { replace: true })}
          >
            Clear filters
          </button>
        </div>
      ) : (
        <ResultList matches={results} />
      )}

      <Pagination
        limit={query.limit}
        offset={query.offset}
        total={data?.total}
        onChange={(offset) => update({ offset })}
      />
    </div>
  );
}