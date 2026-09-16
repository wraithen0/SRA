import { render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes, useLocation } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";
import { LandingPage } from "./LandingPage";
import { VocabularyProvider } from "../api/VocabularyContext";
import { resetMockState } from "../api/client";

function LocationProbe() {
  const location = useLocation();
  return <span data-testid="location">{location.pathname + location.search}</span>;
}

function renderPage(initial = "/") {
  return render(
    <VocabularyProvider>
      <MemoryRouter initialEntries={[initial]}>
        <Routes>
          <Route path="/" element={<LandingPage />} />
          <Route path="/search" element={<LocationProbe />} />
        </Routes>
      </MemoryRouter>
    </VocabularyProvider>
  );
}

afterEach(() => {
  vi.unstubAllEnvs();
  resetMockState();
});

describe("LandingPage", () => {
  it("renders hero copy, three profile cards, and how-it-works", async () => {
    vi.stubEnv("VITE_SRA_MOCK", "1");
    renderPage();
    expect(screen.getByRole("heading", { name: /Ranked by what actually pays/i })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /Start your search/i })).toBeInTheDocument();
    await waitFor(() =>
      expect(screen.getByRole("heading", { name: /First-generation student/i })).toBeInTheDocument()
    );
    expect(screen.getByRole("heading", { name: /Student with a disability/i })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: /International STEM student/i })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: /How it works/i })).toBeInTheDocument();
  });

  it("renders the national section from the default search", async () => {
    vi.stubEnv("VITE_SRA_MOCK", "1");
    renderPage();
    await waitFor(() => expect(screen.getByText("Federal Pell Grant")).toBeInTheDocument());
    expect(screen.getByRole("heading", { name: "National programmes" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "National deadlines" })).toBeInTheDocument();
  });

  it("redirects to /search when it carries query params", () => {
    vi.stubEnv("VITE_SRA_MOCK", "1");
    renderPage("/?profile=first_generation&state=CA");
    expect(screen.getByTestId("location").textContent).toBe("/search?profile=first_generation&state=CA");
  });

  it("links each profile card to its prefilled search", async () => {
    vi.stubEnv("VITE_SRA_MOCK", "1");
    renderPage();
    const link = await screen.findByRole("link", { name: /student with a disability/i });
    expect(link).toHaveAttribute("href", "/search?profile=student_with_disability");
  });
});
