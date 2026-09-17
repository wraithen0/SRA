import { useEffect, useState, type FormEvent } from "react";
import { useVocabulary } from "../../api/VocabularyContext";
import type { SearchQuery } from "../../api/types";
import { profileLabel } from "../../lib/url";
import { ActiveFilters } from "./ActiveFilters";
import { FilterBar, type FilterValues } from "./FilterBar";
import { SearchForm } from "./SearchForm";

function fromQuery(query: SearchQuery): FilterValues {
  return {
    profile: query.profile,
    state: query.state ?? "",
    control: query.control ?? "",
    level: query.level ?? "",
    stemOnly: query.stem_only === true,
    maxNetPrice: query.max_net_price !== undefined ? String(query.max_net_price) : ""
  };
}

function toQueryPatch(next: Partial<FilterValues> & { q?: string }): Partial<SearchQuery> {
  const patch: Partial<SearchQuery> = {};
  if ("q" in next) patch.q = next.q || undefined;
  if (next.profile !== undefined) patch.profile = next.profile;
  if (next.state !== undefined) patch.state = next.state || undefined;
  if (next.control !== undefined) patch.control = next.control || undefined;
  if (next.level !== undefined) patch.level = next.level || undefined;
  if (next.stemOnly !== undefined) patch.stem_only = next.stemOnly || undefined;
  if (next.maxNetPrice !== undefined) {
    patch.max_net_price = next.maxNetPrice ? Number(next.maxNetPrice) : undefined;
  }
  return patch;
}

export function SearchConsole({
  query,
  loading,
  onCommit
}: {
  query: SearchQuery;
  loading: boolean;
  onCommit: (patch: Partial<SearchQuery>) => void;
}) {
  const { profiles } = useVocabulary();
  const committed = fromQuery(query);
  const [values, setValues] = useState<FilterValues>(committed);
  const [q, setQ] = useState(query.q ?? "");

  const committedKey = `${JSON.stringify(committed)}${query.q ?? ""}`;

  useEffect(() => {
    setQ(query.q ?? "");
    setValues(fromQuery(query));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [committedKey]);

  const dirty =
    q !== (query.q ?? "") || JSON.stringify(values) !== JSON.stringify(committed);

  const submit = (event: FormEvent) => {
    event.preventDefault();
    onCommit({
      offset: 0,
      q: q || undefined,
      ...toQueryPatch({
        profile: values.profile,
        state: values.state,
        control: values.control,
        level: values.level,
        stemOnly: values.stemOnly,
        maxNetPrice: values.maxNetPrice
      })
    });
  };

  const clearKeyword = () => {
    setQ("");
    onCommit({ q: undefined });
  };

  const commitFilterPatch = (patch: Partial<FilterValues> & { q?: string }) => {
    onCommit(toQueryPatch(patch));
  };

  return (
    <form className="search-console" role="search" onSubmit={submit}>
      <SearchForm value={q} onChange={setQ} onClear={clearKeyword} />

      <FilterBar
        values={values}
        onChange={(patch) => setValues((prev) => ({ ...prev, ...patch }))}
        actions={
          <button
            type="submit"
            className="button button--primary update-ranking"
            disabled={loading || !dirty}
          >
            Update ranking
          </button>
        }
      />

      <ActiveFilters
        q={query.q ?? undefined}
        values={committed}
        profileLabel={profileLabel(committed.profile, profiles)}
        onChange={commitFilterPatch}
      />
    </form>
  );
}