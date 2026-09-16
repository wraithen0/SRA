# SRA — Student Resource Architecture (Financial-Aid Intelligence)

US college and university discovery engine with **financial-aid and scholarship intelligence**, engineered specifically for three underserved student profiles:

| Profile Key | Target Audience | Primary Needs Addressed |
|---|---|---|
| `first_generation` | First-generation college students | Net price estimates, institutional grants, application-fee waivers, FAFSA codes & dates, TRIO/mentorship programs |
| `student_with_disability` | Students requiring academic or physical accommodations | Disability services office, accommodation processes, assistive tech funding, state vocational rehabilitation (VR) |
| `international_stem` | International students seeking STEM degrees | Need-based institutional aid, tuition waivers, graduate funding (RA/TA), CSS Profile requirements, CPT/OPT guidance |

Instead of querying live websites on every user request, SRA operates **cache-first from local SQLite storage**. It returns ranked institutions with match scores, ranked "why" signals, official application and fee-waiver links, key deadlines, matched funding programs, a step-by-step action playbook, and explicit unverified gaps.

---

## 1. Quick Start

### Python Embedded Mode (Zero External Runtime Dependencies)
The core library runs entirely on standard Python 3.10+ with zero third-party dependencies required.

```bash
# Clone and install in development mode
pip install -e .

# 1. Build the federal institution universe + seed program catalogue
sra-schools build

# 2. Search for colleges ranked for first-generation students in California
sra-schools search first_generation --state CA --limit 5
```

### HTTP Sidecar Mode (For Any Frontend or Backend Language)
Install optional HTTP dependencies (`fastapi` and `uvicorn`):

```bash
pip install -e ".[server]"

# Start the sidecar API service on port 8000
uvicorn sra_schools.server:app --port 8000 --reload
```

---

## 2. Core Architecture

```
sra_schools/
├── api.py           # SRA - Programmatic entry point (search, school, enrich, build, status)
├── config.py        # Settings and environment configuration (SRA_*)
├── models.py        # Domain dataclasses: Institution, Fact, Deadline, AidProgram, SchoolMatch, SearchReport
├── taxonomy.py      # Needs, Topics, and Freshness policies (50+ tracked signals)
├── profiles.py      # Profile specifications: topic weights, filters, and playbook blueprints
├── sources.py       # Curated registry of trusted sources and campus URL patterns
├── db/
│   ├── schema.sql   # SQLite schema (institutions, web_pages, facts, deadlines, aid_programs, query_cache)
│   ├── database.py  # Thread-safe SQLite connection with WAL mode and transaction managers
│   ├── repository.py# Typed queries, bulk upserts, and candidate ranking pre-sorts
│   └── cache.py     # PageCache (HTTP ETag / Last-Modified tracking) and QueryCache
├── extract/
│   ├── rules.py     # Deterministic regex & heuristic extractor (fees, deadlines, FAFSA/CSS codes)
│   ├── fetchers.py  # Transport layer: TinyFish API (for JS-rendered pages), Direct HTTP, or Offline
│   └── pipeline.py  # Budget-bounded crawl coordinator
├── ingest/
│   ├── scorecard.py # Federal College Scorecard CSV streaming and column normalization
│   ├── programs.py  # Curated aid programs parser (data/programs/*.json)
│   └── seed.py      # Portable .json.gz cache bundle exporter and importer
└── server.py        # FastAPI service exposing full REST endpoints
```

---

## 3. Data Model & Response Contract

Every search returns a standardized, transparent `SearchReport`:

```json
{
  "profile": "first_generation",
  "count": 1,
  "universe_size": 6243,
  "cache": {
    "hit": true,
    "fingerprint": "7f8b9...c3"
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
      "score": 88.5,
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
          "detail": "Check eligibility criteria or request a waiver code.",
          "url": "https://admissions.berkeley.edu/apply/fee-waiver",
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

## 4. CLI Usage

```bash
# Search institutions by profile
sra-schools search first_generation --state CA --limit 10

# Search with filters and output JSON
sra-schools search international_stem --max-net-price 25000 -f json

# Inspect full profile intelligence for a specific school (by UnitID or Name)
sra-schools school 110635 --profile first_generation
sra-schools school "Harvard" --profile international_stem

# List matching national & institutional aid programs
sra-schools programs --profile student_with_disability

# Check cache health, database size, and topic coverage
sra-schools status
```

---

## 5. Configuration & Environment Variables

| Variable | Default | Description |
|---|---|---|
| `SRA_HOME` | `~/.cache/sra-schools` | Directory holding cache databases and downloads |
| `SRA_DB` | `$SRA_HOME/sra_cache.db` | Explicit SQLite database file path |
| `SRA_OFFLINE` | `0` | If `1`, completely disables all outbound HTTP requests |
| `TINYFISH_API_KEY`| `None` | Optional API key for scraping JS-heavy or WAF-protected pages |
| `SRA_MAX_PAGES_PER_RUN` | `200` | Fetch budget cap for `enrich` and `refresh` operations |
| `SRA_SEARCH_CACHE_TTL` | `21600` (6 hrs) | Query cache TTL in seconds |
