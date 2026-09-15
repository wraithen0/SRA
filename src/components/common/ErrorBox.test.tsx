import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { ApiError } from "../../api/client";
import { ErrorBox } from "./ErrorBox";

describe("ErrorBox", () => {
  it("shows the server detail for an ApiError", () => {
    render(<ErrorBox error={new ApiError(500, "boom")} />);
    expect(screen.getByRole("alert")).toHaveTextContent("boom");
  });

  it("falls back to the error message and does not apologize", () => {
    render(<ErrorBox error={new Error("network down")} />);
    const alert = screen.getByRole("alert");
    expect(alert).toHaveTextContent("network down");
    expect(alert.textContent?.toLowerCase()).not.toContain("sorry");
  });
});