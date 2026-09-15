import { describe, expect, it } from "vitest";
import { formatConfidence, formatDate, formatDaysLeft, formatNetPrice } from "./format";

describe("formatDate", () => {
  it("formats an ISO date and handles null", () => {
    expect(formatDate("2027-01-05")).toContain("2027");
    expect(formatDate(null)).toBe("—");
  });
});

describe("formatNetPrice", () => {
  it("formats a number and marks null as not verified", () => {
    expect(formatNetPrice(14200)).toContain("14,200");
    expect(formatNetPrice(null)).toBe("Not verified");
  });
});

describe("formatDaysLeft", () => {
  it("describes past, today, and future", () => {
    expect(formatDaysLeft(-3)).toBe("3 days ago");
    expect(formatDaysLeft(0)).toBe("Today");
    expect(formatDaysLeft(1)).toBe("1 day left");
    expect(formatDaysLeft(12)).toBe("12 days left");
  });
});

describe("formatConfidence", () => {
  it("renders a percentage", () => {
    expect(formatConfidence(0.95)).toBe("95% confidence");
  });
});