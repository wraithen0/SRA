import { Clock } from "lucide-react";

export function StaleBadge({ stale }: { stale: boolean }) {
  if (!stale) return null;
  return (
    <span className="stale-badge">
      <Clock size={16} aria-hidden="true" />
      Some evidence is past its freshness window
    </span>
  );
}