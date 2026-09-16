"""Programme catalogue: validation, needs/level/citizenship filtering, verdicts."""

from __future__ import annotations

import pytest

from sra_schools.ingest.programs import (
    LoadResult,
    ProgramLoader,
    apply_verdicts,
    dns_verdicts,
    verify_urls,
)
from sra_schools.models import AidProgram
from sra_schools.taxonomy import Level
from tests.conftest import CannedFetcher


def _sample(**overrides):
    base = {
        "program_id": "test-grant",
        "name": "Test Grant",
        "provider": "Example Foundation",
        "official_url": "https://example.org/grant",
        "kind": "scholarship",
        "levels": ["undergraduate"],
        "citizenship": ["us_citizen", "permanent_resident"],
        "needs": ["undergraduate_scholarship"],
        "eligibility": ["GPA 3.0+"],
        "apply_steps": ["Submit by March 1"],
        "how_to_win": ["Tell a specific story"],
        "deadlines": [{"label": "Round 1", "date": "2026-11-01", "category": "scholarship"}],
        "confidence": 0.8,
        "verified_at": "2026-09-15",
    }
    base.update(overrides)
    return base


def test_parse_record_accepts_a_valid_record():
    program = ProgramLoader.parse_record(_sample())
    assert program.program_id == "test-grant"
    assert program.levels == ["undergraduate"]
    assert "undergraduate_scholarship" in program.needs


def test_parse_record_derives_needs_when_absent():
    program = ProgramLoader.parse_record(_sample(needs=[]))
    assert "undergraduate_scholarship" in program.needs


def test_parse_record_requires_an_official_url():
    with pytest.raises(ValueError):
        ProgramLoader.parse_record(_sample(official_url=""))


def test_parse_record_rejects_unknown_needs():
    with pytest.raises(ValueError):
        ProgramLoader.parse_record(_sample(needs=["time_travel_grant"], kind=None))


def test_load_files_returns_summary_and_persists(tmp_path, db, repo):
    path = tmp_path / "seed.json"
    path.write_text(json.dumps([_sample(), _sample(program_id="second", name="Second",
                                                  official_url="https://example.org/second")]))
    result = ProgramLoader(repo).load_files([path])
    assert isinstance(result, LoadResult) and result.programs and not result.rejected
    assert repo.db.count("aid_programs") == 2


def test_programmes_are_filtered_by_level_citizenship_needs(db, repo):
    repo.upsert_program(AidProgram(program_id="ug", name="UG", official_url="https://x.org/a",
                                     kind="scholarship", levels=["undergraduate"],
                                     needs=["undergraduate_scholarship"],
                                     citizenship=["us_citizen"]))
    repo.upsert_program(AidProgram(program_id="grad", name="Grad", official_url="https://x.org/b",
                                      kind="assistantship", levels=["graduate"],
                                      needs=["fully_funded_degree"], citizenship=["any"]))
    repo.upsert_program(AidProgram(program_id="intl-only", name="Intl", official_url="https://x.org/c",
                                      kind="scholarship", levels=["graduate"],
                                      needs=["fully_funded_degree"], citizenship=["international"]))
    undergraduate = repo.programs(level="undergraduate")
    assert {p.program_id for p in undergraduate} == {"ug"}
    grad_any = repo.programs(level="graduate", citizenship=["international", "any"])
    assert {p.program_id for p in grad_any} >= {"grad", "intl-only"}


def test_apply_verdicts_retires_dead_official_urls(db, repo):
    repo.upsert_program(AidProgram(program_id="alive", name="Alive", official_url="https://example.org/a",
                                      kind="scholarship", needs=["undergraduate_scholarship"],
                                      levels=["undergraduate"]))
    repo.upsert_program(AidProgram(program_id="dead", name="Dead", official_url="https://example.org/dead",
                                      kind="scholarship", needs=["undergraduate_scholarship"],
                                      levels=["undergraduate"]))
    verdicts = {
        "https://example.org/a": {"ok": True, "verdict": "ok", "status": 200, "chars": 5000},
        "https://example.org/dead": {"ok": False, "verdict": "dead", "status": 404},
    }
    outcome = apply_verdicts(repo, verdicts)
    assert "dead" in outcome["retired"]
    assert repo.get_program("dead").active == 0
    assert repo.get_program("alive").active == 1


def test_apply_verdicts_keeps_blocked_programmes_active(db, repo):
    repo.upsert_program(AidProgram(program_id="blocked", name="Blocked", official_url="https://example.org/b",
                                      kind="scholarship", needs=["undergraduate_scholarship"],
                                      levels=["undergraduate"]))
    outcome = apply_verdicts(repo, {"https://example.org/b": {"ok": False, "verdict": "blocked",
                                                                "status": 403}})
    assert "blocked" not in outcome["retired"]
    assert repo.get_program("blocked").verification_status == "blocked"


def test_dns_verdicts_flags_unresolvable_hosts():
    verdicts = dns_verdicts(["https://this-host-is-impossible-xyz.test/grant",
                             "https://example.org/grant"])
    assert any(v.verdict == "dead" for v in verdicts.values())
    assert any(v.verdict == "resolves" for v in verdicts.values())


def test_verify_urls_uses_the_blocked_vs_dead_distinction():
    fetcher = CannedFetcher({
        "https://ok.org/": type("P", (), {"url": "https://ok.org/", "status": 200,
                                           "text": "x" * 5000, "error": None, "not_modified": False, "chars": 5000})(),
        "https://blocked.org/": type("P", (), {"url": "https://blocked.org/", "status": 403,
                                                "text": "", "error": "HTTP 403", "not_modified": False, "chars": 0})(),
    })
    result = verify_urls(["https://ok.org/", "https://blocked.org/"], fetcher)
    assert result["https://ok.org/"].verdict == "ok"
    assert result["https://blocked.org/"].verdict == "blocked"


def test_deadlines_are_normalised_to_iso_or_text():
    program = ProgramLoader.parse_record(_sample(deadlines=[
        {"label": "Annual", "date": "2026-11-01"},
        {"label": "Rolling", "deadline_text": "Open until filled"},
    ]))
    assert any(d.date_iso == "2026-11-01" for d in program.deadlines)
    assert any(d.date_text == "Open until filled" for d in program.deadlines)


def test_citizenship_enum_is_exposed():
    assert Level.UNDERGRADUATE.value == "undergraduate"


import json  # noqa: E402  (kept near related imports for readability)
