"""Portable cache bundles: ``data/seed/sra-seed.json.gz``.

A fresh checkout should answer real searches without re-scraping anything. The
export side writes the enriched subset (institutions, facts, deadlines, links,
programmes, and page *validators* without bodies); the import side replays it into
SQLite. Bodies stay out of the bundle - they are the bulk of the cache and can be
re-fetched with an ETag, which is exactly what the validators enable.
"""

from __future__ import annotations

import gzip
import json
from datetime import datetime
from pathlib import Path
from typing import Any

from .. import util
from ..db.database import iso
from ..taxonomy import TOPICS
from ..util import fingerprint

BUNDLE_VERSION = "1"


def export_seed(
    sra: Any,  # noqa: ANN401 - avoids importing api.py in a cycle
    path: Path | str,
    *,
    profiles: list[str] | None = None,
    limit: int | None = None,
    include_pages: bool = True,
) -> dict[str, Any]:
    """Write the enriched part of the cache to a gzipped JSON bundle."""
    db = sra.db
    unitids = _units_for_export(db, profiles=profiles, limit=limit)
    if not unitids:
        raise RuntimeError("nothing enriched yet - run `sra-schools enrich` first")
    placeholders = ",".join("?" * len(unitids))
    institutions = [dict(row) for row in db.query(
        f"SELECT * FROM institutions WHERE unitid IN ({placeholders})", unitids)]
    for row in institutions:
        row["seeded"] = 1
    facts = [dict(row) for row in db.query(
        f"SELECT unitid, topic, value_text, value_json, value_date, value_num, value_bool, "
        f"evidence, url, extractor, extractor_ver, confidence, observed_at, expires_at "
        f"FROM facts WHERE superseded_at IS NULL AND unitid IN ({placeholders}) ORDER BY unitid, topic",
        unitids)]
    deadlines = [dict(row) for row in db.query(
        f"SELECT unitid, program_id, label, date_iso, date_text, category, recurring_annual, url, "
        f"observed_at, expires_at FROM deadlines WHERE unitid IN ({placeholders}) OR unitid IS NULL",
        unitids)]
    links = [dict(row) for row in db.query(
        f"SELECT unitid, url, anchor_text, topic, kind, score, source_url FROM links "
        f"WHERE unitid IN ({placeholders})", unitids)]
    programs = [dict(row) for row in db.query("SELECT * FROM aid_programs")]
    joins = [dict(row) for row in db.query(
        f"SELECT unitid, program_id, relationship, evidence, url FROM institution_programs "
        f"WHERE unitid IN ({placeholders})", unitids)]
    pages: list[dict[str, Any]] = []
    if include_pages:
        pages = [dict(row) for row in db.query(
            f"SELECT url, institution_unitid, topic, final_url, title, status, etag, last_modified, "
            f"content_sha256, fetched_at, ttl_seconds, expires_at FROM web_pages "
            f"WHERE institution_unitid IN ({placeholders})", unitids)]

    bundle = {
        "bundle_version": BUNDLE_VERSION,
        "meta": {
            "exported_at": iso(),
            "dataset_version": db.get_meta("dataset_version"),
            "sources_version": db.get_meta("sources_version"),
            "counts": {
                "institutions": len(institutions), "facts": len(facts),
                "deadlines": len(deadlines), "links": len(links), "programs": len(programs),
                "institution_programs": len(joins), "pages": len(pages),
            },
            "checksum": fingerprint({
                "f": [(f["unitid"], f["topic"], f.get("value_text")) for f in facts],
                "p": [p.get("program_id") for p in programs],
            }),
        },
        "institutions": institutions,
        "facts": facts,
        "deadlines": deadlines,
        "links": links,
        "programs": programs,
        "institution_programs": joins,
        "pages": pages,
    }
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    with gzip.open(target, "wt", encoding="utf-8") as handle:
        json.dump(bundle, handle, ensure_ascii=False, default=str, separators=(",", ":"))
    return {
        "institutions": len(institutions),
        "path": str(target),
        "bytes": target.stat().st_size,
        "counts": bundle["meta"]["counts"],
        "checksum": bundle["meta"]["checksum"],
    }


def import_seed(sra: Any, path: Path | str, *, only_if_empty: bool = False) -> dict[str, Any]:  # noqa: ANN401
    """Replay a bundle into SQLite. Idempotent: re-importing refreshes values."""
    source = Path(path)
    if not source.exists():
        raise FileNotFoundError(source)
    with gzip.open(source, "rt", encoding="utf-8") as handle:
        bundle = json.load(handle)
    if str(bundle.get("bundle_version")) != BUNDLE_VERSION:
        raise RuntimeError(f"unsupported bundle version {bundle.get('bundle_version')}")
    db = sra.db
    if only_if_empty and db.count("institutions") > 0:
        return {"skipped": True, "reason": "cache already populated"}

    now = iso()
    # Build the insert dynamically so the placeholder count always matches the tuple
    _inst_columns = [
        "unitid", "name", "city", "state_abbr", "zip", "lat", "lon", "url_homepage",
        "url_net_price_calc", "opeid", "opeid6", "control", "preddeg", "highdeg",
        "carnegie", "locale", "region", "accreditor", "hbcu", "pbi", "aanapii",
        "tribally_controlled", "women_only", "men_only", "religious_affiliation",
        "distance_only", "year_round", "graduate_only", "currently_operating",
        "enrollment_undergrad", "enrollment_graduate", "enrollment_total",
        "admissions_rate", "open_admissions", "sat_mid", "act_mid", "tuition_in_state",
        "tuition_out_state", "cost_attending", "avg_net_price", "median_family_income",
        "pct_pell", "median_debt_undergrad", "median_debt_graduate", "median_earnings",
        "grad_rate_150", "retention_ft", "first_gen_pct", "parent_ed_pct_hs", "stem_share",
        "stem_share_exact", "international_share", "pct_grad_prof", "application_count",
        "dataset_version", "seeded", "state_name", "first_seen_at", "updated_at",
    ]
    _inst_placeholders = ",".join("?" * len(_inst_columns))
    _inst_updates = ", ".join(
        f"{c}=excluded.{c}" for c in _inst_columns if c not in ("unitid", "first_seen_at")
    )
    with db.tx() as cur:
        cur.executemany(
            f"INSERT INTO institutions({','.join(_inst_columns)}) VALUES({_inst_placeholders}) "
            f"ON CONFLICT(unitid) DO UPDATE SET {_inst_updates}",
            [
                (
                    inst["unitid"], inst.get("name"), inst.get("city"), inst.get("state_abbr"),
                    inst.get("zip"), inst.get("lat"), inst.get("lon"), inst.get("url_homepage"),
                    inst.get("url_net_price_calc"), inst.get("opeid"), inst.get("opeid6"),
                    inst.get("control"), inst.get("preddeg"), inst.get("highdeg"),
                    inst.get("carnegie"), inst.get("locale"), inst.get("region"),
                    inst.get("accreditor"), _i(inst.get("hbcu")), _i(inst.get("pbi")),
                    _i(inst.get("aanapii")), _i(inst.get("tribally_controlled")),
                    _i(inst.get("women_only")), _i(inst.get("men_only")),
                    inst.get("religious_affiliation"), _i(inst.get("distance_only")),
                    _i(inst.get("year_round")), _i(inst.get("graduate_only")),
                    _i(inst.get("currently_operating"), 1), inst.get("enrollment_undergrad"),
                    inst.get("enrollment_graduate"), inst.get("enrollment_total"),
                    inst.get("admissions_rate"), _i(inst.get("open_admissions"), None),
                    inst.get("sat_mid"), inst.get("act_mid"), inst.get("tuition_in_state"),
                    inst.get("tuition_out_state"), inst.get("cost_attending"),
                    inst.get("avg_net_price"), inst.get("median_family_income"),
                    inst.get("pct_pell"), inst.get("median_debt_undergrad"),
                    inst.get("median_debt_graduate"), inst.get("median_earnings"),
                    inst.get("grad_rate_150"), inst.get("retention_ft"), inst.get("first_gen_pct"),
                    inst.get("parent_ed_pct_hs"), inst.get("stem_share"),
                    inst.get("stem_share_exact"), inst.get("international_share"),
                    inst.get("pct_grad_prof"), inst.get("application_count"),
                    inst.get("dataset_version"), 1, _state_name(inst.get("state_abbr")), now, now,
                )
                for inst in bundle.get("institutions", [])
            ],
        )
    written = {
        "facts": _insert_facts(db, bundle.get("facts", [])),
        "deadlines": _insert_deadlines(db, bundle.get("deadlines", [])),
        "links": _insert_links(db, bundle.get("links", [])),
        "programs": _insert_programs(db, bundle.get("programs", [])),
        "institution_programs": _insert_joins(db, bundle.get("institution_programs", [])),
        "pages": _insert_pages(db, bundle.get("pages", [])),
        "institutions": len(bundle.get("institutions", [])),
    }
    db.set_meta("dataset_version", bundle.get("meta", {}).get("dataset_version"))
    db.set_meta("seed_checksum", bundle.get("meta", {}).get("checksum"))
    db.set_meta("seed_imported_at", now)
    sra.bump_epoch()
    return {"counts": written, "checksum": bundle.get("meta", {}).get("checksum")}


# --------------------------------------------------------------------- inserts
def _i(value: Any, default: int | None = 0) -> int | None:  # noqa: ANN401
    if value is None:
        return default
    if isinstance(value, bool):
        return int(value)
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


_STATE_NAMES: dict[str, str] = {}


def _state_name(abbr: str | None) -> str | None:
    if not abbr:
        return None
    if not _STATE_NAMES:
        from .scorecard import _STATE_NAMES as names  # private by convention, reused deliberately

        _STATE_NAMES.update(names)
    return _STATE_NAMES.get(abbr.upper())


def _insert_facts(db: Any, rows: list[dict[str, Any]]) -> int:  # noqa: ANN401
    payload = [
        (
            r["unitid"], r["topic"], r.get("value_text"), r.get("value_json"),
            r.get("value_date"), r.get("value_num"), r.get("value_bool"), r.get("evidence"),
            r.get("url") or "", r.get("extractor") or "rule", r.get("extractor_ver") or "v1",
            float(r.get("confidence") or 0.6), r.get("observed_at") or iso(),
            r.get("expires_at") or iso(datetime.fromtimestamp(2**31 - 1)),
        )
        for r in rows if r.get("topic") in TOPIC_KEYS
    ]
    if not payload:
        return 0
    with db.tx() as cur:
        cur.executemany(
            "INSERT INTO facts(unitid, topic, value_text, value_json, value_date, value_num, "
            "value_bool, evidence, url, extractor, extractor_ver, confidence, observed_at, "
            "expires_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?) "
            "ON CONFLICT(unitid, topic, url, extractor, evidence) DO UPDATE SET "
            "value_text=excluded.value_text, value_json=excluded.value_json, "
            "value_date=excluded.value_date, value_num=excluded.value_num, "
            "value_bool=excluded.value_bool, confidence=excluded.confidence, "
            "expires_at=excluded.expires_at",
            payload,
        )
    return len(payload)


def _insert_deadlines(db: Any, rows: list[dict[str, Any]]) -> int:  # noqa: ANN401
    payload = [
        (r.get("unitid"), r.get("program_id"), r.get("label"), r.get("date_iso"),
         r.get("date_text"), r.get("category") or "application", _i(r.get("recurring_annual")),
         r.get("url"), r.get("observed_at") or iso(), r.get("expires_at"))
        for r in rows if r.get("label")
    ]
    if not payload:
        return 0
    with db.tx() as cur:
        cur.executemany(
            "INSERT INTO deadlines(unitid, program_id, label, date_iso, date_text, category, "
            "recurring_annual, url, observed_at, expires_at) VALUES(?,?,?,?,?,?,?,?,?,?) "
            "ON CONFLICT(unitid, program_id, label, date_iso, date_text) DO UPDATE SET "
            "category=excluded.category, url=excluded.url, expires_at=excluded.expires_at",
            payload,
        )
    return len(payload)


def _insert_links(db: Any, rows: list[dict[str, Any]]) -> int:  # noqa: ANN401
    payload = [
        (r.get("unitid"), r.get("url"), r.get("anchor_text"), r.get("topic"),
         r.get("kind") or "discovery", float(r.get("score") or 0.5), r.get("source_url"),
         iso(), iso())
        for r in rows if r.get("url")
    ]
    if not payload:
        return 0
    with db.tx() as cur:
        cur.executemany(
            "INSERT INTO links(unitid, url, anchor_text, topic, kind, score, source_url, "
            "first_seen_at, last_seen_at) VALUES(?,?,?,?,?,?,?,?,?) "
            "ON CONFLICT(unitid, url, topic) DO UPDATE SET score=excluded.score, "
            "anchor_text=excluded.anchor_text, last_seen_at=excluded.last_seen_at",
            payload,
        )
    return len(payload)


_PROGRAM_COLUMNS = [
    "program_id", "name", "provider", "official_url", "apply_url", "kind", "levels", "citizenship",
    "needs", "profile_tags", "amount_text", "coverage_text", "stipend_text", "renewable",
    "stem_eligible", "disability_scope", "eligibility", "apply_steps", "how_to_win",
    "documentation_required", "work_auth_notes", "state", "notes", "sources", "confidence",
    "verified_at", "active",
]


def _insert_programs(db: Any, rows: list[dict[str, Any]]) -> int:  # noqa: ANN401
    payload = [tuple(r.get(col) for col in _PROGRAM_COLUMNS) for r in rows
               if r.get("program_id") and r.get("official_url") and r.get("name")]
    if not payload:
        return 0
    sql = (
        f"INSERT INTO aid_programs({','.join(_PROGRAM_COLUMNS)}, updated_at) "
        f"VALUES({','.join('?' * (len(_PROGRAM_COLUMNS) + 1))}) "
        "ON CONFLICT(program_id) DO UPDATE SET "
        + ", ".join(f"{c}=excluded.{c}" for c in _PROGRAM_COLUMNS if c != "program_id")
    )
    with db.tx() as cur:
        cur.executemany(sql, [row + (iso(),) for row in payload])
    return len(payload)


def _insert_joins(db: Any, rows: list[dict[str, Any]]) -> int:  # noqa: ANN401
    payload = [(r["unitid"], r["program_id"], r.get("relationship") or "eligible_applicant",
                r.get("evidence"), r.get("url"), iso())
               for r in rows if r.get("unitid") and r.get("program_id")]
    if not payload:
        return 0
    with db.tx() as cur:
        cur.executemany(
            "INSERT INTO institution_programs(unitid, program_id, relationship, evidence, url, "
            "observed_at) VALUES(?,?,?,?,?,?) ON CONFLICT(unitid, program_id, relationship) "
            "DO UPDATE SET evidence=excluded.evidence, url=excluded.url",
            payload,
        )
    return len(payload)


def _insert_pages(db: Any, rows: list[dict[str, Any]]) -> int:  # noqa: ANN401
    """Validators only: a body-less page entry lets ``refresh`` send If-None-Match."""
    payload = [
        (r["url"], util.short_hash(r["url"]), r.get("institution_unitid"), r.get("topic"),
         r.get("final_url"), r.get("title"), r.get("status"), None, None, r.get("etag"),
         r.get("last_modified"), r.get("content_sha256"), None, 0, 0,
         r.get("fetched_at") or iso(), int(r.get("ttl_seconds") or 90 * 86400),
         r.get("expires_at") or iso(), "seed")
        for r in rows if r.get("url")
    ]
    if not payload:
        return 0
    with db.tx() as cur:
        cur.executemany(
            "INSERT OR REPLACE INTO web_pages(url, url_hash, institution_unitid, topic, final_url, "
            "title, status, error, content_type, etag, last_modified, content_sha256, body_gzip, "
            "body_chars, attempts, fetched_at, ttl_seconds, expires_at, last_http_status) "
            "VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            payload,
        )
    return len(payload)


def _units_for_export(db: Any, *, profiles: list[str] | None, limit: int | None) -> list[int]:  # noqa: ANN401
    """Institutions to include in a seed bundle.

    With a profile, every operating institution is a candidate (the profile's
    search will rank them); without one, fall back to only what is enriched.
    """
    if profiles:
        sql = "SELECT unitid FROM institutions WHERE COALESCE(currently_operating, 1) = 1 ORDER BY unitid"
        params: list[Any] = []
        if limit:
            sql += " LIMIT ?"
            params.append(int(limit))
        return [row[0] for row in db.query(sql, params)]
    # no profile: only institutions we have facts for
    sql = "SELECT DISTINCT unitid FROM facts WHERE superseded_at IS NULL ORDER BY unitid"
    params: list[Any] = []
    if limit:
        sql += " LIMIT ?"
        params.append(int(limit))
    return [row[0] for row in db.query(sql, params)]


def _profile_topics(profile: str) -> set[str]:
    from ..profiles import get_profile

    prof = get_profile(profile)
    if prof is None:
        return set()
    return {t for t in (*prof.required_topics, *prof.preferred_topics)}


TOPIC_KEYS = set(TOPICS)


def bundle_size(path: Path | str) -> int:
    return Path(path).stat().st_size
