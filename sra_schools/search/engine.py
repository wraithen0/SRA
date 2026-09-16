"""Profile-aware search over the cached universe.

The engine is cache-first and never blocks on the network unless the caller asks
for it (``live=True``). Repeated identical searches are served from the query
cache; the report says which layer answered it.
"""

from __future__ import annotations

import sqlite3
from collections.abc import Mapping, Sequence
from datetime import timedelta
from typing import Any

from .. import util
from ..db.cache import CacheStatus, QueryCache
from ..db.repository import Repository
from ..models import (
    AidProgram,
    CacheInfo,
    Deadline,
    Fact,
    Institution,
    PlaybookStep,
    SchoolMatch,
    SearchQuery,
    SearchReport,
)
from ..profiles import Profile, get_profile
from ..sources import SourceRegistry
from ..taxonomy import TOPICS, Topic
from .ranking import Scorer, describe_signals

#: profile-driven pre-sort so the candidate window holds the plausible schools
#: before the (expensive) evidence-based re-rank.
_PRIOR_SQL = {
    "first_generation": "COALESCE(avg_net_price, 1e9) ASC, COALESCE(first_gen_pct, 0) DESC",
    "student_with_disability": "COALESCE(avg_net_price, 1e9) ASC, COALESCE(enrollment_total, 0) DESC",
    "international_stem": "COALESCE(international_share, 0) DESC, COALESCE(avg_net_price, 1e9) ASC",
}
_DEFAULT_PRIOR = "COALESCE(avg_net_price, 1e9) ASC, COALESCE(enrollment_total, 0) DESC"


class SearchEngine:
    def __init__(
        self,
        repo: Repository,
        *,
        query_cache: QueryCache | None = None,
        registry: SourceRegistry | None = None,
        pipeline: Any | None = None,  # noqa: ANN401 - avoid a hard import cycle
        cache_searches: bool = True,
        max_candidates: int = 8000,
        search_cache_ttl_s: int | None = None,
        **kwargs: Any,  # noqa: ANN401 - forward compatibility
    ) -> None:
        self.repo = repo
        if query_cache is None and cache_searches:
            query_cache = QueryCache(repo.db)
        self.query_cache = query_cache
        self.registry = registry or SourceRegistry.load()
        self.pipeline = pipeline
        self.cache_searches = cache_searches
        self.max_candidates = max_candidates
        if search_cache_ttl_s is not None and query_cache is not None:
            query_cache.default_ttl = search_cache_ttl_s

    # ------------------------------------------------------------------ public
    def search(self, query: SearchQuery) -> SearchReport:
        profile = get_profile(query.profile)
        if profile is not None:
            defaults = profile.default_filters or {}
            for field_name, value in defaults.items():
                if getattr(query, field_name, None) in (None, "", []):
                    setattr(query, field_name, value)
        epoch = str(self.repo.db.get_meta("data_epoch", "0"))
        fingerprint = query.fingerprint(epoch)
        cached: SearchReport | None = None

        if self.cache_searches and self.query_cache is not None and not query.live:
            payload, status = self.query_cache.get(fingerprint)
            if payload and status in (CacheStatus.FRESH, CacheStatus.STALE) and query.include_stale:
                cached = self._report_from_cache(payload, query, profile, fingerprint, status)
            if cached is not None and status == CacheStatus.FRESH:
                return cached

        report = self._run(query, profile)
        report.cache = CacheInfo(
            hit=False,
            fingerprint=fingerprint,
            note="recomputed" if cached is None else "recomputed (a stale copy existed)",
        )
        if self.cache_searches and self.query_cache is not None:
            self.query_cache.put(fingerprint, report.to_dict(), profile=query.profile or "none",
                                 params=query.to_dict())
            report.cache.expires_at = util.iso(
                util.utcnow() + timedelta(seconds=int(getattr(self.query_cache, "default_ttl", 21600)))
            )
        return report

    def _report_from_cache(self, payload: dict[str, Any], query: SearchQuery,
                           profile: Profile | None, fingerprint: str,
                           status: str) -> SearchReport | None:
        try:
            matches = [_match_from_payload(item) for item in payload.get("results", [])]
            programs = [_program_from_payload(item) for item in payload.get("national_programs", [])]
        except (KeyError, TypeError, ValueError):
            return None
        report = SearchReport(
            query=query,
            profile=profile.key if profile else None,
            matches=matches[query.offset : query.offset + max(1, query.limit)],
            national_programs=programs,
            national_deadlines=[Deadline(**{k: v for k, v in item.items()
                                            if k in Deadline.__slots__})  # type: ignore[attr-defined]
                                for item in payload.get("national_deadlines", [])],
            generated_at=payload.get("generated_at") or util.iso(),
            dataset_version=payload.get("dataset_version"),
            universe_size=int(payload.get("universe_size") or 0),
        )
        report.cache = CacheInfo(
            hit=status == CacheStatus.FRESH,
            fingerprint=fingerprint,
            note=f"query_cache:{status}",
        )
        return report

    # ------------------------------------------------------------------ internals
    def _run(self, query: SearchQuery, profile: Profile | None) -> SearchReport:
        rows = self._candidates(query, profile)
        institutions = [Institution.from_row(row) for row in rows]
        unitids = [inst.unitid for inst in institutions]
        facts_map = self.repo.facts_many(unitids)
        deadlines_map = self.repo.deadlines_many(unitids)
        programs = self._programs_for(query, profile)
        linked = self.repo.db.query(
            f"SELECT unitid, program_id FROM institution_programs WHERE unitid IN ({_ph(unitids)})",
            unitids,
        ) if unitids else []
        by_unit: dict[int, set[str]] = {}
        for row in linked:
            by_unit.setdefault(int(row["unitid"]), set()).add(row["program_id"])

        scorer = Scorer(profile) if profile else None
        matches: list[SchoolMatch] = []
        for inst in institutions:
            facts = facts_map.get(inst.unitid, {})
            deadlines = list(deadlines_map.get(inst.unitid, []))
            # synthesise deadline records from dated facts so the playbook works
            # even when no explicit deadline rows were written
            fact_deadlines = _deadlines_from_facts(inst.unitid, facts)
            deadlines = _merge_deadlines(deadlines, fact_deadlines)
            mine = [p for p in programs if p.program_id in by_unit.get(inst.unitid, set())] + programs
            mine = _unique_programs(mine)
            if scorer is None:
                score, signals = 0.0, {}
            else:
                score, signals = scorer.score(inst, facts, deadlines, mine)
            if query.q:
                score += _text_bonus(query.q, inst, facts)
            matches.append(self._assemble(inst, facts, deadlines, mine, score, signals, profile,
                                          query=query))
        matches.sort(key=lambda m: (-m.score, m.institution.name))
        offset = max(0, query.offset)
        page = matches[offset : offset + max(1, query.limit)]

        return SearchReport(
            query=query,
            profile=profile.key if profile else None,
            matches=page,
            national_programs=programs[: max(6, query.limit)],
            national_deadlines=_program_deadlines(programs),
            dataset_version=self.repo.db.get_meta("dataset_version"),
            universe_size=self.repo.db.count("institutions"),
        )

    def _candidates(self, query: SearchQuery, profile: Profile | None) -> list[sqlite3.Row]:
        sql = ["SELECT * FROM institutions WHERE COALESCE(currently_operating, 1) = 1"]
        params: list[Any] = []
        if query.state:
            sql.append("AND upper(state_abbr) = ?")
            params.append(query.state.strip().upper())
        if query.control:
            sql.append("AND control = ?")
            params.append(_canonical_control(query.control))
        if query.level == "undergraduate":
            sql.append("AND preddeg IN ('2_year', '4_year')")
        elif query.level == "graduate":
            sql.append("AND (highdeg = 'graduates' OR enrollment_graduate > 0)")
        elif query.level == "community":
            sql.append("AND preddeg = '2_year'")
        if query.graduate is True:
            sql.append("AND (highdeg = 'graduates' OR enrollment_graduate > 0)")
        elif query.graduate is False:
            sql.append("AND COALESCE(enrollment_graduate, 0) = 0")
        if query.stem_only:
            sql.append("AND stem_share >= 0.15")
        if query.max_net_price is not None:
            sql.append("AND (avg_net_price IS NULL OR avg_net_price <= ?)")
            params.append(float(query.max_net_price))
        if query.min_aid_generosity is not None and profile:
            sql.append("AND (cost_attending IS NULL OR avg_net_price IS NULL OR "
                       "(cost_attending > 0 AND 1.0 - avg_net_price / cost_attending >= ?))")
            params.append(float(query.min_aid_generosity))
        if query.exclude_unitids:
            sql.append(f"AND unitid NOT IN ({_ph(query.exclude_unitids)})")
            params.extend(int(u) for u in query.exclude_unitids)
        if query.require:
            placeholders = ",".join("?" * len(query.require))
            sql.append(
                f"AND unitid IN (SELECT unitid FROM facts WHERE superseded_at IS NULL "
                f"AND topic IN ({placeholders}) GROUP BY unitid HAVING COUNT(DISTINCT topic) = ?)"
            )
            params.extend([*query.require, len(query.require)])
        if query.q:
            # split on commas so "University, There" matches name=University, city=There
            parts = [p.strip() for p in query.q.split(",") if p.strip()]
            if len(parts) > 1:
                # multi-part query: each part must match name or city
                for part in parts:
                    like = f"%{part}%"
                    sql.append("AND (name LIKE ? OR city LIKE ? OR url_homepage LIKE ?)")
                    params.extend([like, like, like])
            else:
                like = f"%{query.q.strip()}%"
                sql.append("AND (name LIKE ? OR city LIKE ? OR upper(state_abbr) = ? OR url_homepage LIKE ?)")
                params.extend([like, like, query.q.strip().upper(), like])
        prior = _PRIOR_SQL.get(profile.key if profile else "", _DEFAULT_PRIOR)
        window = self.max_candidates
        sql.append(f"ORDER BY {prior} LIMIT ?")
        params.append(int(window))
        return self.repo.db.query(" ".join(sql), params)

    def _programs_for(self, query: SearchQuery, profile: Profile | None) -> list[AidProgram]:
        needs = list(query.needs) or (list(profile.program_needs) if profile else [])
        level = query.level or (profile.program_levels[0] if profile and profile.program_levels else None)
        citizenship = list(profile.program_citizenship) if profile else []
        found = self.repo.programs(profile=profile.key if profile else None, needs=needs,
                                   level=level, citizenship=citizenship, limit=40)
        found.sort(key=lambda p: (-p.confidence, _soonest_deadline(p) or "9999"))
        return found

    def _assemble(self, inst: Institution, facts: Mapping[str, list[Fact]],
                  deadlines: Sequence[Deadline], programs: Sequence[AidProgram], score: float,
                  signals: Mapping[str, float], profile: Profile | None,
                  *, query: SearchQuery) -> SchoolMatch:
        links = resolve_links(inst, facts, self.registry)
        needed = list(profile.required_topics) + list(profile.preferred_topics) if profile else list(facts)
        gaps = [
            TOPICS[topic].label for topic in needed
            if topic in TOPICS and not _live(facts.get(topic))
        ]
        stale = any(f.is_stale() for entries in facts.values() for f in entries)
        observed = [f.observed_at for entries in facts.values() for f in entries if f.observed_at]
        reasons = describe_signals(signals, profile.weights if profile else {}, top=6)
        return SchoolMatch(
            institution=inst,
            score=round(max(0.0, min(100.0, score)), 1),
            signals=dict(signals),
            reasons=reasons,
            facts=_display_facts(facts, needed),
            links=links,
            deadlines=sorted(deadlines, key=lambda d: d.date_iso or "9999-12-31"),
            programs=list(programs),
            playbook=build_playbook(profile, links, deadlines, facts) if profile else [],
            gaps=gaps[:12],
            needs_covered=[t for t in needed if _live(facts.get(t))],
            last_verified=max(observed) if observed else None,
            stale=stale,
        )


# ------------------------------------------------------------------- helpers
def _deadlines_from_facts(unitid: int, facts: Mapping[str, list[Fact]]) -> list[Deadline]:
    """Turn dated facts (application_deadline_*, priority_filing_deadline, ...) into Deadline rows."""
    out: list[Deadline] = []
    seen: set[tuple[str, str]] = set()
    for topic, entries in facts.items():
        topic_obj = TOPICS.get(topic)
        if topic_obj is None or topic_obj.value_type != "date":
            continue
        for fact in entries:
            if not fact.value_date:
                continue
            if hasattr(fact, 'is_stale') and fact.is_stale():
                continue
            label = fact.label or topic_obj.label
            key = (label, fact.value_date)
            if key in seen:
                continue
            seen.add(key)
            category = "application"
            if "priority" in topic or "filing" in topic:
                category = "aid"
            elif "graduate" in topic:
                category = "graduate_application"
            elif "transfer" in topic:
                category = "transfer_application"
            out.append(Deadline(
                unitid=unitid, label=label, date_iso=fact.value_date[:10],
                category=category, url=fact.url, observed_at=fact.observed_at,
            ))
    return out


def _merge_deadlines(existing: list[Deadline], synthesized: list[Deadline]) -> list[Deadline]:
    seen = {(d.label, d.date_iso, d.category) for d in existing}
    out = list(existing)
    for d in synthesized:
        if (d.label, d.date_iso, d.category) not in seen:
            out.append(d)
            seen.add((d.label, d.date_iso, d.category))
    return out


def _live(entries: Sequence[Fact] | None) -> bool:
    return any(not f.is_stale() for f in (entries or []))


def _display_facts(facts: Mapping[str, list[Fact]], needed: Sequence[str],
                   *, per_topic: int = 3) -> list[Fact]:
    """Profile-relevant first, distinct values only - a page repeats itself constantly."""
    order = list(dict.fromkeys([*[t for t in needed if t in facts], *sorted(facts)]))
    out: list[Fact] = []
    for topic in order:
        entries = sorted(facts.get(topic) or [], key=lambda f: (-f.confidence, f.url))
        seen: set[str] = set()
        kept = 0
        for fact in entries:
            key = str(fact.value_text or fact.value_date or util.dumps(fact.value_json))[:180]
            if key in seen:
                continue
            seen.add(key)
            out.append(fact)
            kept += 1
            if kept >= per_topic:
                break
    return out


def _ph(items: Sequence[Any]) -> str:  # noqa: ANN401
    return ",".join("?" * max(1, len(list(items))))


def _canonical_control(value: str) -> str:
    text = value.strip().lower()
    if text.startswith("pub"):
        return "public"
    if "profit" in text and "for" in text:
        return "private_for_profit"
    if "nonprofit" in text or "non-profit" in text or text.startswith("priv"):
        return "private_nonprofit"
    return text


def _unique_programs(programs: Sequence[AidProgram]) -> list[AidProgram]:
    out: dict[str, AidProgram] = {}
    for program in programs:
        out.setdefault(program.program_id, program)
    return list(out.values())


def _soonest_deadline(program: AidProgram) -> str | None:
    dates = sorted(d.date_iso for d in program.deadlines if d.date_iso)
    return dates[0] if dates else None


def _program_deadlines(programs: Sequence[AidProgram]) -> list[Deadline]:
    out = [d for p in programs for d in p.deadlines]
    today = util.utcnow().date().isoformat()
    out = [d for d in out if (d.date_iso or today) >= today]
    out.sort(key=lambda d: d.date_iso or "9999")
    return out[:30]


def _text_bonus(needle: str, inst: Institution, facts: Mapping[str, list[Fact]]) -> float:
    word = needle.strip().lower()
    if not word:
        return 0.0
    bonus = 0.0
    if word in inst.name.lower():
        bonus += 18.0
    if inst.city and word in inst.city.lower():
        bonus += 6.0
    if inst.state_abbr and word == inst.state_abbr.lower():
        bonus += 4.0
    for entries in facts.values():
        for fact in entries:
            if word in (fact.value_text or "").lower() or word in (fact.evidence or "").lower():
                bonus += 1.5
                break
    return min(bonus, 25.0)


#: topics whose value *is* a URL, in preference order for the "links" block
LINK_PRIORITY = (
    "fafsa_school_code", "financial_aid_office", "net_price_calculator", "admissions_office",
    "application_portal", "application_fee_waiver", "merit_scholarship", "first_gen_program",
    "mentorship_program", "trio_student_support_services", "summer_bridge_program",
    "disability_services_office", "accommodation_request_process", "assistive_technology",
    "campus_accessibility", "international_student_office", "i20_and_document_process",
    "aid_for_international_students", "graduate_funding_package", "undergraduate_research_office",
    "reu_program", "internship_career_office", "priority_filing_deadline",
)


def resolve_links(inst: Institution, facts: Mapping[str, list[Fact]],
                  registry: SourceRegistry | None = None) -> dict[str, str]:
    """topic -> the best official URL we hold, home page as the last resort."""
    links: dict[str, str] = {}
    for topic in LINK_PRIORITY:
        fact = _best_url_fact(facts.get(topic))
        if fact:
            links[topic] = fact
        elif facts.get(topic):
            # fall back to the source page URL for non-URL facts (e.g. codes)
            live = [f for f in facts[topic] if not f.is_stale() and f.url]
            if live:
                links[topic] = max(live, key=lambda f: f.confidence).url
    if inst.url_net_price_calc and "net_price_calculator" not in links:
        links["net_price_calculator"] = inst.url_net_price_calc
    if inst.url_homepage:
        links.setdefault("home", inst.url_homepage)
    fallbacks = {
        "fafsa_school_code": "https://studentaid.gov/h/apply-for-aid/fafsa",
        "application_fee_waiver": "https://www.commonapp.org/advice/fee-waivers-for-common-app",
        "assistive_technology": "https://www.aatap.net/directory/",
        "accommodation_funding": "https://www.rsa.gov/website/directories/state-development-disability-agencies-services",
        "visa_and_eligibility_info": "https://travel.state.gov/content/travel/en/us-visas/study/student-visa.html",
        "financial_certification": "https://www.studyinthestates.edu/",
    }
    for topic, url in fallbacks.items():
        if topic not in links and _live(facts.get(topic)):
            links.setdefault(topic, url)
    return links


def _best_url_fact(entries: Sequence[Fact] | None) -> str | None:
    candidates: list[tuple[float, int, str]] = []
    for fact in entries or []:
        if fact.is_stale():
            continue
        url = None
        if isinstance(fact.value_json, dict):
            url = fact.value_json.get("url")
        url = url or (fact.value_text if (fact.value_text or "").startswith("http") else None)
        if not url:
            continue
        recency = util.parse_iso(fact.observed_at)
        candidates.append((fact.confidence, int(recency.timestamp()) if recency else 0, url))
    if not candidates:
        return None
    return max(candidates)[2]


# ------------------------------------------------------------------- playbook
def build_playbook(profile: Profile | None, links: Mapping[str, str],
                   deadlines: Sequence[Deadline], facts: Mapping[str, list[Fact]]) -> list[PlaybookStep]:
    """Turn the profile's steps into concrete, per-school instructions."""
    if profile is None:
        return []
    steps: list[PlaybookStep] = []
    for order, spec in enumerate(profile.steps, start=1):
        url = next((links[topic] for topic in spec.topics if topic in links), None)
        deadline = _pick_deadline(deadlines, spec.topics)
        answered = any(_live(facts.get(topic)) for topic in spec.topics) or not spec.topics
        detail = spec.detail
        status = "action"
        if spec.topics and not answered and spec.when_missing:
            detail = f"{spec.detail} *{spec.when_missing}*"
            status = "verify"
        if url:
            detail = f"{detail} [{_link_label(spec)}]({url})"
        steps.append(
            PlaybookStep(
                order=order, title=spec.title, detail=detail, url=url,
                deadline=(deadline.date_iso or deadline.date_text) if deadline else None,
                status=status,
            )
        )
    return steps


def _pick_deadline(deadlines: Sequence[Deadline], topics: Sequence[str]) -> Deadline | None:
    wanted = set(topics)
    future = [d for d in deadlines if not d.is_past]
    if not future:
        return None
    aid = any(t in wanted for t in ("priority_filing_deadline",))
    grad = any(t in wanted for t in ("application_deadline_graduate",))
    for deadline in future:
        if aid and deadline.category in {"aid", "scholarship"}:
            return deadline
        if grad and deadline.category == "graduate_application":
            return deadline
        if not aid and not grad and deadline.category.endswith("application"):
            return deadline
    return future[0]


def _link_label(spec: Any) -> str:  # noqa: ANN401
    topic = spec.topics[0] if spec.topics else None
    obj: Topic | None = TOPICS.get(topic) if topic else None
    return obj.label if obj else "Official page"


def _match_from_payload(payload: dict[str, Any]) -> SchoolMatch:
    inst = Institution(**{k: v for k, v in payload.get("institution", {}).items()
                          if k in Institution.__dataclass_fields__})  # type: ignore[attr-defined]
    return SchoolMatch(
        institution=inst,
        score=float(payload.get("score", 0.0)),
        signals=payload.get("signals", {}),
        reasons=list(payload.get("why", [])),
        facts=[_fact_from_payload(item) for item in payload.get("facts", [])],
        links=payload.get("links", {}),
        deadlines=[Deadline(**{k: v for k, v in item.items()
                               if k in Deadline.__dataclass_fields__})  # type: ignore[attr-defined]
                   for item in payload.get("deadlines", [])],
        programs=[_program_from_payload(item) for item in payload.get("programs", [])],
        playbook=[PlaybookStep(**{k: v for k, v in item.items()
                                  if k in PlaybookStep.__dataclass_fields__})  # type: ignore[attr-defined]
                  for item in payload.get("playbook", [])],
        gaps=payload.get("gaps", []),
        needs_covered=payload.get("needs_covered", []),
        last_verified=payload.get("last_verified"),
        stale=bool(payload.get("stale", False)),
    )


def _fact_from_payload(payload: dict[str, Any]) -> Fact:
    fields = {f for f in Fact.__dataclass_fields__}  # type: ignore[attr-defined]
    kwargs = {k: v for k, v in payload.items() if k in fields}
    kwargs["unitid"] = int(kwargs.get("unitid") or 0)
    kwargs.setdefault("topic", "")
    kwargs.setdefault("url", "")
    kwargs.setdefault("extractor", "rule")
    kwargs.setdefault("observed_at", "")
    kwargs.setdefault("expires_at", "")
    if kwargs.get("value_json") is None and isinstance(kwargs.get("value"), (list, dict)):
        kwargs["value_json"] = kwargs["value"]
    return Fact(**kwargs)


def _program_from_payload(payload: dict[str, Any]) -> AidProgram:
    fields = {f for f in AidProgram.__dataclass_fields__}  # type: ignore[attr-defined]
    kwargs = {k: v for k, v in payload.items() if k in fields and k != "deadlines"}
    program = AidProgram(**kwargs)
    program.deadlines = [Deadline(**{k: v for k, v in item.items()
                                    if k in Deadline.__dataclass_fields__})  # type: ignore[attr-defined]
                         for item in payload.get("deadlines", [])]
    return program
