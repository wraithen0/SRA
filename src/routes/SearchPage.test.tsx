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
});