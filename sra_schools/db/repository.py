"""Typed read/write layer over the SQLite cache."""

from __future__ import annotations

import sqlite3
from collections.abc import Iterable, Sequence
from datetime import timedelta
from typing import Any

from .. import util
from ..models import AidProgram, Deadline, Fact, Institution, LinkRecord
from ..taxonomy import TOPICS
from .database import Database, iso, now_utc

#: bump when the fact shape or rule semantics change, so cached extractions are
#: re-run rather than trusted
EXTRACTOR_VER = "v1"


class Repository:
    def __init__(self, db: Database) -> None:
        self.db = db

    # ------------------------------------------------------------ institutions
    def upsert_institutions(self, rows: Iterable[dict[str, Any]], *, dataset_version: str | None = None,
                            batch: int = 500) -> int:
        """Bulk insert/update the federal backbone. Returns rows touched."""
        columns = [c for c in _INSTITUTION_COLUMNS]
        updates = [c for c in columns if c not in {"unitid", "first_seen_at"}]
        sql = (
            f"INSERT INTO institutions({','.join(columns)}) VALUES ({','.join('?' * len(columns))}) "
            "ON CONFLICT(unitid) DO UPDATE SET "
            + ",".join(f"{c}=COALESCE(excluded.{c}, institutions.{c})" for c in updates)
        )
        now = iso()
        buffer: list[list[Any]] = []
        written = 0

        def flush() -> None:
            nonlocal written
            if not buffer:
                return
            with self.db.tx() as cur:
                cur.executemany(sql, buffer)
            written += len(buffer)
            buffer.clear()

        for row in rows:
            payload = []
            for col in columns:
                if col == "first_seen_at" or col == "updated_at":
                    payload.append(now)
                    continue
                val = row.get(col)
                if isinstance(val, bool):
                    val = int(val)
                if col == "dataset_version" and dataset_version:
                    val = dataset_version
                payload.append(val)
            buffer.append(payload)
            if len(buffer) >= batch:
                flush()
        flush()
        return written

    def get_institution(self, unitid: int) -> Institution | None:
        row = self.db.one("SELECT * FROM institutions WHERE unitid = ?", (int(unitid),))
        return Institution.from_row(row) if row else None

    def find_institution(self, needle: str) -> Institution | None:
        """Best-effort lookup by UnitID, OPEID or (partial) name."""
        needle = (needle or "").strip()
        if not needle:
            return None
        if needle.isdigit():
            inst = self.get_institution(int(needle))
            if inst:
                return inst
            row = self.db.one("SELECT * FROM institutions WHERE opeid = ? OR opeid6 = ?", (needle, needle[:6]))
            return Institution.from_row(row) if row else None
        # try exact, then prefix / substring; a query like "State University, There"
        # should still find "State University, Here" via the part before the comma
        if "," in needle:
            needle = needle.split(",")[0].strip()
        row = self.db.one(
            "SELECT * FROM institutions WHERE lower(name) = lower(?) LIMIT 1", (needle,),
        ) or self.db.one(
            "SELECT * FROM institutions WHERE name LIKE ? ORDER BY length(name) LIMIT 1",
            (f"{needle}%",),
        ) or self.db.one(
            "SELECT * FROM institutions WHERE name LIKE ? ORDER BY length(name) LIMIT 1",
            (f"%{needle}%",),
        )
        return Institution.from_row(row) if row else None

    def institutions_due(self, *, limit: int = 100, unitids: Sequence[int] | None = None) -> list[Institution]:
        sql = "SELECT * FROM institutions WHERE (next_due_at IS NULL OR next_due_at <= ?)"
        params: list[Any] = [iso()]
        if unitids:
            sql += f" AND unitid IN ({','.join('?' * len(unitids))})"
            params.extend(int(u) for u in unitids)
        sql += " ORDER BY (next_due_at IS NULL) DESC, next_due_at LIMIT ?"
        params.append(limit)
        return [Institution.from_row(r) for r in self.db.query(sql, params)]

    def set_seeded(self, unitids: Iterable[int]) -> None:
        values = [(int(u),) for u in unitids]
        if not values:
            return
        self.db.executemany("UPDATE institutions SET seeded = 1 WHERE unitid = ?", values)

    def mark_next_due(self, unitid: int, *, earliest: str | None) -> None:
        self.db.execute("UPDATE institutions SET next_due_at = ? WHERE unitid = ?", (earliest, int(unitid)))

    def recompute_due(self, unitid: int) -> None:
        earliest = self.db.scalar(
            "SELECT MIN(expires_at) FROM facts WHERE unitid = ? AND superseded_at IS NULL", (int(unitid),)
        )
        self.mark_next_due(unitid, earliest=earliest)

    # ------------------------------------------------------------------ facts
    def replace_url_facts(self, unitid: int, url: str, findings: Sequence[Any], *,
                          extractor: str, version: str, content_sha: str | None = None,
                          notes: str | None = None) -> int:
        """Retire older-derivation facts for this URL and insert the new ones atomically.

        Doing retire and insert in one transaction matters: if the process dies
        between them the URL is left with no live facts while the extraction log
        claims it is done, and the page is then never re-parsed again.
        """
        rows = self._fact_rows(unitid, url, findings, extractor=extractor, version=version)
        with self.db.tx() as cur:
            cur.execute(
                "UPDATE facts SET superseded_at = ? WHERE unitid = ? AND url = ? AND extractor = ? "
                "AND superseded_at IS NULL AND (extractor_ver IS NULL OR extractor_ver <> ?)",
                (iso(), int(unitid), url, extractor, version),
            )
            if rows:
                cur.executemany(_FACT_INSERT, rows)
            if content_sha:
                cur.execute(
                    "INSERT OR REPLACE INTO extractions(url, content_sha256, extractor, "
                    "extractor_ver, facts_found, notes, extracted_at) VALUES(?,?,?,?,?,?,?)",
                    (url, content_sha, extractor, version, len(rows), _clip(notes, 300), iso()),
                )
        return len(rows)

    def _fact_rows(self, unitid: int, url: str, findings: Sequence[Any], *,
                   extractor: str, version: str) -> list[tuple[Any, ...]]:
        rows: list[tuple[Any, ...]] = []
        for finding in findings:
            topic = getattr(finding, "topic", None)
            if topic is None or topic not in TOPICS:
                continue
            value_json = getattr(finding, "value_json", None)
            if isinstance(value_json, (bool, int, float, str)):
                value_json = {"value": value_json}
            ttl = getattr(finding, "ttl_seconds", lambda: 90 * 86400)()
            observed_at = getattr(finding, "observed_at", None) or iso()
            expires_at = getattr(finding, "expires_at", None) or iso(now_utc() + timedelta(seconds=ttl))
            value_date = getattr(finding, "value_date", None)
            value_text = _clip(getattr(finding, "value_text", None), 800)
            # for date-type topics, auto-populate value_date from value_text if needed
            if value_date is None and value_text and TOPICS[topic].value_type == "date":
                parsed = util.parse_date_fragments(value_text)
                if parsed:
                    value_date = util.iso_or_none(parsed[0][1])
            rows.append((
                int(unitid),
                topic,
                value_text,
                util.dumps(value_json) if value_json else None,
                value_date,
                getattr(finding, "value_num", None),
                _bool_int(getattr(finding, "value_bool", None)),
                _clip(getattr(finding, "evidence", None), 700),
                url,
                extractor,
                version,
                float(getattr(finding, "confidence", 0.6) or 0.6),
                observed_at,
                expires_at,
            ))
        return rows

    def add_facts(self, unitid: int, url: str, findings: Sequence[Any], *,
                  extractor: str = "rule", version: str = EXTRACTOR_VER) -> int:
        """Insert findings; re-asserting the same claim refreshes its expiry."""
        rows = self._fact_rows(unitid, url, findings, extractor=extractor, version=version)
        if not rows:
            return 0
        with self.db.tx() as cur:
            cur.executemany(_FACT_INSERT, rows)
        return len(rows)

    def supersede_topic(self, unitid: int, topic: str, *, except_url: str | None = None) -> None:
        """A page was re-parsed and no longer states this claim."""
        sql = "UPDATE facts SET superseded_at = ? WHERE unitid = ? AND topic = ? AND superseded_at IS NULL"
        params: list[Any] = [iso(), int(unitid), topic]
        if except_url:
            sql += " AND url <> ?"
            params.append(except_url)
        self.db.execute(sql, params)

    def facts_for(self, unitid: int, *, live_only: bool = True) -> list[Fact]:
        sql = "SELECT * FROM facts WHERE unitid = ?"
        params: list[Any] = [int(unitid)]
        if live_only:
            sql += " AND superseded_at IS NULL"
        sql += " ORDER BY topic, confidence DESC"
        return [Fact.from_row(row) for row in self.db.query(sql, params)]

    def facts_by_topic(self, unitid: int) -> dict[str, list[Fact]]:
        grouped: dict[str, list[Fact]] = {}
        for fact in self.facts_for(unitid):
            grouped.setdefault(fact.topic, []).append(fact)
        return grouped

    def facts_many(self, unitids: Sequence[int]) -> dict[int, dict[str, list[Fact]]]:
        """Bulk load for a candidate page - one query, no N+1."""
        out: dict[int, dict[str, list[Fact]]] = {int(u): {} for u in unitids}
        ids = [int(u) for u in unitids if u]
        if not ids:
            return out
        for chunk in util.chunks(ids, 400):
            placeholders = ",".join("?" * len(chunk))
            rows = self.db.query(
                f"SELECT * FROM facts WHERE superseded_at IS NULL AND unitid IN ({placeholders}) "
                "ORDER BY unitid, topic, confidence DESC",
                chunk,
            )
            for row in rows:
                fact = Fact.from_row(row)
                out.setdefault(fact.unitid, {}).setdefault(fact.topic, []).append(fact)
        return out

    def deadlines_many(self, unitids: Sequence[int]) -> dict[int, list[Deadline]]:
        out: dict[int, list[Deadline]] = {int(u): [] for u in unitids}
        ids = [int(u) for u in unitids if u]
        if not ids:
            return out
        for chunk in util.chunks(ids, 400):
            placeholders = ",".join("?" * len(chunk))
            rows = self.db.query(
                f"SELECT * FROM deadlines WHERE unitid IN ({placeholders}) "
                "AND (expires_at IS NULL OR expires_at > ?) "
                "ORDER BY COALESCE(date_iso, '9999'), label",
                [*chunk, iso()],
            )
            for row in rows:
                out.setdefault(int(row["unitid"]), []).append(_deadline_from_row(row))
        return out

    def fact_counts(self) -> dict[str, int]:
        rows = self.db.query(
            "SELECT topic, COUNT(*) c, COUNT(DISTINCT unitid) u FROM facts "
            "WHERE superseded_at IS NULL GROUP BY topic"
        )
        return {row["topic"]: row["c"] for row in rows}

    def institutions_with_facts(self, topics: Sequence[str]) -> list[int]:
        if not topics:
            return []
        sql = (f"SELECT DISTINCT unitid FROM facts WHERE superseded_at IS NULL AND topic IN "
               f"({','.join('?' * len(topics))})")
        return [row[0] for row in self.db.query(sql, list(topics))]

    # ------------------------------------------------------------------ links
    def add_links(self, unitid: int | None, links: Sequence[Any], *, source_url: str | None = None) -> int:
        rows = []
        for link in links:
            url = getattr(link, "url", None) or (link.get("url") if isinstance(link, dict) else None)
            if not url:
                continue
            topic = getattr(link, "topic", None) or (link.get("topic") if isinstance(link, dict) else None)
            rows.append((
                unitid, url, _clip(getattr(link, "anchor", None) or (link.get("anchor") if isinstance(link, dict) else None), 200),
                topic, getattr(link, "kind", "discovery") if not isinstance(link, dict) else link.get("kind", "discovery"),
                float(getattr(link, "score", 0.5) if not isinstance(link, dict) else link.get("score", 0.5)),
                source_url, iso(), iso(),
            ))
        if not rows:
            return 0
        with self.db.tx() as cur:
            cur.executemany(
                """
                INSERT INTO links(unitid, url, anchor_text, topic, kind, score, source_url,
                                  first_seen_at, last_seen_at)
                VALUES(?,?,?,?,?,?,?,?,?)
                ON CONFLICT(unitid, url, topic) DO UPDATE SET
                    anchor_text=excluded.anchor_text,
                    score=MAX(links.score, excluded.score),
                    last_seen_at=excluded.last_seen_at
                """,
                rows,
            )
        return len(rows)

    def links_for(self, unitid: int, *, topic: str | None = None) -> list[LinkRecord]:
        sql = "SELECT * FROM links WHERE unitid = ?"
        params: list[Any] = [int(unitid)]
        if topic:
            sql += " AND topic = ?"
            params.append(topic)
        sql += " ORDER BY score DESC LIMIT 60"
        return [LinkRecord(url=r["url"], topic=r["topic"] or "", anchor_text=r["anchor_text"],
                           kind=r["kind"] or "discovery", score=float(r["score"] or 0))
                for r in self.db.query(sql, params)]

    # -------------------------------------------------------------- deadlines
    def add_deadlines(self, unitid: int | None, deadlines: Sequence[Deadline]) -> int:
        rows = [
            (
                unitid, d.program_id, _clip(d.label, 120), d.date_iso, _clip(d.date_text, 120),
                d.category, int(d.recurring_annual), d.url, iso(),
                iso(now_utc() + timedelta(days=30 if d.category in {"aid", "application"} else 90)),
            )
            for d in deadlines
        ]
        if not rows:
            return 0
        with self.db.tx() as cur:
            cur.executemany(
                """
                INSERT INTO deadlines(unitid, program_id, label, date_iso, date_text, category,
                                      recurring_annual, url, observed_at, expires_at)
                VALUES(?,?,?,?,?,?,?,?,?,?)
                ON CONFLICT(unitid, program_id, label, date_iso, date_text) DO UPDATE SET
                    category=excluded.category, url=excluded.url,
                    observed_at=excluded.observed_at, expires_at=excluded.expires_at
                """,
                rows,
            )
        return len(rows)

    def deadlines_for(self, unitid: int) -> list[Deadline]:
        rows = self.db.query(
            "SELECT * FROM deadlines WHERE unitid = ? AND (expires_at IS NULL OR expires_at > ?) "
            "ORDER BY COALESCE(date_iso, '9999') , label",
            (int(unitid), iso()),
        )
        return [_deadline_from_row(r) for r in rows]

    def upcoming_deadlines(self, *, limit: int = 40) -> list[Deadline]:
        rows = self.db.query(
            "SELECT d.*, i.name AS inst FROM deadlines d "
            "LEFT JOIN institutions i ON i.unitid = d.unitid "
            "WHERE d.date_iso >= ? ORDER BY d.date_iso LIMIT ?",
            (util.utcnow().date().isoformat(), limit),
        )
        out = []
        for row in rows:
            deadline = _deadline_from_row(row)
            if row["inst"]:
                deadline.label = f"{row['inst']}: {deadline.label}"
            out.append(deadline)
        return out

    # ---------------------------------------------------------- aid programmes
    def upsert_program(self, program: AidProgram) -> None:
        values: dict[str, Any] = {
            "program_id": program.program_id,
            "name": program.name,
            "provider": program.provider,
            "official_url": program.official_url,
            "apply_url": program.apply_url,
            "kind": program.kind,
            "levels": util.dumps(program.levels),
            "citizenship": util.dumps(program.citizenship),
            "needs": util.dumps(program.needs),
            "profile_tags": util.dumps(program.profile_tags),
            "amount_text": program.amount_text,
            "coverage_text": program.coverage_text,
            "stipend_text": program.stipend_text,
            "renewable": _bool_int(program.renewable),
            "stem_eligible": _bool_int(program.stem_eligible),
            "disability_scope": util.dumps(program.disability_scope),
            "eligibility": util.dumps(program.eligibility),
            "apply_steps": util.dumps(program.apply_steps),
            "how_to_win": util.dumps(program.how_to_win),
            "documentation_required": program.documentation_required,
            "work_auth_notes": program.work_auth_notes,
            "state": program.state,
            "notes": program.notes,
            "sources": util.dumps(program.sources),
            "confidence": program.confidence,
            "verified_at": program.verified_at,
            "active": 1,
            "updated_at": iso(),
        }
        columns = list(values)
        updates = [c for c in columns if c != "program_id"]
        sql = (
            f"INSERT INTO aid_programs({','.join(columns)}) VALUES({','.join('?' * len(columns))}) "
            "ON CONFLICT(program_id) DO UPDATE SET "
            + ", ".join(f"{c}=excluded.{c}" for c in updates)
        )
        with self.db.tx() as cur:
            cur.execute(sql, [values[c] for c in columns])
        self.replace_program_deadlines(program)

    def replace_program_deadlines(self, program: AidProgram) -> None:
        with self.db.tx() as cur:
            cur.execute("DELETE FROM deadlines WHERE program_id = ?", (program.program_id,))
        if not program.deadlines:
            return
        rows = [(None, program.program_id, _clip(d.label, 120), d.date_iso, _clip(d.date_text or "", 120) or None,
                 d.category, int(d.recurring_annual), d.url, iso(), None) for d in program.deadlines]
        with self.db.tx() as cur:
            cur.executemany(
                """
                INSERT INTO deadlines(unitid, program_id, label, date_iso, date_text, category,
                                      recurring_annual, url, observed_at, expires_at)
                VALUES(?,?,?,?,?,?,?,?,?,?)
                ON CONFLICT(unitid, program_id, label, date_iso, date_text) DO UPDATE SET
                    category=excluded.category, url=excluded.url
                """,
                rows,
            )

    def get_program(self, program_id: str) -> AidProgram | None:
        row = self.db.one("SELECT * FROM aid_programs WHERE program_id = ?", (program_id,))
        if not row:
            return None
        return _attach_program_deadlines(self.db, [_program_from_row(row)])[0]

    def programs(self, *, profile: str | None = None, needs: Sequence[str] | None = None,
                 level: str | None = None, citizenship: Sequence[str] | None = None,
                 kind: str | None = None, state: str | None = None, limit: int = 200) -> list[AidProgram]:
        sql = "SELECT * FROM aid_programs WHERE active = 1"
        params: list[Any] = []
        if kind:
            sql += " AND kind = ?"
            params.append(kind)
        if state:
            sql += " AND (state = ? OR state IS NULL OR state = '')"
            params.append(state.upper())
        if limit:
            sql += " LIMIT ?"
            params.append(limit * 3)
        rows = self.db.query(sql, params)
        out = [_program_from_row(r) for r in rows]
        out = [p for p in out if _program_matches(p, profile=profile, needs=needs, level=level,
                                                  citizenship=citizenship)]
        out = _attach_program_deadlines(self.db, out[:limit])
        return out[:limit]

    def link_program_to_institution(self, unitid: int, program_id: str, *, relationship: str,
                                    evidence: str | None = None, url: str | None = None) -> None:
        with self.db.tx() as cur:
            cur.execute(
                "INSERT INTO institution_programs(unitid, program_id, relationship, evidence, url, observed_at) "
                "VALUES(?,?,?,?,?,?) ON CONFLICT(unitid, program_id, relationship) DO UPDATE SET "
                "evidence=excluded.evidence, url=excluded.url, observed_at=excluded.observed_at",
                (int(unitid), program_id, relationship, _clip(evidence, 500), url, iso()),
            )

    def programs_for_institution(self, unitid: int) -> list[tuple[AidProgram, str]]:
        rows = self.db.query(
            "SELECT p.*, ip.relationship FROM institution_programs ip "
            "JOIN aid_programs p ON p.program_id = ip.program_id AND p.active = 1 "
            "WHERE ip.unitid = ? ORDER BY ip.relationship",
            (int(unitid),),
        )
        programs = [_program_from_row(r) for r in rows]
        _attach_program_deadlines(self.db, programs)
        return [(p, r["relationship"]) for p, r in zip(programs, rows)]

    # ------------------------------------------------------------ extraction log
    def extraction_done(self, url: str, content_sha: str, extractor: str, version: str) -> bool:
        row = self.db.one(
            "SELECT facts_found FROM extractions WHERE url=? AND content_sha256=? AND extractor=? "
            "AND extractor_ver=?",
            (url, content_sha, extractor, version),
        )
        return row is not None

    def log_extraction(self, url: str, content_sha: str, extractor: str, version: str,
                       facts_found: int, *, notes: str | None = None) -> None:
        with self.db.tx() as cur:
            cur.execute(
                "INSERT OR REPLACE INTO extractions(url, content_sha256, extractor, extractor_ver, "
                "facts_found, notes, extracted_at) VALUES(?,?,?,?,?,?,?)",
                (url, content_sha, extractor, version, facts_found, _clip(notes, 300), iso()),
            )

    # ------------------------------------------------------------------- stats
    def status(self) -> dict[str, Any]:
        total = self.db.count("institutions")
        return {
            "institutions": total,
            "institutions_seeded": self.db.count("institutions", "seeded = 1"),
            "institutions_with_graduate_programs": self.db.count(
                "institutions", "highdeg IN ('4','graduates') OR graduate_only = 1"
            ),
            "facts": self.db.count("facts", "superseded_at IS NULL"),
            "facts_stale": self.db.count("facts", "superseded_at IS NULL AND expires_at < ?", (iso(),)),
            "links": self.db.count("links"),
            "deadlines": self.db.count("deadlines"),
            "programs": self.db.count("aid_programs", "active = 1"),
            "institution_program_links": self.db.count("institution_programs"),
            "dataset_version": self.db.get_meta("dataset_version"),
            "scorecard_source": self.db.get_meta("dataset_source"),
            "sources_version": self.db.get_meta("sources_version"),
            "last_crawl": self.db.one("SELECT * FROM crawl_runs ORDER BY id DESC LIMIT 1"),
            "coverage": self._coverage(),
        }

    def _coverage(self) -> dict[str, int]:
        rows = self.db.query(
            "SELECT COUNT(DISTINCT unitid) AS units FROM institutions"
        )
        universe = int(rows[0]["units"]) if rows else 0
        per_topic = {
            row["topic"]: row["n"]
            for row in self.db.query(
                "SELECT topic, COUNT(DISTINCT unitid) n FROM facts WHERE superseded_at IS NULL GROUP BY topic"
            )
        }
        return {"universe": universe, "by_topic": per_topic}


_FACT_INSERT = """
    INSERT INTO facts(unitid, topic, value_text, value_json, value_date, value_num,
                      value_bool, evidence, url, extractor, extractor_ver, confidence,
                      observed_at, expires_at)
    VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)
    ON CONFLICT(unitid, topic, url, extractor, evidence) DO UPDATE SET
        value_text=excluded.value_text,
        value_json=excluded.value_json,
        value_date=excluded.value_date,
        value_num=excluded.value_num,
        value_bool=excluded.value_bool,
        extractor_ver=excluded.extractor_ver,
        confidence=MAX(facts.confidence, excluded.confidence),
        observed_at=excluded.observed_at,
        expires_at=excluded.expires_at,
        superseded_at=NULL
"""

# ------------------------------------------------------------------- helpers
_INSTITUTION_COLUMNS = [
    "unitid", "opeid", "opeid6", "name", "slug", "city", "state_abbr", "state_name", "zip",
    "county", "lat", "lon", "url_homepage", "url_net_price_calc", "control", "preddeg", "highdeg",
    "carnegie", "locale", "region", "accreditor", "hbcu", "pbi", "aanapii", "tribally_controlled",
    "women_only", "men_only", "religious_affiliation", "distance_only", "year_round",
    "graduate_only", "currently_operating", "enrollment_undergrad", "enrollment_graduate",
    "enrollment_total", "admissions_rate", "open_admissions", "sat_mid", "act_mid",
    "tuition_in_state", "tuition_out_state", "cost_attending", "avg_net_price",
    "median_family_income", "pct_pell", "median_debt_undergrad", "median_debt_graduate",
    "median_earnings", "grad_rate_150", "retention_ft", "first_gen_pct", "parent_ed_pct_hs",
    "stem_share", "stem_share_exact", "international_share", "pct_grad_prof",
    "application_count", "dataset_version", "first_seen_at", "updated_at",
]


def _clip(value: str | None, limit: int) -> str | None:
    if value is None:
        return None
    value = str(value)
    return value[:limit] if len(value) > limit else value


def _bool_int(value: Any) -> int | None:  # noqa: ANN401
    if value is None:
        return None
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, (int, float)):
        return int(bool(value))
    text = str(value).strip().lower()
    if text in {"1", "true", "yes"}:
        return 1
    if text in {"0", "false", "no"}:
        return 0
    return None


def _deadline_from_row(row: sqlite3.Row) -> Deadline:
    return Deadline(
        label=row["label"],
        category=row["category"] or "application",
        date_iso=row["date_iso"],
        date_text=row["date_text"],
        url=row["url"],
        program_id=row["program_id"],
        unitid=row["unitid"],
        recurring_annual=bool(row["recurring_annual"]),
        observed_at=row["observed_at"],
    )


def _program_from_row(row: sqlite3.Row) -> AidProgram:
    program = AidProgram(
        program_id=row["program_id"],
        name=row["name"],
        official_url=row["official_url"],
        provider=row["provider"],
        apply_url=row["apply_url"],
        kind=row["kind"],
        levels=util.loads(row["levels"], []),
        citizenship=util.loads(row["citizenship"], []),
        needs=util.loads(row["needs"], []),
        profile_tags=util.loads(row["profile_tags"], []),
        amount_text=row["amount_text"],
        coverage_text=row["coverage_text"],
        stipend_text=row["stipend_text"],
        renewable=_opt_bool(row["renewable"]),
        stem_eligible=_opt_bool(row["stem_eligible"]),
        disability_scope=util.loads(row["disability_scope"], []),
        eligibility=util.loads(row["eligibility"], []),
        apply_steps=util.loads(row["apply_steps"], []),
        how_to_win=util.loads(row["how_to_win"], []),
        documentation_required=row["documentation_required"],
        work_auth_notes=row["work_auth_notes"],
        state=row["state"],
        notes=row["notes"],
        sources=util.loads(row["sources"], []),
        confidence=float(row["confidence"] or 0.6),
        verified_at=row["verified_at"],
        verification_status=(row["verification_status"] if "verification_status" in row.keys() else None),
        verification_note=(row["verification_note"] if "verification_note" in row.keys() else None),
        active=bool(row["active"]) if "active" in row.keys() else True,
    )
    if row["program_id"]:
        program.deadlines = []
    return program


def _attach_program_deadlines(db: Database, programs: Sequence[AidProgram]) -> list[AidProgram]:
    """One query for all programme deadlines, then grouped in memory."""
    ids = [p.program_id for p in programs]
    if not ids:
        return list(programs)
    placeholders = ",".join("?" * len(ids))
    rows = db.query(
        f"SELECT * FROM deadlines WHERE unitid IS NULL AND program_id IN ({placeholders}) "
        "ORDER BY COALESCE(date_iso, '9999')",
        ids,
    )
    grouped: dict[str, list[Deadline]] = {}
    for row in rows:
        grouped.setdefault(row["program_id"], []).append(_deadline_from_row(row))
    for program in programs:
        program.deadlines = grouped.get(program.program_id, [])
    return list(programs)


def _opt_bool(value: Any) -> bool | None:  # noqa: ANN401
    return None if value is None else bool(value)


def _program_matches(program: AidProgram, *, profile: str | None, needs: Sequence[str] | None,
                     level: str | None, citizenship: Sequence[str] | None) -> bool:
    if profile and program.profile_tags and profile not in program.profile_tags:
        return False
    if needs and program.needs and not (set(needs) & set(program.needs)):
        return False
    if level and program.levels and level != "any" and level not in program.levels:
        return False
    if citizenship:
        caps = set(citizenship)
        if program.citizenship and not (caps & set(program.citizenship)) and "any" not in program.citizenship:
            return False
    return True
