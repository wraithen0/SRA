export function Pagination({
  limit,
  offset,
  total,
  onChange
}: {
  limit: number;
  offset: number;
  total: number | undefined;
  onChange: (offset: number) => void;
}) {
  const canGoBack = offset > 0;
  const canGoForward = total === undefined ? true : offset + limit < total;
  const showNav = canGoBack || canGoForward;

  if (total === 0) return null;
  if (total === undefined && !showNav) return null;

  const start = offset + 1;
  const end = total === undefined ? offset + limit : Math.min(offset + limit, total);
  const page = Math.floor(offset / limit) + 1;

  return (
    <nav className="pagination reveal" aria-label="Result pages">
      {total !== undefined ? (
        <p className="pagination__summary">
          Showing {start}–{end} of {total}
        </p>
      ) : null}
      {showNav ? (
        <div className="pagination__controls">
          <button
            type="button"
            className="pagination__btn"
            disabled={!canGoBack}
            onClick={() => onChange(Math.max(0, offset - limit))}
          >
            Previous
          </button>
          <span className="pagination__counter" aria-hidden="true">
            Page {page}
          </span>
          <button
            type="button"
            className="pagination__btn"
            disabled={!canGoForward}
            onClick={() => onChange(offset + limit)}
          >
            Next
          </button>
        </div>
      ) : null}
    </nav>
  );
}