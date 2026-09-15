import type { Deadline, Reason } from "../api/types";

export function sortDeadlines(list: Deadline[]): Deadline[] {
  return [...list].sort((a, b) => a.date_iso.localeCompare(b.date_iso));
}

export function sortReasons(list: Reason[]): Reason[] {
  return [...list].sort((a, b) => b.weight - a.weight);
}