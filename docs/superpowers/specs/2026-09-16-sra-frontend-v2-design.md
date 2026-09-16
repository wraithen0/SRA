# SRA Frontend v2 Design Spec

Date: 2026-09-16
Status: Approved for implementation planning

Supersedes the v2 scope of `2026-09-15-sra-frontend-design.md`. The v1 spec's
decisions (GET-only client, Modern SaaS, vocabulary pass-through, mock
transport, provenance-never-hidden) remain normative. This spec adds:

1. A national layer on the search contract (`national_programs`,
   `national_deadlines`, `cache`, `universe_size`, `count`).
2. A marketing/home landing page at `/`, moving the search tool to `/search`.
3. Housekeeping so the repo is lint-clean and router/test warnings are gone.

## Scope

### In scope (v2)

- Extend `SearchResponse` with the README `SearchReport` fields.
- Surface the national layer and cache provenance on `SearchPage`.
- New `LandingPage` at `/` (hero, profile cards, how-it-works, trust strip,
  national deadlines/programmes section).
- Route change: `/` → landing, `/search` → search; legacy `/?…` URLs redirect
  to `/search?…`.
- Header nav update (brand → `/`, "Search" → `/search`).
- Fix 2 lint warnings in `VocabularyContext.tsx`.
- Enable React Router v7 future flags to clear warnings.
- Quiet `act(...)` test warnings where cheap.
- Unit + e2e coverage for all of the above.

### Out of scope (v2)

- Any backend change or new dependency.
- Standalone programmes/deadlines pages (still embedded arrays).
- Auth, SSR, deployment.
- Replacing the existing Modern SaaS visual system.

## Decisions

| Area | Decision | Rationale |
|---|---|---|
| National layer | Optional fields on `SearchResponse`; rendered only when present | Backwards compatible with the current mock and any older sidecar |
| Reuse | `ProgramList` / `DeadlineList` gain an optional `title` prop | National sections reuse established rendering; no new list components |
| Landing data | `LandingPage` fetches `search({...DEFAULT_QUERY, limit: 1})` and renders its national arrays | One code path, exercises the full contract, no new endpoint |
| Routing | `/` redirects to `/search?…` when query params exist | Legacy deep links (`/?profile=…&state=CA`) keep working |
| Provenance | Cache hit/miss + fingerprint + universe size shown on search results | "Provenance is the product" |
| Icons/copy | Lucide only, no emoji; sentence case | Matches v1 |

## Contract changes

`src/api/types.ts` — `SearchResponse` gains optional fields:

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

Fixture `search.ca.first_generation.json` gains:

- `universe_size: 6243`
- `cache: { hit: true, fingerprint: "7f8b9c3" }`
- `national_programs`: 2–3 sample programs (with amounts + deadlines)
- `national_deadlines`: 2–3 sample deadlines

`src/api/mock.ts` empty-result branch gains `universe_size` so callers never
read `undefined` in the empty case.

## SearchPage changes

- Section title uses `count ?? results.length` for the returned-count wording.
- New provenance line when `universe_size`/`cache` present:

  `"{universe_size} schools searched · cache {hit|miss} · {fingerprint}"`

  (fingerprint shown short-form: first 8 characters).
- `National programmes` and `National deadlines` sections rendered from
  `national_programs` / `national_deadlines` when non-empty, using
  `ProgramList` / `DeadlineList` with the `title` prop.

## Landing page

`src/routes/LandingPage.tsx` + `src/components/landing/`:
`ProfileCards.tsx`, `HowItWorks.tsx`, `NationalSection.tsx`.

`LandingPage` behavior:

- If `useSearchParams()` yields any query params, render `<Navigate
  to={{ pathname: "/search", search }} replace />`.
- Otherwise render the marketing page (see design in chat, section B).

Layout, copy, and CTAs follow v1 tokens and the approved in-chat design. All
profile profile keys use the v1 pass-through rules; labels come from
`useVocabulary().profiles`. CTAs: hero `→ /search`, each profile card
`→ /search?profile={key}`.

## Routing

`src/main.tsx`:

```ts
children: [
  { index: true, element: <LandingPage /> },
  { path: "search", element: <SearchPage /> },
  { path: "schools/:key", element: <SchoolPage /> },
  { path: "*", element: <NotFoundPage /> }
]
```

React Router future flags enable `v7_startTransition` and
`v7_relativeSplatPath` on `createBrowserRouter`.

`src/components/layout/Header.tsx`: brand → `/`, nav "Search" → `/search`.
`src/routes/SchoolPage.tsx` + `src/routes/NotFoundPage.tsx`: back links →
`/search`.

## Testing

- `LandingPage.test.tsx`: hero + three profile cards render; national sections
  render from fixtures; a URL with query params redirects to `/search?…`.
- Update `SearchPage`, `SchoolPage`, `App` tests for the `/search` base where
  they hardcode `/`.
- e2e `smoke.spec.ts`: add a landing→search flow; keep the existing
  GET-only + school-detail assertions (update the initial URL to `/search`).

## Verification before completion

Run in order and confirm:

1. `npm run typecheck`
2. `npm run lint` (0 warnings)
3. `npm test`
4. `npm run test:e2e`
5. `npm run build`

## Handshake checklist (v1, still binding)

- [ ] GET-only; no POST helper in `src/`.
- [ ] Profile/topic/link/signal keys pass through unmapped.
- [ ] `gaps`, `stale`, and evidence always rendered.
- [ ] Lucide only, no emoji; headings serif, body sans.