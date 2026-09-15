import type { ReactNode } from "react";
import { render, screen, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import school from "../../fixtures/school.243744.json";
import stale from "../../fixtures/school.230038.json";
import type { Match } from "../../api/types";
import { VocabularyProvider } from "../../api/VocabularyContext";
import { resetMockState } from "../../api/client";
import { ScorePanel } from "./ScorePanel";
import { OfficialLinks } from "./OfficialLinks";
import { FactsEvidence } from "./FactsEvidence";
import { GapsPanel } from "./GapsPanel";
import { PlaybookChecklist } from "./PlaybookChecklist";
import { DeadlineList } from "./DeadlineList";
import { StaleBadge } from "../layout/StaleBadge";

const match = school as unknown as Match;
const staleMatch = stale as unknown as Match;

beforeEach(() => {
  vi.stubEnv("VITE_SRA_MOCK", "1");
});

afterEach(() => {
  vi.unstubAllEnvs();
  resetMockState();
});

function wrap(node: ReactNode) {
  return render(<VocabularyProvider>{node}</VocabularyProvider>);
}

describe("rule 1: score and reason bars", () => {
  it("renders the score with the profile label and sorts reasons by weight", () => {
    wrap(<ScorePanel match={match} profileLabelText="First-generation student" />);
    expect(screen.getByText("42/100")).toBeInTheDocument();
    expect(screen.getByText(/First-generation student/)).toBeInTheDocument();
    const bars = screen.getAllByRole("meter");
    expect(bars[0]).toHaveAttribute("aria-valuenow", "22");
  });
});

describe("rule 2: official links", () => {
  it("labels links from topics and falls back to the raw key", async () => {
    wrap(
      <OfficialLinks
        links={{ net_price_calculator: "https://x.test", custom_key: "https://y.test" }}
      />
    );
    const known = await screen.findByRole("link", { name: /Net price calculator/i });
    expect(known).toHaveAttribute("href", "https://x.test");
    expect(screen.getByRole("link", { name: /custom_key/ })).toHaveAttribute("href", "https://y.test");
  });
});

describe("rule 3: facts evidence", () => {
  it("shows evidence, source, and tags llm facts", () => {
    wrap(<FactsEvidence facts={match.facts} />);
    expect(screen.getByText(/Stanford meets the full need/i)).toBeInTheDocument();
    expect(screen.getByText(/model-inferred/i)).toBeInTheDocument();
    expect(screen.getByText(/61% confidence/)).toBeInTheDocument();
  });
});

describe("rule 4: gaps always visible", () => {
  it("lists gaps", () => {
    wrap(<GapsPanel gaps={match.gaps} />);
    expect(screen.getByRole("heading", { name: /Not verified yet/i })).toBeInTheDocument();
    expect(screen.getByText("FAFSA federal school code")).toBeInTheDocument();
  });

  it("renders an empty state when there are no gaps", () => {
    wrap(<GapsPanel gaps={[]} />);
    expect(screen.getByRole("heading", { name: /Not verified yet/i })).toBeInTheDocument();
    expect(screen.getByText(/Nothing flagged/i)).toBeInTheDocument();
  });
});

describe("rule 5: playbook", () => {
  it("orders steps and marks verify steps", () => {
    wrap(<PlaybookChecklist steps={match.playbook} />);
    const section = screen.getByRole("heading", { name: /Playbook/i }).closest("section")!;
    const items = within(section).getAllByRole("listitem");
    expect(items[0]).toHaveTextContent("Create your Federal Student Aid");
    const verify = items.find((item) => item.textContent?.includes("Confirm the California"));
    expect(verify?.className).toContain("playbook-step--verify");
    expect(within(verify!).getByText(/Verify on the page/i)).toBeInTheDocument();
  });
});

describe("rule 6: deadlines", () => {
  it("sorts ascending and dims past deadlines", () => {
    wrap(<DeadlineList deadlines={match.deadlines} />);
    const section = screen.getByRole("heading", { name: /Deadlines/i }).closest("section")!;
    const rows = within(section).getAllByRole("listitem");
    expect(rows[0]).toHaveTextContent("CSS Profile priority filing");
    expect(rows[0].className).toContain("deadline--past");
    expect(rows[2]).toHaveTextContent("Regular Decision");
  });
});

describe("rule 7: stale", () => {
  it("shows the freshness badge for a stale match", () => {
    render(<StaleBadge stale={staleMatch.stale} />);
    expect(screen.getByText(/past its freshness window/i)).toBeInTheDocument();
  });
});