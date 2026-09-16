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
  const brandLinks = screen.getAllByRole("link", { name: /SRA/ });
  expect(brandLinks).toHaveLength(2);
  brandLinks.forEach((link) => expect(link).toHaveAttribute("href", "/"));
  const searchLinks = screen.getAllByRole("link", { name: "Search" });
  expect(searchLinks).toHaveLength(2);
  searchLinks.forEach((link) => expect(link).toHaveAttribute("href", "/search"));
  expect(screen.getByRole("contentinfo")).toBeInTheDocument();
});