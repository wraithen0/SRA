import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { StaleBadge } from "./StaleBadge";

describe("StaleBadge", () => {
  it("renders when stale", () => {
    render(<StaleBadge stale />);
    expect(screen.getByText(/past its freshness window/i)).toBeInTheDocument();
  });

  it("renders nothing when fresh", () => {
    const { container } = render(<StaleBadge stale={false} />);
    expect(container).toBeEmptyDOMElement();
  });
});