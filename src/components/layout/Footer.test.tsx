import { render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { MemoryRouter } from "react-router-dom";
import { Footer } from "./Footer";
import { VocabularyProvider } from "../../api/VocabularyContext";
import { resetMockState } from "../../api/client";

afterEach(() => {
  vi.unstubAllEnvs();
  resetMockState();
});

function renderFooter() {
  vi.stubEnv("VITE_SRA_MOCK", "1");
  render(
    <VocabularyProvider>
      <MemoryRouter>
        <Footer />
      </MemoryRouter>
    </VocabularyProvider>
  );
}

describe("Footer", () => {
  it("renders the brand, mission, and provenance motto", () => {
    renderFooter();
    expect(screen.getByRole("contentinfo")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /SRA/ })).toHaveAttribute("href", "/");
    expect(screen.getByText(/financial-aid intelligence/)).toBeInTheDocument();
    expect(screen.getByText(/Gaps and stale evidence are always shown/)).toBeInTheDocument();
  });

  it("links Explore to Home, Search, and the School Record Archive", () => {
    renderFooter();
    expect(screen.getByRole("link", { name: "Home" })).toHaveAttribute("href", "/");
    expect(screen.getByRole("link", { name: "Search" })).toHaveAttribute("href", "/search");
    expect(screen.getByRole("link", { name: "School Record Archive" })).toHaveAttribute("href", "/search");
  });

  it("links the three student profiles to prefilled searches", async () => {
    renderFooter();
    await waitFor(() =>
      expect(screen.getByRole("link", { name: "First-generation student" })).toHaveAttribute(
        "href",
        "/search?profile=first_generation"
      )
    );
    expect(screen.getByRole("link", { name: "Student with a disability" })).toHaveAttribute(
      "href",
      "/search?profile=student_with_disability"
    );
    expect(screen.getByRole("link", { name: "International STEM student" })).toHaveAttribute(
      "href",
      "/search?profile=international_stem"
    );
  });

  it("shows the copyright and data-mode notice in the bottom bar", () => {
    renderFooter();
    expect(screen.getByText(/© \d{4} SRA/)).toBeInTheDocument();
    expect(screen.getByText(/Mock data/)).toBeInTheDocument();
  });
});