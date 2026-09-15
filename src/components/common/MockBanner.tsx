import { useEffect, useState } from "react";
import { isMockActive } from "../../api/client";

export function MockBanner() {
  const [active, setActive] = useState(isMockActive());

  useEffect(() => {
    const id = setInterval(() => setActive(isMockActive()), 500);
    return () => clearInterval(id);
  }, []);

  if (!active) return null;
  return (
    <div className="mock-banner" role="status">
      MOCK DATA — the SRA sidecar is unreachable, showing fixtures. Do not trust these values.
    </div>
  );
}