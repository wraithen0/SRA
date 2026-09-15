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

  if (!canGoBack && !canGoForward) return null;

  return (
    <nav className="pagination" aria-label="Result pages">
      <button type="button" disabled={!canGoBack} onClick={() => onChange(Math.max(0, offset - limit))}>
        Previous
      </button>
      <button type="button" disabled={!canGoForward} onClick={() => onChange(offset + limit)}>
        Next
      </button>
    </nav>
  );
}