# SRA Frontend Design Spec

Date: 2026-09-15
Status: Approved for implementation planning

## Purpose

A React web client that consumes the SRA backend (`http://localhost:8000` by
default) and renders ranked school matches according to the SRA Integration
Guide. The guide is the contract; this spec defines only the frontend side of
it.

## Scope

### In scope (v1)

- Search results list with score, `why` reason bars, and `gaps`.
- School detail view with all seven rendering rules.
- Filter dropdowns driven by `/api/v1/profiles` and `/api/v1/topics`.
- Cache-health status badge from `/api/v1/status`.
- Mock/fixture transport so the UI is developable and testable without the
  sidecar.
- Vitest unit + component tests and a Playwright smoke test.

### Out of scope (v1)

- All admin `POST` endpoints (`/enrich`, `/api/v1/refresh`, `/build`,
  `/programs/verify`, `/seed/export`, `/seed/import`).
- Live crawling (`live=True`) on the request path.
- Authentication, SSR, hosting/deployment.
- Standalone programmes-only or deadlines-only views.
- Any mutation of backend state from the browser.

## Decisions

| Area | Decision | Rationale |
|---|---|---|
| Stack | React + TypeScript + Vite | Fast dev server; no SSR needed for a localhost API. |
| Data layer | Hand-rolled typed `fetch` client + small `useApi` hook | ~7 GET endpoints; no cache-invalidation pressure yet. Keeps error contract and mock swap explicit. |
| Routing | `react-router-dom`, filters encoded in the URL query string | Search has ~9 params; deep-linkable, back-button-correct results. |
| Mock | Swappable transport inside the API client, selected by `VITE_SRA_MOCK` | No service-worker setup; deterministic fixtures; enables dev fallback. |
| Styling | Hand-written CSS (`tokens.css`, `base.css`, `components.css`) | No dependency; full control over provenance-heavy layout. |
| Visual direction | Modern SaaS (white base, Playfair Display headings, Inter body, `#5EA832` green accent, Lucide icons, no emoji) | Polished, product-focused aesthetic; skill presets fit an aid-comparison tool. |
| Test depth | Full Vitest + Playwright | Component rules and GET-only guarantee both verified. |
| Mock fallback | Visible "MOCK DATA" banner in dev only | Prevents mistaking fixtures for live data. Production never falls back. |

## Module layout

```
E:\SRA\
  package.json, tsconfig.json, vite.config.ts, index.html
  .env.example                     # VITE_SRA_API_BASE, VITE_SRA_MOCK
  src/
    main.tsx                       # router + providers
    App.tsx                        # shell: header, status badge, <Outlet>
    api/
      types.ts                     # TrustedProfile, Match, Institution, Signal,
                                   #   Reason, Fact, Deadline, Program,
                                   #   PlaybookStep, SearchResponse, StatusResponse
      client.ts                    # GET-only fetch wrapper; ApiError; mock dispatch
      endpoints.ts                 # search, school, programs, deadlines,
                                   #   status, profiles, topics (GET only)
      mock.ts                      # fixture transport
    fixtures/
      search.ca.first_generation.json
      school.243744.json
      school.230038.json
      profiles.json
      topics.json
      status.json
    hooks/
      useApi.ts                    # {data,error,loading,refetch}
      useDebouncedValue.ts         # q input -> URL param
    routes/
      SearchPage.tsx               # owns useSearchParams <-> SearchQuery
      SchoolPage.tsx               # /schools/:key
      NotFoundPage.tsx
    components/
      layout/    Header.tsx, StatusBadge.tsx, StaleBadge.tsx, ProfileSelect.tsx
      search/    SearchForm.tsx, FilterBar.tsx, ResultCard.tsx, ResultList.tsx, Pagination.tsx
      school/    SchoolHeader.tsx, ScorePanel.tsx, ReasonBars.tsx,
                 OfficialLinks.tsx, FactsEvidence.tsx, GapsPanel.tsx,
                 PlaybookChecklist.tsx, DeadlineList.tsx, ProgramList.tsx
      common/    Markdown.tsx, Money.tsx, Confidence.tsx, ErrorBox.tsx, MockBanner.tsx
    lib/
      url.ts                       # SearchQuery <-> URLSearchParams codec
      sort.ts                      # deadline sort by date_iso, is_past dim
      format.ts                    # date_iso, avg_net_price null handling
    styles/ tokens.css, base.css, components.css
```

## API client contract

`src/api/client.ts`:

- **GET-only.** `endpoints.ts` exposes only GET functions. There is no POST
  helper in the module. Admin routes are absent from the codebase entirely, so
  the UI cannot call them.
- Base URL from `VITE_SRA_API_BASE`, default `http://localhost:8000`.
- `ApiError { status: number; detail: string }`. Non-2xx responses parse the
  `{ "detail": ... }` body.
- `GET /api/v1/schools/{key}` returning 404 throws a distinct
  `UnknownSchoolError` (subclass of `ApiError`) so `SchoolPage` renders a
  dedicated not-found view rather than a generic error.
- 500 responses surface `detail` through `ErrorBox`.
- **Vocabulary is pass-through.** Profile keys, topic keys, link keys, and
  signal keys travel network -> props -> DOM unmapped. Human labels come from
  `/api/v1/profiles` and `/api/v1/topics`; when a label is missing the raw key
  is displayed. Labels are never invented.
- **Mock dispatch.** When `VITE_SRA_MOCK=1`, all calls route to `mock.ts`,
  which resolves the same response shapes from `fixtures/`. In development,
  a network failure against a real base URL falls back to fixtures and sets a
  global "mock active" flag that renders `MockBanner`. Production builds
  (`import.meta.env.PROD`) never fall back and never render the banner.

### Endpoints used

| Function | Method + path |
|---|---|
| `search(query)` | `GET /api/v1/search` |
| `school(key, profile)` | `GET /api/v1/schools/{key}` |
| `programs(query)` | `GET /api/v1/programs` |
| `deadlines(unitid)` | `GET /api/v1/deadlines` |
| `status()` | `GET /api/v1/status` |
| `profiles()` | `GET /api/v1/profiles` |
| `topics()` | `GET /api/v1/topics` |

Note: `programs()` and `deadlines()` exist in the API layer for completeness of
the documented contract, but v1 renders programmes and deadlines only as
embedded arrays inside a school match (`programs[]`, `deadlines[]`). The
standalone endpoints are not surfaced as separate views in v1.

## Routing and URL state

`react-router-dom`, `BrowserRouter`.

| Route | Component | Notes |
|---|---|---|
| `/` | `SearchPage` | Filters live in the URL query string. |
| `/schools/:key` | `SchoolPage` | `key` = unitid, OPEID, or name. |
| `*` | `NotFoundPage` | |

`SearchQuery` is the single source of truth, encoded by `lib/url.ts`:

```
profile, q, state, control, level, stem_only, max_net_price, require, limit, offset
```

- Absent params are omitted from the URL; defaults apply on read.
- Defaults: `profile=first_generation`, `limit=10`, `offset=0`. Other params
  unset.
- Numeric params (`max_net_price`, `limit`, `offset`) parse to number; invalid
  values fall back to the default rather than throwing.
- The top-level profile selector (`ProfileSelect`) and the search-page profile
  filter read and write the same `profile` param.

## Rendering rules mapping

The guide's seven rules are normative. Each maps to exactly one component.

| # | Guide rule | Component(s) | Behavior |
|---|---|---|---|
| 1 | Score + why -> header + reason bars | `ScorePanel`, `ReasonBars` | Header text: `"{score}/100 for {profileLabel}"`. Bars sorted by `why[].weight` descending; bar width = `value`; each bar shows `label` and `value`. |
| 2 | `links` -> Official links | `OfficialLinks` | Iterate `links` key -> URL. Label from `/api/v1/topics`, raw key fallback. Render as external anchors. |
| 3 | `facts` -> evidence list | `FactsEvidence` | Show `value`, verbatim `evidence` quote, source `url`, and `topic`. When `extractor === "llm"`, render a "model-inferred — verify on the page" tag. Show `confidence`. |
| 4 | `gaps` -> "Not verified yet" | `GapsPanel` | Always rendered, even when `gaps` is empty (empty state: "Nothing flagged"). Never collapsed or hidden. |
| 5 | `playbook` -> ordered checklist | `PlaybookChecklist` | Sort by `order`. `detail` rendered via `Markdown` (sanitized; only `[label](url)` links). `status === "verify"` gets warning (⚠️) styling; `status === "action"` gets normal styling. |
| 6 | `deadlines` -> sort, dim past | `DeadlineList` | Sort ascending by `date_iso`. `is_past` rows dimmed. Show `label`, `date_iso`, `days_left`, `category`, `url`. |
| 7 | `stale` -> freshness badge | `StaleBadge` | When a match or school has `stale === true`, show "some evidence is past its freshness window". Per-fact `stale` flags also render in `FactsEvidence`. |

Additional provenance requirements:

- `FactsEvidence` renders `observed_at` and `expires_at` when present.
- `StatusBadge` (from `/api/v1/status`) shows cache health in the header.
- `last_verified` renders in `SchoolHeader`.
- Provenance (gaps, stale, evidence, confidence, extractor) is never hidden.

## Visual direction (Modern SaaS)

Applies the modern-saas design system to the working views (search + school
detail). Marketing sections (hero, logo strip, pricing, testimonials, footer)
are **out of scope**; the app has no sign-up flow.

### Tokens

`src/styles/tokens.css` defines every value as a CSS custom property. No
hardcoded colors or sizes in component styles.

Runtime dependencies beyond React: `react-router-dom` and `lucide-react`
(icons). No CSS framework.

```css
--bg-page:#FFFFFF; --bg-subtle:#F8F8F8; --bg-muted:#F5F5F4; --bg-dark:#111111;
--bg-pattern: /* diagonal crosshatch SVG data URI */;
--text-primary:#111111; --text-secondary:#666666; --text-muted:#999999;
--border:#E8E8E8; --border-dashed:rgba(17,17,17,0.18);
--accent:#5EA832; --accent-hover:#4D8E28; --accent-light:#EEF7E6; --accent-fg:#FFFFFF;
--chart-bar:#E8D87A; --chart-area:rgba(232,216,122,0.25);
--font-display:'Playfair Display',Georgia,serif;
--font-body:'Inter',system-ui,sans-serif;
--radius-sm:6px; --radius-md:10px; --radius-lg:14px; --radius-xl:20px; --radius-pill:999px;
--shadow-sm/md/lg/float; --max-w:1200px;
```

Hard rules:

- **Headings serif, everything else sans. Never mixed.** H1/H2 and section
  titles use `--font-display`; nav, body, cards, buttons, labels, and captions
  use `--font-body`.
- **Data visualization uses `--chart-bar` (warm yellow), never the green
  accent.** Reason bars are data, so they are `--chart-bar`.
- **Lucide icons only, no emoji.** The guide's ️ for `status:"verify"` and
  staleness is rendered with the `AlertTriangle` Lucide icon. Sizes: 16px
  inline, 20px default, 24px feature icons.
- Google Fonts loaded via `<link>` in `index.html`: Playfair Display 700/800,
  Inter 400/500/600.

### App shell

- **Navbar** (`Header.tsx`): sticky, white, bottom border fades in when
  `scrollY > 40`. Layout `[SRA logo] → [Search, Profiles, Status] → [status
  badge]`. No dark CTA button (no sign-up exists).
- Decorative **dashed vertical lines** frame the `--max-w` content column.
- **Cards** (`ResultCard`, feature cards): white, `1px solid var(--border)`,
  `--radius-lg`, `--shadow-sm`; hover transitions border-color to `--accent`,
  no lift.

### Section treatment

| Surface | Treatment |
|---|---|
| Score + `why` | Hero-style panel: Playfair score, "for {profileLabel}" subtitle, reason bars in `--chart-bar`. |
| `links` | Feature-card grid, topic labels via `/topics`, Lucide `ArrowUpRight`. |
| `facts` | Evidence list on `--bg-muted` with no border; `extractor:"llm"` gets an `--accent-light` "Model-inferred — verify on the page" badge. |
| `gaps` | "Not verified yet" on `--bg-pattern` crosshatch. Always rendered. |
| `playbook` | Numbered (order carries real sequence): Playfair numerals, Inter detail, sanitized Markdown. `status:"verify"` → `AlertTriangle`. |
| `deadlines` | On `--bg-pattern`; sorted by `date_iso`; `is_past` dimmed to `--text-muted`. |
| `stale` | `--accent-light` badge near the header plus per-fact marker. |

### Motion

Restrained, one orchestrated moment. Scroll-reveal via `IntersectionObserver`
adding `.visible`, staggered `0/80/160ms`. Reason bars animate width
`0 → value` on reveal. Buttons `translateY(-2px)` + shadow on hover. All motion
is disabled under `@media (prefers-reduced-motion: reduce)`.

### Copy

Sentence case, plain verbs, action names constant through the flow. Empty
results: "No schools matched these filters." with a "Clear filters" invite.
Unknown school: "No record for `{key}`." with a "Back to search" link. Errors
state what happened without apologizing.

## Error handling

| Condition | UI |
|---|---|
| 404 on `/schools/{key}` | `SchoolPage` not-found view with the `detail` message and a link back to search. |
| 404 on other GETs | `ErrorBox` with `detail`. |
| 500 / network error | `ErrorBox` with `detail` (or a generic message when no body). |
| Dev network failure with mock enabled | Fallback to fixtures + `MockBanner`. |
| Empty results | `ResultList` empty state ("No schools matched these filters"). |

## Testing

### Vitest (jsdom) + Testing Library

Unit:

- `lib/url.ts` — `SearchQuery` <-> params round-trip; defaults; invalid numeric
  fallback.
- `lib/sort.ts` — deadline ascending sort; `is_past` preserved.
- `api/client.ts` — 404 -> `UnknownSchoolError`; 500 -> `ApiError` with
  `detail`; mock dispatch when `VITE_SRA_MOCK=1`; no fallback when `PROD`.

Component (asserting each rendering rule against fixtures):

- `ScorePanel` header reads `"{score}/100 for {profileLabel}"`; `ReasonBars`
  sorted by weight desc.
- `OfficialLinks` uses topic labels, falls back to raw key for unknown keys.
- `FactsEvidence` shows the evidence quote + source url; an `extractor:"llm"`
  fact shows the model-inferred tag.
- `GapsPanel` renders on empty `gaps`.
- `PlaybookChecklist` is ordered; a `status:"verify"` step gets warning styling;
  `Markdown` renders `[label](url)` links and strips raw HTML.
- `DeadlineList` is sorted ascending; `is_past` rows have the dimmed class.
- `StaleBadge` appears when `stale === true`.

### Playwright (mock mode)

Single smoke test:

1. Load `/`, confirm results render with score and reason bars.
2. Change a filter, confirm the URL updates and results re-render.
3. Click a result through to `/schools/:key`, confirm all seven rule sections
   are present.
4. Assert every request issued during the run is GET — no `POST` ever reaches
   the network.

## Verification before completion

Run, in order, and confirm output:

1. `npm run typecheck` (`tsc --noEmit`)
2. `npm run lint`
3. `npm run test` (Vitest)
4. `npm run test:e2e` (Playwright, mock mode)
5. `npm run build`

## Handshake checklist (from the guide)

- [ ] Frontend calls only GET endpoints; admin `POST`s never reach the browser.
- [ ] Profile keys, topic keys, and link keys pass through unmapped.
- [ ] `gaps`, `stale`, and evidence are always rendered.