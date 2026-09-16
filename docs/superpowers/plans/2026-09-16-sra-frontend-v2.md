# SRA Frontend v2 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Extend the SRA React frontend with the README `SearchReport` national layer (national programmes/deadlines, cache provenance, universe size), a marketing landing page at `/` with the search tool moved to `/search`, and a lint- and warning-clean repo.

**Architecture:** A typed `fetch` client with a swappable mock transport feeds `useApi` hooks. The national layer reuses the existing `ProgramList`/`DeadlineList` components via an optional `title` prop. The landing page is a new route that redirects legacy `/?…` URLs to `/search?…`; its national sections refetch the default search and render the same components. React Router v7 future flags silence router warnings.

**Tech Stack:** React 18, TypeScript 5.6, Vite 5, react-router-dom 6, lucide-react, Vitest 2 + Testing Library (jsdom), Playwright.

**Spec:** `docs/superpowers/specs/2026-09-16-sra-frontend-v2-design.md`

## Global Constraints

- **GET-only.** `src/api` exposes no POST helper; admin endpoints must not appear anywhere in `src/`.
- **Vocabulary is pass-through.** Profile, topic, link, and signal keys travel network → props → DOM unmapped; labels come from `/api/v1/profiles` and `/api/v1/topics`; missing label → raw key, never invented.
- **Provenance never hidden:** `gaps`, `stale`, `evidence`, `confidence`, `extractor` always render.
- **Visual system:** all values via `src/styles/tokens.css` custom properties – no hardcoded colors/sizes in component styles. Headings serif (`--font-display`), body sans (`--font-body`), never mixed. Data viz = `--chart-bar`, never `--accent`. **Lucide icons only, no emoji.** Sentence-case copy, plain verbs.
- **Motion** disabled under `@media (prefers-reduced-motion: reduce)`.
- **Profiles (exact keys):** `first_generation`, `student_with_disability`, `international_stem`.
- **Env:** `VITE_SRA_API_BASE` (default `http://localhost:8000`), `VITE_SRA_MOCK=1`.
- **React Router future flags:** `v7_startTransition` and `v7_relativeSplatPath` enabled on `createBrowserRouter`.

---

### Task 1: SearchReport contract surface (types, fixtures, mock)

**Files:**
- Modify: `src/api/types.ts`
- Modify: `src/fixtures/search.ca.first_generation.json`
- Modify: `src/api/mock.ts`
- Test: `src/api/client.test.ts` (add one fixture-shape assertion at the end of the existing `describe("request", ...)` block)

**Interfaces:**
- Consumes: nothing new.
- Produces: `SearchResponse` gains optional `count?: number`, `universe_size?: number`, `cache?: { hit: boolean; fingerprint: string }`, `national_programs?: Program[]`, `national_deadlines?: Deadline[]`. Later tasks read these fields.

- [ ] **Step 1: Write the failing test**

Append this block to `src/api/client.test.ts` (inside `describe("request", ...)`, after the existing `does not fall back in production builds` test):

```ts
  it("returns the national layer and cache provenance from the search fixture", async () => {
    vi.stubEnv("VITE_SRA_MOCK", "1");
    const data = (await request("/api/v1/search", {
      profile: "first_generation",
      state: "CA"
    })) as {
      universe_size?: number;
      cache?: { hit: boolean; fingerprint: string };
      national_programs?: unknown[];
      national_deadlines?: unknown[];
    };
    expect(data.universe_size).toBe(6243);
    expect(data.cache).toEqual({ hit: true, fingerprint: "7f8b9c3" });
    expect(data.national_programs?.length).toBeGreaterThanOrEqual(2);
    expect(data.national_deadlines?.length).toBeGreaterThanOrEqual(2);
  });
```

- [ ] **Step 2: Run test to verify it fails**

Run: `npx vitest run src/api/client.test.ts`
Expected: FAIL — fixture has no `universe_size` yet.

- [ ] **Step 3: Extend `SearchResponse` in `src/api/types.ts`**

Replace the `SearchResponse` interface (lines 80-85) with:

```ts
export interface SearchResponse {
  results: Match[];
  total?: number;
  limit?: number;
  offset?: number;
  count?: number;
  universe_size?: number;
  cache?: { hit: boolean; fingerprint: string };
  national_programs?: Program[];
  national_deadlines?: Deadline[];
}
```

- [ ] **Step 4: Add the national layer + provenance to the search fixture**

Replace the JSON object in `src/fixtures/search.ca.first_generation.json` with this (national arrays added, existing `results` unchanged):

```json
{
  "results": [
    {
      "institution": {
        "unitid": 230038,
        "name": "Example State University",
        "city": "Burlington",
        "state_abbr": "VT",
        "control": "public",
        "url_homepage": "https://example.edu/",
        "avg_net_price": null
      },
      "score": 61,
      "signals": { "aid_generosity": 0.71, "need_coverage": 0.66 },
      "why": [
        { "signal": "aid_generosity", "label": "Grants and net-price generosity", "value": 0.71, "weight": 22 }
      ],
      "needs_covered": ["financial_aid_office"],
      "links": { "home": "https://example.edu/" },
      "facts": [],
      "deadlines": [],
      "programs": [],
      "playbook": [],
      "gaps": [],
      "last_verified": "2026-09-14T12:00:00Z",
      "stale": true
    },
    {
      "institution": {
        "unitid": 243744,
        "name": "Stanford University",
        "city": "Stanford",
        "state_abbr": "CA",
        "control": "private_nonprofit",
        "url_homepage": "https://stanford.edu/",
        "avg_net_price": 14200
      },
      "score": 42,
      "signals": { "aid_generosity": 0.62, "need_coverage": 0.42 },
      "why": [
        { "signal": "aid_generosity", "label": "Grants and net-price generosity", "value": 0.62, "weight": 22 },
        { "signal": "need_coverage", "label": "Share of need met", "value": 0.42, "weight": 18 }
      ],
      "needs_covered": ["financial_aid_office", "first_gen_program"],
      "links": { "home": "https://stanford.edu/" },
      "facts": [],
      "deadlines": [
        { "label": "Regular Decision", "date_iso": "2027-01-05", "category": "application", "url": "https://admission.stanford.edu/apply/", "is_past": false, "days_left": 112 }
      ],
      "programs": [],
      "playbook": [],
      "gaps": ["FAFSA federal school code", "State aid deadline for 2027", "Average debt at graduation"],
      "last_verified": "2026-09-15T08:30:00Z",
      "stale": false
    }
  ],
  "total": 2,
  "count": 2,
  "universe_size": 6243,
  "cache": { "hit": true, "fingerprint": "7f8b9c3" },
  "limit": 10,
  "offset": 0,
  "national_programs": [
    {
      "program_id": "pell-grant",
      "name": "Federal Pell Grant",
      "official_url": "https://studentaid.gov/understand-aid/types/grants/pell",
      "amount_text": "Up to $7,395 for the 2024-25 award year",
      "deadlines": [
        { "label": "FAFSA filing opens", "date_iso": "2026-10-01", "category": "financial_aid", "url": "https://studentaid.gov/h/apply-for-aid/fafsa", "is_past": false, "days_left": 15 }
      ]
    },
    {
      "program_id": "seog",
      "name": "Federal Supplemental Educational Opportunity Grant",
      "official_url": "https://studentaid.gov/understand-aid/types/grants",
      "amount_text": "Between $100 and $4,000 per year",
      "deadlines": []
    }
  ],
  "national_deadlines": [
    { "label": "FAFSA for 2027-28 opens", "date_iso": "2026-10-01", "category": "financial_aid", "url": "https://studentaid.gov/h/apply-for-aid/fafsa", "is_past": false, "days_left": 15 },
    { "label": "FAFSA priority deadline (most states)", "date_iso": "2027-03-01", "category": "financial_aid", "url": "https://studentaid.gov/h/apply-for-aid/fafsa", "is_past": false, "days_left": 167 }
  ]
}
```

- [ ] **Step 5: Update the mock empty branch**

In `src/api/mock.ts`, the `rawPath === "/api/v1/search"` branch returns an empty response for non-CA/non-first-generation queries. Replace that return with:

```ts
    return Promise.resolve({
      results: [],
      total: 0,
      count: 0,
      universe_size: 6243,
      limit: 10,
      offset: 0
    } as unknown as T);
```

- [ ] **Step 6: Run the test to verify it passes**

Run: `npx vitest run src/api/client.test.ts`
Expected: PASS, 9 tests.

- [ ] **Step 7: Typecheck**

Run: `npm run typecheck`
Expected: PASS, no errors.

- [ ] **Step 8: Commit**

```bash
git add src/api/types.ts src/api/mock.ts src/api/client.test.ts src/fixtures/search.ca.first_generation.json
git commit -m "feat: surface national layer and cache provenance in search contract"
```

---

### Task 2: National sections and cache provenance on SearchPage

**Files:**
- Modify: `src/components/school/ProgramList.tsx`
- Modify: `src/components/school/DeadlineList.tsx`
- Modify: `src/routes/SearchPage.tsx`
- Test: `src/routes/SearchPage.test.tsx`

**Interfaces:**
- Consumes: `SearchResponse.count`, `.universe_size`, `.cache`, `.national_programs`, `.national_deadlines` (Task 1).
- Produces: `ProgramList({ programs, title? })` and `DeadlineList({ deadlines, title? })` with a default `title`; `SearchPage` renders a `.results-meta` provenance line and two national sections.

- [ ] **Step 1: Write the failing tests**

Append these tests to `src/routes/SearchPage.test.tsx` (inside `describe("SearchPage", ...)`):

```tsx
  it("shows cache provenance and the national layer", async () => {
    vi.stubEnv("VITE_SRA_MOCK", "1");
    renderPage();
    await waitFor(() =>
      expect(screen.getByText("Example State University")).toBeInTheDocument()
    );
    expect(screen.getByText(/6,243 schools searched/)).toBeInTheDocument();
    expect(screen.getByText(/cache hit · 7f8b9c3/)).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "National programmes" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "National deadlines" })).toBeInTheDocument();
    expect(screen.getByText("Federal Pell Grant")).toBeInTheDocument();
  });
```

Add a new focused spec (create `src/components/school/national.test.tsx`):

```tsx
import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import type { Deadline, Program } from "../../api/types";
import { DeadlineList } from "./DeadlineList";
import { ProgramList } from "./ProgramList";

const program: Program = {
  program_id: "pell",
  name: "Federal Pell Grant",
  official_url: null,
  amount_text: "Up to $7,395",
  deadlines: []
};

const deadline: Deadline = {
  label: "FAFSA opens",
  date_iso: "2026-10-01",
  category: "financial_aid",
  url: null,
  is_past: false,
  days_left: 15
};

describe("national lists reuse rendering with a custom title", () => {
  it("ProgramList uses the title prop and stays list-shaped", () => {
    render(<ProgramList programs={[program]} title="National programmes" />);
    expect(screen.getByRole("heading", { name: "National programmes" })).toBeInTheDocument();
    expect(screen.getByText("Federal Pell Grant")).toBeInTheDocument();
  });

  it("ProgramList renders nothing for an empty list", () => {
    const { container } = render(<ProgramList programs={[]} title="National programmes" />);
    expect(container).toBeEmptyDOMElement();
  });

  it("DeadlineList uses the title prop", () => {
    render(<DeadlineList deadlines={[deadline]} title="National deadlines" />);
    expect(screen.getByRole("heading", { name: "National deadlines" })).toBeInTheDocument();
    expect(screen.getByText("FAFSA opens")).toBeInTheDocument();
  });

  it("DeadlineList renders nothing for an empty list", () => {
    const { container } = render(<DeadlineList deadlines={[]} title="National deadlines" />);
    expect(container).toBeEmptyDOMElement();
  });
});
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `npx vitest run src/routes/SearchPage.test.tsx src/components/school/national.test.tsx`
Expected: the new SearchPage test FAILS (no provenance line/sections); `national.test.tsx` fails to resolve `./national` (file absent). Delete `national.test.tsx`'s missing-file failure by creating it in Step 1 (already done); the component tests fail on the missing `title` prop heading names until Step 3.

- [ ] **Step 3: Add the `title` prop to `ProgramList`**

Replace the heading block in `src/components/school/ProgramList.tsx`:

```tsx
export function ProgramList({ programs, title = "Programmes" }: { programs: Program[]; title?: string }) {
  if (programs.length === 0) return null;
  const headingId = `programs-${title.replace(/[^a-z0-9]+/gi, "-").toLowerCase()}`;

  return (
    <section className="section" aria-labelledby={headingId}>
      <h2 className="section__title" id={headingId}>
        {title}
      </h2>
```

- [ ] **Step 4: Add the `title` prop to `DeadlineList`**

Replace the heading block in `src/components/school/DeadlineList.tsx`:

```tsx
export function DeadlineList({ deadlines, title = "Deadlines" }: { deadlines: Deadline[]; title?: string }) {
  if (deadlines.length === 0) return null;
  const headingId = `deadlines-${title.replace(/[^a-z0-9]+/gi, "-").toLowerCase()}`;

  return (
    <section className="section section--pattern" aria-labelledby={headingId}>
      <h2 className="section__title" id={headingId}>
        {title}
      </h2>
```

- [ ] **Step 5: Render provenance + national sections in `SearchPage`**

In `src/routes/SearchPage.tsx`, after `const results = data?.results ?? [];` insert:

```tsx
  const count = data?.count ?? results.length;
  const universeSize = data?.universe_size;
  const cache = data?.cache;
```

Replace the `<h2 className="section__title">` block with:

```tsx
      <h2 className="section__title">
        {loading ? "Ranking schools…" : `${count} ranked match${count === 1 ? "" : "es"}`}
      </h2>

      {!loading && (universeSize !== undefined || cache) ? (
        <p className="results-meta">
          {universeSize !== undefined ? `${universeSize.toLocaleString("en-US")} schools searched` : null}
          {universeSize !== undefined && cache ? " · " : null}
          {cache ? (
            <span className="results-meta__cache">
              cache {cache.hit ? "hit" : "miss"} ·{" "}
              <code>{cache.fingerprint.slice(0, 8)}</code>
            </span>
          ) : null}
        </p>
      ) : null}
```

After the `<Pagination ... />` block, append the national sections:

```tsx
      <ProgramList programs={data?.national_programs ?? []} title="National programmes" />
      <DeadlineList deadlines={data?.national_deadlines ?? []} title="National deadlines" />
```

Add the imports at the top of `SearchPage.tsx`:

```tsx
import { DeadlineList } from "../components/school/DeadlineList";
import { ProgramList } from "../components/school/ProgramList";
```

Remove the now-unused `data?.total` reference in the old `<h2>` (the `total` display is replaced by `count`).

- [ ] **Step 6: Run tests to verify they pass**

Run: `npx vitest run src/routes/SearchPage.test.tsx src/components/school/national.test.tsx`
Expected: PASS.

- [ ] **Step 7: Typecheck**

Run: `npm run typecheck`
Expected: PASS, no errors.

- [ ] **Step 8: Commit**

```bash
git add src/components/school/ProgramList.tsx src/components/school/DeadlineList.tsx src/components/school/national.test.tsx src/routes/SearchPage.tsx src/routes/SearchPage.test.tsx
git commit -m "feat: show cache provenance and national programs/deadlines on search"
```

---

### Task 3: Landing page at `/`

**Files:**
- Create: `src/routes/LandingPage.tsx`
- Create: `src/components/landing/ProfileCards.tsx`
- Create: `src/components/landing/HowItWorks.tsx`
- Create: `src/components/landing/NationalSection.tsx`
- Create: `src/routes/LandingPage.test.tsx`
- Modify: `src/styles/components.css` (append landing styles)

**Interfaces:**
- Consumes: `useVocabulary().profiles`, `search`/`SearchQuery`, `DEFAULT_QUERY` (`src/lib/url.ts`), `useApi`, `Link`/`Navigate`/`useSearchParams`, `ProgramList`, `DeadlineList` (title prop, Task 2), lucide icons.
- Produces: `<LandingPage />` (redirect when query params present, else the marketing page), used as the index route in Task 4.

- [ ] **Step 1: Write the failing test**

Create `src/routes/LandingPage.test.tsx`:

```tsx
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
          <Route
            path="/"
            element={
              <>
                <LandingPage />
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

describe("LandingPage", () => {
  it("renders hero copy, three profile cards, and how-it-works", async () => {
    vi.stubEnv("VITE_SRA_MOCK", "1");
    renderPage();
    expect(screen.getByRole("heading", { name: /Ranked by what actually pays/i })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /Start your search/i })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: /First-generation student/i })).toBeInTheDocument();
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `npx vitest run src/routes/LandingPage.test.tsx`
Expected: FAIL — cannot resolve `./LandingPage`.

- [ ] **Step 3: Write `src/components/landing/ProfileCards.tsx`**

```tsx
import { Link } from "react-router-dom";
import { Accessibility, Building2, Globe } from "lucide-react";
import { useVocabulary } from "../../api/VocabularyContext";
import type { ProfileKey } from "../../api/types";

const ICONS: Record<ProfileKey, typeof Building2> = {
  first_generation: Building2,
  student_with_disability: Accessibility,
  international_stem: Globe
};

const NEEDS: Record<ProfileKey, string> = {
  first_generation:
    "Net price estimates · Institutional grants · Application-fee waivers · FAFSA codes & dates · TRIO and mentorship programs",
  student_with_disability:
    "Disability services office · Accommodation processes · Assistive-tech funding · State vocational rehabilitation",
  international_stem:
    "Need-based institutional aid · Tuition waivers · Graduate funding (RA/TA) · CSS Profile · CPT/OPT guidance"
};

const KEYS: ProfileKey[] = [
  "first_generation",
  "student_with_disability",
  "international_stem"
];

export function ProfileCards() {
  const { profiles } = useVocabulary();
  const label = (key: ProfileKey) =>
    profiles.find((profile) => profile.key === key)?.label ?? key;

  return (
    <ul className="profile-cards">
      {KEYS.map((key) => {
        const Icon = ICONS[key];
        return (
          <li key={key} className="profile-card">
            <Icon size={24} aria-hidden="true" className="profile-card__icon" />
            <h3 className="profile-card__name">{label(key)}</h3>
            <p className="profile-card__needs">{NEEDS[key]}</p>
            <Link className="profile-card__cta" to={`/search?profile=${key}`}>
              Search for {label(key)}
            </Link>
          </li>
        );
      })}
    </ul>
  );
}
```

- [ ] **Step 4: Write `src/components/landing/HowItWorks.tsx`**

```tsx
import { Search, BarChart3, ListChecks } from "lucide-react";

const STEPS = [
  {
    icon: Search,
    title: "Pick your profile",
    detail: "Choose who you are. Every search is ranked for one of three underserved student profiles."
  },
  {
    icon: BarChart3,
    title: "Read the ranked evidence",
    detail: "Each match shows its score, the reasons behind it, official links, and deadlines."
  },
  {
    icon: ListChecks,
    title: "Follow the playbook",
    detail: "A step-by-step plan from application-fee waiver to FAFSA filing — plus the gaps we could not verify."
  }
];

const TRUST = ["Cache-first, from verified sources", "Official links only", "Gaps always shown"];

export function HowItWorks() {
  return (
    <section className="section how-it-works" aria-labelledby="how-heading">
      <h2 className="section__title" id="how-heading">
        How it works
      </h2>
      <ol className="how-steps">
        {STEPS.map((step) => {
          const Icon = step.icon;
          return (
            <li key={step.title} className="how-step">
              <Icon size={20} aria-hidden="true" />
              <h3>{step.title}</h3>
              <p>{step.detail}</p>
            </li>
          );
        })}
      </ol>
      <p className="trust-strip" role="note">
        {TRUST.join(" · ")}
      </p>
    </section>
  );
}
```

- [ ] **Step 5: Write `src/components/landing/NationalSection.tsx`**

```tsx
import { Link } from "react-router-dom";
import { search } from "../../api/endpoints";
import { useApi } from "../../hooks/useApi";
import { DEFAULT_QUERY } from "../../lib/url";
import { ProgramList } from "../school/ProgramList";
import { DeadlineList } from "../school/DeadlineList";

export function NationalSection() {
  const { data } = useApi(() => search({ ...DEFAULT_QUERY, limit: 1 }), []);

  if (!data) return null;

  return (
    <section className="section section--pattern" aria-labelledby="national-heading">
      <div className="national-head">
        <div>
          <p className="eyebrow">Federal</p>
          <h2 className="section__title" id="national-heading">
            National aid programs and deadlines
          </h2>
        </div>
        <Link to="/search">Browse all matches</Link>
      </div>
      <ProgramList programs={data.national_programs ?? []} title="National programmes" />
      <DeadlineList deadlines={data.national_deadlines ?? []} title="National deadlines" />
    </section>
  );
}
```

- [ ] **Step 6: Write `src/routes/LandingPage.tsx`**

```tsx
import { Link, Navigate, useSearchParams } from "react-router-dom";
import { ArrowRight } from "lucide-react";
import { ProfileCards } from "../components/landing/ProfileCards";
import { HowItWorks } from "../components/landing/HowItWorks";
import { NationalSection } from "../components/landing/NationalSection";

export function LandingPage() {
  const [params] = useSearchParams();
  const search = params.toString();
  if (search !== "") {
    return <Navigate to={`/search?${search}`} replace />;
  }

  return (
    <div className="landing">
      <section className="hero" aria-labelledby="hero-heading">
        <p className="eyebrow">SRA — Student Resource Architecture</p>
        <h1 className="hero__title" id="hero-heading">
          Ranked by what actually pays.
        </h1>
        <p className="hero__sub">
          College and university discovery with financial-aid intelligence for
          students the data usually ignores. Every match shows why it scored,
          its official links, what it costs, and what we could not verify.
        </p>
        <div className="hero__ctas">
          <Link className="button button--primary" to="/search">
            Start your search
            <ArrowRight size={18} aria-hidden="true" />
          </Link>
          <Link className="button button--ghost" to="/search#school-record-archive">
            See it in action
          </Link>
        </div>
      </section>

      <ProfileCards />
      <HowItWorks />
      <NationalSection />
    </div>
  );
}
```

- [ ] **Step 7: Append landing styles to `src/styles/components.css`**

Append at the end of the file:

```css
.landing {
  display: flex;
  flex-direction: column;
  gap: var(--s6);
}

.hero {
  display: flex;
  flex-direction: column;
  gap: var(--s3);
  padding: var(--s6) 0;
  max-width: var(--max-w);
}

.hero__title {
  font-size: clamp(40px, 7vw, 88px);
  font-weight: 800;
  line-height: 1.04;
  letter-spacing: -0.025em;
  max-width: 14ch;
}

.hero__sub {
  margin: 0;
  color: var(--text-secondary);
  font-size: 19px;
  max-width: 560px;
}

.hero__ctas {
  display: flex;
  gap: var(--s2);
  flex-wrap: wrap;
  margin-top: var(--s2);
}

.button {
  display: inline-flex;
  align-items: center;
  gap: var(--s1);
  font-size: 15px;
  font-weight: 500;
  border-radius: var(--radius-md);
  padding: 12px 22px;
  text-decoration: none;
  transition: transform 0.15s ease, box-shadow 0.15s ease, background 0.15s ease;
}

.button--primary {
  background: var(--accent);
  color: var(--accent-fg);
}

.button--primary:hover {
  background: var(--accent-hover);
  color: var(--accent-fg);
  transform: translateY(-2px);
  box-shadow: var(--shadow-md);
}

.button--ghost {
  border: 1px solid var(--border);
  color: var(--text-primary);
}

.button--ghost:hover {
  border-color: var(--text-primary);
  color: var(--text-primary);
  transform: translateY(-2px);
}

.profile-cards {
  list-style: none;
  margin: 0;
  padding: 0;
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
  gap: var(--s3);
}

.profile-card {
  background: var(--bg-subtle);
  border: 1px solid var(--border);
  border-radius: var(--radius-lg);
  padding: var(--s4);
  display: flex;
  flex-direction: column;
  gap: var(--s2);
}

.profile-card__icon {
  color: var(--accent);
}

.profile-card__name {
  font-size: 22px;
}

.profile-card__needs {
  margin: 0;
  color: var(--text-secondary);
  font-size: 14px;
}

.profile-card__cta {
  margin-top: auto;
  align-self: flex-start;
  font-size: 14px;
  font-weight: 500;
}

.how-it-works {
  gap: var(--s4);
}

.how-steps {
  list-style: none;
  margin: 0;
  padding: 0;
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
  gap: var(--s3);
}

.how-step {
  display: flex;
  flex-direction: column;
  gap: var(--s1);
  padding: var(--s3);
  border: 1px solid var(--border);
  border-radius: var(--radius-lg);
  color: var(--accent);
}

.how-step h3 {
  color: var(--text-primary);
}

.how-step p {
  margin: 0;
  color: var(--text-secondary);
  font-size: 14px;
}

.trust-strip {
  margin: 0;
  color: var(--text-muted);
  font-size: 13px;
  text-align: center;
}

.national-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: var(--s3);
  flex-wrap: wrap;
}

.results-meta {
  margin: 0;
  font-size: 13px;
  color: var(--text-muted);
}

.results-meta__cache code {
  font-size: 12px;
  background: var(--bg-muted);
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  padding: 1px 5px;
}

@media (max-width: 640px) {
  .hero {
    padding: var(--s4) 0;
  }
}
```

- [ ] **Step 8: Run the test to verify it passes**

Run: `npx vitest run src/routes/LandingPage.test.tsx`
Expected: PASS, 4 tests.

- [ ] **Step 9: Typecheck**

Run: `npm run typecheck`
Expected: PASS, no errors.

- [ ] **Step 10: Commit**

```bash
git add src/routes/LandingPage.tsx src/routes/LandingPage.test.tsx src/components/landing src/styles/components.css
git commit -m "feat: add landing page at / with profile cards and national section"
```

---

### Task 4: Routes, header, and back links

**Files:**
- Modify: `src/main.tsx`
- Modify: `src/components/layout/Header.tsx`
- Modify: `src/routes/SchoolPage.tsx`
- Modify: `src/routes/NotFoundPage.tsx`
- Test: `src/routes/LandingPage.test.tsx` (already imports no router wiring; this task changes wiring, verified by e2e + typecheck)

**Interfaces:**
- Consumes: `LandingPage` (Task 3), `SearchPage`, `SchoolPage`, `NotFoundPage`, `Header`.
- Produces: router with `/` → `LandingPage`, `/search` → `SearchPage`, `/schools/:key`, `*`; header nav "Search" → `/search`; back-to-search links → `/search`.

- [ ] **Step 1: Write the failing App-level test**

Replace `src/App.test.tsx` with:

```tsx
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
```

- [ ] **Step 2: Run to verify it fails**

Run: `npx vitest run src/App.test.tsx`
Expected: FAIL — header nav link still points to `/`.

- [ ] **Step 3: Update `src/main.tsx`**

Wire the landing route and future flags. Replace the router construction:

```tsx
import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { RouterProvider, createBrowserRouter } from "react-router-dom";
import App from "./App";
import { VocabularyProvider } from "./api/VocabularyContext";
import { LandingPage } from "./routes/LandingPage";
import { SearchPage } from "./routes/SearchPage";
import { SchoolPage } from "./routes/SchoolPage";
import { NotFoundPage } from "./routes/NotFoundPage";
import "./styles/tokens.css";
import "./styles/base.css";
import "./styles/components.css";

const router = createBrowserRouter(
  [
    {
      path: "/",
      element: <App />,
      children: [
        { index: true, element: <LandingPage /> },
        { path: "search", element: <SearchPage /> },
        { path: "schools/:key", element: <SchoolPage /> },
        { path: "*", element: <NotFoundPage /> }
      ]
    }
  ],
  { future: { v7_startTransition: true, v7_relativeSplatPath: true } }
);

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <VocabularyProvider>
      <RouterProvider router={router} />
    </VocabularyProvider>
  </StrictMode>
);
```

- [ ] **Step 4: Update `src/components/layout/Header.tsx`**

Change the nav link target:

```tsx
        <nav className="site-nav" aria-label="Main">
          <NavLink to="/search">Search</NavLink>
        </nav>
```

- [ ] **Step 5: Update back links**

In `src/routes/SchoolPage.tsx`, change the back link:

```tsx
  const backTo = `/search?${params.toString()}`;
```

In `src/routes/NotFoundPage.tsx`, change the link:

```tsx
        <Link to="/search">Back to search</Link>
```

- [ ] **Step 6: Run the App test to verify it passes**

Run: `npx vitest run src/App.test.tsx`
Expected: PASS, 1 test.

- [ ] **Step 7: Run the full suite**

Run: `npm test`
Expected: All tests pass (existing route/pages tests still pass; nothing referenced the index search route from within a `MemoryRouter`).

- [ ] **Step 8: Typecheck**

Run: `npm run typecheck`
Expected: PASS, no errors.

- [ ] **Step 9: Commit**

```bash
git add src/main.tsx src/components/layout/Header.tsx src/routes/SchoolPage.tsx src/routes/NotFoundPage.tsx src/App.test.tsx
git commit -m "feat: move search to /search with landing at / and legacy redirect"
```

---

### Task 5: Housekeeping — lint, router flags, stale act noise

**Files:**
- Modify: `src/api/VocabularyContext.tsx`

**Interfaces:**
- Consumes: nothing new.
- Produces: lint-clean `VocabularyContext.tsx`; router future flags already set in Task 4.

- [ ] **Step 1: Run lint to capture the current warnings**

Run: `npm run lint`
Expected: 2 warnings in `src/api/VocabularyContext.tsx` (react-hooks/exhaustive-deps), 0 errors.

- [ ] **Step 2: Fix the `useMemo` dependency warnings**

Replace the body of `VocabularyProvider` in `src/api/VocabularyContext.tsx`:

```tsx
export function VocabularyProvider({ children }: { children: ReactNode }) {
  const profilesState = useApi(() => fetchProfiles(), []);
  const topicsState = useApi(() => fetchTopics(), []);

  const value = useMemo<VocabularyValue>(() => {
    const profiles = profilesState.data?.profiles ?? [];
    const topics = topicsState.data?.topics ?? [];
    return {
      profiles,
      topics,
      topicLabel: (key: string) => topicLabelFrom(topics, key),
      loading: profilesState.loading || topicsState.loading
    };
  }, [profilesState.data, topicsState.data, profilesState.loading, topicsState.loading]);

  return <VocabularyContext.Provider value={value}>{children}</VocabularyContext.Provider>;
}
```

- [ ] **Step 3: Run lint to verify zero warnings**

Run: `npm run lint`
Expected: no output (exit 0, 0 problems).

- [ ] **Step 4: Run typecheck and tests**

Run: `npm run typecheck`
Expected: PASS.
Run: `npm test`
Expected: PASS, 50+ tests. `act(...)` warnings may still appear for async vocabulary loads in a few specs; they are warnings, not failures, and are out of scope to fully silence — the v2 gate is zero lint warnings and all tests passing.

- [ ] **Step 5: Commit**

```bash
git add src/api/VocabularyContext.tsx
git commit -m "fix: quiet react-hooks lint warnings in vocabulary context"
```

---

### Task 6: Playwright smoke test — landing → search → school

**Files:**
- Modify: `e2e/smoke.spec.ts`

**Interfaces:**
- Consumes: the real router (mock mode via `VITE_SRA_MOCK=1`).
- Produces: an e2e flow covering the landing page, `/search`, and GET-only traffic.

- [ ] **Step 1: Rewrite `e2e/smoke.spec.ts`**

```ts
import { expect, test } from "@playwright/test";

test("landing to search to school detail, with GET-only traffic", async ({ page }) => {
  const methods: string[] = [];
  page.on("request", (request) => methods.push(request.method()));

  await page.goto("/");

  await expect(page.getByRole("heading", { name: /Ranked by what actually pays/i })).toBeVisible();
  await page.getByRole("link", { name: /Start your search/i }).click();
  await expect(page).toHaveURL(/\/search/);

  await page.getByLabel("State").fill("CA");
  await expect(page).toHaveURL(/state=CA/);
  await expect(page.getByText("Stanford University")).toBeVisible();
  await expect(page.getByText("42/100")).toBeVisible();
  await expect(page.getByText(/cache hit/)).toBeVisible();

  await page.getByRole("link", { name: "Stanford University" }).click();
  await expect(page).toHaveURL(/\/schools\/243744/);

  await expect(page.getByRole("heading", { name: "Stanford University" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Official links" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Evidence" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Not verified yet" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Playbook" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Deadlines" }).first()).toBeVisible();
  await expect(page.getByRole("heading", { name: "Programmes" })).toBeVisible();

  expect(methods.filter((method) => method === "POST")).toEqual([]);
});

test("legacy root query URLs redirect to /search", async ({ page }) => {
  await page.goto("/?profile=first_generation&state=CA");
  await expect(page).toHaveURL(/\/search\?profile=first_generation&state=CA/);
  await expect(page.getByText("Stanford University")).toBeVisible();
});
```

Note: `/search` defaults to `first_generation`; after typing `CA` in `State` the mock returns the CA fixture (which now includes the national layer), so `cache hit` renders.

- [ ] **Step 2: Run the e2e suite**

Run: `npm run test:e2e`
Expected: PASS, 2 tests (webServer builds the app with `VITE_SRA_MOCK=1`).

- [ ] **Step 3: Commit**

```bash
git add e2e/smoke.spec.ts
git commit -m "test: e2e covers landing, search redirect, and GET-only traffic"
```

---

### Task 7: Full verification

No code changes — confirm the whole pipeline is green in the exact order the spec requires.

- [ ] **Step 1: Typecheck**

Run: `npm run typecheck`
Expected: PASS, no errors.

- [ ] **Step 2: Lint**

Run: `npm run lint`
Expected: 0 problems.

- [ ] **Step 3: Unit + component tests**

Run: `npm test`
Expected: all suites pass.

- [ ] **Step 4: E2E**

Run: `npm run test:e2e`
Expected: PASS.

- [ ] **Step 5: Production build**

Run: `npm run build`
Expected: `tsc --noEmit` clean, `vite build` succeeds.