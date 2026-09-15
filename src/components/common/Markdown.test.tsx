import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { Markdown } from "./Markdown";

describe("Markdown", () => {
  it("renders inline links", () => {
    render(
      <Markdown text="Add Stanford with the federal code. [Look up the code](https://studentaid.gov/)" />
    );
    const link = screen.getByRole("link", { name: "Look up the code" });
    expect(link).toHaveAttribute("href", "https://studentaid.gov/");
    expect(link).toHaveAttribute("rel", "noopener noreferrer");
  });

  it("strips raw HTML", () => {
    render(<Markdown text="Safe <img src=x onerror=alert(1)> text" />);
    expect(screen.queryByRole("img")).not.toBeInTheDocument();
    expect(screen.getByText(/Safe/)).toBeInTheDocument();
  });

  it("does not create a link for javascript: urls", () => {
    render(<Markdown text="[click](javascript:alert(1))" />);
    expect(screen.queryByRole("link")).not.toBeInTheDocument();
  });
});