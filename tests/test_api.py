"""End-to-end: the SRA facade, the CLI handlers, and the seed bundle round-trip."""

from __future__ import annotations

import gzip
import json
import tempfile
from pathlib import Path

import pytest

from sra_schools import SRA
from sra_schools.api import get_sra
from sra_schools.cli import main
from sra_schools.config import Settings
from sra_schools.db.cache import PageCache
from sra_schools.extract.fetchers import PageResult
from sra_schools.extract.rules import Finding
from sra_schools.models import SearchQuery
from tests.conftest import CannedFetcher, INSTITUTION_ROWS


@pytest.fixture
def sra(tmp_path):
    instance = SRA(Settings.from_env(home=tmp_path / "home", offline=True))
    yield instance
    instance.db.close()


def _open_sra(tmp_path):
    return SRA(Settings.from_env(home=tmp_path / "home", offline=True))


def test_status_reports_counts(sra):
    payload = sra.status()
    assert payload["institutions"] == 0
    assert "cache" in payload and "query_cache" in payload
    assert "profiles" in payload


def test_search_and_school_endpoints(sra):
    sra.repo.upsert_institutions(INSTITUTION_ROWS)
    report = sra.search(profile="first_generation", limit=5)
    assert report.count >= 1
    top_unitid = report.matches[0].unitid
    match = sra.school(top_unitid, profile="first_generation")
    assert match is not None and match.institution.unitid == top_unitid
    assert match.playbook


def test_school_by_name_and_opeid(sra):
    sra.repo.upsert_institutions(INSTITUTION_ROWS)
    assert sra.school("State University, There") is not None
    assert sra.school("100002") is not None
    assert sra.school("zzzznope") is None


def test_programs_list_filters_to_a_profile(sra):
    from sra_schools.models import AidProgram
    sra.repo.upsert_program(AidProgram(program_id="g1", name="Grant 1", official_url="https://x.org/1",
                                         kind="scholarship", needs=["undergraduate_scholarship"],
                                         levels=["undergraduate"], citizenship=["any"]))
    sra.repo.upsert_program(AidProgram(program_id="g2", name="Grant 2", official_url="https://x.org/2",
                                         kind="assistantship", needs=["fully_funded_degree"],
                                         levels=["graduate"], citizenship=["any"]))
    programs = sra.programs("first_generation")
    assert {p.program_id for p in programs} == {"g1"}


def test_describe_renders_markdown(sra):
    assert "# Cache status" in sra.describe()


def test_search_json_is_serializable(sra):
    sra.repo.upsert_institutions(INSTITUTION_ROWS)
    report = sra.search(profile="first_generation", limit=3)
    data = json.loads(report.to_json())
    assert data["count"] == report.count
    assert data["results"][0]["institution"]["name"]


def test_cli_status_is_read_only(sra, monkeypatch, capsys):
    sra.repo.upsert_institutions(INSTITUTION_ROWS)
    rc = main(["--home", str(sra.settings.home), "status"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "institutions" in out


def test_cli_search_rejects_unknown_profile(capsys):
    rc = main(["search", "not-a-real-profile"])
    assert rc == 2


def test_cli_topics_lists_every_topic(capsys):
    rc = main(["topics"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "fafsa_school_code" in out and "net_price_calculator" in out


# ---------------------------------------------------------------- seed bundle
def test_seed_bundle_round_trips(tmp_path):
    src = _open_sra(tmp_path / "a")
    src.repo.upsert_institutions(INSTITUTION_ROWS)
    url = "https://state.example.edu/aid"
    src.repo.add_facts(100001, url, [
        Finding(topic="fafsa_school_code", value_text="001234", evidence="fafsa",
                confidence=0.9, url=url, observed_at="2026-09-01", expires_at="2027-09-01"),
        Finding(topic="net_price_calculator", value_text="https://state.example.edu/npc",
                evidence="npc", confidence=0.8, url=url, observed_at="2026-09-01",
                expires_at="2027-09-01"),
    ], version="test")
    src.pages.put(url, status=200, body="body", ttl_seconds=3600)
    bundle = tmp_path / "seed.json.gz"
    outcome = src.seed_export(bundle, profiles=["first_generation"])
    assert outcome["institutions"] == 3 and Path(bundle).exists()

    dest = _open_sra(tmp_path / "b")
    imported = dest.seed_import(bundle)
    assert imported["counts"]["facts"] == 2
    assert dest.repo.facts_by_topic(100001)["fafsa_school_code"][0].value_text == "001234"
    assert dest.search(profile="first_generation", limit=5).count >= 1


def test_seed_bundle_is_valid_gzipped_json(tmp_path):
    sra = _open_sra(tmp_path / "a")
    sra.repo.upsert_institutions(INSTITUTION_ROWS)
    from sra_schools.extract.rules import Finding
    sra.repo.add_facts(100001, "https://state.example.edu/aid", [
        Finding(topic="fafsa_school_code", value_text="001234", evidence="fafsa",
                confidence=0.9, url="https://state.example.edu/aid",
                observed_at="2026-09-01", expires_at="2027-09-01"),
    ], version="test")
    bundle = tmp_path / "seed.json.gz"
    sra.seed_export(bundle)
    with gzip.open(bundle, "rt", encoding="utf-8") as handle:
        payload = json.load(handle)
    assert payload["bundle_version"] and "institutions" in payload and "facts" in payload


# ------------------------------------------------------------ offline fetch path
def test_offline_fetcher_never_touches_the_network(tmp_path, repo):
    from sra_schools.extract.fetchers import OfflineFetcher
    fetcher = OfflineFetcher()
    results = fetcher.fetch(["https://example.org/x"])
    assert all(r.error == "offline: no fetcher configured" for r in results)


def test_purge_expired_drops_stale_pages(tmp_path, repo):
    cache = PageCache(repo.db)
    cache.put("https://x.org/old", status=200, body="x", ttl_seconds=60)
    cache.db.execute("UPDATE web_pages SET expires_at = '2020-01-01T00:00:00+00:00' WHERE url = ?",
                     ("https://x.org/old",))
    assert cache.purge_expired() >= 1


def test_shared_singleton_is_reused(tmp_path):
    first = get_sra(home=tmp_path / "shared")
    second = get_sra(home=tmp_path / "shared")
    assert first is second
    SRA.reset()
    third = get_sra(home=tmp_path / "shared")
    assert third is not first
