# SRA Integration Guide (Backend & Frontend)

This guide provides end-to-end specifications for integrating **SRA (Student Resource Architecture)** into existing backends (Python, Node.js, Go, etc.) and frontends (React, Next.js, Vue).

---

## 1. Profiles & Core Domain Keys

Always use these exact profile keys:
- **`first_generation`**: First-gen college students seeking scholarships, net price clarity, fee waivers, and mentorship.
- **`student_with_disability`**: Students seeking accommodation funding, assistive technology grants, and disability services.
- **`international_stem`**: Non-US citizens seeking fully funded bachelor's/master's, tuition waivers, and CPT/OPT pathways.

---

## 2. Backend Integration

### Option A: Embedded Python Integration (Fastest, In-Process)
Use this option when your backend is written in Python (FastAPI, Django, Flask). Core reads are **pure SQLite cache reads** (sub-millisecond latency, zero network overhead on user request paths).

```python
from sra_schools import SRA

# 1. Open the cache (thread-safe, shared connection with WAL mode)
sra = SRA.open()

# 2. Search colleges for a profile
report = sra.search(
    profile="first_generation",
    state="CA",
    max_net_price=25000.0,
    limit=10,
    offset=0,
    live=False,  # Keep False on web request paths (pure cache reads)
)

print(f"Total matching universe: {report.universe_size}")
for match in report.matches:
    print(f"School: {match.institution.name} (Score: {match.score})")
    print(f"  Apply URL: {match.links.get('application_portal')}")
    print(f"  Fee Waiver URL: {match.links.get('application_fee_waiver')}")
    print(f"  Why it matched: {[w['label'] for w in match.why[:3]]}")
    print(f"  Action Playbook: {len(match.playbook)} steps")
    print(f"  Data Gaps: {match.gaps}")

# 3. Retrieve single institution detail (by UnitID or fuzzy name)
match = sra.school("110635", profile="first_generation")

# 4. Query aid programs catalogue
programs = sra.programs(profile="student_with_disability", limit=20)

# 5. Query upcoming deadlines
deadlines = sra.deadlines(unitid=110635)
```

---

### Option B: HTTP Sidecar Service (Any Language)
Run `sra_schools.server` as a microservice.

```bash
# Start server
uvicorn sra_schools.server:app --host 0.0.0.0 --port 8000
```

#### Comprehensive API Endpoints Reference (All 17 Endpoints)

##### 1. System Health & Documentation

- **`GET /`**
  - **Description**: Basic root metadata and link to interactive documentation.
  - **Response (`200 OK`)**:
    ```json
    { "name": "SRA — Scholarship Research Assistant", "version": "0.1.0", "docs": "/docs", "openapi": "/openapi.json" }
    ```
- **`GET /docs`**
  - **Description**: Interactive Swagger UI explorer for all endpoints.
- **`GET /openapi.json`**
  - **Description**: Complete OpenAPI 3.1.0 schema specification.

##### 2. College Search & Discovery

- **`POST /api/v1/search`** (Recommended for Web/Mobile Apps)
  - **Description**: Search and rank institutions using a structured JSON body.
  - **Request Body (`application/json`)**:
    ```json
    {
      "profile": "first_generation",       // "first_generation" | "student_with_disability" | "international_stem"
      "q": "Berkeley",                     // Optional text query (name, city, state)
      "needs": ["application_fee_waiver"], // Optional explicit needs override
      "state": "CA",                       // 2-letter state abbreviation
      "control": "public",                 // "public" | "private_nonprofit" | "private_for_profit"
      "level": "undergraduate",            // "undergraduate" | "graduate"
      "stem_only": false,                  // Filter for STEM-dense institutions
      "max_net_price": 20000.0,            // Maximum average net price in USD
      "min_aid_generosity": 0.6,           // Minimum aid generosity ratio (0.0 to 1.0)
      "require": ["net_price_calculator"], // Only schools with verified facts for these topics
      "limit": 10,                         // 1 to 100 (default: 20)
      "offset": 0,                         // Pagination offset
      "live": false,                       // Allow network crawl on cache miss (default: false)
      "include_stale": true                // Allow cached data older than TTL (default: true)
    }
    ```
  - **Response (`200 OK`)**: Standard `SearchReport` JSON containing results, why signals, links, deadlines, and playbooks.

- **`GET /api/v1/search`**
  - **Description**: Equivalent search using URL query parameters (e.g. `?profile=first_generation&state=CA&limit=10`).
  - **Response (`200 OK`)**: Standard `SearchReport` JSON.

- **`GET /api/v1/search/markdown`**
  - **Description**: Executes the search query and returns the results rendered as formatted Markdown text.
  - **Query Params**: Same as `GET /api/v1/search`.
  - **Response (`200 OK`)**: `Content-Type: text/plain; charset=utf-8` containing human-readable tables and bullet points.

##### 3. Institution Details

- **`GET /api/v1/schools/{key}`**
  - **Description**: Complete intelligence for a single institution.
  - **Path Parameter**: `{key}` can be a 6-digit federal `unitid` (e.g. `110635`), `opeid`, or a school name query (e.g. `Berkeley`).
  - **Query Params**: `profile` (optional profile key to customize score, why signals, and playbook).
  - **Response (`200 OK`)**: Full `SchoolMatch` JSON object.
  - **Errors**: `404 Not Found` if no institution matches `{key}`.

- **`GET /api/v1/schools/{key}/markdown`**
  - **Description**: Returns single institution detail rendered as a formatted Markdown profile.
  - **Response (`200 OK`)**: `Content-Type: text/plain; charset=utf-8`.

##### 4. Aid & Scholarship Programmes Catalogue

- **`GET /api/v1/programs`**
  - **Description**: Filterable catalogue of national, state, and institutional aid programmes (grants, scholarships, services).
  - **Query Params**:
    - `profile`: Filter programs tagged for this profile.
    - `needs`: Filter by need key(s).
    - `level`: `undergraduate` | `graduate`.
    - `state`: Two-letter state code.
    - `stem_only`: Boolean (`true` | `false`).
    - `kind`: `scholarship` | `grant` | `fellowship` | `services` | `need_based_aid`.
    - `limit`: Results per page (default: 50).
    - `offset`: Pagination offset (default: 0).
  - **Response (`200 OK`)**: `{"count": N, "results": [...]}`.

- **`GET /api/v1/programs/{program_id}`**
  - **Description**: Full detail for a single aid programme by its unique slug ID (e.g. `rsa-state-vocational-rehabilitation-services-program`, `css-profile-fee-waiver`).
  - **Response (`200 OK`)**: Single `AidProgram` object including `official_url`, `apply_url`, `eligibility`, `deadlines`, and `apply_steps`.
  - **Errors**: `404 Not Found` if `{program_id}` does not exist.

##### 5. Deadlines Calendar

- **`GET /api/v1/deadlines`**
  - **Description**: Retrieves verified application and financial aid filing deadlines.
  - **Query Params**:
    - `unitid`: Filter deadlines for a specific institution (e.g. `?unitid=110635`).
    - `limit`: Maximum deadlines to return (default: 40).
  - **Response (`200 OK`)**: `{"count": N, "results": [{"label": "...", "date_iso": "YYYY-MM-DD", "category": "aid"|"application", ...}]}`.

##### 6. Metadata & System Health

- **`GET /api/v1/status`**
  - **Description**: Cache health, total institutions, programs, coverage by topic, and query cache hit rates.
  - **Response (`200 OK`)**: `{"institutions": N, "programs": N, "deadlines": N, "cache": {...}, "query_cache": {...}}`.

- **`GET /api/v1/profiles`**
  - **Description**: Lists all supported student profiles with their descriptions, required topics, and default weights.
  - **Response (`200 OK`)**: `{"count": 3, "results": [{"key": "first_generation", ...}, ...]}`.

- **`GET /api/v1/topics`**
  - **Description**: Lists all 52 tracked fact topics (e.g. `fafsa_school_code`, `application_fee_waiver`, `css_profile_code`) with their freshness policies and value types.
  - **Response (`200 OK`)**: `{"count": 52, "results": [{"key": "...", "label": "...", "value_type": "url"|"date"|"text"|"money"}, ...]}`.

##### 7. Administrative, Ingest & Seed Operations

- **`POST /api/v1/build`**
  - **Description**: Ingests federal College Scorecard institutions and seeds the programme catalogue into SQLite.
  - **Request Body (`application/json`)**:
    ```json
    { "source": "/path/to/Scorecard.csv", "url": null, "no_programs": false, "rebuild": false }
    ```
  - **Response (`200 OK`)**: `{"institutions": N, "programs": N, "dataset_version": "..."}`.

- **`POST /api/v1/enrich`**
  - **Description**: Triggers budget-bounded web crawling for targeted institutions to discover fee waivers, deadlines, and contact links.
  - **Request Body (`application/json`)**:
    ```json
    { "unitids": [110635], "profile": "first_generation", "limit": 10, "force": false }
    ```
  - **Response (`200 OK`)**: Array of crawl reports per institution.

- **`POST /api/v1/refresh`**
  - **Description**: Re-crawls only institutions whose cached pages have passed their freshness TTL.
  - **Request Body (`application/json`)**:
    ```json
    { "limit": 100, "profile": null, "purge": false }
    ```
  - **Response (`200 OK`)**: Summary of fetched, revalidated, and updated facts.

- **`POST /api/v1/programs/verify`**
  - **Description**: Audits the health and DNS/HTTP validity of all programme application links.
  - **Request Body (`application/json`)**:
    ```json
    { "limit": 100, "dns_only": true }
    ```
  - **Response (`200 OK`)**: `{"audited": N, "results": {...}}`.

- **`POST /api/v1/seed/export`**
  - **Description**: Exports the enriched cache state into a portable gzip-compressed bundle.
  - **Request Body (`application/json`)**:
    ```json
    { "path": "/path/to/seed_export.json.gz", "profiles": ["first_generation"], "limit": 500 }
    ```
  - **Response (`201 Created`)**: `{"institutions": N, "bytes": N, "checksum": "...", "path": "..."}`.

- **`POST /api/v1/seed/import`**
  - **Description**: Restores or populates an empty SQLite cache from a portable seed bundle without requiring a full re-crawl.
  - **Query / Param**: `?path=/path/to/seed.json.gz`.
  - **Response (`201 Created`)**: `{"institutions": N, "counts": {...}, "checksum": "..."}`.
#### Search Request Example (`POST /api/v1/search`)
```http
POST /api/v1/search HTTP/1.1
Host: localhost:8000
Content-Type: application/json

{
  "profile": "first_generation",
  "state": "CA",
  "control": "public",
  "max_net_price": 20000.0,
  "limit": 10,
  "offset": 0
}
```

#### Response Example (`HTTP 200 OK`)
```json
{
  "profile": "first_generation",
  "count": 1,
  "universe_size": 420,
  "cache": {
    "hit": true,
    "fingerprint": "8cf13...b2"
  },
  "results": [
    {
      "institution": {
        "unitid": 110635,
        "name": "University of California-Berkeley",
        "city": "Berkeley",
        "state_abbr": "CA",
        "control": "public",
        "avg_net_price": 14200.0,
        "cost_attending": 44000.0,
        "url_homepage": "https://www.berkeley.edu"
      },
      "score": 84.5,
      "why": [
        {
          "signal": "need_coverage",
          "label": "Answers the needs you listed",
          "value": 0.88,
          "weight": 26.0
        },
        {
          "signal": "aid_generosity",
          "label": "Grants and net-price generosity",
          "value": 0.79,
          "weight": 22.0
        }
      ],
      "links": {
        "application_portal": "https://admissions.berkeley.edu/apply",
        "application_fee_waiver": "https://admissions.berkeley.edu/apply/fee-waiver",
        "net_price_calculator": "https://financialaid.berkeley.edu/calculator",
        "financial_aid_office": "https://financialaid.berkeley.edu",
        "fafsa_school_code": "https://studentaid.gov/h/apply-for-aid/fafsa"
      },
      "deadlines": [
        {
          "label": "FAFSA Priority Filing",
          "date_iso": "2025-03-02",
          "category": "aid"
        },
        {
          "label": "First-Year Application",
          "date_iso": "2025-11-30",
          "category": "application"
        }
      ],
      "playbook": [
        {
          "order": 1,
          "title": "Estimate your real price before you apply",
          "detail": "Run the net price calculator with family tax numbers.",
          "url": "https://financialaid.berkeley.edu/calculator",
          "status": "action"
        },
        {
          "order": 2,
          "title": "Get the application fee waived",
          "detail": "Check institutional criteria or request a fee waiver code.",
          "url": "https://admissions.berkeley.edu/apply/fee-waiver",
          "status": "action"
        },
        {
          "order": 3,
          "title": "Submit the application before the earliest deadline you can meet",
          "detail": "Institutional scholarships often have earlier priority deadlines than regular admission.",
          "url": "https://admissions.berkeley.edu/apply",
          "deadline": "2025-11-30",
          "status": "action"
        },
        {
          "order": 4,
          "title": "File the FAFSA with this school code on day one",
          "detail": "Use federal school code 001312.",
          "url": "https://studentaid.gov/h/apply-for-aid/fafsa",
          "deadline": "2025-03-02",
          "status": "action"
        }
      ],
      "gaps": [
        "Emergency aid grant process unverified"
      ]
    }
  ],
  "national_programs": [],
  "national_deadlines": []
}
```

---

## 3. Frontend Integration Guidelines

When building the UI (React/Vue/Mobile), render these 5 elements for each school:

### 1. Match Score & "Why" Badges
- Display `match.score` (0–100).
- Render `match.why` as explanation badges or bullet points so students understand *why* this school ranked high (e.g. *"Grants and net-price generosity: 88%"*).

### 2. Action Buttons (Links)
- **Apply Online**: Render `match.links.application_portal` as the primary application button.
- **Request Fee Waiver**: Render `match.links.application_fee_waiver` as a secondary button or badge so students do not pay out-of-pocket application fees.
- **Estimate Cost**: Link `match.links.net_price_calculator`.

### 3. Ordered Playbook Checklist
Render `match.playbook` as an interactive checklist:
- Each step contains `order`, `title`, `detail`, and optional `url` and `deadline`.
- Allow the student to check off completed steps.

### 4. Application & Aid Deadlines
- Render `match.deadlines` grouped by `category` (`application` vs `aid`).
- Highlight dates approaching within 30 days.

### 5. Transparency & Provenance (Gaps)
- Render `match.gaps` in a collapsible or warning drawer (e.g. *"3 items unverified for this campus"*).
- Showing what is verified versus unverified is load-bearing for trust.

---

## 4. Frontend TypeScript Types

```typescript
export type StudentProfile =
  | "first_generation"
  | "student_with_disability"
  | "international_stem";

export interface SearchRequest {
  profile?: StudentProfile;
  q?: string;
  state?: string;
  control?: "public" | "private_nonprofit" | "private_for_profit";
  level?: "undergraduate" | "graduate";
  stem_only?: boolean;
  max_net_price?: number;
  min_aid_generosity?: number;
  limit?: number;
  offset?: number;
}

export interface WhySignal {
  signal: string;
  label: string;
  value: number;
  weight: number;
}

export interface Deadline {
  label: string;
  date_iso?: string;
  date_text?: string;
  category: "application" | "aid" | "scholarship" | "other";
}

export interface PlaybookStep {
  order: number;
  title: string;
  detail: string;
  url?: string;
  deadline?: string;
  status: "action" | "verify" | "done";
}

export interface SchoolMatch {
  institution: {
    unitid: number;
    name: string;
    city: string;
    state_abbr: string;
    control: string;
    avg_net_price?: number;
    cost_attending?: number;
    url_homepage?: string;
  };
  score: number;
  why: WhySignal[];
  links: Record<string, string>;
  deadlines: Deadline[];
  playbook: PlaybookStep[];
  gaps: string[];
}

export interface SearchReport {
  profile?: StudentProfile;
  count: number;
  universe_size: number;
  results: SchoolMatch[];
}
```
