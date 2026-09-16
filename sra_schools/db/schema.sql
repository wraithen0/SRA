-- sra-schools cache schema
-- Three layers of caching:
--   1. institutions      : the federal backbone (IPEDS UNITID / College Scorecard)
--   2. web_pages         : raw HTTP/TinyFish responses, validator-aware, TTL-aware
--   3. facts/deadlines   : derived, keyed by content hash so an unchanged page never
--                          gets re-parsed (and never re-bills an LLM)
--   4. query_cache       : whole profile searches, so repeated API hits are O(1)

PRAGMA journal_mode = WAL;

CREATE TABLE IF NOT EXISTS meta (
    key         TEXT PRIMARY KEY,
    value       TEXT NOT NULL,
    updated_at  TEXT NOT NULL
);

-- ---------------------------------------------------------------- institution
CREATE TABLE IF NOT EXISTS institutions (
    unitid              INTEGER PRIMARY KEY,          -- IPEDS UnitID (stable federal id)
    opeid               TEXT,                         -- OPEID (Title IV)
    opeid6              TEXT,
    name                TEXT NOT NULL,
    slug                TEXT,
    city                TEXT,
    state_abbr          TEXT,
    state_name          TEXT,
    zip                 TEXT,
    county              TEXT,
    lat                 REAL,
    lon                 REAL,
    url_homepage        TEXT,
    url_net_price_calc  TEXT,
    control             TEXT,                         -- public | private_nonprofit | private_for_profit
    preddeg             TEXT,                         -- 2-year | 4-year | less-than-2-year
    highdeg             TEXT,                         -- certificate | associates | bachelors | graduates
    carnegie            TEXT,
    locale              TEXT,
    region              TEXT,
    accreditor          TEXT,
    hbcu                INTEGER DEFAULT 0,
    pbi                 INTEGER DEFAULT 0,
    aanapii             INTEGER DEFAULT 0,
    tribally_controlled INTEGER DEFAULT 0,
    women_only          INTEGER DEFAULT 0,
    men_only            INTEGER DEFAULT 0,
    religious_affiliation TEXT,
    distance_only       INTEGER DEFAULT 0,
    year_round          INTEGER DEFAULT 0,
    graduate_only       INTEGER DEFAULT 0,
    currently_operating INTEGER DEFAULT 1,
    -- size / selectivity / cost / aid (federal data, refreshed with the dataset)
    enrollment_undergrad REAL,
    enrollment_graduate  REAL,
    enrollment_total     REAL,
    admissions_rate      REAL,
    open_admissions      INTEGER,
    sat_mid              REAL,
    act_mid              REAL,
    tuition_in_state     REAL,
    tuition_out_state    REAL,
    cost_attending       REAL,
    avg_net_price        REAL,
    median_family_income REAL,
    pct_pell             REAL,
    median_debt_undergrad REAL,
    median_debt_graduate REAL,
    median_earnings      REAL,
    grad_rate_150        REAL,
    retention_ft         REAL,
    first_gen_pct        REAL,                        -- PAR_ED_PCT_1STGEN
    parent_ed_pct_hs     REAL,
    stem_share           REAL,                        -- max of the STEM CIP families
    stem_share_exact     REAL,                        -- PCIP26 physical sciences
    international_share  REAL,                        -- UGDS_NRA non-resident alien share
    pct_grad_prof        REAL,
    application_count    REAL,
    -- bookkeeping
    dataset_version      TEXT,
    seeded               INTEGER DEFAULT 0,           -- included in the shipped seed
    first_seen_at        TEXT,
    updated_at           TEXT,
    next_due_at          TEXT                         -- earliest topic expiry (refresh queue)
);
CREATE INDEX IF NOT EXISTS idx_inst_state   ON institutions(state_abbr);
CREATE INDEX IF NOT EXISTS idx_inst_control ON institutions(control);
CREATE INDEX IF NOT EXISTS idx_inst_name    ON institutions(name);
CREATE INDEX IF NOT EXISTS idx_inst_due     ON institutions(next_due_at);
CREATE INDEX IF NOT EXISTS idx_inst_seed    ON institutions(seeded);

-- ------------------------------------------------------------------ page cache
CREATE TABLE IF NOT EXISTS web_pages (
    url             TEXT PRIMARY KEY,
    url_hash        TEXT NOT NULL,
    institution_unitid INTEGER,
    topic           TEXT,                             -- primary topic this page was fetched for
    final_url       TEXT,
    title           TEXT,
    status          INTEGER,
    error           TEXT,
    content_type    TEXT,
    etag            TEXT,
    last_modified   TEXT,
    content_sha256  TEXT,
    body_gzip       BLOB,
    body_chars      INTEGER,
    attempts        INTEGER DEFAULT 1,
    fetched_at      TEXT NOT NULL,
    ttl_seconds     INTEGER NOT NULL,
    expires_at      TEXT NOT NULL,
    last_http_status TEXT
);
CREATE INDEX IF NOT EXISTS idx_pages_expiry ON web_pages(expires_at);
CREATE INDEX IF NOT EXISTS idx_pages_inst   ON web_pages(institution_unitid);

-- ---------------------------------------------------- link discovery per school
CREATE TABLE IF NOT EXISTS links (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    unitid        INTEGER,
    url           TEXT NOT NULL,
    anchor_text   TEXT,
    topic         TEXT,
    kind          TEXT,                                -- official | candidate | discovery
    score         REAL DEFAULT 0,
    source_url    TEXT,
    first_seen_at TEXT,
    last_seen_at  TEXT,
    http_status   INTEGER,
    UNIQUE (unitid, url, topic)
);
CREATE INDEX IF NOT EXISTS idx_links_unit ON links(unitid, topic);

-- -------------------------------------------------------------------- facts
CREATE TABLE IF NOT EXISTS facts (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    unitid        INTEGER NOT NULL,
    topic         TEXT NOT NULL,                        -- taxonomy.Topic.key
    value_text    TEXT,
    value_json    TEXT,                                 -- list/dict payloads
    value_date    TEXT,                                 -- ISO date if parseable
    value_num     REAL,
    value_bool    INTEGER,
    evidence      TEXT,                                 -- verbatim snippet that produced it
    url           TEXT NOT NULL,                        -- source page
    extractor     TEXT NOT NULL,                        -- rule | llm | dataset | curated | manual
    extractor_ver TEXT,
    confidence    REAL DEFAULT 0.6,
    observed_at   TEXT NOT NULL,
    expires_at    TEXT NOT NULL,
    superseded_at TEXT,
    UNIQUE (unitid, topic, url, extractor, evidence)
);
CREATE INDEX IF NOT EXISTS idx_facts_unit  ON facts(unitid, topic);
CREATE INDEX IF NOT EXISTS idx_facts_live  ON facts(superseded_at, expires_at);

-- ---------------------------------------------------------------- deadlines
CREATE TABLE IF NOT EXISTS deadlines (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    unitid       INTEGER,
    program_id   TEXT,                                  -- national programme deadline
    label        TEXT NOT NULL,
    date_iso     TEXT,                                  -- NULL when only text is known
    date_text    TEXT,
    category     TEXT,                                  -- application | aid | scholarship | visa | renewal
    recurring_annual INTEGER DEFAULT 0,
    url          TEXT,
    observed_at  TEXT,
    expires_at   TEXT,
    UNIQUE (unitid, program_id, label, date_iso, date_text)
);
CREATE INDEX IF NOT EXISTS idx_dead_unit ON deadlines(unitid, date_iso);
CREATE INDEX IF NOT EXISTS idx_dead_prog ON deadlines(program_id);

-- ----------------------------------------------------------- national catalog
CREATE TABLE IF NOT EXISTS aid_programs (
    program_id     TEXT PRIMARY KEY,
    name           TEXT NOT NULL,
    provider       TEXT,
    official_url   TEXT NOT NULL,
    apply_url      TEXT,
    kind           TEXT,
    levels         TEXT,          -- json
    citizenship    TEXT,          -- json
    needs          TEXT,          -- json
    profile_tags   TEXT,          -- json
    amount_text    TEXT,
    coverage_text  TEXT,
    stipend_text   TEXT,
    renewable      INTEGER,
    stem_eligible  INTEGER,
    disability_scope TEXT,        -- json
    eligibility    TEXT,          -- json bullets
    apply_steps    TEXT,          -- json ordered steps
    how_to_win     TEXT,          -- json tips
    documentation_required TEXT,
    work_auth_notes TEXT,
    state          TEXT,
    notes          TEXT,
    sources        TEXT,          -- json
    confidence     REAL,
    verified_at    TEXT,
    verification_status TEXT,               -- ok | blocked | dead | empty | pending
    verification_note   TEXT,
    active         INTEGER DEFAULT 1,
    updated_at     TEXT
);
CREATE INDEX IF NOT EXISTS idx_prog_profile ON aid_programs(kind);

-- ---------------------------------------------- programme <-> institution join
CREATE TABLE IF NOT EXISTS institution_programs (
    unitid      INTEGER NOT NULL,
    program_id  TEXT NOT NULL,
    relationship TEXT,            -- onsite_host | eligible_applicant | named_partner | required_for_aid
    evidence    TEXT,
    url         TEXT,
    observed_at TEXT,
    UNIQUE (unitid, program_id, relationship)
);

-- ------------------------------------------------- extraction short-circuit log
CREATE TABLE IF NOT EXISTS extractions (
    url            TEXT NOT NULL,
    content_sha256 TEXT NOT NULL,
    extractor      TEXT NOT NULL,
    extractor_ver  TEXT NOT NULL,
    facts_found    INTEGER,
    notes          TEXT,
    extracted_at   TEXT NOT NULL,
    PRIMARY KEY (url, content_sha256, extractor, extractor_ver)
);

-- ----------------------------------------------------- search-result cache
CREATE TABLE IF NOT EXISTS query_cache (
    fingerprint  TEXT PRIMARY KEY,   -- sha256(profile + filters + dataset epoch)
    profile      TEXT,
    params_json  TEXT,
    results_json TEXT,
    result_count INTEGER,
    created_at   TEXT NOT NULL,
    expires_at   TEXT NOT NULL,
    hit_count    INTEGER DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_qc_expiry ON query_cache(expires_at);

-- ------------------------------------------------------------- crawl ledger
CREATE TABLE IF NOT EXISTS crawl_runs (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    started_at    TEXT,
    finished_at   TEXT,
    trigger       TEXT,             -- build | refresh | enrich | manual
    query         TEXT,
    pages_planned INTEGER,
    pages_fetched INTEGER,
    pages_fresh   INTEGER,
    pages_revalidated INTEGER,
    pages_failed  INTEGER,
    facts_written INTEGER,
    llm_calls     INTEGER,
    error         TEXT
);

CREATE TABLE IF NOT EXISTS search_feedback_ignore (
    unitid INTEGER PRIMARY KEY, note TEXT, created_at TEXT
);

-- full-text over the institution universe + its fact summary line
CREATE VIRTUAL TABLE IF NOT EXISTS institutions_fts USING fts5(
    name, city, state_abbr, url_homepage, blurb, content=''
);
