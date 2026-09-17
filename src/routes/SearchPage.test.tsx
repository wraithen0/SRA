import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes, useLocation } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";
import { SearchPage } from "./SearchPage";
import { VocabularyProvider } from "../api/VocabularyContext";
import { resetMockState } from "../api/client";

function LocationProbe() {
  const location = useLocation();
  return <span data-testid="location">{location.search}</span>;
}

function renderPage(initial = "/?profile=first_generation&state=CA") {
  return render(
    <VocabularyProvider>
      <MemoryRouter initialEntries={[initial]}>
        <Routes>
          <Route
            path="/"
            element={
              <>
                <SearchPage />
                <LocationProbe />
              </>
            }
          />
        </Routes>
      </MemoryRouter>
    </VocabularyProvider>
  );
}

afterEach(() => {
  vi.unstubAllEnvs();
  resetMockState();
});

describe("SearchPage", () => {
  it("renders ranked results with score and reason bars", async () => {
    vi.stubEnv("VITE_SRA_MOCK", "1");
    renderPage();
    await waitFor(() =>
      expect(screen.getByText("Example State University")).toBeInTheDocument()
    );
    expect(screen.getByText("61/100")).toBeInTheDocument();
    expect(screen.getAllByRole("meter").length).toBeGreaterThan(0);
  });

  it("shows a gaps count on each result", async () => {
    vi.stubEnv("VITE_SRA_MOCK", "1");
    renderPage();
    await waitFor(() => expect(screen.getByText(/3 not verified/)).toBeInTheDocument());
  });

  it("writes filter changes into the URL", async () => {
    vi.stubEnv("VITE_SRA_MOCK", "1");
    renderPage("/?profile=first_generation&state=");
    await waitFor(() =>
      expect(screen.getByText("Example State University")).toBeInTheDocument()
    );
    await userEvent.type(screen.getByLabelText("State"), "CA");
    await waitFor(() =>
      expect(screen.getByTestId("location").textContent).toContain("state=CA")
    );
  });

  it("shows an actionable empty state", async () => {
    vi.stubEnv("VITE_SRA_MOCK", "1");
    renderPage("/?profile=first_generation&state=TX");
    await waitFor(() =>
      expect(screen.getByText(/No schools matched these filters/i)).toBeInTheDocument()
    );
    expect(screen.getByRole("button", { name: /Clear filters/i })).toBeInTheDocument();
  });

  it("shows cache provenance and the national layer", async () => {
    vi.stubEnv("VITE_SRA_MOCK", "1");
    renderPage();
    await waitFor(() =>
      expect(screen.getByText("Example State University")).toBeInTheDocument()
    );
    expect(screen.getByText(/6,243 schools searched/)).toBeInTheDocument();
    expect(screen.getByText(/cache hit/, { selector: ".results-meta__cache" })).toBeInTheDocument();
    expect(screen.getByText("7f8b9c3")).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "National programmes" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "National deadlines" })).toBeInTheDocument();
    expect(screen.getByText("Federal Pell Grant")).toBeInTheDocument();
  });

  it("shows removable filter chips and removes a single filter", async () => {
    vi.stubEnv("VITE_SRA_MOCK", "1");
    renderPage("/?profile=first_generation&state=CA&stem_only=true&max_net_price=15000&q=stanford");
    await waitFor(() =>
      expect(screen.getByText("Example State University")).toBeInTheDocument()
    );
    expect(screen.getAllByRole("button", { name: /^Remove / }).length).toBeGreaterThan(0);
    await userEvent.click(screen.getByRole("button", { name: "Remove CA" }));
    await waitFor(() =>
      expect(screen.getByTestId("location").textContent).not.toContain("state=")
    );
    expect(screen.getByTestId("location").textContent).toContain("stem_only=true");
    expect(screen.getByTestId("location").textContent).toContain("q=stanford");
    expect(screen.getByTestId("location").textContent).toContain("max_net_price=15000");
  });

  it("clears all active filters but keeps the profile", async () => {
    vi.stubEnv("VITE_SRA_MOCK", "1");
    renderPage("/?profile=first_generation&state=CA&stem_only=true&q=stanford");
    await waitFor(() =>
      expect(screen.getByText("Example State University")).toBeInTheDocument()
    );
    await userEvent.click(screen.getByRole("button", { name: "Clear all" }));
    await waitFor(() =>
      expect(screen.getByTestId("location").textContent).not.toContain("state=")
    );
    const location = screen.getByTestId("location").textContent ?? "";
    expect(location).toContain("profile=first_generation");
    expect(location).not.toContain("stem_only");
    expect(location).not.toContain("q=");
    expect(location).not.toContain("max_net_price");
  });

  it("renders a rank number on each ranked result", async () => {
    vi.stubEnv("VITE_SRA_MOCK", "1");
    const { container } = renderPage();
    await waitFor(() =>
      expect(screen.getByText("Example State University")).toBeInTheDocument()
    );
    const ranks = [...container.querySelectorAll(".result-card__rank")].map(
      (element) => element.textContent
    );
    expect(ranks).toEqual(["#1", "#2"]);
  });

  it("shows a paging summary when the total is known", async () => {
    vi.stubEnv("VITE_SRA_MOCK", "1");
    renderPage();
    await waitFor(() =>
      expect(screen.getByText("Example State University")).toBeInTheDocument()
    );
    expect(screen.getByText(/Showing 1–2 of 2/)).toBeInTheDocument();
  });

  it("shows skeleton cards while ranking", async () => {
    vi.stubEnv("VITE_SRA_MOCK", "1");
    const { container } = renderPage();
    expect(container.querySelector(".result-skeleton")).not.toBeNull();
    await waitFor(() =>
      expect(screen.getByText("Example State University")).toBeInTheDocument()
    );
  });
});