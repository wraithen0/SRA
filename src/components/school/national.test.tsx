import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import type { Deadline, Program } from "../../api/types";
import { DeadlineList } from "./DeadlineList";
import { ProgramList } from "./ProgramList";

const program: Program = {
  program_id: "pell",
  name: "Federal Pell Grant",
  official_url: null,
  amount_text: "Up to $7,395",
  deadlines: []
};

const deadline: Deadline = {
  label: "FAFSA opens",
  date_iso: "2026-10-01",
  category: "financial_aid",
  url: null,
  is_past: false,
  days_left: 15
};

describe("national lists reuse rendering with a custom title", () => {
  it("ProgramList uses the title prop and stays list-shaped", () => {
    render(<ProgramList programs={[program]} title="National programmes" />);
    expect(screen.getByRole("heading", { name: "National programmes" })).toBeInTheDocument();
    expect(screen.getByText("Federal Pell Grant")).toBeInTheDocument();
  });

  it("ProgramList renders nothing for an empty list", () => {
    const { container } = render(<ProgramList programs={[]} title="National programmes" />);
    expect(container).toBeEmptyDOMElement();
  });

  it("DeadlineList uses the title prop", () => {
    render(<DeadlineList deadlines={[deadline]} title="National deadlines" />);
    expect(screen.getByRole("heading", { name: "National deadlines" })).toBeInTheDocument();
    expect(screen.getByText("FAFSA opens")).toBeInTheDocument();
  });

  it("DeadlineList renders nothing for an empty list", () => {
    const { container } = render(<DeadlineList deadlines={[]} title="National deadlines" />);
    expect(container).toBeEmptyDOMElement();
  });
});