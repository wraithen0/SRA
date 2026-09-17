import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import type { Deadline, Program } from "../../api/types";
import { NationalLayer } from "./NationalLayer";

const pellDeadline: Deadline = {
  label: "FAFSA filing opens",
  date_iso: "2026-10-01",
  category: "financial_aid",
  url: "https://studentaid.gov/h/apply-for-aid/fafsa",
  is_past: false,
  days_left: 15
};

const pell: Program = {
  program_id: "pell-grant",
  name: "Federal Pell Grant",
  official_url: "https://studentaid.gov/understand-aid/types/grants/pell",
  amount_text: "Up to $7,395 for the 2024-25 award year",
  deadlines: [pellDeadline]
};

const seog: Program = {
  program_id: "seog",
  name: "Federal Supplemental Educational Opportunity Grant",
  official_url: "https://studentaid.gov/understand-aid/types/grants",
  amount_text: "Between $100 and $4,000 per year",
  deadlines: []
};

const nationalDeadlines: Deadline[] = [
  {
    label: "FAFSA for 2027-28 opens",
    date_iso: "2026-10-01",
    category: "financial_aid",
    url: "https://studentaid.gov/h/apply-for-aid/fafsa",
    is_past: false,
    days_left: 15
  },
  {
    label: "FAFSA priority deadline (most states)",
    date_iso: "2027-03-01",
    category: "financial_aid",
    url: "https://studentaid.gov/h/apply-for-aid/fafsa",
    is_past: false,
    days_left: 167
  }
];

function renderLayer(programs: Program[], deadlines: Deadline[]) {
  return render(
    <MemoryRouter>
      <NationalLayer programs={programs} deadlines={deadlines} />
    </MemoryRouter>
  );
}

describe("NationalLayer", () => {
  it("renders the section head with a Browse all matches link", () => {
    renderLayer([pell], nationalDeadlines);
    expect(screen.getByText("Federal")).toBeInTheDocument();
    expect(
      screen.getByRole("heading", { name: "National aid programs & deadlines" })
    ).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /Browse all matches/ })).toHaveAttribute(
      "href",
      "/search"
    );
  });

  it("keeps programme cards free of nested deadline content", () => {
    renderLayer([pell, seog], nationalDeadlines);
    expect(screen.getByRole("heading", { name: "PROGRAMMES" })).toBeInTheDocument();
    expect(
      screen.queryByText("FAFSA filing opens", { selector: ".national-programme" })
    ).not.toBeInTheDocument();
  });

  it("combines programme and national deadlines into one dedicated, sorted section", () => {
    renderLayer([pell], nationalDeadlines);
    const rows = [...document.querySelectorAll(".national-deadline")].map(
      (row) => row.textContent ?? ""
    );
    expect(screen.getByRole("heading", { name: "UPCOMING DEADLINES" })).toBeInTheDocument();
    expect(rows).toHaveLength(3);
    expect(rows[0]).toMatch(/FAFSA filing opens/);
    expect(rows[1]).toMatch(/FAFSA for 2027-28 opens/);
    expect(rows[2]).toMatch(/FAFSA priority deadline/);
  });

  it("shows human-readable deadline categories instead of raw keys", () => {
    renderLayer([pell], nationalDeadlines);
    expect(screen.queryByText("financial_aid")).not.toBeInTheDocument();
    expect(screen.getAllByText("Financial aid").length).toBeGreaterThan(0);
  });

  it("shows the amount and an Official page link per programme", () => {
    renderLayer([pell], nationalDeadlines);
    expect(screen.getByText("Up to $7,395 for the 2024-25 award year")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /Official page/ })).toHaveAttribute(
      "href",
      "https://studentaid.gov/understand-aid/types/grants/pell"
    );
  });

  it("renders deadline rows as links when a url is present", () => {
    renderLayer([pell], nationalDeadlines);
    expect(
      screen.getByRole("link", { name: /FAFSA for 2027-28 opens/ })
    ).toHaveAttribute("href", "https://studentaid.gov/h/apply-for-aid/fafsa");
    const row = screen.getByText("FAFSA filing opens").closest(".national-deadline");
    expect(row?.querySelector("a")).not.toBeNull();
  });

  it("keeps deadline rows plain when no url exists", () => {
    const plain: Deadline = { ...pellDeadline, label: "No link deadline", url: null };
    renderLayer([], [plain]);
    expect(screen.queryByRole("link", { name: /No link deadline/ })).not.toBeInTheDocument();
    const row = screen.getByText("No link deadline").closest(".national-deadline");
    expect(row?.querySelector("a")).toBeNull();
  });

  it("renders the date as a big day/month plus year", () => {
    renderLayer([pell], nationalDeadlines);
    expect(screen.getAllByText("OCT 1").length).toBeGreaterThanOrEqual(2);
    expect(screen.getAllByText("2026").length).toBeGreaterThanOrEqual(2);
    expect(screen.getAllByText("15 days left").length).toBeGreaterThanOrEqual(2);
  });

  it("dimmes past deadlines", () => {
    const past: Deadline = { ...pellDeadline, label: "Past deadline", is_past: true, days_left: -3 };
    renderLayer([], [past]);
    expect(document.querySelector(".national-deadline--past")).not.toBeNull();
  });

  it("renders nothing for empty programmes and deadlines", () => {
    const { container } = renderLayer([], []);
    expect(container).toBeEmptyDOMElement();
  });

  it("skips the programme block when only deadlines exist", () => {
    renderLayer([], nationalDeadlines);
    expect(
      screen.queryByRole("heading", { name: "PROGRAMMES" })
    ).not.toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "UPCOMING DEADLINES" })).toBeInTheDocument();
  });
});