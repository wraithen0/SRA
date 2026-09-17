import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import type { SearchQuery } from "../../api/types";
import { VocabularyProvider } from "../../api/VocabularyContext";
import { resetMockState } from "../../api/client";
import { SearchConsole } from "./SearchConsole";

afterEach(() => {
  vi.unstubAllEnvs();
  resetMockState();
});

const baseQuery: SearchQuery = { profile: "first_generation", limit: 10, offset: 0 };

function renderConsole(query: SearchQuery, options: { loading?: boolean; onCommit?: ReturnType<typeof vi.fn> } = {}) {
  vi.stubEnv("VITE_SRA_MOCK", "1");
  const onCommit = options.onCommit ?? vi.fn();
  const view = render(
    <VocabularyProvider>
      <SearchConsole query={query} loading={options.loading ?? false} onCommit={onCommit} />
    </VocabularyProvider>
  );
  return { ...view, onCommit };
}

function updateButton() {
  return screen.getByRole("button", { name: "Update ranking" });
}

describe("SearchConsole", () => {
  it("commits keyword and filters when Update ranking is clicked", async () => {
    const view = renderConsole(baseQuery);
    await userEvent.type(screen.getByLabelText("School name or keyword"), "stanford");
    await userEvent.type(screen.getByLabelText("State"), "CA");
    await userEvent.click(updateButton());
    expect(view.onCommit).toHaveBeenCalledTimes(1);
    const patch = view.onCommit.mock.calls[0][0] as Partial<SearchQuery>;
    expect(patch.q).toBe("stanford");
    expect(patch.state).toBe("CA");
    expect(patch.offset).toBe(0);
  });

  it("enables the button only when there are pending changes", async () => {
    renderConsole(baseQuery);
    expect(updateButton()).toBeDisabled();
    await userEvent.type(screen.getByLabelText("State"), "CA");
    expect(updateButton()).toBeEnabled();
    await userEvent.type(screen.getByLabelText("State"), "{Backspace}{Backspace}");
    expect(updateButton()).toBeDisabled();
  });

  it("disables the button while loading even with pending changes", async () => {
    renderConsole(baseQuery, { loading: true });
    await userEvent.type(screen.getByLabelText("State"), "CA");
    expect(updateButton()).toBeDisabled();
  });

  it("submits when Enter is pressed in the keyword field", async () => {
    const view = renderConsole(baseQuery);
    const keyword = screen.getByLabelText("School name or keyword");
    await userEvent.type(keyword, "stanford");
    await userEvent.type(keyword, "{Enter}");
    expect(view.onCommit).toHaveBeenCalledTimes(1);
    expect(view.onCommit.mock.calls[0][0]).toMatchObject({ q: "stanford" });
  });

  it("commits immediately when a chip is removed", async () => {
    const view = renderConsole({ ...baseQuery, state: "CA" });
    await userEvent.click(screen.getByRole("button", { name: "Remove CA" }));
    expect(view.onCommit).toHaveBeenCalledTimes(1);
    const patch = view.onCommit.mock.calls[0][0] as Partial<SearchQuery>;
    expect(patch.state).toBeUndefined();
  });

  it("clearing the keyword commits immediately", async () => {
    const view = renderConsole({ ...baseQuery, q: "stanford" });
    await userEvent.click(screen.getByRole("button", { name: "Clear search" }));
    expect(view.onCommit).toHaveBeenCalledWith({ q: undefined });
  });

  it("resyncs the draft when the committed query changes externally", async () => {
    const view = renderConsole({ ...baseQuery, state: "CA" });
    expect((screen.getByLabelText("State") as HTMLInputElement).value).toBe("CA");
    view.rerender(
      <VocabularyProvider>
        <SearchConsole query={baseQuery} loading={false} onCommit={view.onCommit} />
      </VocabularyProvider>
    );
    await waitFor(() =>
      expect((screen.getByLabelText("State") as HTMLInputElement).value).toBe("")
    );
  });
});
