import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, expect, it, vi } from "vitest";
import App from "./App";
import { VocabularyProvider } from "./api/VocabularyContext";
import { resetMockState } from "./api/client";

afterEach(() => {
  vi.unstubAllEnvs();
  resetMockState();
});

it("renders the app shell with a header, brand link, footer, and a search nav link", () => {
  vi.stubEnv("VITE_SRA_MOCK", "1");
  render(
    <VocabularyProvider>
      <MemoryRouter initialEntries={["/"]}>
        <App />
      </MemoryRouter>
    </VocabularyProvider>
  );
  expect(screen.getByRole("banner")).toBeInTheDocument();
  expect(screen.getByRole("link", { name: /SRA/ })).toBeInTheDocument();
  expect(screen.getByRole("link", { name: /Search/ })).toHaveAttribute("href", "/search");
  expect(screen.getByRole("contentinfo")).toBeInTheDocument();
});