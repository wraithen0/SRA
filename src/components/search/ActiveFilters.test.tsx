import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { ActiveFilters } from "./ActiveFilters";
import type { FilterValues } from "./FilterBar";
import { DEFAULT_QUERY } from "../../lib/url";

const base: FilterValues = {
  profile: "first_generation",
  state: "",
  control: "",
  level: "",
  stemOnly: false,
  maxNetPrice: ""
};

const PROFILE_LABEL = "First-generation student";

describe("ActiveFilters", () => {
  it("renders the profile chip when no other filter is active", () => {
    render(
      <ActiveFilters
        q={undefined}
        values={base}
        profileLabel={PROFILE_LABEL}
        onChange={vi.fn()}
      />
    );
    expect(screen.getByText(PROFILE_LABEL)).toBeInTheDocument();
    expect(screen.getByText(/1 filter applied/)).toBeInTheDocument();
  });

  it("renders a chip per active filter", () => {
    render(
      <ActiveFilters
        q="stanford"
        values={{ ...base, state: "CA", control: "public", stemOnly: true, maxNetPrice: "15000" }}
        profileLabel={PROFILE_LABEL}
        onChange={vi.fn()}
      />
    );
    expect(screen.getByText('"stanford"')).toBeInTheDocument();
    expect(screen.getByText(PROFILE_LABEL)).toBeInTheDocument();
    expect(screen.getByText("CA")).toBeInTheDocument();
    expect(screen.getByText("Public")).toBeInTheDocument();
    expect(screen.getByText("STEM only")).toBeInTheDocument();
    expect(screen.getByText("Net price ≤ $15,000")).toBeInTheDocument();
    expect(screen.getByText(/6 filters applied/)).toBeInTheDocument();
  });

  it("calls onChange to remove a single filter", async () => {
    const onChange = vi.fn();
    render(
      <ActiveFilters
        q={undefined}
        values={{ ...base, state: "CA" }}
        profileLabel={PROFILE_LABEL}
        onChange={onChange}
      />
    );
    await userEvent.click(screen.getByRole("button", { name: "Remove CA" }));
    expect(onChange).toHaveBeenCalledWith({ state: "" });
  });

  it("resets the profile to the default when its chip is removed", async () => {
    const onChange = vi.fn();
    render(
      <ActiveFilters
        q={undefined}
        values={{ ...base, profile: "international_stem" }}
        profileLabel="International STEM student"
        onChange={onChange}
      />
    );
    await userEvent.click(
      screen.getByRole("button", { name: "Remove International STEM student" })
    );
    expect(onChange).toHaveBeenCalledWith({ profile: DEFAULT_QUERY.profile });
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
        profileLabel={PROFILE_LABEL}
        onChange={onChange}
      />
    );
    await userEvent.click(screen.getByRole("button", { name: "Clear all" }));
    expect(onChange).toHaveBeenCalledWith({
      q: undefined,
      profile: DEFAULT_QUERY.profile,
      state: "",
      control: "",
      level: "",
      stemOnly: false,
      maxNetPrice: ""
    });
  });
});