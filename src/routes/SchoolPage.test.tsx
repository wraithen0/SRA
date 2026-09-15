import { render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";
import { SchoolPage } from "./SchoolPage";
import { VocabularyProvider } from "../api/VocabularyContext";
import { resetMockState } from "../api/client";

function renderSchool(key: string, search = "?profile=first_generation") {
  return render(
    <VocabularyProvider>
      <MemoryRouter initialEntries={[`/schools/${key}${search}`]}>
        <Routes>
          <Route path="/schools/:key" element={<SchoolPage />} />
        </Routes>
      </MemoryRouter>
    </VocabularyProvider>
  );
}

afterEach(() => {
  vi.unstubAllEnvs();
  resetMockState();
});

describe("SchoolPage", () => {
  it("renders every rule section", async () => {
    vi.stubEnv("VITE_SRA_MOCK", "1");
    renderSchool("243744");
    await waitFor(() =>
      expect(screen.getByRole("heading", { name: "Stanford University" })).toBeInTheDocument()
    );
    expect(screen.getByText("42/100")).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: /Official links/i })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: /Evidence/i })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: /Not verified yet/i })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: /Playbook/i })).toBeInTheDocument();
    expect(screen.getAllByRole("heading", { name: /Deadlines/i }).length).toBeGreaterThan(0);
    expect(screen.getByRole("heading", { name: /Programmes/i })).toBeInTheDocument();
  });

  it("renders a not-found view for an unknown school key", async () => {
    vi.stubEnv("VITE_SRA_MOCK", "1");
    renderSchool("999999");
    await waitFor(() => expect(screen.getByText(/No record for/i)).toBeInTheDocument());
    expect(screen.getByRole("link", { name: /Back to search/i })).toBeInTheDocument();
  });
});