import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { ResultSkeleton } from "./ResultSkeleton";

describe("ResultSkeleton", () => {
  it("renders a status region with the requested number of cards", () => {
    const { container } = render(<ResultSkeleton count={3} />);
    expect(screen.getByRole("status")).toBeInTheDocument();
    expect(container.querySelectorAll(".result-skeleton__card")).toHaveLength(3);
  });
});