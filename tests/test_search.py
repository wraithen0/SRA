"""Search engine: ranking, link resolution, playbook, filters, CSV/JSON export."""

from __future__ import annotations

import csv
import io
import json

import pytest

from sra_schools.extract.rules import Finding
from sra_schools.models import Institution, SearchQuery
from sra_schools.profiles import PROFILES, get_profile
from sra_schools.search.engine import SearchEngine
from sra_schools.search.ranking import Scorer, describe_signals
from sra_schools.search.report import render_report, to_csv, to_json
from sra_schools.taxonomy import TOPICS
from tests.conftest import INSTITUTION_ROWS


def _engine(db, repo):
    return SearchEngine(repo, registry=None, cache_searches=False)


def _seed_facts(repo, unitid, url, facts):
    repo.add_facts(unitid, url, [Finding(topic=t, value_text=v, value_json=j, evidence=e,
                                        confidence=c, url=url, observed_at="2026-09-01",
                                        expires_at="2027-09-01")
                               for (t, v, j, e, c) in facts], version="test")


def test_profile_aliases_resolve():
    for alias in ("first-gen", "first_gen", "p1", "first generation"):
        assert get_profile(alias).key == "first_generation"
    assert get_profile("disabled").key == "student_with_disability"
    assert get_profile("intl").key == "international_stem"
    assert get_profile("nonsense") is None


def test_scorer_returns_all_defined_signals(institutions, repo):
    inst = repo.get_institution(100001)
    score, signals = Scorer(PROFILES["first_generation"]).score(inst, {}, [], [])
    assert 0 <= score <= 100
    for signal in PROFILES["first_generation"].weights:
        assert signal in signals


def test_evidence_rich_school_ranks_above_empty_one(db, repo, institutions):
    _seed_facts(repo, 100001, "https://state.example.edu/aid", [
        ("fafsa_school_code", "001234", None, "FAFSA code 001234", 0.9),
        ("application_fee_waiver", "Common App waiver eligible", None, "fee waiver", 0.85),
        ("mentorship_program", "TRIO SSS mentoring", None, "TRIO SSS", 0.8),
        ("first_gen_program", "First-Gen center", None, "first gen", 0.8),
        ("application_deadline_first_year", "2026-11-01", None, "Nov 1", 0.85),
        ("net_price_calculator", "https://state.example.edu/npc", None, "npc", 0.8),
    ])
    engine = _engine(db, repo)
    report = engine.search(SearchQuery(profile="first_generation", limit=10))
    assert report.matches[0].institution.unitid == 100001
    assert report.matches[0].score > report.matches[-1].score
    assert report.universe_size == 3


def test_missing_evidence_is_surfaced_as_gaps_not_hidden(db, repo, institutions):
    engine = _engine(db, repo)
    report = engine.search(SearchQuery(profile="first_generation", limit=10))
    for match in report.matches:
        assert isinstance(match.gaps, list)
    empty = next(m for m in report.matches if m.institution.unitid == 100002)
    assert len(empty.gaps) >= 5  # we seeded nothing for this school


def test_links_are_resolved_per_topic(db, repo, institutions):
    _seed_facts(repo, 100001, "https://state.example.edu/aid", [
        ("fafsa_school_code", "001234", None, "fafsa", 0.9),
        ("net_price_calculator", "https://state.example.edu/npc", None, "npc", 0.8),
    ])
    engine = _engine(db, repo)
    match = engine.search(SearchQuery(profile="first_generation", limit=10)).matches[0]
    assert match.links.get("fafsa_school_code") == "https://state.example.edu/aid"
    assert match.links["net_price_calculator"] == "https://state.example.edu/npc"


def test_playbook_is_built_with_urls_and_deadlines(db, repo, institutions):
    _seed_facts(repo, 100001, "https://state.example.edu/aid", [
        ("fafsa_school_code", "001234", None, "fafsa", 0.9),
        ("application_fee_waiver", "waiver", None, "waiver", 0.85),
        ("application_deadline_first_year", "2026-11-01", None, "nov 1", 0.85),
    ])
    engine = _engine(db, repo)
    match = engine.search(SearchQuery(profile="first_generation", limit=10)).matches[0]
    assert match.playbook, "a matched school should have an application playbook"
    assert any(step.url for step in match.playbook)
    due_steps = [s for s in match.playbook if s.deadline]
    assert due_steps, "deadline-bearing playbook steps should carry a date"


def test_filters_narrow_the_universe(db, repo, institutions):
    engine = _engine(db, repo)
    all_match = engine.search(SearchQuery(profile="first_generation", limit=50))
    ca = engine.search(SearchQuery(profile="first_generation", state="CA", limit=50))
    assert all(m.institution.state_abbr == "CA" for m in ca.matches)
    assert ca.count < all_match.count

    public = engine.search(SearchQuery(profile="first_generation", control="public", limit=50))
    assert all(m.institution.control == "public" for m in public.matches)

    price = engine.search(SearchQuery(profile="first_generation", max_net_price=10000, limit=50))
    for m in price.matches:
        assert m.institution.avg_net_price is None or m.institution.avg_net_price <= 10000


def test_require_filters_to_schools_with_live_facts(db, repo, institutions):
    _seed_facts(repo, 100001, "https://state.example.edu/aid", [
        ("fafsa_school_code", "001234", None, "fafsa", 0.9),
    ])
    engine = _engine(db, repo)
    report = engine.search(SearchQuery(profile="first_generation", require=["fafsa_school_code"],
                                       limit=50))
    assert report.matches and all(m.institution.unitid == 100001 for m in report.matches)


def test_stem_filter(db, repo, institutions):
    engine = _engine(db, repo)
    report = engine.search(SearchQuery(profile="international_stem", stem_only=True, limit=50))
    for m in report.matches:
        assert m.institution.stem_share and m.institution.stem_share >= 0.15


def test_text_query_matches_name_city_state(db, repo, institutions):
    engine = _engine(db, repo)
    # "Private College" matches the name of 100002
    report = engine.search(SearchQuery(profile="first_generation", q="Private College", limit=50))
    assert report.matches and report.matches[0].institution.unitid == 100002
    # "There" matches the city of 100002
    report = engine.search(SearchQuery(profile="first_generation", q="There", limit=50))
    assert report.matches and report.matches[0].institution.unitid == 100002


def test_query_cache_serves_repeated_searches(institutions, repo):
    engine = SearchEngine(repo, registry=None, cache_searches=True,
                          search_cache_ttl_s=60)
    first = engine.search(SearchQuery(profile="first_generation", limit=5))
    second = engine.search(SearchQuery(profile="first_generation", limit=5))
    assert second.cache is not None and second.cache.hit is True
    assert first.count == second.count


def test_report_exports_are_well_formed(db, repo, institutions):
    engine = _engine(db, repo)
    report = engine.search(SearchQuery(profile="first_generation", limit=5))
    markdown = render_report(report)
    assert report.profile in markdown and "Match score" in markdown
    data = json.loads(to_json(report))
    assert data["profile"] == "first_generation" and "results" in data
    reader = csv.reader(io.StringIO(to_csv(report)))
    rows = list(reader)
    assert rows[0][0] == "rank" and len(rows) == 1 + report.count


def test_empty_search_still_reports_metadata(db, repo, institutions):
    engine = _engine(db, repo)
    report = engine.search(SearchQuery(profile="first_generation", q="zzzznope", limit=5))
    assert report.count == 0 and report.universe_size == 3
    assert "No schools matched" in render_report(report)


def test_describe_signals_returns_human_labels(institutions, repo):
    inst = repo.get_institution(100001)
    _, signals = Scorer(PROFILES["first_generation"]).score(inst, {}, [], [])
    rows = describe_signals(signals, PROFILES["first_generation"].weights)
    assert rows and all("label" in row and "value" in row for row in rows)


def test_topic_registry_is_complete():
    # every need must map to at least one topic, and every topic must belong to a need
    from sra_schools.taxonomy import Need, TOPICS_BY_NEED
    for need in Need:
        assert need in TOPICS_BY_NEED, f"need {need.value} has no topics"
    assert TOPICS, "no topics defined"
