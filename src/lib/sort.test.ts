import { describe, expect, it } from "vitest";
import { sortDeadlines, sortReasons } from "./sort";
import type { Deadline, Reason } from "../api/types";

const deadline = (date_iso: string, is_past = false): Deadline => ({
  label: date_iso,
  date_iso,
  category: "application",
  url: null,
  is_past,
  days_left: 0
});

describe("sortDeadlines", () => {
  it("sorts ascending by date_iso", () => {
    const out = sortDeadlines([
      deadline("2027-01-05"),
      deadline("2026-11-01"),
      deadline("2026-03-15")
    ]);
    expect(out.map((d) => d.date_iso)).toEqual(["2026-03-15", "2026-11-01", "2027-01-05"]);
  });

  it("does not mutate the input", () => {
    const input = [deadline("2027-01-05"), deadline("2026-03-15")];
    sortDeadlines(input);
    expect(input[0].date_iso).toBe("2027-01-05");
  });

  it("keeps is_past intact", () => {
    const out = sortDeadlines([deadline("2026-03-15", true)]);
    expect(out[0].is_past).toBe(true);
  });
});

describe("sortReasons", () => {
  it("sorts by weight descending", () => {
    const reasons: Reason[] = [
      { signal: "a", label: "A", value: 0.2, weight: 15 },
      { signal: "b", label: "B", value: 0.9, weight: 22 }
    ];
    expect(sortReasons(reasons).map((r) => r.signal)).toEqual(["b", "a"]);
  });
});