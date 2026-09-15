import { useApi } from "../../hooks/useApi";
import { status } from "../../api/endpoints";

const COUNT = new Intl.NumberFormat("en-US");

export function StatusBadge() {
  const { data, error, loading } = useApi(() => status(), []);

  if (loading) return <span className="status-badge">Checking cache</span>;
  if (error || !data) return <span className="status-badge status-badge--down">Cache unavailable</span>;

  return (
    <span className="status-badge" title="Backend cache health">
      {COUNT.format(data.schools ?? 0)} schools
      <span className="status-badge__sep" aria-hidden="true">
        ·
      </span>
      {data.programs ?? 0} programmes
    </span>
  );
}