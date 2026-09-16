# SRA — Student Resource Archive · Web Frontend

The frontend for **SRA (Student Resource Architecture / Archive)**: college and
university discovery with financial-aid intelligence, engineered for the
students the college rankings usually ignore.

This is the **frontend side** of the SRA project. It is a
React + TypeScript single-page app that consumes the read-only REST API
(`/api/v1/*`) served by the SRA sidecar (`sra_schools`). Everything is driven by
data: ranked school matches, evidence-backed facts, playbooks, deadlines, and
aid programmes — with provenance never hidden.

## Highlights

- **Profile-aware search** for three underserved student profiles:
  - `first_generation` — first-gen students seeking scholarships, net-price
    clarity, application-fee waivers, and mentorship
  - `student_with_disability` — students needing accommodation funding,
    assistive-technology grants, and disability services
  - `international_stem` — non-US citizens seeking fully funded degrees,
    tuition waivers, and visa-legal research/internship paths
- **Transparency by design** — searches show why a school ranked
  (`why` with signal weights), which gaps remain, and whether the result came
  from a fresh cache hit (fingerprint included).
- **Provenance-first** — data quality is the product. Stale evidence, missing
  gaps, and cache state are always visible, never hidden.
- **GET-only** — the client never mutates the backend; it reads search results,
  school records, status, profiles, and the topic vocabulary.
- **Resilient data layer** — a bundled fixture transport lets the app run
  without the sidecar, and it automatically reverts to live data the moment the
  backend recovers (with a visible "Mock data" notice while fallback is active).

## Tech Stack

| Layer | Choice |
|---|---|
| Language | TypeScript (strict) |
| Framework | React 18 + React Router 6 |
| Styling | Hand-rolled CSS design tokens (accent `#5ea832`) |
| Icons | Lucide (no emoji) |
| Build tooling | Vite |
| Unit tests | Vitest + Testing Library (jsdom) |
| E2E tests | Playwright (Chromium) |
| Lint / types | ESLint + `tsc --noEmit` |

## Getting Started

### Prerequisites

- Node.js 18+ and npm
- (Optional) the SRA sidecar on `http://localhost:8000` for live data. See the
  companion backend (`sra_schools`) for setup. Not required — the app falls
  back to bundled fixtures in development.

### Install

```bash
npm install
```

### Run the dev server

```bash
npm run dev
```

Open http://localhost:5173. With no sidecar running, the app serves fixture
data and shows a small "Mock data" banner in the footer.

## Configuration

Environment variables are read from a local `.env` file (see `.env.example`):

| Variable | Default | Purpose |
|---|---|---|
| `VITE_SRA_API_BASE` | `http://localhost:8000` | Base URL of the SRA sidecar |
| `VITE_SRA_MOCK` | `0` | Force the fixture transport (`1`) regardless of connectivity |

### Data modes

| Mode | When | Behavior |
|---|---|---|
| **Live API** | No env override, backend reachable | `GET {api_base}/api/v1/*`; fixture fallback disabled |
| **Fallback (dev)** | `VITE_SRA_MOCK` unset/`0`, network error, non-production | Serves bundled fixtures; shows a "Mock data" banner; reverts to live data automatically once the backend recovers |
| **Forced mock** | `VITE_SRA_MOCK=1` | Always serves fixtures (also used by unit + e2e tests for hermetic runs) |

## Commands

| Command | Description |
|---|---|
| `npm run dev` | Start the Vite dev server |
| `npm run build` | Type-check then production build to `dist/` |
| `npm run preview` | Preview the production build |
| `npm run lint` | ESLint across the repo |
| `npm run typecheck` | `tsc --noEmit` |
| `npm test` | Run all unit tests once (Vitest + jsdom) |
| `npm run test:watch` | Unit tests in watch mode |
| `npm run test:e2e` | Playwright end-to-end smoke tests (internal build + preview) |

### Standard verification (run in order)

```bash
npm run typecheck
npm run lint
npm test
npm run test:e2e
npm run build
```

## API Contract

All requests are `GET`. Handled endpoints:

| Endpoint | Used by |
|---|---|
| `GET /api/v1/search` | `SearchPage`, landing-page national sections |
| `GET /api/v1/schools/{key}` | `SchoolPage` (single `Match` record) |
| `GET /api/v1/profiles` | `VocabularyProvider` (profile title/logline/needs) |
| `GET /api/v1/topics` | `VocabularyProvider` (topic labels) |
| `GET /api/v1/status` | `StatusBadge` (cache-health counts) |
| `GET /api/v1/programs` | Programme catalogue |
| `GET /api/v1/deadlines` | Deadline lookups |

Domain-specific types live in `src/api/types.ts`; typed endpoint helpers in
`src/api/endpoints.ts`. Enveloped list endpoints (`profiles`, `topics`,
`programs`, `deadlines`) return `{ count, results }`.

### Vocabulary rules

- Profile/topic/link/signal **keys pass through unmapped** — the app never
  rewrites backend identifiers.
- Display labels come only from the live `/profiles` and `/topics` payloads
  (theme `VocabularyContext`); unknown keys render their raw key as a safe
  fallback.

## Routes

| Path | Page |
|---|---|
| `/` | Marketing landing (hero, profile cards, national programmes/deadlines) |
| `/search` | Ranked college search with filters, provenance, pagination |
| `/schools/:key` | School record: score, reasons, official links, evidence, gaps, playbook, deadlines, programmes |
| `/?…` legacy | Redirects to `/search?…` preserving query params |
| `*` | Not-found page |

## Project Structure

```
src/
├─ api/             HTTP client, endpoint helpers, mock transport, contracts
│  ├─ client.ts     GET-only fetch + fixture fallback + error mapping
│  ├─ endpoints.ts  Typed wrappers for each /api/v1 endpoint
│  ├─ mock.ts       Fixture-backed transport; 404 for unknown schools
│  ├─ types.ts      Domain types (Match, Fact, Program, Deadline, …)
│  └─ VocabularyContext.tsx  Profile/topic label provider
├─ components/
│  ├─ common/       MockBanner, ErrorBox, Confidence, Markdown
│  ├─ landing/      ProfileCards, HowItWorks, NationalSection
│  ├─ layout/       Header, Footer, ProfileSelect, state badges
│  ├─ school/       ScorePanel, ReasonBars, OfficialLinks, FactsEvidence,
│  │                GapsPanel, PlaybookChecklist, DeadlineList, ProgramList
│  └─ search/       SearchForm, FilterBar, ResultList/Card, Pagination
├─ fixtures/        Mock responses (schools, search, profiles, topics, status)
├─ hooks/           useApi, useDebouncedValue, useMockActive
├─ lib/             format, sort, URL (de)serialization helpers
├─ routes/          LandingPage, SearchPage, SchoolPage, NotFoundPage
├─ styles/          tokens.css, base.css, components.css
└─ test/            Vitest setup (jest-dom)
e2e/                Playwright smoke tests
public/             Static assets (e.g. favicon.svg)
```

## Design Principles

- **GET-only.** No mutating requests exist anywhere in `src/`.
- **Provenance is the product.** Cache hit/miss, fingerprints, staleness, gaps,
  and evidence are rendered — never suppressed.
- **Pass-through keys.** Backend identifiers cross the wire untouched.
- **Accessible & restrained.** Semantic landmarks, focus-visible styles,
  reduced-motion support; Lucide icons only.

## Testing

- **Unit (Vitest + Testing Library):** components, hooks, client transport
  (mock vs. live, fallback + recovery), URL serialization, formatting.
- **E2E (Playwright, Chromium):** landing → search → school-detail journey with
  a GET-only traffic guard, plus the legacy `/?…` redirect. The e2e server runs
  in forced-mock mode for hermetic, dependency-free runs.

---

**SRA** — College discovery for the students the data usually ignores.