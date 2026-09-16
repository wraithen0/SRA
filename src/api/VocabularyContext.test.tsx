import { render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { VocabularyProvider, useVocabulary } from "./VocabularyContext";
import { resetMockState } from "./client";

function Probe() {
  const { profiles, topicLabel } = useVocabulary();
  return (
    <div>
      <span data-testid="count">{profiles.length}</span>
      <span data-testid="first-label">
        {profiles.find((profile) => profile.key === "first_generation")?.label ?? "missing"}
      </span>
      <span data-testid="known">{topicLabel("net_price_calculator")}</span>
      <span data-testid="unknown">{topicLabel("not_a_topic")}</span>
    </div>
  );
}

afterEach(() => {
  vi.unstubAllEnvs();
  resetMockState();
});

describe("VocabularyProvider", () => {
  it("loads profiles and labels topics with a raw-key fallback", async () => {
    vi.stubEnv("VITE_SRA_MOCK", "1");
    render(
      <VocabularyProvider>
        <Probe />
      </VocabularyProvider>
    );
    await waitFor(() => expect(screen.getByTestId("count")).toHaveTextContent("3"));
    expect(screen.getByTestId("first-label")).toHaveTextContent("First-generation student");
    expect(screen.getByTestId("known")).toHaveTextContent("Net price calculator");
    expect(screen.getByTestId("unknown")).toHaveTextContent("not_a_topic");
  });
});