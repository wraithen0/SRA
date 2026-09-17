import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { ActiveFilters } from "./ActiveFilters";
import type { FilterValues } from "./FilterBar";

const base: FilterValues = {
  profile: "first_generation",
  state: "",
  control: "",
  level: "",
  stemOnly: false,
  maxNetPrice: ""
};

describe("ActiveFilters", () => {
  it("renders nothing when no filters are active", () => {
    render(<ActiveFilters q={undefined} values={base} onChange={vi.fn()} />);
    expect(screen.queryByText(/filters applied/)).not.toBeInTheDocument();
  });

  it("renders a chip per active filter", () => {
    render(
      <ActiveFilters
        q="stanford"
        values={{ ...base, state: "CA", control: "public", stemOnly: true, maxNetPrice: "15000" }}
        onChange={vi.fn()}
      />
    );
    expect(screen.getByText('"stanford"')).toBeInTheDocument();
    expect(screen.getByText("CA")).toBeInTheDocument();
    expect(screen.getByText("Public")).toBeInTheDocument();
    expect(screen.getByText("STEM only")).toBeInTheDocument();
    expect(screen.getByText("Net price ≤ $15,000")).toBeInTheDocument();
    expect(screen.getByText(/5 filters applied/)).toBeInTheDocument();
  });

  it("calls onChange to remove a single filter", async () => {
    const onChange = vi.fn();
    render(<ActiveFilters q={undefined} values={{ ...base, state: "CA" }} onChange={onChange} />);
    await userEvent.click(screen.getByRole("button", { name: "Remove CA" }));
    expect(onChange).toHaveBeenCalledWith({ state: "" });
  });

  it("calls onChange to clear all filters", async () => {
    const onChange = vi.fn();
    render(
      <ActiveFilters
        q="stanford"
        values={{
          ...base,
          state: "CA",
          control: "public",
          level: "4-year",
          stemOnly: true,
          maxNetPrice: "15000"
        }}
        onChange={onChange}
      />
    );
    await userEvent.click(screen.getByRole("button", { name: "Clear all" }));
    expect(onChange).toHaveBeenCalledWith({
      q: undefined,
      state: "",
      control: "",
      level: "",
      stemOnly: false,
      maxNetPrice: ""
    });
  });
});