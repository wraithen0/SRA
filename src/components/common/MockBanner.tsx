import { useMockActive } from "../../hooks/useMockActive";

export function MockBanner() {
  const active = useMockActive();

  if (!active) return null;
  return (
    <div className="mock-banner" role="status">
      MOCK DATA — the SRA sidecar is unreachable, showing fixtures. Do not trust these values.
    </div>
  );
}