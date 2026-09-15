# SRA Frontend Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a React + TypeScript web client that consumes the SRA backend's GET endpoints and renders ranked school matches per the SRA Integration Guide's seven rendering rules, in a Modern SaaS visual style.

**Architecture:** Vite/React SPA. A GET-only typed `fetch` client with a swappable fixture transport feeds small `useApi` hooks. Search filters live in the URL query string via `react-router-dom`. School detail is one component per rendering rule. Backend vocabulary (profile/topic/link/signal keys) passes through unmapped; labels come from `/profiles` and `/topics`.

**Tech Stack:** React 18, TypeScript 5.6, Vite 5, react-router-dom 6, lucide-react, Vitest 2 + Testing Library (jsdom), Playwright.

**Spec:** `docs/superpowers/specs/2026-09-15-sra-frontend-design.md`

## Global Constraints

- **GET-only.** The API module exposes no POST helper; admin endpoints must not appear anywhere in `src/`.
- **Vocabulary is pass-through.** Profile, topic, link, and signal keys travel network → props → DOM unmapped. Missing label falls back to the raw key, never invented.
- **Provenance never hidden:** `gaps`, `stale`, `evidence`, `confidence`, `extractor` always render.
- **Guide rule 4:** `GapsPanel` always renders, even when `gaps` is empty.
- **Visual system:** all values are CSS custom properties in `src/styles/tokens.css`; no hardcoded colors/sizes in component styles. Headings serif (`--font-display`), everything else sans (`--font-body`) — never mixed. Data viz uses `--chart-bar` (`#E8D87A`), never `--accent`. **Lucide icons only — no emoji.**
- **Profiles (exact keys):** `first_generation`, `student_with_disability`, `international_stem`.
- **Environment:** `VITE_SRA_API_BASE` (default `http://localhost:8000`), `VITE_SRA_MOCK=1`.
- **Motion** disabled under `@media (prefers-reduced-motion: reduce)`.

---

### Task 1: Scaffold the Vite project

**Files:**
- Create: `package.json`, `tsconfig.json`, `vite.config.ts`, `index.html`, `eslint.config.js`, `.gitignore`, `.env.example`
- Create: `src/main.tsx`, `src/App.tsx`, `src/vite-env.d.ts`, `src/test/setup.ts`, `src/App.test.tsx`

**Interfaces:**
- Consumes: nothing.
- Produces: a working dev/test/build toolchain with scripts `dev`, `build`, `lint`, `typecheck`, `test`, `test:e2e`.

- [ ] **Step 1: Write `package.json`**

```json
{
  "name": "sra-web",
  "private": true,
  "version": "0.1.0",
  "type": "module",
  "scripts": {
    "dev": "vite",
    "build": "tsc --noEmit && vite build",
    "preview": "vite preview",
    "lint": "eslint .",
    "typecheck": "tsc --noEmit",
    "test": "vitest run",
    "test:watch": "vitest",
    "test:e2e": "playwright test"
  },
  "dependencies": {
    "lucide-react": "^0.460.0",
    "react": "^18.3.1",
    "react-dom": "^18.3.1",
    "react-router-dom": "^6.28.0"
  },
  "devDependencies": {
    "@eslint/js": "^9.14.0",
    "@playwright/test": "^1.48.2",
    "@testing-library/dom": "^10.4.0",
    "@testing-library/jest-dom": "^6.6.3",
    "@testing-library/react": "^16.0.1",
    "@testing-library/user-event": "^14.5.2",
    "@types/node": "^22.9.0",
    "@types/react": "^18.3.12",
    "@types/react-dom": "^18.3.1",
    "@vitejs/plugin-react": "^4.3.3",
    "eslint": "^9.14.0",
    "eslint-plugin-react-hooks": "^5.0.0",
    "eslint-plugin-react-refresh": "^0.4.14",
    "globals": "^15.12.0",
    "jsdom": "^25.0.1",
    "typescript": "~5.6.3",
    "typescript-eslint": "^8.13.0",
    "vite": "^5.4.10",
    "vitest": "^2.1.4"
  }
}
```

- [ ] **Step 2: Write `tsconfig.json`**

```json
{
  "compilerOptions": {
    "target": "ES2022",
    "useDefineForClassFields": true,
    "lib": ["ES2022", "DOM", "DOM.Iterable"],
    "module": "ESNext",
    "skipLibCheck": true,
    "moduleResolution": "bundler",
    "resolveJsonModule": true,
    "isolatedModules": true,
    "moduleDetection": "force",
    "noEmit": true,
    "jsx": "react-jsx",
    "strict": true,
    "noUnusedLocals": true,
    "noUnusedParameters": true,
    "noFallthroughCasesInSwitch": true,
    "types": ["vitest/globals", "@testing-library/jest-dom", "node"]
  },
  "include": ["src", "vite.config.ts", "e2e", "playwright.config.ts"]
}
```

- [ ] **Step 3: Write `vite.config.ts`**

```ts
/// <reference types="vitest/config" />
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  test: {
    environment: "jsdom",
    globals: true,
    setupFiles: ["./src/test/setup.ts"],
    css: false,
  },
});
```

- [ ] **Step 4: Write `index.html`**

```html
<!doctype html>
<html lang="en">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <link rel="preconnect" href="https://fonts.googleapis.com" />
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin />
    <link
      href="https://fonts.googleapis.com/css2?family=Playfair+Display:wght@700;800&family=Inter:wght@400;500;600&display=swap"
      rel="stylesheet"
    />
    <title>SRA — School Record Archive</title>
  </head>
  <body>
    <div id="root"></div>
    <script type="module" src="/src/main.tsx"></script>
  </body>
</html>
```

- [ ] **Step 5: Write `eslint.config.js`, `.gitignore`, `.env.example`**

```js
import js from "@eslint/js";
import globals from "globals";
import reactHooks from "eslint-plugin-react-hooks";
import reactRefresh from "eslint-plugin-react-refresh";
import tseslint from "typescript-eslint";

export default tseslint.config(
  { ignores: ["dist", "playwright-report", "test-results"] },
  {
    files: ["**/*.{ts,tsx}"],
    extends: [js.configs.recommended, ...tseslint.configs.recommended],
    languageOptions: { ecmaVersion: 2022, globals: globals.browser },
    plugins: { "react-hooks": reactHooks, "react-refresh": reactRefresh },
    rules: {
      ...reactHooks.configs.recommended.rules,
      "react-refresh/only-export-components": "off"
    }
  }
);
```

`.gitignore`:

```
node_modules
dist
.env
.env.local
playwright-report
test-results
```

`.env.example`:

```
VITE_SRA_API_BASE=http://localhost:8000
VITE_SRA_MOCK=0
```

- [ ] **Step 6: Write `src/vite-env.d.ts` and `src/test/setup.ts`**

`src/vite-env.d.ts`:

```ts
/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_SRA_API_BASE?: string;
  readonly VITE_SRA_MOCK?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
```

`src/test/setup.ts`:

```ts
import "@testing-library/jest-dom/vitest";
```

- [ ] **Step 7: Write the failing test `src/App.test.tsx`**

```tsx
import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import App from "./App";

it("renders the app shell", () => {
  render(
    <MemoryRouter>
      <App />
    </MemoryRouter>
  );
  expect(screen.getByRole("banner")).toBeInTheDocument();
});
```

- [ ] **Step 8: Write minimal `src/App.tsx` and `src/main.tsx`**

`src/App.tsx`:

```tsx
import { Outlet } from "react-router-dom";

export default function App() {
  return (
    <>
      <header role="banner">
        <a href="/">SRA</a>
      </header>
      <main>
        <Outlet />
      </main>
    </>
  );
}
```

`src/main.tsx`:

```tsx
import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { RouterProvider, createBrowserRouter } from "react-router-dom";
import App from "./App";

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <RouterProvider
      router={createBrowserRouter([
        {
          path: "/",
          element: <App />,
          children: [{ index: true, element: <div>Search</div> }]
        }
      ])}
    />
  </StrictMode>
);
```

- [ ] **Step 9: Install and run tests**

Run: `npm install`
Then: `npm run test`
Expected: install succeeds; 1 test passes.

- [ ] **Step 10: Commit**

```bash
git add package.json package-lock.json tsconfig.json vite.config.ts index.html eslint.config.js .gitignore .env.example src
git commit -m "chore: scaffold Vite React TypeScript project"
```

---

### Task 2: Domain types

**Files:**
- Create: `src/api/types.ts`

**Interfaces:**
- Consumes: nothing.
- Produces: `ProfileKey`, `Institution`, `Reason`, `Fact`, `Deadline`, `Program`, `PlaybookStatus`, `PlaybookStep`, `Match`, `SearchResponse`, `SearchQuery`, `StatusResponse`, `ProfileOption`, `TopicOption`, `ProfilesResponse`, `TopicsResponse`. Every later task imports from here.

- [ ] **Step 1: Write `src/api/types.ts`**

```ts
export type ProfileKey =
  | "first_generation"
  | "student_with_disability"
  | "international_stem";

export interface Institution {
  unitid: number;
  name: string;
  city: string | null;
  state_abbr: string | null;
  control: string | null;
  url_homepage: string | null;
  avg_net_price: number | null;
  [key: string]: unknown;
}

export interface Reason {
  signal: string;
  label: string;
  value: number;
  weight: number;
}

export interface Fact {
  topic: string;
  value: string;
  url: string | null;
  extractor: "rule" | "llm";
  confidence: number;
  evidence: string | null;
  observed_at: string | null;
  expires_at: string | null;
  stale: boolean;
}

export interface Deadline {
  label: string;
  date_iso: string;
  category: string;
  url: string | null;
  is_past: boolean;
  days_left: number;
}

export interface Program {
  program_id: string;
  name: string;
  official_url: string | null;
  amount_text: string | null;
  deadlines: Deadline[];
}

export type PlaybookStatus = "action" | "verify";

export interface PlaybookStep {
  order: number;
  title: string;
  detail: string;
  url: string | null;
  deadline: string | null;
  status: PlaybookStatus;
}

export interface Match {
  institution: Institution;
  score: number;
  signals: Record<string, number>;
  why: Reason[];
  needs_covered: string[];
  links: Record<string, string>;
  facts: Fact[];
  deadlines: Deadline[];
  programs: Program[];
  playbook: PlaybookStep[];
  gaps: string[];
  last_verified: string | null;
  stale: boolean;
}

export interface SearchResponse {
  results: Match[];
  total?: number;
  limit?: number;
  offset?: number;
}

export interface SearchQuery {
  profile: ProfileKey;
  q?: string;
  state?: string;
  control?: string;
  level?: string;
  stem_only?: boolean;
  max_net_price?: number;
  require?: string;
  limit: number;
  offset: number;
}

export interface StatusResponse {
  ok?: boolean;
  schools?: number;
  programs?: number;
  stale?: number;
  [key: string]: unknown;
}

export interface ProfileOption {
  key: string;
  label: string;
}

export interface TopicOption {
  key: string;
  label: string;
}

export interface ProfilesResponse {
  profiles: ProfileOption[];
}

export interface TopicsResponse {
  topics: TopicOption[];
}
```

- [ ] **Step 2: Verify it typechecks**

Run: `npm run typecheck`
Expected: PASS, no errors.

- [ ] **Step 3: Commit**

```bash
git add src/api/types.ts
git commit -m "feat: add SRA domain types"
```

---

### Task 3: Fixtures

**Files:**
- Create: `src/fixtures/school.243744.json`, `src/fixtures/school.230038.json`, `src/fixtures/search.ca.first_generation.json`, `src/fixtures/profiles.json`, `src/fixtures/topics.json`, `src/fixtures/status.json`

**Interfaces:**
- Consumes: `src/api/types.ts` shapes.
- Produces: fixture JSON consumed by `src/api/mock.ts`.

`243744` exercises every field and every rule: `stale:false`, a `status:"verify"` playbook step, an `extractor:"llm"` fact with `observed_at`/`expires_at`, and mixed past/future deadlines. `230038` exercises `stale:true` and an empty `gaps:[]`.

- [ ] **Step 1: Write `src/fixtures/school.243744.json`**

```json
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
  "signals": {
    "aid_generosity": 0.62,
    "need_coverage": 0.42,
    "first_gen_support": 0.55,
    "net_price_affordability": 0.31
  },
  "why": [
    { "signal": "aid_generosity", "label": "Grants and net-price generosity", "value": 0.62, "weight": 22 },
    { "signal": "first_gen_support", "label": "First-generation support programs", "value": 0.55, "weight": 20 },
    { "signal": "need_coverage", "label": "Share of need met", "value": 0.42, "weight": 18 },
    { "signal": "net_price_affordability", "label": "Affordability after aid", "value": 0.31, "weight": 15 }
  ],
  "needs_covered": ["financial_aid_office", "first_gen_program", "net_price_calculator"],
  "links": {
    "home": "https://stanford.edu/",
    "financial_aid": "https://financialaid.stanford.edu/",
    "net_price_calculator": "https://financialaid.stanford.edu/undergrad/aid/net-price-calculator.html"
  },
  "facts": [
    {
      "topic": "institutional_grant",
      "value": "Stanford meets 100% of demonstrated need with no-loan packages.",
      "url": "https://financialaid.stanford.edu/undergrad/aid/",
      "extractor": "rule",
      "confidence": 0.95,
      "evidence": "Stanford meets the full need of all admitted students who apply for aid.",
      "observed_at": "2026-08-02T10:00:00Z",
      "expires_at": "2027-08-02T10:00:00Z",
      "stale": false
    },
    {
      "topic": "first_gen_program",
      "value": "Dedicated first-generation support office and pre-orientation program.",
      "url": "https://firstgen.stanford.edu/",
      "extractor": "llm",
      "confidence": 0.61,
      "evidence": "Our office supports students who are the first in their family to attend college.",
      "observed_at": "2026-05-11T10:00:00Z",
      "expires_at": "2027-05-11T10:00:00Z",
      "stale": false
    }
  ],
  "deadlines": [
    { "label": "Restrictive Early Action", "date_iso": "2026-11-01", "category": "application", "url": "https://admission.stanford.edu/apply/", "is_past": false, "days_left": 47 },
    { "label": "Regular Decision", "date_iso": "2027-01-05", "category": "application", "url": "https://admission.stanford.edu/apply/", "is_past": false, "days_left": 112 },
    { "label": "CSS Profile priority filing", "date_iso": "2026-03-15", "category": "financial_aid", "url": "https://financialaid.stanford.edu/", "is_past": true, "days_left": -137 }
  ],
  "programs": [
    {
      "program_id": "stanford-knight-hennessy",
      "name": "Knight-Hennessy Scholars",
      "official_url": "https://knight-hennessy.stanford.edu/",
      "amount_text": "Full funding including tuition and stipend",
      "deadlines": [
        { "label": "Knight-Hennessy deadline", "date_iso": "2026-10-08", "category": "program", "url": "https://knight-hennessy.stanford.edu/", "is_past": false, "days_left": 23 }
      ]
    }
  ],
  "playbook": [
    {
      "order": 1,
      "title": "Create your Federal Student Aid (FSA) ID",
      "detail": "You need an FSA ID before anything else. It takes about 10 minutes and both the student and a parent may need one.",
      "url": "https://studentaid.gov/fsa-id/",
      "deadline": "2026-10-01",
      "status": "action"
    },
    {
      "order": 2,
      "title": "File the FAFSA",
      "detail": "Add Stanford with the federal school code. [Look up Stanford's code](https://studentaid.gov/), then file.",
      "url": "https://studentaid.gov/h/apply-for-aid/fafsa",
      "deadline": "2027-01-05",
      "status": "action"
    },
    {
      "order": 3,
      "title": "Confirm the California state aid deadline",
      "detail": "State aid rules change yearly and we could not verify this year's date for this school.",
      "url": null,
      "deadline": null,
      "status": "verify"
    }
  ],
  "gaps": ["FAFSA federal school code", "State aid deadline for 2027", "Average debt at graduation"],
  "last_verified": "2026-09-15T08:30:00Z",
  "stale": false
}
```

- [ ] **Step 2: Write `src/fixtures/school.230038.json`**

```json
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
    { "signal": "aid_generosity", "label": "Grants and net-price generosity", "value": 0.71, "weight": 22 },
    { "signal": "need_coverage", "label": "Share of need met", "value": 0.66, "weight": 18 }
  ],
  "needs_covered": ["financial_aid_office"],
  "links": { "home": "https://example.edu/" },
  "facts": [
    {
      "topic": "institutional_grant",
      "value": "Need-based grant program for in-state students.",
      "url": "https://example.edu/aid",
      "extractor": "rule",
      "confidence": 0.88,
      "evidence": "Awards range from $2,000 to $12,000 annually.",
      "observed_at": "2024-01-10T10:00:00Z",
      "expires_at": "2025-01-10T10:00:00Z",
      "stale": true
    }
  ],
  "deadlines": [],
  "programs": [],
  "playbook": [
    {
      "order": 1,
      "title": "File the FAFSA",
      "detail": "File as early as possible.",
      "url": "https://studentaid.gov/h/apply-for-aid/fafsa",
      "deadline": "2027-02-01",
      "status": "action"
    }
  ],
  "gaps": [],
  "last_verified": "2026-09-14T12:00:00Z",
  "stale": true
}
```

- [ ] **Step 3: Write `src/fixtures/search.ca.first_generation.json`**

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
  "limit": 10,
  "offset": 0
}
```

- [ ] **Step 4: Write `src/fixtures/profiles.json`, `src/fixtures/topics.json`, `src/fixtures/status.json`**

`src/fixtures/profiles.json`:

```json
{
  "profiles": [
    { "key": "first_generation", "label": "First-generation student" },
    { "key": "student_with_disability", "label": "Student with a disability" },
    { "key": "international_stem", "label": "International STEM student" }
  ]
}
```

`src/fixtures/topics.json`:

```json
{
  "topics": [
    { "key": "home", "label": "Homepage" },
    { "key": "financial_aid", "label": "Financial aid office" },
    { "key": "net_price_calculator", "label": "Net price calculator" },
    { "key": "institutional_grant", "label": "Institutional grant" },
    { "key": "first_gen_program", "label": "First-generation program" },
    { "key": "aid_generosity", "label": "Grants and net-price generosity" },
    { "key": "need_coverage", "label": "Share of need met" },
    { "key": "first_gen_support", "label": "First-generation support programs" },
    { "key": "net_price_affordability", "label": "Affordability after aid" }
  ]
}
```

`src/fixtures/status.json`:

```json
{
  "ok": true,
  "schools": 6243,
  "programs": 75,
  "stale": 41
}
```

- [ ] **Step 5: Verify JSON parses**

Run: `node -e "['243744','230038'].forEach(u=>require('./src/fixtures/school.'+u+'.json'));['search.ca.first_generation','profiles','topics','status'].forEach(f=>require('./src/fixtures/'+f+'.json'));console.log('ok')"`
Expected: prints `ok`.

- [ ] **Step 6: Commit**

```bash
git add src/fixtures
git commit -m "feat: add SRA fixtures covering all rendering rules"
```

---

### Task 4: API client, endpoints, and mock transport

**Files:**
- Create: `src/api/client.ts`, `src/api/mock.ts`, `src/api/endpoints.ts`
- Test: `src/api/client.test.ts`

**Interfaces:**
- Consumes: `types.ts`.
- Produces:
  - `class ApiError extends Error { status: number; detail: string }`
  - `class UnknownSchoolError extends ApiError`
  - `isMockActive(): boolean`, `resetMockState(): void`, `resolveConfig(): { baseUrl: string; mock: boolean }`
  - `buildQuery(params: Record<string, unknown>): string`
  - `request<T>(path: string, params?: Record<string, unknown>): Promise<T>`
  - endpoints: `search(q: SearchQuery): Promise<SearchResponse>`, `school(key: string, profile: ProfileKey): Promise<Match>`, `programs(q?: Record<string, unknown>): Promise<unknown>`, `deadlines(unitid: number): Promise<unknown>`, `status(): Promise<StatusResponse>`, `profiles(): Promise<ProfilesResponse>`, `topics(): Promise<TopicsResponse>`

- [ ] **Step 1: Write the failing test `src/api/client.test.ts`**

```ts
import { afterEach, describe, expect, it, vi } from "vitest";
import {
  ApiError,
  UnknownSchoolError,
  buildQuery,
  isMockActive,
  request,
  resetMockState
} from "./client";

afterEach(() => {
  vi.unstubAllGlobals();
  vi.unstubAllEnvs();
  resetMockState();
});

describe("buildQuery", () => {
  it("omits undefined and empty values and encodes the rest", () => {
    expect(buildQuery({ profile: "first_generation", state: "CA", q: undefined })).toBe(
      "?profile=first_generation&state=CA"
    );
  });

  it("serializes booleans and numbers", () => {
    expect(buildQuery({ stem_only: true, limit: 10 })).toBe("?stem_only=true&limit=10");
  });

  it("returns an empty string when there is nothing to send", () => {
    expect(buildQuery({})).toBe("");
  });
});

describe("request", () => {
  it("throws UnknownSchoolError on a 404 for a school path", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        new Response(JSON.stringify({ detail: "unknown school" }), {
          status: 404,
          headers: { "content-type": "application/json" }
        })
      )
    );
    await expect(request("/api/v1/schools/nope")).rejects.toBeInstanceOf(UnknownSchoolError);
  });

  it("throws ApiError carrying the detail on a 500", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        new Response(JSON.stringify({ detail: "boom" }), {
          status: 500,
          headers: { "content-type": "application/json" }
        })
      )
    );
    const err = (await request("/api/v1/status").catch((e) => e)) as ApiError;
    expect(err).toBeInstanceOf(ApiError);
    expect(err.status).toBe(500);
    expect(err.detail).toBe("boom");
  });

  it("uses the mock transport when VITE_SRA_MOCK is 1", async () => {
    vi.stubEnv("VITE_SRA_MOCK", "1");
    const fetchSpy = vi.fn();
    vi.stubGlobal("fetch", fetchSpy);
    const status = (await request("/api/v1/status")) as { schools: number };
    expect(fetchSpy).not.toHaveBeenCalled();
    expect(status.schools).toBe(6243);
    expect(isMockActive()).toBe(true);
  });

  it("falls back to fixtures on a network error in dev", async () => {
    vi.stubEnv("VITE_SRA_MOCK", "0");
    vi.stubEnv("PROD", false);
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new TypeError("network down")));
    const status = (await request("/api/v1/status")) as { schools: number };
    expect(status.schools).toBe(6243);
    expect(isMockActive()).toBe(true);
  });

  it("does not fall back in production builds", async () => {
    vi.stubEnv("VITE_SRA_MOCK", "0");
    vi.stubEnv("PROD", true);
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new TypeError("network down")));
    await expect(request("/api/v1/status")).rejects.toBeInstanceOf(TypeError);
  });
});
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `npx vitest run src/api/client.test.ts`
Expected: FAIL — cannot resolve `./client`.

- [ ] **Step 3: Write `src/api/mock.ts`**

```ts
import school243744 from "../fixtures/school.243744.json";
import school230038 from "../fixtures/school.230038.json";
import searchCa from "../fixtures/search.ca.first_generation.json";
import profilesFixture from "../fixtures/profiles.json";
import topicsFixture from "../fixtures/topics.json";
import statusFixture from "../fixtures/status.json";

const schools: Record<string, unknown> = {
  "243744": school243744,
  "230038": school230038,
  Stanford: school243744,
  "Stanford University": school243744
};

export function mockRequest<T>(path: string, params: Record<string, unknown> = {}): Promise<T> {
  const rawPath = path.split("?")[0];

  if (rawPath === "/api/v1/search") {
    const state = String(params.state ?? "CA").toUpperCase();
    const profile = String(params.profile ?? "first_generation");
    if (state === "CA" && profile === "first_generation") {
      return Promise.resolve(searchCa as unknown as T);
    }
    return Promise.resolve({ results: [], total: 0, limit: 10, offset: 0 } as unknown as T);
  }

  if (rawPath.startsWith("/api/v1/schools/")) {
    const key = decodeURIComponent(rawPath.slice("/api/v1/schools/".length));
    const found = schools[key];
    if (!found) return Promise.reject(new Error(`__mock_404__${key}`));
    return Promise.resolve(found as unknown as T);
  }

  if (rawPath === "/api/v1/programs") {
    return Promise.resolve({ programs: [] } as unknown as T);
  }

  if (rawPath === "/api/v1/deadlines") {
    const unitid = String(params.unitid ?? "243744");
    const found = schools[unitid] as { deadlines?: unknown[] } | undefined;
    return Promise.resolve({ deadlines: found?.deadlines ?? [] } as unknown as T);
  }

  if (rawPath === "/api/v1/status") {
    return Promise.resolve(statusFixture as unknown as T);
  }

  if (rawPath === "/api/v1/profiles") {
    return Promise.resolve(profilesFixture as unknown as T);
  }

  if (rawPath === "/api/v1/topics") {
    return Promise.resolve(topicsFixture as unknown as T);
  }

  return Promise.reject(new Error(`__mock_unhandled__${rawPath}`));
}
```

- [ ] **Step 4: Write `src/api/client.ts`**

```ts
import { mockRequest } from "./mock";

export class ApiError extends Error {
  status: number;
  detail: string;

  constructor(status: number, detail: string) {
    super(detail);
    this.name = "ApiError";
    this.status = status;
    this.detail = detail;
  }
}

export class UnknownSchoolError extends ApiError {
  constructor(detail: string) {
    super(404, detail);
    this.name = "UnknownSchoolError";
  }
}

let mockActive = false;

export function isMockActive(): boolean {
  return mockActive;
}

export function resetMockState(): void {
  mockActive = false;
}

export function resolveConfig(): { baseUrl: string; mock: boolean } {
  return {
    baseUrl: import.meta.env.VITE_SRA_API_BASE ?? "http://localhost:8000",
    mock: import.meta.env.VITE_SRA_MOCK === "1"
  };
}

export function buildQuery(params: Record<string, unknown>): string {
  const search = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value === undefined || value === null || value === "") continue;
    search.set(key, String(value));
  }
  const qs = search.toString();
  return qs ? `?${qs}` : "";
}

async function readDetail(res: Response): Promise<string> {
  try {
    const body = (await res.json()) as { detail?: unknown };
    if (typeof body.detail === "string") return body.detail;
  } catch {
    return res.statusText || "Request failed";
  }
  return res.statusText || "Request failed";
}

function toApiError(err: Error, path: string): Error {
  if (err.message.startsWith("__mock_404__")) {
    const key = err.message.replace("__mock_404__", "");
    if (path.startsWith("/api/v1/schools/")) {
      return new UnknownSchoolError(`No record for ${key}.`);
    }
    return new ApiError(404, "Not found");
  }
  if (err.message.startsWith("__mock_unhandled__")) {
    return new ApiError(404, "Not found");
  }
  return err;
}

export async function request<T>(
  path: string,
  params: Record<string, unknown> = {}
): Promise<T> {
  const { baseUrl, mock } = resolveConfig();

  if (mock) {
    mockActive = true;
    return mockRequest<T>(path, params).catch((err: Error) => {
      throw toApiError(err, path);
    });
  }

  let res: Response;
  try {
    res = await fetch(`${baseUrl}${path}${buildQuery(params)}`, {
      method: "GET",
      headers: { accept: "application/json" }
    });
  } catch (err) {
    if (!import.meta.env.PROD) {
      mockActive = true;
      try {
        return await mockRequest<T>(path, params);
      } catch (mockErr) {
        throw toApiError(mockErr as Error, path);
      }
    }
    throw err;
  }

  if (!res.ok) {
    const detail = await readDetail(res);
    if (res.status === 404 && path.startsWith("/api/v1/schools/")) {
      throw new UnknownSchoolError(detail);
    }
    throw new ApiError(res.status, detail);
  }

  return (await res.json()) as T;
}
```

- [ ] **Step 5: Write `src/api/endpoints.ts`**

```ts
import { request } from "./client";
import type {
  Match,
  ProfileKey,
  ProfilesResponse,
  SearchQuery,
  SearchResponse,
  StatusResponse,
  TopicsResponse
} from "./types";

export function search(query: SearchQuery): Promise<SearchResponse> {
  return request<SearchResponse>("/api/v1/search", { ...query });
}

export function school(key: string, profile: ProfileKey): Promise<Match> {
  return request<Match>(`/api/v1/schools/${encodeURIComponent(key)}`, { profile });
}

export function programs(query: Record<string, unknown> = {}): Promise<unknown> {
  return request<unknown>("/api/v1/programs", query);
}

export function deadlines(unitid: number): Promise<unknown> {
  return request<unknown>("/api/v1/deadlines", { unitid });
}

export function status(): Promise<StatusResponse> {
  return request<StatusResponse>("/api/v1/status");
}

export function profiles(): Promise<ProfilesResponse> {
  return request<ProfilesResponse>("/api/v1/profiles");
}

export function topics(): Promise<TopicsResponse> {
  return request<TopicsResponse>("/api/v1/topics");
}
```

- [ ] **Step 6: Run the test to verify it passes**

Run: `npx vitest run src/api/client.test.ts`
Expected: PASS, 8 tests.

- [ ] **Step 7: Commit**

```bash
git add src/api
git commit -m "feat: add GET-only API client with mock transport"
```

---

### Task 5: URL query codec

**Files:**
- Create: `src/lib/url.ts`
- Test: `src/lib/url.test.ts`

**Interfaces:**
- Consumes: `SearchQuery`, `ProfileKey`, `ProfileOption` from `types.ts`.
- Produces: `DEFAULT_QUERY: SearchQuery`, `parseSearchQuery(params: URLSearchParams): SearchQuery`, `serializeSearchQuery(q: SearchQuery): URLSearchParams`, `profileLabel(key: string, options: ProfileOption[]): string`.

- [ ] **Step 1: Write the failing test `src/lib/url.test.ts`**

```ts
import { describe, expect, it } from "vitest";
import { DEFAULT_QUERY, parseSearchQuery, serializeSearchQuery, profileLabel } from "./url";

describe("parseSearchQuery", () => {
  it("applies defaults for absent params", () => {
    expect(parseSearchQuery(new URLSearchParams())).toEqual(DEFAULT_QUERY);
  });

  it("parses booleans, numbers, and known profiles", () => {
    const q = parseSearchQuery(
      new URLSearchParams("profile=international_stem&stem_only=true&limit=25&max_net_price=15000")
    );
    expect(q.profile).toBe("international_stem");
    expect(q.stem_only).toBe(true);
    expect(q.limit).toBe(25);
    expect(q.max_net_price).toBe(15000);
  });

  it("falls back to defaults for invalid numbers and unknown profiles", () => {
    const q = parseSearchQuery(new URLSearchParams("limit=abc&offset=-1&profile=made_up"));
    expect(q.limit).toBe(DEFAULT_QUERY.limit);
    expect(q.offset).toBe(DEFAULT_QUERY.offset);
    expect(q.profile).toBe(DEFAULT_QUERY.profile);
  });

  it("treats stem_only=false as false", () => {
    expect(parseSearchQuery(new URLSearchParams("stem_only=false")).stem_only).toBe(false);
  });
});

describe("serializeSearchQuery", () => {
  it("writes the required params and omits the unset ones", () => {
    const params = serializeSearchQuery({ ...DEFAULT_QUERY, state: "CA" });
    expect(params.toString()).toBe("profile=first_generation&limit=10&offset=0&state=CA");
  });

  it("round-trips through parse", () => {
    const original = {
      ...DEFAULT_QUERY,
      profile: "international_stem" as const,
      q: "engineering",
      stem_only: true
    };
    expect(parseSearchQuery(serializeSearchQuery(original))).toEqual(original);
  });
});

describe("profileLabel", () => {
  it("returns the matching label and falls back to the raw key", () => {
    const options = [{ key: "first_generation", label: "First-generation student" }];
    expect(profileLabel("first_generation", options)).toBe("First-generation student");
    expect(profileLabel("made_up", options)).toBe("made_up");
  });
});
```

- [ ] **Step 2: Run to verify it fails**

Run: `npx vitest run src/lib/url.test.ts`
Expected: FAIL — cannot resolve `./url`.

- [ ] **Step 3: Write `src/lib/url.ts`**

```ts
import type { ProfileKey, ProfileOption, SearchQuery } from "../api/types";

const PROFILE_KEYS: ProfileKey[] = [
  "first_generation",
  "student_with_disability",
  "international_stem"
];

export const DEFAULT_QUERY: SearchQuery = {
  profile: "first_generation",
  limit: 10,
  offset: 0
};

function toNonNegativeInt(value: string | null, fallback: number): number {
  if (value === null || value.trim() === "") return fallback;
  const n = Number(value);
  if (!Number.isFinite(n) || n < 0) return fallback;
  return Math.trunc(n);
}

export function parseSearchQuery(params: URLSearchParams): SearchQuery {
  const profileParam = params.get("profile");
  const profile = PROFILE_KEYS.includes(profileParam as ProfileKey)
    ? (profileParam as ProfileKey)
    : DEFAULT_QUERY.profile;

  const query: SearchQuery = {
    profile,
    limit: toNonNegativeInt(params.get("limit"), DEFAULT_QUERY.limit),
    offset: toNonNegativeInt(params.get("offset"), DEFAULT_QUERY.offset)
  };

  const q = params.get("q");
  if (q) query.q = q;
  const state = params.get("state");
  if (state) query.state = state;
  const control = params.get("control");
  if (control) query.control = control;
  const level = params.get("level");
  if (level) query.level = level;
  const require = params.get("require");
  if (require) query.require = require;

  const stemOnly = params.get("stem_only");
  if (stemOnly !== null) query.stem_only = stemOnly !== "false";

  const maxNetPrice = params.get("max_net_price");
  if (maxNetPrice !== null) {
    const n = Number(maxNetPrice);
    if (Number.isFinite(n) && n >= 0) query.max_net_price = Math.trunc(n);
  }

  return query;
}

export function serializeSearchQuery(query: SearchQuery): URLSearchParams {
  const params = new URLSearchParams();
  params.set("profile", query.profile);
  params.set("limit", String(query.limit));
  params.set("offset", String(query.offset));
  if (query.q) params.set("q", query.q);
  if (query.state) params.set("state", query.state);
  if (query.control) params.set("control", query.control);
  if (query.level) params.set("level", query.level);
  if (query.require) params.set("require", query.require);
  if (query.stem_only !== undefined) params.set("stem_only", String(query.stem_only));
  if (query.max_net_price !== undefined) params.set("max_net_price", String(query.max_net_price));
  return params;
}

export function profileLabel(key: string, options: ProfileOption[]): string {
  return options.find((option) => option.key === key)?.label ?? key;
}
```

- [ ] **Step 4: Run to verify it passes**

Run: `npx vitest run src/lib/url.test.ts`
Expected: PASS, 7 tests.

- [ ] **Step 5: Commit**

```bash
git add src/lib/url.ts src/lib/url.test.ts
git commit -m "feat: add URL search-query codec"
```

---

### Task 6: Sorting and formatting helpers

**Files:**
- Create: `src/lib/sort.ts`, `src/lib/format.ts`
- Test: `src/lib/sort.test.ts`, `src/lib/format.test.ts`

**Interfaces:**
- Consumes: `Deadline`, `Reason` from `types.ts`.
- Produces: `sortDeadlines(list: Deadline[]): Deadline[]`, `sortReasons(list: Reason[]): Reason[]`, `formatDate(iso: string | null): string`, `formatNetPrice(value: number | null): string`, `formatDaysLeft(days: number): string`, `formatConfidence(value: number): string`.

- [ ] **Step 1: Write the failing test `src/lib/sort.test.ts`**

```ts
import { describe, expect, it } from "vitest";
import { sortDeadlines, sortReasons } from "./sort";
import type { Deadline, Reason } from "../api/types";

const deadline = (date_iso: string, is_past = false): Deadline => ({
  label: date_iso,
  date_iso,
  category: "application",
  url: null,
  is_past,
  days_left: 0
});

describe("sortDeadlines", () => {
  it("sorts ascending by date_iso", () => {
    const out = sortDeadlines([
      deadline("2027-01-05"),
      deadline("2026-11-01"),
      deadline("2026-03-15")
    ]);
    expect(out.map((d) => d.date_iso)).toEqual(["2026-03-15", "2026-11-01", "2027-01-05"]);
  });

  it("does not mutate the input", () => {
    const input = [deadline("2027-01-05"), deadline("2026-03-15")];
    sortDeadlines(input);
    expect(input[0].date_iso).toBe("2027-01-05");
  });

  it("keeps is_past intact", () => {
    const out = sortDeadlines([deadline("2026-03-15", true)]);
    expect(out[0].is_past).toBe(true);
  });
});

describe("sortReasons", () => {
  it("sorts by weight descending", () => {
    const reasons: Reason[] = [
      { signal: "a", label: "A", value: 0.2, weight: 15 },
      { signal: "b", label: "B", value: 0.9, weight: 22 }
    ];
    expect(sortReasons(reasons).map((r) => r.signal)).toEqual(["b", "a"]);
  });
});
```

- [ ] **Step 2: Write the failing test `src/lib/format.test.ts`**

```ts
import { describe, expect, it } from "vitest";
import { formatConfidence, formatDate, formatDaysLeft, formatNetPrice } from "./format";

describe("formatDate", () => {
  it("formats an ISO date and handles null", () => {
    expect(formatDate("2027-01-05")).toContain("2027");
    expect(formatDate(null)).toBe("—");
  });
});

describe("formatNetPrice", () => {
  it("formats a number and marks null as not verified", () => {
    expect(formatNetPrice(14200)).toContain("14,200");
    expect(formatNetPrice(null)).toBe("Not verified");
  });
});

describe("formatDaysLeft", () => {
  it("describes past, today, and future", () => {
    expect(formatDaysLeft(-3)).toBe("3 days ago");
    expect(formatDaysLeft(0)).toBe("Today");
    expect(formatDaysLeft(1)).toBe("1 day left");
    expect(formatDaysLeft(12)).toBe("12 days left");
  });
});

describe("formatConfidence", () => {
  it("renders a percentage", () => {
    expect(formatConfidence(0.95)).toBe("95% confidence");
  });
});
```

- [ ] **Step 3: Run to verify they fail**

Run: `npx vitest run src/lib/sort.test.ts src/lib/format.test.ts`
Expected: FAIL — cannot resolve `./sort` and `./format`.

- [ ] **Step 4: Write `src/lib/sort.ts`**

```ts
import type { Deadline, Reason } from "../api/types";

export function sortDeadlines(list: Deadline[]): Deadline[] {
  return [...list].sort((a, b) => a.date_iso.localeCompare(b.date_iso));
}

export function sortReasons(list: Reason[]): Reason[] {
  return [...list].sort((a, b) => b.weight - a.weight);
}
```

- [ ] **Step 5: Write `src/lib/format.ts`**

```ts
const DATE_FORMAT = new Intl.DateTimeFormat("en-US", {
  year: "numeric",
  month: "short",
  day: "numeric",
  timeZone: "UTC"
});

const CURRENCY_FORMAT = new Intl.NumberFormat("en-US", {
  style: "currency",
  currency: "USD",
  maximumFractionDigits: 0
});

export function formatDate(iso: string | null): string {
  if (!iso) return "—";
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return iso;
  return DATE_FORMAT.format(date);
}

export function formatNetPrice(value: number | null): string {
  if (value === null || value === undefined) return "Not verified";
  return CURRENCY_FORMAT.format(value);
}

export function formatDaysLeft(days: number): string {
  if (days === 0) return "Today";
  if (days < 0) return `${Math.abs(days)} day${Math.abs(days) === 1 ? "" : "s"} ago`;
  return `${days} day${days === 1 ? "" : "s"} left`;
}

export function formatConfidence(value: number): string {
  return `${Math.round(value * 100)}% confidence`;
}
```

- [ ] **Step 6: Run to verify they pass**

Run: `npx vitest run src/lib/sort.test.ts src/lib/format.test.ts`
Expected: PASS, 8 tests.

- [ ] **Step 7: Commit**

```bash
git add src/lib/sort.ts src/lib/sort.test.ts src/lib/format.ts src/lib/format.test.ts
git commit -m "feat: add deadline/reason sorting and formatting helpers"
```

---

### Task 7: Hooks and vocabulary context

**Files:**
- Create: `src/hooks/useApi.ts`, `src/hooks/useDebouncedValue.ts`, `src/api/VocabularyContext.tsx`
- Test: `src/hooks/useApi.test.tsx`, `src/api/VocabularyContext.test.tsx`

**Interfaces:**
- Consumes: `profiles`/`topics` from `endpoints.ts`.
- Produces:
  - `interface ApiState<T> { data: T | null; error: Error | null; loading: boolean; refetch: () => void }`
  - `useApi<T>(factory: () => Promise<T>, deps: unknown[]): ApiState<T>`
  - `useDebouncedValue<T>(value: T, delayMs: number): T`
  - `VocabularyProvider({ children })`, `useVocabulary(): { profiles: ProfileOption[]; topics: TopicOption[]; topicLabel(key: string): string; loading: boolean }`
  - `topicLabelFrom(topics: TopicOption[], key: string): string`

- [ ] **Step 1: Write the failing test `src/hooks/useApi.test.tsx`**

```tsx
import { renderHook, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { useApi } from "./useApi";

describe("useApi", () => {
  it("resolves data and clears loading", async () => {
    const { result } = renderHook(() => useApi(() => Promise.resolve("ok"), []));
    expect(result.current.loading).toBe(true);
    await waitFor(() => expect(result.current.loading).toBe(false));
    expect(result.current.data).toBe("ok");
    expect(result.current.error).toBeNull();
  });

  it("captures errors", async () => {
    const { result } = renderHook(() => useApi(() => Promise.reject(new Error("nope")), []));
    await waitFor(() => expect(result.current.error).toBeInstanceOf(Error));
    expect(result.current.data).toBeNull();
  });

  it("does not warn about setting state after unmount", async () => {
    const spy = vi.spyOn(console, "error");
    const { unmount } = renderHook(() => useApi(() => Promise.resolve("ok"), []));
    unmount();
    await new Promise((resolve) => setTimeout(resolve, 10));
    expect(spy).not.toHaveBeenCalled();
    spy.mockRestore();
  });
});
```

- [ ] **Step 2: Run to verify it fails**

Run: `npx vitest run src/hooks/useApi.test.tsx`
Expected: FAIL — cannot resolve `./useApi`.

- [ ] **Step 3: Write `src/hooks/useApi.ts`**

```ts
import { useCallback, useEffect, useRef, useState } from "react";

export interface ApiState<T> {
  data: T | null;
  error: Error | null;
  loading: boolean;
  refetch: () => void;
}

export function useApi<T>(factory: () => Promise<T>, deps: unknown[]): ApiState<T> {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<Error | null>(null);
  const [loading, setLoading] = useState(true);
  const [nonce, setNonce] = useState(0);
  const mounted = useRef(true);
  const factoryRef = useRef(factory);
  factoryRef.current = factory;

  useEffect(() => {
    mounted.current = true;
    return () => {
      mounted.current = false;
    };
  }, []);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);
    factoryRef
      .current()
      .then((value) => {
        if (cancelled || !mounted.current) return;
        setData(value);
        setLoading(false);
      })
      .catch((err: unknown) => {
        if (cancelled || !mounted.current) return;
        setError(err instanceof Error ? err : new Error(String(err)));
        setData(null);
        setLoading(false);
      });
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [...deps, nonce]);

  const refetch = useCallback(() => setNonce((n) => n + 1), []);

  return { data, error, loading, refetch };
}
```

- [ ] **Step 4: Write `src/hooks/useDebouncedValue.ts`**

```ts
import { useEffect, useState } from "react";

export function useDebouncedValue<T>(value: T, delayMs: number): T {
  const [debounced, setDebounced] = useState(value);

  useEffect(() => {
    const id = setTimeout(() => setDebounced(value), delayMs);
    return () => clearTimeout(id);
  }, [value, delayMs]);

  return debounced;
}
```

- [ ] **Step 5: Write the failing test `src/api/VocabularyContext.test.tsx`**

```tsx
import { render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { VocabularyProvider, useVocabulary } from "./VocabularyContext";
import { resetMockState } from "./client";

function Probe() {
  const { profiles, topicLabel } = useVocabulary();
  return (
    <div>
      <span data-testid="count">{profiles.length}</span>
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
    expect(screen.getByTestId("known")).toHaveTextContent("Net price calculator");
    expect(screen.getByTestId("unknown")).toHaveTextContent("not_a_topic");
  });
});
```

- [ ] **Step 6: Run to verify it fails**

Run: `npx vitest run src/api/VocabularyContext.test.tsx`
Expected: FAIL — cannot resolve `./VocabularyContext`.

- [ ] **Step 7: Write `src/api/VocabularyContext.tsx`**

```tsx
import { createContext, useContext, useMemo, type ReactNode } from "react";
import { profiles as fetchProfiles, topics as fetchTopics } from "./endpoints";
import type { ProfileOption, TopicOption } from "./types";
import { useApi } from "../hooks/useApi";

export function topicLabelFrom(topics: TopicOption[], key: string): string {
  return topics.find((topic) => topic.key === key)?.label ?? key;
}

interface VocabularyValue {
  profiles: ProfileOption[];
  topics: TopicOption[];
  topicLabel: (key: string) => string;
  loading: boolean;
}

const VocabularyContext = createContext<VocabularyValue>({
  profiles: [],
  topics: [],
  topicLabel: (key) => key,
  loading: true
});

export function VocabularyProvider({ children }: { children: ReactNode }) {
  const profilesState = useApi(() => fetchProfiles(), []);
  const topicsState = useApi(() => fetchTopics(), []);

  const profiles = profilesState.data?.profiles ?? [];
  const topics = topicsState.data?.topics ?? [];

  const value = useMemo<VocabularyValue>(
    () => ({
      profiles,
      topics,
      topicLabel: (key: string) => topicLabelFrom(topics, key),
      loading: profilesState.loading || topicsState.loading
    }),
    [profiles, topics, profilesState.loading, topicsState.loading]
  );

  return <VocabularyContext.Provider value={value}>{children}</VocabularyContext.Provider>;
}

export function useVocabulary(): VocabularyValue {
  return useContext(VocabularyContext);
}
```

- [ ] **Step 8: Run to verify all pass**

Run: `npx vitest run src/hooks src/api/VocabularyContext.test.tsx`
Expected: PASS, 4 tests.

- [ ] **Step 9: Commit**

```bash
git add src/hooks src/api/VocabularyContext.tsx src/api/VocabularyContext.test.tsx
git commit -m "feat: add useApi hook and vocabulary context"
```

---

### Task 8: Shared components (Markdown, ErrorBox, Confidence, MockBanner)

**Files:**
- Create: `src/components/common/Markdown.tsx`, `ErrorBox.tsx`, `Confidence.tsx`, `MockBanner.tsx`
- Test: `src/components/common/Markdown.test.tsx`, `src/components/common/ErrorBox.test.tsx`

**Interfaces:**
- Consumes: `formatConfidence` from `lib/format.ts`, `isMockActive` from `client.ts`, `AlertTriangle`/`Info` from `lucide-react`.
- Produces: `<Markdown text={string} />`, `<ErrorBox error={Error|null} />`, `<Confidence value={number} />`, `<MockBanner />`.

`Markdown` supports only `[label](url)` links with `https?://` targets and strips all other markup.

- [ ] **Step 1: Write the failing test `src/components/common/Markdown.test.tsx`**

```tsx
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { Markdown } from "./Markdown";

describe("Markdown", () => {
  it("renders inline links", () => {
    render(
      <Markdown text="Add Stanford with the federal code. [Look up the code](https://studentaid.gov/)" />
    );
    const link = screen.getByRole("link", { name: "Look up the code" });
    expect(link).toHaveAttribute("href", "https://studentaid.gov/");
    expect(link).toHaveAttribute("rel", "noopener noreferrer");
  });

  it("strips raw HTML", () => {
    render(<Markdown text="Safe <img src=x onerror=alert(1)> text" />);
    expect(screen.queryByRole("img")).not.toBeInTheDocument();
    expect(screen.getByText(/Safe/)).toBeInTheDocument();
  });

  it("does not create a link for javascript: urls", () => {
    render(<Markdown text="[click](javascript:alert(1))" />);
    expect(screen.queryByRole("link")).not.toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Run to verify it fails**

Run: `npx vitest run src/components/common/Markdown.test.tsx`
Expected: FAIL — cannot resolve `./Markdown`.

- [ ] **Step 3: Write `src/components/common/Markdown.tsx`**

```tsx
import { Fragment, type ReactNode } from "react";

export function Markdown({ text }: { text: string }) {
  const nodes: ReactNode[] = [];
  const pattern = /\[([^\]]+)\]\((https?:\/\/[^\s)]+)\)|<[^>]*>/g;
  let lastIndex = 0;
  let key = 0;
  let match: RegExpExecArray | null;

  while ((match = pattern.exec(text)) !== null) {
    if (match.index > lastIndex) {
      nodes.push(<Fragment key={key++}>{text.slice(lastIndex, match.index)}</Fragment>);
    }
    if (match[1] && match[2]) {
      nodes.push(
        <a key={key++} href={match[2]} target="_blank" rel="noopener noreferrer">
          {match[1]}
        </a>
      );
    }
    lastIndex = pattern.lastIndex;
  }

  if (lastIndex < text.length) {
    nodes.push(<Fragment key={key++}>{text.slice(lastIndex)}</Fragment>);
  }

  return <>{nodes}</>;
}
```

- [ ] **Step 4: Write the failing test `src/components/common/ErrorBox.test.tsx`**

```tsx
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { ApiError } from "../../api/client";
import { ErrorBox } from "./ErrorBox";

describe("ErrorBox", () => {
  it("shows the server detail for an ApiError", () => {
    render(<ErrorBox error={new ApiError(500, "boom")} />);
    expect(screen.getByRole("alert")).toHaveTextContent("boom");
  });

  it("falls back to the error message and does not apologize", () => {
    render(<ErrorBox error={new Error("network down")} />);
    const alert = screen.getByRole("alert");
    expect(alert).toHaveTextContent("network down");
    expect(alert.textContent?.toLowerCase()).not.toContain("sorry");
  });
});
```

- [ ] **Step 5: Run to verify it fails**

Run: `npx vitest run src/components/common/ErrorBox.test.tsx`
Expected: FAIL — cannot resolve `./ErrorBox`.

- [ ] **Step 6: Write the remaining common components**

`src/components/common/ErrorBox.tsx`:

```tsx
import { AlertTriangle } from "lucide-react";

export function ErrorBox({ error }: { error: Error | null }) {
  if (!error) return null;
  return (
    <div className="error-box" role="alert">
      <AlertTriangle size={20} aria-hidden="true" />
      <span>{error.message || "Request failed."}</span>
    </div>
  );
}
```

`src/components/common/Confidence.tsx`:

```tsx
import { formatConfidence } from "../../lib/format";

export function Confidence({ value }: { value: number }) {
  return <span className="confidence">{formatConfidence(value)}</span>;
}
```

`src/components/common/MockBanner.tsx`:

```tsx
import { useEffect, useState } from "react";
import { isMockActive } from "../../api/client";

export function MockBanner() {
  const [active, setActive] = useState(isMockActive());

  useEffect(() => {
    const id = setInterval(() => setActive(isMockActive()), 500);
    return () => clearInterval(id);
  }, []);

  if (!active) return null;
  return (
    <div className="mock-banner" role="status">
      MOCK DATA — the SRA sidecar is unreachable, showing fixtures. Do not trust these values.
    </div>
  );
}
```

Because mock mode is activated lazily by the first request, `MockBanner` polls `isMockActive()` rather than reading it once, so the banner appears as soon as a fallback happens.

- [ ] **Step 7: Run to verify all pass**

Run: `npx vitest run src/components/common`
Expected: PASS, 5 tests.

- [ ] **Step 8: Commit**

```bash
git add src/components/common
git commit -m "feat: add markdown, error, confidence, and mock banner components"
```

---

### Task 9: Layout (Header, StatusBadge, StaleBadge, ProfileSelect)

**Files:**
- Create: `src/components/layout/Header.tsx`, `StatusBadge.tsx`, `StaleBadge.tsx`, `ProfileSelect.tsx`
- Test: `src/components/layout/StaleBadge.test.tsx`, `src/components/layout/StatusBadge.test.tsx`

**Interfaces:**
- Consumes: `status()` from `endpoints.ts`, `useApi`, `useVocabulary`, `ProfileKey`, `Clock`/`GraduationCap` from `lucide-react`.
- Produces: `<Header />`, `<StatusBadge />`, `<StaleBadge stale={boolean} />`, `<ProfileSelect value={ProfileKey} onChange={(v: ProfileKey) => void} id={string} />`.

- [ ] **Step 1: Write the failing tests**

`src/components/layout/StaleBadge.test.tsx`:

```tsx
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { StaleBadge } from "./StaleBadge";

describe("StaleBadge", () => {
  it("renders when stale", () => {
    render(<StaleBadge stale />);
    expect(screen.getByText(/past its freshness window/i)).toBeInTheDocument();
  });

  it("renders nothing when fresh", () => {
    const { container } = render(<StaleBadge stale={false} />);
    expect(container).toBeEmptyDOMElement();
  });
});
```

`src/components/layout/StatusBadge.test.tsx`:

```tsx
import { render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { StatusBadge } from "./StatusBadge";
import { resetMockState } from "../../api/client";

afterEach(() => {
  vi.unstubAllEnvs();
  resetMockState();
});

describe("StatusBadge", () => {
  it("shows cache-health counts from /status", async () => {
    vi.stubEnv("VITE_SRA_MOCK", "1");
    render(<StatusBadge />);
    await waitFor(() => expect(screen.getByText(/6,243/)).toBeInTheDocument());
    expect(screen.getByText(/75 programmes/)).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Run to verify they fail**

Run: `npx vitest run src/components/layout`
Expected: FAIL — cannot resolve `./StaleBadge`.

- [ ] **Step 3: Write the layout components**

`src/components/layout/StaleBadge.tsx`:

```tsx
import { Clock } from "lucide-react";

export function StaleBadge({ stale }: { stale: boolean }) {
  if (!stale) return null;
  return (
    <span className="stale-badge">
      <Clock size={16} aria-hidden="true" />
      Some evidence is past its freshness window
    </span>
  );
}
```

`src/components/layout/StatusBadge.tsx`:

```tsx
import { useApi } from "../../hooks/useApi";
import { status } from "../../api/endpoints";

const COUNT = new Intl.NumberFormat("en-US");

export function StatusBadge() {
  const { data, error, loading } = useApi(() => status(), []);

  if (loading) return <span className="status-badge">Checking cache</span>;
  if (error || !data) return <span className="status-badge status-badge--down">Cache unavailable</span>;

  return (
    <span className="status-badge" title="Backend cache health">
      {COUNT.format(data.schools ?? 0)} schools
      <span className="status-badge__sep" aria-hidden="true">
        ·
      </span>
      {data.programs ?? 0} programmes
    </span>
  );
}
```

`src/components/layout/ProfileSelect.tsx`:

```tsx
import { useVocabulary } from "../../api/VocabularyContext";
import type { ProfileKey } from "../../api/types";

const PROFILE_KEYS: ProfileKey[] = [
  "first_generation",
  "student_with_disability",
  "international_stem"
];

export function ProfileSelect({
  value,
  onChange,
  id = "profile"
}: {
  value: ProfileKey;
  onChange: (value: ProfileKey) => void;
  id?: string;
}) {
  const { profiles } = useVocabulary();

  return (
    <label className="field" htmlFor={id}>
      <span className="field__label">Profile</span>
      <select
        id={id}
        className="field__input"
        value={value}
        onChange={(event) => onChange(event.target.value as ProfileKey)}
      >
        {PROFILE_KEYS.map((key) => (
          <option key={key} value={key}>
            {profiles.find((profile) => profile.key === key)?.label ?? key}
          </option>
        ))}
      </select>
    </label>
  );
}
```

`src/components/layout/Header.tsx`:

```tsx
import { useEffect, useState } from "react";
import { NavLink } from "react-router-dom";
import { GraduationCap } from "lucide-react";
import { StatusBadge } from "./StatusBadge";

export function Header() {
  const [scrolled, setScrolled] = useState(false);

  useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > 40);
    window.addEventListener("scroll", onScroll, { passive: true });
    onScroll();
    return () => window.removeEventListener("scroll", onScroll);
  }, []);

  return (
    <header className={`site-header${scrolled ? " site-header--scrolled" : ""}`} role="banner">
      <div className="site-header__inner">
        <NavLink to="/" className="brand">
          <GraduationCap size={24} aria-hidden="true" />
          <span>SRA</span>
        </NavLink>
        <nav className="site-nav" aria-label="Main">
          <NavLink to="/" end>
            Search
          </NavLink>
        </nav>
        <StatusBadge />
      </div>
    </header>
  );
}
```

- [ ] **Step 4: Run to verify they pass**

Run: `npx vitest run src/components/layout`
Expected: PASS, 3 tests.

- [ ] **Step 5: Commit**

```bash
git add src/components/layout
git commit -m "feat: add header, status badge, stale badge, profile select"
```

---

### Task 10: School detail components (all seven rules)

**Files:**
- Create: `src/components/school/SchoolHeader.tsx`, `ScorePanel.tsx`, `ReasonBars.tsx`, `OfficialLinks.tsx`, `FactsEvidence.tsx`, `GapsPanel.tsx`, `PlaybookChecklist.tsx`, `DeadlineList.tsx`, `ProgramList.tsx`
- Test: `src/components/school/rules.test.tsx`

**Interfaces:**
- Consumes: `Match`, `Reason`, `Fact`, `Deadline`, `Program`, `PlaybookStep`; `sortDeadlines`, `sortReasons`, `formatDate`, `formatDaysLeft`, `formatNetPrice`; `Markdown`, `Confidence`; `useVocabulary`; `StaleBadge`.
- Produces: the nine components above.

- [ ] **Step 1: Write the failing test `src/components/school/rules.test.tsx`**

```tsx
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
```

- [ ] **Step 2: Run to verify it fails**

Run: `npx vitest run src/components/school/rules.test.tsx`
Expected: FAIL — cannot resolve `./ScorePanel`.

- [ ] **Step 3: Write `ReasonBars.tsx`, `ScorePanel.tsx`, `SchoolHeader.tsx`**

`src/components/school/ReasonBars.tsx`:

```tsx
import type { Reason } from "../../api/types";
import { sortReasons } from "../../lib/sort";

export function ReasonBars({ reasons }: { reasons: Reason[] }) {
  if (reasons.length === 0) return null;

  return (
    <ul className="reason-bars">
      {sortReasons(reasons).map((reason) => (
        <li key={reason.signal} className="reason-bar">
          <span className="reason-bar__label">{reason.label}</span>
          <span
            className="reason-bar__track"
            role="meter"
            aria-valuenow={reason.weight}
            aria-valuemin={0}
            aria-valuemax={100}
            aria-label={`${reason.label} weight`}
          >
            <span
              className="reason-bar__fill"
              style={{ width: `${Math.round(reason.value * 100)}%` }}
            />
          </span>
          <span className="reason-bar__value">{reason.value.toFixed(2)}</span>
          <span className="reason-bar__weight">w{reason.weight}</span>
        </li>
      ))}
    </ul>
  );
}
```

`src/components/school/ScorePanel.tsx`:

```tsx
import type { Match } from "../../api/types";
import { ReasonBars } from "./ReasonBars";

export function ScorePanel({ match, profileLabelText }: { match: Match; profileLabelText: string }) {
  return (
    <section className="score-panel" aria-labelledby="score-heading">
      <p className="score-panel__score" id="score-heading">
        {Math.round(match.score)}/100
      </p>
      <p className="score-panel__subtitle">for {profileLabelText}</p>
      <ReasonBars reasons={match.why} />
    </section>
  );
}
```

`src/components/school/SchoolHeader.tsx`:

```tsx
import type { Match } from "../../api/types";
import { formatDate, formatNetPrice } from "../../lib/format";
import { StaleBadge } from "../layout/StaleBadge";

export function SchoolHeader({ match }: { match: Match }) {
  const { institution } = match;
  return (
    <header className="school-header">
      <p className="eyebrow">Unit ID {institution.unitid}</p>
      <h1 className="school-header__name">{institution.name}</h1>
      <p className="school-header__meta">
        {[institution.city, institution.state_abbr].filter(Boolean).join(", ")}
        {institution.control ? ` · ${institution.control.replace(/_/g, " ")}` : ""}
      </p>
      <dl className="school-header__facts">
        <div>
          <dt>Average net price</dt>
          <dd>{formatNetPrice(institution.avg_net_price)}</dd>
        </div>
        <div>
          <dt>Last verified</dt>
          <dd>{formatDate(match.last_verified)}</dd>
        </div>
      </dl>
      <StaleBadge stale={match.stale} />
    </header>
  );
}
```

- [ ] **Step 4: Write `OfficialLinks.tsx`, `FactsEvidence.tsx`, `GapsPanel.tsx`**

`src/components/school/OfficialLinks.tsx`:

```tsx
import { ArrowUpRight } from "lucide-react";
import { useVocabulary } from "../../api/VocabularyContext";

export function OfficialLinks({ links }: { links: Record<string, string> }) {
  const { topicLabel } = useVocabulary();
  const entries = Object.entries(links);

  if (entries.length === 0) return null;

  return (
    <section className="section" aria-labelledby="links-heading">
      <h2 className="section__title" id="links-heading">
        Official links
      </h2>
      <ul className="link-grid">
        {entries.map(([key, url]) => (
          <li key={key}>
            <a className="link-card" href={url} target="_blank" rel="noopener noreferrer">
              <span>{topicLabel(key)}</span>
              <ArrowUpRight size={20} aria-hidden="true" />
            </a>
          </li>
        ))}
      </ul>
    </section>
  );
}
```

`src/components/school/FactsEvidence.tsx`:

```tsx
import { Info } from "lucide-react";
import type { Fact } from "../../api/types";
import { Confidence } from "../common/Confidence";
import { formatDate } from "../../lib/format";

export function FactsEvidence({ facts }: { facts: Fact[] }) {
  if (facts.length === 0) return null;

  return (
    <section className="section" aria-labelledby="facts-heading">
      <h2 className="section__title" id="facts-heading">
        Evidence
      </h2>
      <ul className="evidence-list">
        {facts.map((fact, index) => (
          <li
            key={`${fact.topic}-${index}`}
            className={`evidence${fact.stale ? " evidence--stale" : ""}`}
          >
            <p className="evidence__value">{fact.value}</p>
            {fact.evidence ? <blockquote className="evidence__quote">{fact.evidence}</blockquote> : null}
            <p className="evidence__meta">
              <span className="evidence__topic">{fact.topic}</span>
              <Confidence value={fact.confidence} />
              {fact.observed_at ? (
                <span className="evidence__date">Observed {formatDate(fact.observed_at)}</span>
              ) : null}
              {fact.extractor === "llm" ? (
                <span className="evidence__llm">
                  <Info size={16} aria-hidden="true" />
                  Model-inferred — verify on the page
                </span>
              ) : null}
            </p>
            {fact.url ? (
              <a
                className="evidence__source"
                href={fact.url}
                target="_blank"
                rel="noopener noreferrer"
              >
                Source
              </a>
            ) : null}
          </li>
        ))}
      </ul>
    </section>
  );
}
```

`src/components/school/GapsPanel.tsx`:

```tsx
import { AlertTriangle } from "lucide-react";

export function GapsPanel({ gaps }: { gaps: string[] }) {
  return (
    <section className="section section--pattern gaps-panel" aria-labelledby="gaps-heading">
      <h2 className="section__title" id="gaps-heading">
        Not verified yet
      </h2>
      {gaps.length === 0 ? (
        <p className="gaps-panel__empty">Nothing flagged.</p>
      ) : (
        <ul className="gaps-panel__list">
          {gaps.map((gap) => (
            <li key={gap} className="gap-line">
              <AlertTriangle size={16} aria-hidden="true" />
              <span>{gap}</span>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
```

- [ ] **Step 5: Write `PlaybookChecklist.tsx`, `DeadlineList.tsx`, `ProgramList.tsx`**

`src/components/school/PlaybookChecklist.tsx`:

```tsx
import type { PlaybookStep } from "../../api/types";
import { Markdown } from "../common/Markdown";
import { formatDate } from "../../lib/format";

export function PlaybookChecklist({ steps }: { steps: PlaybookStep[] }) {
  if (steps.length === 0) return null;
  const ordered = [...steps].sort((a, b) => a.order - b.order);

  return (
    <section className="section" aria-labelledby="playbook-heading">
      <h2 className="section__title" id="playbook-heading">
        Playbook
      </h2>
      <ol className="playbook">
        {ordered.map((step) => (
          <li
            key={step.order}
            className={`playbook-step${step.status === "verify" ? " playbook-step--verify" : ""}`}
          >
            <span className="playbook-step__number" aria-hidden="true">
              {step.order}
            </span>
            <div className="playbook-step__body">
              <h3 className="playbook-step__title">{step.title}</h3>
              <p className="playbook-step__detail">
                <Markdown text={step.detail} />
              </p>
              <p className="playbook-step__meta">
                {step.status === "verify" ? (
                  <span className="playbook-step__tag">Verify on the page</span>
                ) : null}
                {step.deadline ? <span>{formatDate(step.deadline)}</span> : null}
                {step.url ? (
                  <a href={step.url} target="_blank" rel="noopener noreferrer">
                    Open
                  </a>
                ) : null}
              </p>
            </div>
          </li>
        ))}
      </ol>
    </section>
  );
}
```

`src/components/school/DeadlineList.tsx`:

```tsx
import type { Deadline } from "../../api/types";
import { formatDate, formatDaysLeft } from "../../lib/format";
import { sortDeadlines } from "../../lib/sort";

export function DeadlineList({ deadlines }: { deadlines: Deadline[] }) {
  if (deadlines.length === 0) return null;

  return (
    <section className="section section--pattern" aria-labelledby="deadlines-heading">
      <h2 className="section__title" id="deadlines-heading">
        Deadlines
      </h2>
      <ul className="deadline-list">
        {sortDeadlines(deadlines).map((deadline) => (
          <li
            key={`${deadline.label}-${deadline.date_iso}`}
            className={`deadline${deadline.is_past ? " deadline--past" : ""}`}
          >
            <span className="deadline__label">{deadline.label}</span>
            <span className="deadline__date">{formatDate(deadline.date_iso)}</span>
            <span className="deadline__days">{formatDaysLeft(deadline.days_left)}</span>
            <span className="deadline__category">{deadline.category}</span>
          </li>
        ))}
      </ul>
    </section>
  );
}
```

`src/components/school/ProgramList.tsx`:

```tsx
import type { Program } from "../../api/types";
import { DeadlineList } from "./DeadlineList";

export function ProgramList({ programs }: { programs: Program[] }) {
  if (programs.length === 0) return null;

  return (
    <section className="section" aria-labelledby="programs-heading">
      <h2 className="section__title" id="programs-heading">
        Programmes
      </h2>
      <ul className="program-list">
        {programs.map((program) => (
          <li key={program.program_id} className="program-card">
            <h3 className="program-card__name">{program.name}</h3>
            {program.amount_text ? (
              <p className="program-card__amount">{program.amount_text}</p>
            ) : null}
            {program.official_url ? (
              <a href={program.official_url} target="_blank" rel="noopener noreferrer">
                Official page
              </a>
            ) : null}
            <DeadlineList deadlines={program.deadlines} />
          </li>
        ))}
      </ul>
    </section>
  );
}
```

- [ ] **Step 6: Run to verify it passes**

Run: `npx vitest run src/components/school/rules.test.tsx`
Expected: PASS, 8 tests.

- [ ] **Step 7: Commit**

```bash
git add src/components/school
git commit -m "feat: add school detail components covering all seven rendering rules"
```

---

### Task 11: Search components and SearchPage

**Files:**
- Create: `src/components/search/SearchForm.tsx`, `FilterBar.tsx`, `ResultCard.tsx`, `ResultList.tsx`, `Pagination.tsx`, `src/routes/SearchPage.tsx`
- Test: `src/routes/SearchPage.test.tsx`

**Interfaces:**
- Consumes: `search()` from `endpoints.ts`, `parseSearchQuery`/`serializeSearchQuery`/`DEFAULT_QUERY`, `useVocabulary`, `useDebouncedValue`, `useApi`, `Match`, `ReasonBars`, `StaleBadge`, `ErrorBox`, `formatNetPrice`.
- Produces: `<SearchPage />`, `<ResultList matches={Match[]} />`, `<FilterBar values={FilterValues} onChange={...} />`, `<Pagination limit offset total onChange />`.

- [ ] **Step 1: Write the failing test `src/routes/SearchPage.test.tsx`**

```tsx
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes, useLocation } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";
import { SearchPage } from "./SearchPage";
import { VocabularyProvider } from "../api/VocabularyContext";
import { resetMockState } from "../api/client";

function LocationProbe() {
  const location = useLocation();
  return <span data-testid="location">{location.search}</span>;
}

function renderPage(initial = "/?profile=first_generation&state=CA") {
  return render(
    <VocabularyProvider>
      <MemoryRouter initialEntries={[initial]}>
        <Routes>
          <Route
            path="/"
            element={
              <>
                <SearchPage />
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

describe("SearchPage", () => {
  it("renders ranked results with score and reason bars", async () => {
    vi.stubEnv("VITE_SRA_MOCK", "1");
    renderPage();
    await waitFor(() =>
      expect(screen.getByText("Example State University")).toBeInTheDocument()
    );
    expect(screen.getByText("61/100")).toBeInTheDocument();
    expect(screen.getAllByRole("meter").length).toBeGreaterThan(0);
  });

  it("shows a gaps count on each result", async () => {
    vi.stubEnv("VITE_SRA_MOCK", "1");
    renderPage();
    await waitFor(() => expect(screen.getByText(/3 not verified/)).toBeInTheDocument());
  });

  it("writes filter changes into the URL", async () => {
    vi.stubEnv("VITE_SRA_MOCK", "1");
    renderPage("/?profile=first_generation&state=");
    await waitFor(() =>
      expect(screen.getByText("Example State University")).toBeInTheDocument()
    );
    await userEvent.type(screen.getByLabelText("State"), "CA");
    await waitFor(() =>
      expect(screen.getByTestId("location").textContent).toContain("state=CA")
    );
  });

  it("shows an actionable empty state", async () => {
    vi.stubEnv("VITE_SRA_MOCK", "1");
    renderPage("/?profile=first_generation&state=TX");
    await waitFor(() =>
      expect(screen.getByText(/No schools matched these filters/i)).toBeInTheDocument()
    );
    expect(screen.getByRole("button", { name: /Clear filters/i })).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Run to verify it fails**

Run: `npx vitest run src/routes/SearchPage.test.tsx`
Expected: FAIL — cannot resolve `./SearchPage`.

- [ ] **Step 3: Write `ResultCard.tsx`, `ResultList.tsx`, `Pagination.tsx`**

`src/components/search/ResultCard.tsx`:

```tsx
import { Link, useLocation } from "react-router-dom";
import type { Match } from "../../api/types";
import { ReasonBars } from "../school/ReasonBars";
import { StaleBadge } from "../layout/StaleBadge";
import { formatNetPrice } from "../../lib/format";

export function ResultCard({ match }: { match: Match }) {
  const { institution } = match;
  const { search } = useLocation();
  const gapCount = match.gaps.length;

  return (
    <li className="result-card">
      <div className="result-card__head">
        <div>
          <h3 className="result-card__name">
            <Link to={`/schools/${institution.unitid}${search}`}>{institution.name}</Link>
          </h3>
          <p className="result-card__meta">
            {[institution.city, institution.state_abbr].filter(Boolean).join(", ")}
            {" · "}
            Net price {formatNetPrice(institution.avg_net_price)}
          </p>
        </div>
        <p className="result-card__score">{Math.round(match.score)}/100</p>
      </div>
      <ReasonBars reasons={match.why} />
      <div className="result-card__foot">
        <StaleBadge stale={match.stale} />
        <span className={`result-card__gaps${gapCount === 0 ? " result-card__gaps--none" : ""}`}>
          {gapCount === 0 ? "Nothing flagged" : `${gapCount} not verified`}
        </span>
      </div>
    </li>
  );
}
```

`src/components/search/ResultList.tsx`:

```tsx
import type { Match } from "../../api/types";
import { ResultCard } from "./ResultCard";

export function ResultList({ matches }: { matches: Match[] }) {
  if (matches.length === 0) return null;
  return (
    <ul className="result-list">
      {matches.map((match) => (
        <ResultCard key={match.institution.unitid} match={match} />
      ))}
    </ul>
  );
}
```

`src/components/search/Pagination.tsx`:

```tsx
export function Pagination({
  limit,
  offset,
  total,
  onChange
}: {
  limit: number;
  offset: number;
  total: number | undefined;
  onChange: (offset: number) => void;
}) {
  const canGoBack = offset > 0;
  const canGoForward = total === undefined ? true : offset + limit < total;

  if (!canGoBack && !canGoForward) return null;

  return (
    <nav className="pagination" aria-label="Result pages">
      <button type="button" disabled={!canGoBack} onClick={() => onChange(Math.max(0, offset - limit))}>
        Previous
      </button>
      <button type="button" disabled={!canGoForward} onClick={() => onChange(offset + limit)}>
        Next
      </button>
    </nav>
  );
}
```

- [ ] **Step 4: Write `SearchForm.tsx` and `FilterBar.tsx`**

`src/components/search/SearchForm.tsx`:

```tsx
import { useEffect, useState } from "react";
import { Search } from "lucide-react";
import { useDebouncedValue } from "../../hooks/useDebouncedValue";

export function SearchForm({ value, onChange }: { value: string; onChange: (value: string) => void }) {
  const [draft, setDraft] = useState(value);
  const debounced = useDebouncedValue(draft, 300);

  useEffect(() => {
    setDraft(value);
  }, [value]);

  useEffect(() => {
    if (debounced !== value) onChange(debounced);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [debounced]);

  return (
    <form className="search-form" role="search" onSubmit={(event) => event.preventDefault()}>
      <label className="field field--grow" htmlFor="q">
        <span className="field__label">School name or keyword</span>
        <span className="field__with-icon">
          <Search size={20} aria-hidden="true" />
          <input
            id="q"
            className="field__input"
            type="search"
            value={draft}
            placeholder="Stanford"
            onChange={(event) => setDraft(event.target.value)}
          />
        </span>
      </label>
    </form>
  );
}
```

`src/components/search/FilterBar.tsx`:

```tsx
import type { ProfileKey } from "../../api/types";
import { ProfileSelect } from "../layout/ProfileSelect";

export interface FilterValues {
  profile: ProfileKey;
  state: string;
  control: string;
  level: string;
  stemOnly: boolean;
  maxNetPrice: string;
}

const CONTROLS = ["", "public", "private_nonprofit", "private_forprofit"];
const LEVELS = ["", "2-year", "4-year"];

export function FilterBar({
  values,
  onChange
}: {
  values: FilterValues;
  onChange: (next: Partial<FilterValues>) => void;
}) {
  return (
    <div className="filter-bar">
      <ProfileSelect value={values.profile} onChange={(profile) => onChange({ profile })} />

      <label className="field" htmlFor="state">
        <span className="field__label">State</span>
        <input
          id="state"
          className="field__input"
          value={values.state}
          maxLength={2}
          placeholder="CA"
          onChange={(event) => onChange({ state: event.target.value.toUpperCase() })}
        />
      </label>

      <label className="field" htmlFor="control">
        <span className="field__label">Control</span>
        <select
          id="control"
          className="field__input"
          value={values.control}
          onChange={(event) => onChange({ control: event.target.value })}
        >
          {CONTROLS.map((value) => (
            <option key={value || "any"} value={value}>
              {value ? value.replace(/_/g, " ") : "Any"}
            </option>
          ))}
        </select>
      </label>

      <label className="field" htmlFor="level">
        <span className="field__label">Level</span>
        <select
          id="level"
          className="field__input"
          value={values.level}
          onChange={(event) => onChange({ level: event.target.value })}
        >
          {LEVELS.map((value) => (
            <option key={value || "any"} value={value}>
              {value || "Any"}
            </option>
          ))}
        </select>
      </label>

      <label className="field" htmlFor="max_net_price">
        <span className="field__label">Max net price</span>
        <input
          id="max_net_price"
          className="field__input"
          inputMode="numeric"
          value={values.maxNetPrice}
          placeholder="15000"
          onChange={(event) => onChange({ maxNetPrice: event.target.value.replace(/[^0-9]/g, "") })}
        />
      </label>

      <label className="field field--check" htmlFor="stem_only">
        <input
          id="stem_only"
          type="checkbox"
          checked={values.stemOnly}
          onChange={(event) => onChange({ stemOnly: event.target.checked })}
        />
        <span className="field__label">STEM only</span>
      </label>
    </div>
  );
}
```

- [ ] **Step 5: Write `src/routes/SearchPage.tsx`**

```tsx
import { useCallback } from "react";
import { useSearchParams } from "react-router-dom";
import { search } from "../api/endpoints";
import { ErrorBox } from "../components/common/ErrorBox";
import { FilterBar, type FilterValues } from "../components/search/FilterBar";
import { Pagination } from "../components/search/Pagination";
import { ResultList } from "../components/search/ResultList";
import { SearchForm } from "../components/search/SearchForm";
import { useApi } from "../hooks/useApi";
import { DEFAULT_QUERY, parseSearchQuery, serializeSearchQuery } from "../lib/url";
import type { SearchQuery } from "../api/types";

export function SearchPage() {
  const [params, setParams] = useSearchParams();
  const query = parseSearchQuery(params);

  const { data, error, loading } = useApi(() => search(query), [params.toString()]);

  const update = useCallback(
    (patch: Partial<SearchQuery>) => {
      const next: SearchQuery = {
        ...parseSearchQuery(params),
        ...patch,
        offset: patch.offset ?? 0
      };
      setParams(serializeSearchQuery(next), { replace: true });
    },
    [params, setParams]
  );

  const filterValues: FilterValues = {
    profile: query.profile,
    state: query.state ?? "",
    control: query.control ?? "",
    level: query.level ?? "",
    stemOnly: query.stem_only === true,
    maxNetPrice: query.max_net_price !== undefined ? String(query.max_net_price) : ""
  };

  const onFilterChange = (next: Partial<FilterValues>) => {
    const patch: Partial<SearchQuery> = {};
    if (next.profile !== undefined) patch.profile = next.profile;
    if (next.state !== undefined) patch.state = next.state || undefined;
    if (next.control !== undefined) patch.control = next.control || undefined;
    if (next.level !== undefined) patch.level = next.level || undefined;
    if (next.stemOnly !== undefined) patch.stem_only = next.stemOnly || undefined;
    if (next.maxNetPrice !== undefined) {
      patch.max_net_price = next.maxNetPrice ? Number(next.maxNetPrice) : undefined;
    }
    update(patch);
  };

  const results = data?.results ?? [];

  return (
    <div className="page">
      <div className="page-head">
        <p className="eyebrow">School Record Archive</p>
        <h1 className="page-title">Ranked by what actually pays.</h1>
        <p className="page-sub">
          Every match shows its reasons, its official links, and the facts we could not verify.
        </p>
      </div>

      <SearchForm value={query.q ?? ""} onChange={(q) => update({ q: q || undefined })} />
      <FilterBar values={filterValues} onChange={onFilterChange} />

      <ErrorBox error={error} />

      <h2 className="section__title">
        {loading
          ? "Ranking schools…"
          : `${results.length} ranked match${results.length === 1 ? "" : "es"}`}
        {data?.total !== undefined ? ` of ${data.total}` : ""}
      </h2>

      {!loading && !error && results.length === 0 ? (
        <div className="empty-state">
          <p>No schools matched these filters. Widen the state or raise the net-price cap.</p>
          <button
            type="button"
            onClick={() => setParams(serializeSearchQuery(DEFAULT_QUERY), { replace: true })}
          >
            Clear filters
          </button>
        </div>
      ) : (
        <ResultList matches={results} />
      )}

      <Pagination
        limit={query.limit}
        offset={query.offset}
        total={data?.total}
        onChange={(offset) => update({ offset })}
      />
    </div>
  );
}
```

- [ ] **Step 6: Run to verify it passes**

Run: `npx vitest run src/routes/SearchPage.test.tsx`
Expected: PASS, 4 tests.

- [ ] **Step 7: Commit**

```bash
git add src/components/search src/routes/SearchPage.tsx src/routes/SearchPage.test.tsx
git commit -m "feat: add search page with filters in the URL"
```

---

### Task 12: SchoolPage and NotFoundPage

**Files:**
- Create: `src/routes/SchoolPage.tsx`, `src/routes/NotFoundPage.tsx`
- Test: `src/routes/SchoolPage.test.tsx`

**Interfaces:**
- Consumes: `school()` from `endpoints.ts`, `UnknownSchoolError`, `useVocabulary` + `profileLabel`, all nine school components, `ErrorBox`.
- Produces: `<SchoolPage />`, `<NotFoundPage />`.

- [ ] **Step 1: Write the failing test `src/routes/SchoolPage.test.tsx`**

```tsx
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
```

- [ ] **Step 2: Run to verify it fails**

Run: `npx vitest run src/routes/SchoolPage.test.tsx`
Expected: FAIL — cannot resolve `./SchoolPage`.

- [ ] **Step 3: Write `src/routes/SchoolPage.tsx`**

```tsx
import { Link, useParams, useSearchParams } from "react-router-dom";
import { school } from "../api/endpoints";
import { UnknownSchoolError } from "../api/client";
import { useVocabulary } from "../api/VocabularyContext";
import { ErrorBox } from "../components/common/ErrorBox";
import { useApi } from "../hooks/useApi";
import { parseSearchQuery, profileLabel } from "../lib/url";
import { SchoolHeader } from "../components/school/SchoolHeader";
import { ScorePanel } from "../components/school/ScorePanel";
import { OfficialLinks } from "../components/school/OfficialLinks";
import { FactsEvidence } from "../components/school/FactsEvidence";
import { GapsPanel } from "../components/school/GapsPanel";
import { PlaybookChecklist } from "../components/school/PlaybookChecklist";
import { DeadlineList } from "../components/school/DeadlineList";
import { ProgramList } from "../components/school/ProgramList";

export function SchoolPage() {
  const { key = "" } = useParams();
  const [params] = useSearchParams();
  const query = parseSearchQuery(params);
  const { profiles } = useVocabulary();

  const { data, error, loading } = useApi(() => school(key, query.profile), [key, query.profile]);

  const backTo = `/?${params.toString()}`;

  if (loading) {
    return (
      <div className="page">
        <p className="muted">Loading record…</p>
      </div>
    );
  }

  if (error instanceof UnknownSchoolError) {
    return (
      <div className="page">
        <div className="empty-state">
          <h1 className="page-title">No record for `{key}`.</h1>
          <p>Check the school key, or search by name.</p>
          <Link to={backTo}>Back to search</Link>
        </div>
      </div>
    );
  }

  if (error || !data) {
    return (
      <div className="page">
        <ErrorBox error={error} />
        <Link to={backTo}>Back to search</Link>
      </div>
    );
  }

  return (
    <div className="page page--school">
      <Link className="back-link" to={backTo}>
        Back to search
      </Link>
      <SchoolHeader match={data} />
      <ScorePanel match={data} profileLabelText={profileLabel(query.profile, profiles)} />
      <OfficialLinks links={data.links} />
      <FactsEvidence facts={data.facts} />
      <GapsPanel gaps={data.gaps} />
      <PlaybookChecklist steps={data.playbook} />
      <DeadlineList deadlines={data.deadlines} />
      <ProgramList programs={data.programs} />
    </div>
  );
}
```

- [ ] **Step 4: Write `src/routes/NotFoundPage.tsx`**

```tsx
import { Link } from "react-router-dom";

export function NotFoundPage() {
  return (
    <div className="page">
      <div className="empty-state">
        <h1 className="page-title">That page does not exist.</h1>
        <Link to="/">Back to search</Link>
      </div>
    </div>
  );
}
```

- [ ] **Step 5: Run to verify it passes**

Run: `npx vitest run src/routes/SchoolPage.test.tsx`
Expected: PASS, 2 tests.

- [ ] **Step 6: Commit**

```bash
git add src/routes/SchoolPage.tsx src/routes/SchoolPage.test.tsx src/routes/NotFoundPage.tsx
git commit -m "feat: add school detail and not-found pages"
```

---

### Task 13: Wire the router and global shell

**Files:**
- Modify: `src/main.tsx`
- Modify: `src/App.tsx`
- Test: `src/App.test.tsx`

**Interfaces:**
- Consumes: `Header`, `VocabularyProvider`, `MockBanner`, `SearchPage`, `SchoolPage`, `NotFoundPage`, `isMockActive`.
- Produces: the running application.

- [ ] **Step 1: Replace the test `src/App.test.tsx`**

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

it("renders the app shell with a header, brand link, footer, and mock banner", () => {
  vi.stubEnv("VITE_SRA_MOCK", "1");
  render(
    <VocabularyProvider>
      <MemoryRouter>
        <App />
      </MemoryRouter>
    </VocabularyProvider>
  );
  expect(screen.getByRole("banner")).toBeInTheDocument();
  expect(screen.getByRole("link", { name: /SRA/ })).toBeInTheDocument();
  expect(screen.getByRole("contentinfo")).toBeInTheDocument();
});
```

- [ ] **Step 2: Run to verify it fails**

Run: `npx vitest run src/App.test.tsx`
Expected: FAIL — the stub `App` has no `<footer>` element, so `getByRole("contentinfo")` throws.

- [ ] **Step 3: Write `src/App.tsx`**

```tsx
import { Outlet } from "react-router-dom";
import { Header } from "./components/layout/Header";
import { MockBanner } from "./components/common/MockBanner";

export default function App() {
  return (
    <div className="app-shell">
      <Header />
      <MockBanner />
      <main className="app-main">
        <Outlet />
      </main>
      <footer className="site-footer">
        <p>Provenance is the product. Gaps and stale evidence are always shown.</p>
      </footer>
    </div>
  );
}
```

- [ ] **Step 4: Write `src/main.tsx`**

```tsx
import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { RouterProvider, createBrowserRouter } from "react-router-dom";
import App from "./App";
import { VocabularyProvider } from "./api/VocabularyContext";
import { SearchPage } from "./routes/SearchPage";
import { SchoolPage } from "./routes/SchoolPage";
import { NotFoundPage } from "./routes/NotFoundPage";
import "./styles/tokens.css";
import "./styles/base.css";
import "./styles/components.css";

const router = createBrowserRouter([
  {
    path: "/",
    element: <App />,
    children: [
      { index: true, element: <SearchPage /> },
      { path: "schools/:key", element: <SchoolPage /> },
      { path: "*", element: <NotFoundPage /> }
    ]
  }
]);

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <VocabularyProvider>
      <RouterProvider router={router} />
    </VocabularyProvider>
  </StrictMode>
);
```

- [ ] **Step 5: Run to verify it passes**

Run: `npx vitest run src/App.test.tsx`
Expected: PASS, 1 test.

- [ ] **Step 6: Commit**

```bash
git add src/App.tsx src/main.tsx src/App.test.tsx
git commit -m "feat: wire router, header, and mock banner into the app shell"
```

---

### Task 14: Styles

**Files:**
- Create: `src/styles/tokens.css`, `src/styles/base.css`, `src/styles/components.css`

**Interfaces:**
- Consumes: every class name used in Tasks 8-13.
- Produces: the Modern SaaS visual layer.

- [ ] **Step 1: Write `src/styles/tokens.css`**

```css
:root {
  --bg-page: #ffffff;
  --bg-subtle: #f8f8f8;
  --bg-muted: #f5f5f4;
  --bg-dark: #111111;
  --bg-pattern: url("data:image/svg+xml,%3Csvg width='20' height='20' viewBox='0 0 20 20' xmlns='http://www.w3.org/2000/svg'%3E%3Cpath d='M0 0l20 20M20 0L0 20' stroke='%23E0E0E0' stroke-width='0.5'/%3E%3C/svg%3E");

  --text-primary: #111111;
  --text-secondary: #666666;
  --text-muted: #999999;
  --border: #e8e8e8;
  --border-dashed: rgba(17, 17, 17, 0.18);

  --accent: #5ea832;
  --accent-hover: #4d8e28;
  --accent-light: #eef7e6;
  --accent-fg: #ffffff;

  --chart-bar: #e8d87a;
  --chart-area: rgba(232, 216, 122, 0.25);

  --s1: 8px;
  --s2: 16px;
  --s3: 24px;
  --s4: 32px;
  --s5: 48px;
  --s6: 64px;
  --s7: 80px;
  --s8: 96px;
  --s9: 128px;

  --font-display: "Playfair Display", Georgia, serif;
  --font-body: "Inter", system-ui, sans-serif;

  --radius-sm: 6px;
  --radius-md: 10px;
  --radius-lg: 14px;
  --radius-xl: 20px;
  --radius-pill: 999px;

  --shadow-sm: 0 1px 3px rgba(0, 0, 0, 0.06);
  --shadow-md: 0 4px 16px rgba(0, 0, 0, 0.07), 0 2px 4px rgba(0, 0, 0, 0.04);
  --shadow-lg: 0 8px 32px rgba(0, 0, 0, 0.1);
  --shadow-float: 0 20px 60px rgba(0, 0, 0, 0.12);

  --max-w: 1200px;
}
```

- [ ] **Step 2: Write `src/styles/base.css`**

```css
*,
*::before,
*::after {
  box-sizing: border-box;
}

body {
  margin: 0;
  background: var(--bg-page);
  color: var(--text-primary);
  font-family: var(--font-body);
  font-size: 16px;
  line-height: 1.65;
}

h1,
h2 {
  font-family: var(--font-display);
  margin: 0;
}

h3 {
  font-family: var(--font-body);
  margin: 0;
  font-size: 18px;
  font-weight: 600;
  line-height: 1.3;
}

a {
  color: var(--accent);
}

a:hover {
  color: var(--accent-hover);
}

:focus-visible {
  outline: 2px solid var(--accent);
  outline-offset: 2px;
}

button {
  font-family: var(--font-body);
  cursor: pointer;
}

.app-shell {
  min-height: 100vh;
  display: flex;
  flex-direction: column;
}

.app-main {
  flex: 1;
  width: 100%;
  max-width: var(--max-w);
  margin: 0 auto;
  padding: var(--s5) var(--s3) var(--s7);
}

.page {
  display: flex;
  flex-direction: column;
  gap: var(--s4);
}

.page-head {
  display: flex;
  flex-direction: column;
  gap: var(--s2);
  max-width: 720px;
}

.eyebrow {
  margin: 0;
  font-size: 13px;
  font-weight: 500;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: var(--accent);
}

.page-title {
  font-size: clamp(32px, 4.5vw, 56px);
  font-weight: 800;
  line-height: 1.1;
  letter-spacing: -0.02em;
}

.page-sub {
  margin: 0;
  color: var(--text-secondary);
  max-width: 560px;
}

.muted {
  color: var(--text-muted);
}

.empty-state {
  background: var(--bg-subtle);
  border: 1px solid var(--border);
  border-radius: var(--radius-lg);
  padding: var(--s4);
  display: flex;
  flex-direction: column;
  gap: var(--s2);
  align-items: flex-start;
}

.empty-state button {
  background: var(--accent);
  color: var(--accent-fg);
  border: none;
  border-radius: var(--radius-md);
  padding: 10px 20px;
  font-size: 15px;
  font-weight: 500;
}

.site-footer {
  border-top: 1px solid var(--border);
  background: var(--bg-subtle);
  padding: var(--s3);
}

.site-footer p {
  max-width: var(--max-w);
  margin: 0 auto;
  font-size: 13px;
  color: var(--text-muted);
}

@media (prefers-reduced-motion: reduce) {
  *,
  *::before,
  *::after {
    animation-duration: 0.001ms !important;
    animation-iteration-count: 1 !important;
    transition-duration: 0.001ms !important;
    scroll-behavior: auto !important;
  }
}
```

- [ ] **Step 3: Write `src/styles/components.css`**

```css
.site-header {
  position: sticky;
  top: 0;
  z-index: 20;
  background: var(--bg-page);
  border-bottom: 1px solid transparent;
  transition: box-shadow 0.2s ease, border-color 0.2s ease;
}

.site-header--scrolled {
  border-bottom-color: var(--border);
  box-shadow: 0 1px 20px rgba(0, 0, 0, 0.07);
}

.site-header__inner {
  max-width: var(--max-w);
  margin: 0 auto;
  padding: var(--s2) var(--s3);
  display: flex;
  align-items: center;
  gap: var(--s3);
}

.brand {
  display: inline-flex;
  align-items: center;
  gap: var(--s1);
  font-family: var(--font-display);
  font-weight: 800;
  font-size: 20px;
  color: var(--text-primary);
  text-decoration: none;
}

.site-nav {
  margin-right: auto;
}

.site-nav a {
  font-size: 15px;
  font-weight: 500;
  color: var(--text-secondary);
  text-decoration: none;
  transition: color 0.2s ease;
}

.site-nav a:hover {
  color: var(--text-primary);
}

.status-badge {
  font-size: 13px;
  font-weight: 500;
  color: var(--text-muted);
  border: 1px solid var(--border);
  border-radius: var(--radius-pill);
  padding: 6px 14px;
  white-space: nowrap;
}

.status-badge__sep {
  margin: 0 6px;
}

.stale-badge {
  display: inline-flex;
  align-items: center;
  gap: var(--s1);
  background: var(--accent-light);
  color: var(--accent-hover);
  border-radius: var(--radius-pill);
  padding: 6px 14px;
  font-size: 13px;
  font-weight: 500;
}

.mock-banner {
  background: var(--bg-dark);
  color: #ffffff;
  text-align: center;
  font-size: 13px;
  font-weight: 500;
  padding: var(--s1) var(--s3);
}

.error-box {
  display: flex;
  align-items: center;
  gap: var(--s1);
  background: #fdf3f2;
  border: 1px solid #f2c9c5;
  color: #8c2a22;
  border-radius: var(--radius-md);
  padding: var(--s2);
  font-size: 15px;
}

.search-form {
  display: flex;
  gap: var(--s2);
}

.filter-bar {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(160px, 1fr));
  gap: var(--s2);
  align-items: end;
  padding: var(--s3);
  background: var(--bg-subtle);
  border: 1px solid var(--border);
  border-radius: var(--radius-lg);
}

.field {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.field--grow {
  flex: 1;
}

.field--check {
  flex-direction: row;
  align-items: center;
  gap: var(--s1);
  padding-bottom: 10px;
}

.field__label {
  font-size: 13px;
  font-weight: 500;
  color: var(--text-muted);
}

.field__input {
  font-family: var(--font-body);
  font-size: 15px;
  color: var(--text-primary);
  background: var(--bg-page);
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  padding: 9px 12px;
  width: 100%;
}

.field__with-icon {
  position: relative;
  display: flex;
  align-items: center;
}

.field__with-icon svg {
  position: absolute;
  left: 12px;
  color: var(--text-muted);
}

.field__with-icon .field__input {
  padding-left: 40px;
}

.section {
  display: flex;
  flex-direction: column;
  gap: var(--s3);
}

.section--pattern {
  background-image: var(--bg-pattern);
  border: 1px solid var(--border);
  border-radius: var(--radius-lg);
  padding: var(--s4);
}

.section__title {
  font-size: clamp(24px, 2.6vw, 36px);
  font-weight: 700;
  line-height: 1.15;
  text-align: left;
}

.result-list {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: var(--s2);
}

.result-card {
  background: var(--bg-page);
  border: 1px solid var(--border);
  border-radius: var(--radius-lg);
  padding: var(--s3);
  box-shadow: var(--shadow-sm);
  transition: border-color 0.2s ease;
  display: flex;
  flex-direction: column;
  gap: var(--s2);
}

.result-card:hover {
  border-color: var(--accent);
}

.result-card__head {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: var(--s2);
}

.result-card__name {
  font-size: 20px;
}

.result-card__name a {
  color: var(--text-primary);
  text-decoration: none;
}

.result-card__name a:hover {
  color: var(--accent);
}

.result-card__meta {
  margin: 4px 0 0;
  font-size: 13px;
  color: var(--text-muted);
}

.result-card__score {
  margin: 0;
  font-family: var(--font-display);
  font-size: 28px;
  font-weight: 800;
  white-space: nowrap;
}

.result-card__foot {
  display: flex;
  align-items: center;
  gap: var(--s2);
  flex-wrap: wrap;
}

.result-card__gaps {
  font-size: 13px;
  font-weight: 500;
  color: #8c2a22;
}

.result-card__gaps--none {
  color: var(--text-muted);
}

.reason-bars {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: var(--s1);
}

.reason-bar {
  display: grid;
  grid-template-columns: minmax(140px, 1fr) 2fr auto auto;
  align-items: center;
  gap: var(--s2);
  font-size: 13px;
}

.reason-bar__label {
  color: var(--text-secondary);
}

.reason-bar__track {
  display: block;
  height: 10px;
  background: var(--bg-muted);
  border-radius: var(--radius-pill);
  overflow: hidden;
}

.reason-bar__fill {
  display: block;
  height: 100%;
  background: var(--chart-bar);
  border-radius: var(--radius-pill);
}

.reason-bar__value {
  font-variant-numeric: tabular-nums;
  color: var(--text-primary);
}

.reason-bar__weight {
  color: var(--text-muted);
}

.score-panel {
  background: var(--bg-subtle);
  border: 1px solid var(--border);
  border-radius: var(--radius-lg);
  padding: var(--s4);
  display: flex;
  flex-direction: column;
  gap: var(--s2);
}

.score-panel__score {
  margin: 0;
  font-family: var(--font-display);
  font-size: clamp(48px, 6vw, 72px);
  font-weight: 800;
  line-height: 1;
}

.score-panel__subtitle {
  margin: 0 0 var(--s2);
  color: var(--text-secondary);
}

.school-header {
  display: flex;
  flex-direction: column;
  gap: var(--s2);
}

.school-header__name {
  font-size: clamp(36px, 5vw, 60px);
  font-weight: 800;
  line-height: 1.05;
  letter-spacing: -0.02em;
}

.school-header__meta {
  margin: 0;
  color: var(--text-secondary);
  text-transform: capitalize;
}

.school-header__facts {
  display: flex;
  gap: var(--s5);
  margin: 0;
}

.school-header__facts dt {
  font-size: 13px;
  font-weight: 500;
  color: var(--text-muted);
}

.school-header__facts dd {
  margin: 4px 0 0;
  font-size: 18px;
  font-weight: 600;
}

.link-grid {
  list-style: none;
  margin: 0;
  padding: 0;
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
  gap: var(--s2);
}

.link-card {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--s2);
  background: var(--bg-page);
  border: 1px solid var(--border);
  border-radius: var(--radius-lg);
  padding: var(--s3);
  box-shadow: var(--shadow-sm);
  color: var(--text-primary);
  font-weight: 500;
  text-decoration: none;
  transition: border-color 0.2s ease;
}

.link-card:hover {
  border-color: var(--accent);
  color: var(--text-primary);
}

.evidence-list {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: var(--s2);
}

.evidence {
  background: var(--bg-muted);
  border-radius: var(--radius-lg);
  padding: var(--s3);
  display: flex;
  flex-direction: column;
  gap: var(--s1);
}

.evidence__value {
  margin: 0;
  font-weight: 500;
}

.evidence__quote {
  margin: 0;
  padding-left: var(--s2);
  border-left: 2px solid var(--border);
  color: var(--text-secondary);
  font-style: italic;
}

.evidence__meta {
  display: flex;
  align-items: center;
  gap: var(--s2);
  flex-wrap: wrap;
  margin: 0;
  font-size: 13px;
  color: var(--text-muted);
}

.evidence__topic {
  font-weight: 500;
  color: var(--text-secondary);
}

.evidence__llm {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  background: var(--accent-light);
  color: var(--accent-hover);
  border-radius: var(--radius-pill);
  padding: 4px 10px;
  font-weight: 500;
}

.evidence__source {
  align-self: flex-start;
  font-size: 13px;
  font-weight: 500;
}

.gaps-panel__list {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: var(--s1);
}

.gap-line {
  display: flex;
  align-items: center;
  gap: var(--s1);
  padding: var(--s2) 0;
  border-bottom: 1px dashed var(--border-dashed);
  color: var(--text-secondary);
}

.gaps-panel__empty {
  margin: 0;
  color: var(--text-muted);
}

.playbook {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: var(--s3);
  counter-reset: step;
}

.playbook-step {
  display: grid;
  grid-template-columns: 56px 1fr;
  gap: var(--s2);
}

.playbook-step__number {
  font-family: var(--font-display);
  font-size: 36px;
  font-weight: 800;
  line-height: 1;
  color: var(--text-muted);
}

.playbook-step--verify .playbook-step__number {
  color: var(--accent);
}

.playbook-step__body {
  display: flex;
  flex-direction: column;
  gap: 6px;
  border-left: 1px solid var(--border);
  padding-left: var(--s3);
}

.playbook-step--verify .playbook-step__body {
  border-left-color: var(--accent);
}

.playbook-step__title {
  font-size: 18px;
}

.playbook-step__detail {
  margin: 0;
  color: var(--text-secondary);
}

.playbook-step__meta {
  display: flex;
  align-items: center;
  gap: var(--s2);
  margin: 0;
  font-size: 13px;
  color: var(--text-muted);
}

.playbook-step__tag {
  background: var(--accent-light);
  color: var(--accent-hover);
  border-radius: var(--radius-pill);
  padding: 4px 10px;
  font-weight: 500;
}

.deadline-list {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: var(--s1);
}

.deadline {
  display: grid;
  grid-template-columns: minmax(160px, 1.5fr) 1fr 1fr auto;
  gap: var(--s2);
  align-items: center;
  background: var(--bg-page);
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  padding: 10px var(--s2);
  font-size: 14px;
}

.deadline--past {
  opacity: 0.5;
}

.deadline__label {
  font-weight: 500;
}

.deadline__date,
.deadline__days,
.deadline__category {
  color: var(--text-muted);
}

.program-list {
  list-style: none;
  margin: 0;
  padding: 0;
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
  gap: var(--s2);
}

.program-card {
  background: var(--bg-page);
  border: 1px solid var(--border);
  border-radius: var(--radius-lg);
  padding: var(--s3);
  box-shadow: var(--shadow-sm);
  display: flex;
  flex-direction: column;
  gap: var(--s2);
}

.program-card__name {
  font-size: 18px;
}

.program-card__amount {
  margin: 0;
  color: var(--text-secondary);
}

.pagination {
  display: flex;
  gap: var(--s2);
  justify-content: flex-end;
}

.pagination button {
  background: var(--bg-page);
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  padding: 9px 20px;
  font-size: 15px;
  font-weight: 500;
  transition: transform 0.15s ease, box-shadow 0.15s ease;
}

.pagination button:hover:not(:disabled) {
  transform: translateY(-2px);
  box-shadow: var(--shadow-sm);
}

.pagination button:disabled {
  color: var(--text-muted);
  cursor: not-allowed;
}

.back-link {
  align-self: flex-start;
  font-size: 14px;
  font-weight: 500;
}

@media (max-width: 640px) {
  .app-main {
    padding: var(--s4) var(--s2) var(--s6);
  }

  .site-header__inner {
    flex-wrap: wrap;
    gap: var(--s2);
  }

  .reason-bar,
  .deadline {
    grid-template-columns: 1fr 1fr;
  }

  .school-header__facts {
    gap: var(--s4);
  }
}
```

- [ ] **Step 4: Run the whole unit suite and typecheck**

Run: `npm run typecheck`
Then: `npm run test`
Expected: typecheck clean; all unit suites pass.

- [ ] **Step 5: Commit**

```bash
git add src/styles
git commit -m "feat: add Modern SaaS design tokens and component styles"
```

---

### Task 15: Playwright smoke test

**Files:**
- Create: `playwright.config.ts`, `e2e/smoke.spec.ts`

**Interfaces:**
- Consumes: the built app with `VITE_SRA_MOCK=1`.
- Produces: an end-to-end test proving the seven sections render and no POST is ever issued.

- [ ] **Step 1: Write `playwright.config.ts`**

```ts
import { defineConfig, devices } from "@playwright/test";

export default defineConfig({
  testDir: "./e2e",
  timeout: 30_000,
  use: {
    baseURL: "http://127.0.0.1:4173",
    trace: "on-first-retry"
  },
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"] } }],
  webServer: {
    command: "npm run build && npm run preview -- --port 4173 --strictPort",
    url: "http://127.0.0.1:4173",
    reuseExistingServer: !process.env.CI,
    env: { VITE_SRA_MOCK: "1" },
    timeout: 120_000
  }
});
```

- [ ] **Step 2: Write the failing test `e2e/smoke.spec.ts`**

```ts
import { expect, test } from "@playwright/test";

test("search to school detail, with GET-only traffic", async ({ page }) => {
  const methods: string[] = [];
  page.on("request", (request) => methods.push(request.method()));

  await page.goto("/?profile=first_generation&state=CA");

  await expect(page.getByText("Stanford University")).toBeVisible();
  await expect(page.getByText("42/100")).toBeVisible();

  await page.getByLabel("State").fill("CA");
  await expect(page).toHaveURL(/state=CA/);

  await page.getByRole("link", { name: "Stanford University" }).click();
  await expect(page).toHaveURL(/\/schools\/243744/);

  await expect(page.getByRole("heading", { name: "Stanford University" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Official links" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Evidence" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Not verified yet" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Playbook" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Deadlines" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Programmes" })).toBeVisible();

  expect(methods.filter((method) => method === "POST")).toEqual([]);
});
```

- [ ] **Step 3: Run to verify it fails**

Run: `npx playwright install chromium`
Then: `npm run test:e2e`
Expected: FAIL on the first run before the styles/build are in place, or pass immediately if the build is already complete — either way, confirm the assertion set matches the DOM.

- [ ] **Step 4: Run to verify it passes**

Run: `npm run test:e2e`
Expected: PASS, 1 test.

- [ ] **Step 5: Commit**

```bash
git add playwright.config.ts e2e
git commit -m "test: add Playwright smoke test asserting GET-only traffic"
```

---

### Task 16: Full verification

**Files:** none (verification only)

- [ ] **Step 1: Run the full gate in order**

```bash
npm run typecheck
npm run lint
npm run test
npm run test:e2e
npm run build
```

Expected: every command exits 0. Playwright reports 1 passing test; Vitest reports all suites passing.

- [ ] **Step 2: Confirm the GET-only constraint by inspection**

Run: `git grep -nE "method: ?\"POST\"|/api/v1/enrich|/api/v1/refresh|/api/v1/build|/api/v1/programs/verify|/api/v1/seed" -- src`
Expected: no matches.

- [ ] **Step 3: Commit any fixes from the gate, then tag the milestone**

```bash
git add -A
git commit -m "chore: pass full verification gate"
```

If nothing changed, skip the commit.