import { useEffect, useState } from "react";
import { isMockActive } from "../api/client";

export function useMockActive(forced = false): boolean {
  const [active, setActive] = useState(isMockActive());

  useEffect(() => {
    const id = setInterval(() => setActive(isMockActive()), 500);
    return () => clearInterval(id);
  }, []);

  return forced || active;
}