"""Shared fixtures: a throwaway cache and a canned fetcher (no network, ever)."""

from __future__ import annotations

import pytest

from sra_schools.api import SRA
from sra_schools.config import Settings
from sra_schools.db.cache import PageCache
from sra_schools.db.database import Database
from sra_schools.db.repository import Repository
from sra_schools.extract.fetchers import PageResult


@pytest.fixture
def db(tmp_path):
    handle = Database(tmp_path / "sra-test.sqlite")
    handle.migrate()
    yield handle
    handle.close()


@pytest.fixture
def repo(db):
    return Repository(db)


@pytest.fixture
def cache(db):
    return PageCache(db)


@pytest.fixture
def sra(tmp_path):
    """An offline SRA on its own database (never the shared singleton)."""
    instance = SRA(Settings.from_env(home=tmp_path / "home", offline=True))
    yield instance
    instance.db.close()


INSTITUTION_ROWS = [
    {
        "unitid": 100001, "name": "State University, Here", "city": "Here", "state_abbr": "CA",
        "url_homepage": "https://state.example.edu/", "control": "public", "preddeg": "4_year",
        "highdeg": "graduates", "avg_net_price": 6000, "cost_attending": 25000,
        "pct_pell": 0.55, "first_gen_pct": 0.62, "stem_share": 0.31,
        "international_share": 0.04, "grad_rate_150": 0.61, "enrollment_undergrad": 18000,
        "enrollment_graduate": 4000, "enrollment_total": 22000, "tuition_in_state": 7000,
        "median_debt_undergrad": 15000, "currently_operating": 1,
    },
    {
        "unitid": 100002, "name": "Private College, There", "city": "There", "state_abbr": "NY",
        "url_homepage": "https://private.example.edu/", "control": "private_nonprofit",
        "preddeg": "4_year", "highdeg": "bachelors", "avg_net_price": 34000,
        "cost_attending": 60000, "pct_pell": 0.12, "first_gen_pct": 0.18,
        "stem_share": 0.12, "international_share": 0.22, "grad_rate_150": 0.8,
        "enrollment_undergrad": 2200, "enrollment_total": 2200, "tuition_in_state": 58000,
        "currently_operating": 1,
    },
    {
        "unitid": 100003, "name": "Tiny For Profit Institute", "city": "Nowhere",
        "state_abbr": "NV", "url_homepage": "https://tiny.example.edu/",
        "control": "private_for_profit", "preddeg": "2_year", "highdeg": "certificate",
        "avg_net_price": 0, "cost_attending": 20000, "currently_operating": 1,
    },
]


@pytest.fixture
def institutions(repo):
    repo.upsert_institutions(INSTITUTION_ROWS, dataset_version="test-1")
    return [row["unitid"] for row in INSTITUTION_ROWS]


class CannedFetcher:
    """A fetcher that serves a fixed url -> page map and records every request."""

    name = "canned"

    def __init__(self, pages: dict[str, PageResult] | None = None) -> None:
        self.pages = pages or {}
        self.calls: list[list[str]] = []

    @property
    def requested_urls(self) -> list[str]:
        return [url for batch in self.calls for url in batch]

    def fetch(self, urls, *, ttl_seconds=None, purpose=None, validators=None):  # noqa: ANN001
        self.calls.append(list(urls))
        out: list[PageResult] = []
        for url in urls:
            page = self.pages.get(url)
            if page is None:
                out.append(PageResult(url=url, status=404, error="HTTP 404"))
                continue
            etag, last_modified = (validators or {}).get(url, (None, None))
            if etag or last_modified:
                out.append(PageResult(url=url, status=304, not_modified=True))
            else:
                out.append(page)
        return out


@pytest.fixture
def aid_page() -> str:
    """A synthetic but realistic campus financial-aid page."""
    return """
# Office of Financial Aid and Scholarships

The FAFSA federal school code for State University is 001234. Complete the FAFSA by the
priority filing deadline of March 2, 2027 to receive the maximum University Grant.

Federal Work-Study jobs are available; students are eligible for the Federal Work Study
program based on need.

## Scholarships
Merit scholarships are awarded with automatic consideration - no separate application is
required for the President's Scholarship of up to $12,000 per year.

## Paying your bill
Use the [Net Price Calculator](https://state.example.edu/aid/net-price-calculator) to
estimate your cost before you apply.

## Contact
financialaid@state.example.edu · (555) 201-4400

---
Follow us on Facebook and YouTube · Privacy Statement · All rights reserved
"""


@pytest.fixture
def admissions_page() -> str:
    return """
# Apply to State University

Application deadline for first-year admission: Early Decision November 1, 2026; Regular
Decision January 15, 2027. Admission application fee: $70.

Applicants may request an [application fee waiver](https://state.example.edu/apply/waiver)
if you participated in TRIO Upward Bound, received free or reduced lunch, or are a
first-generation college student.

We are test-optional for fall 2027 entry.

## Students with disabilities
The Disability Support Services office handles accommodation requests. To request
accommodations, submit documentation of a current diagnosis from a qualified professional.
Services include extended test time, note-taking support, ASL interpreting, captioning
and assistive technology lab access.
"""


@pytest.fixture
def intl_page() -> str:
    return """
# International Students

The Office of International Student Services issues the Form I-20 for F-1 students.
Newly admitted students must submit a Certification of Finance and a bank statement showing
one year of expenses before we can release your I-20.

International students are not eligible for federal financial aid and must demonstrate
external funding. TOEFL iBT 80 or IELTS 6.5 is required for admission.

Graduate students on assistantships receive a tuition waiver and a stipend of $28,000.
Students may apply for CPT and OPT; the university supports the 24-month STEM OPT
extension. Undergraduate research opportunities and REU sites are listed by the office of
undergraduate research.
"""
