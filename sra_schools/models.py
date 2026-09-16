"""Dataclasses that cross the module boundary (the shape teammates consume)."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import date
from typing import Any

from . import util
from .taxonomy import Need, Topic, TOPICS


@dataclass(slots=True)
class Institution:
    """One US institution, keyed by IPEDS UnitID."""

    unitid: int
    name: str
    city: str | None = None
    state_abbr: str | None = None
    state_name: str | None = None
    zip: str | None = None
    lat: float | None = None
    lon: float | None = None
    url_homepage: str | None = None
    url_net_price_calc: str | None = None
    opeid: str | None = None
    control: str | None = None
    preddeg: str | None = None
    highdeg: str | None = None
    carnegie: str | None = None
    locale: str | None = None
    region: str | None = None
    accreditor: str | None = None
    hbcu: bool = False
    pbi: bool = False
    aanapii: bool = False
    tribally_controlled: bool = False
    women_only: bool = False
    men_only: bool = False
    religious_affiliation: str | None = None
    distance_only: bool = False
    graduate_only: bool = False
    currently_operating: bool = True
    year_round: bool = False
    application_count: float | None = None
    parent_ed_pct_hs: float | None = None
    pct_grad_prof: float | None = None
    enrollment_undergrad: float | None = None
    enrollment_graduate: float | None = None
    enrollment_total: float | None = None
    admissions_rate: float | None = None
    open_admissions: bool | None = None
    sat_mid: float | None = None
    act_mid: float | None = None
    tuition_in_state: float | None = None
    tuition_out_state: float | None = None
    cost_attending: float | None = None
    avg_net_price: float | None = None
    median_family_income: float | None = None
    pct_pell: float | None = None
    median_debt_undergrad: float | None = None
    median_debt_graduate: float | None = None
    median_earnings: float | None = None
    grad_rate_150: float | None = None
    retention_ft: float | None = None
    first_gen_pct: float | None = None
    stem_share: float | None = None
    international_share: float | None = None
    dataset_version: str | None = None

    @property
    def display(self) -> str:
        loc = " / ".join(x for x in (self.city, self.state_abbr) if x)
        return f"{self.name} ({loc})" if loc else self.name

    @property
    def has_graduate_programs(self) -> bool:
        return (self.highdeg or "") in {"4", "graduates"} or bool(
            (self.enrollment_graduate or 0) > 0
        )

    def to_dict(self, *, verbose: bool = False) -> dict[str, Any]:
        data = {k: v for k, v in asdict(self).items() if v is not None}
        data["display"] = self.display
        if not verbose:
            for quiet in ("lat", "lon", "zip", "accreditor", "locale", "region", "dataset_version"):
                data.pop(quiet, None)
        return data

    @classmethod
    def from_row(cls, row: Any) -> Institution:  # noqa: ANN401
        keys = {f for f in cls.__slots__}  # type: ignore[attr-defined]
        payload: dict[str, Any] = {}
        for key in keys:
            if key not in row.keys():
                continue
            val = row[key]
            if key in {"hbcu", "pbi", "aanapii", "tribally_controlled", "women_only", "men_only",
                       "distance_only", "graduate_only", "open_admissions", "currently_operating",
                       "year_round"}:
                val = bool(val) if val is not None else None
            payload[key] = val
        payload["unitid"] = int(payload["unitid"])
        return cls(**payload)


@dataclass(slots=True)
class Fact:
    """An extracted claim about an institution, always with provenance."""

    unitid: int
    topic: str
    url: str
    extractor: str
    observed_at: str
    expires_at: str
    value_text: str | None = None
    value_json: Any = None  # noqa: ANN401
    value_date: str | None = None
    value_num: float | None = None
    value_bool: bool | None = None
    evidence: str | None = None
    confidence: float = 0.6
    label: str | None = None

    @property
    def topic_obj(self) -> Topic | None:
        return TOPICS.get(self.topic)

    @property
    def need(self) -> Need | None:
        topic = self.topic_obj
        return topic.need if topic else None

    def is_stale(self, *, ref: date | None = None) -> bool:
        stamp = util.parse_iso(self.expires_at)
        return bool(stamp and stamp.date() < (ref or util.utcnow().date()))

    @property
    def value(self) -> Any:  # noqa: ANN401 - the payload is topic-typed
        topic = self.topic_obj
        if topic is None:
            return self.value_text
        if topic.value_type == "bool":
            return self.value_bool
        if topic.value_type == "money":
            return self.value_num if self.value_num is not None else self.value_text
        if topic.value_type in {"list", "url"}:
            return self.value_json if self.value_json else self.value_text
        if topic.value_type == "date":
            return self.value_date or self.value_text
        return self.value_text if self.value_text is not None else self.value_json

    def to_dict(self, *, with_evidence: bool = True) -> dict[str, Any]:
        out: dict[str, Any] = {
            "unitid": self.unitid,
            "topic": self.topic,
            "value": self.value,
            "url": self.url,
            "extractor": self.extractor,
            "confidence": round(self.confidence, 2),
            "observed_at": self.observed_at,
            "expires_at": self.expires_at,
            "stale": self.is_stale(),
        }
        # raw typed fields stay in the payload so a cached report round-trips exactly
        for key in ("value_text", "value_json", "value_date", "value_num", "value_bool"):
            raw = getattr(self, key)
            if raw is not None:
                out[key] = raw
        if with_evidence and self.evidence:
            out["evidence"] = self.evidence
        return out

    @classmethod
    def from_row(cls, row: Any) -> Fact:  # noqa: ANN401
        keys = row.keys()
        return cls(
            unitid=int(row["unitid"]),
            topic=row["topic"],
            url=row["url"] or "",
            extractor=row["extractor"] or "rule",
            observed_at=row["observed_at"] or "",
            expires_at=row["expires_at"] or "",
            value_text=row["value_text"] if "value_text" in keys else None,
            value_json=util.loads(row["value_json"], None) if "value_json" in keys else None,
            value_date=row["value_date"] if "value_date" in keys else None,
            value_num=row["value_num"] if "value_num" in keys else None,
            value_bool=None if ("value_bool" not in keys or row["value_bool"] is None)
            else bool(row["value_bool"]),
            evidence=row["evidence"] if "evidence" in keys else None,
            confidence=float(row["confidence"] or 0.0) if "confidence" in keys else 0.6,
        )


@dataclass(slots=True)
class Deadline:
    label: str
    category: str = "application"
    date_iso: str | None = None
    date_text: str | None = None
    url: str | None = None
    program_id: str | None = None
    unitid: int | None = None
    recurring_annual: bool = False
    observed_at: str | None = None

    @property
    def is_past(self) -> bool:
        return util.is_past(self.date_iso)

    @property
    def days_left(self) -> int | None:
        if not self.date_iso:
            return None
        try:
            return (date.fromisoformat(self.date_iso[:10]) - util.utcnow().date()).days
        except ValueError:
            return None

    def to_dict(self) -> dict[str, Any]:
        out = asdict(self)
        out["is_past"] = self.is_past
        out["days_left"] = self.days_left
        return out


@dataclass(slots=True)
class AidProgram:
    """A national/state/private programme from the curated catalog."""

    program_id: str
    name: str
    official_url: str
    provider: str | None = None
    apply_url: str | None = None
    kind: str | None = None
    levels: list[str] = field(default_factory=list)
    citizenship: list[str] = field(default_factory=list)
    needs: list[str] = field(default_factory=list)
    profile_tags: list[str] = field(default_factory=list)
    amount_text: str | None = None
    coverage_text: str | None = None
    stipend_text: str | None = None
    renewable: bool | None = None
    stem_eligible: bool | None = None
    disability_scope: list[str] = field(default_factory=list)
    eligibility: list[str] = field(default_factory=list)
    apply_steps: list[str] = field(default_factory=list)
    how_to_win: list[str] = field(default_factory=list)
    documentation_required: str | None = None
    work_auth_notes: str | None = None
    state: str | None = None
    notes: str | None = None
    sources: list[str] = field(default_factory=list)
    confidence: float = 0.6
    verified_at: str | None = None
    verification_status: str | None = None
    verification_note: str | None = None
    active: bool = True
    deadlines: list[Deadline] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        out = {k: v for k, v in asdict(self).items() if v not in (None, [], {}, "")}
        out["active"] = self.active
        out["deadlines"] = [d.to_dict() for d in self.deadlines]
        return out


@dataclass(slots=True)
class LinkRecord:
    url: str
    topic: str
    anchor_text: str | None = None
    kind: str = "official"
    score: float = 0.5


@dataclass(slots=True)
class PlaybookStep:
    order: int
    title: str
    detail: str
    url: str | None = None
    deadline: str | None = None
    status: str = "action"  # action | verify | done


@dataclass(slots=True)
class SchoolMatch:
    """One ranked result: the school + everything we know for this profile."""

    institution: Institution
    score: float
    signals: dict[str, float] = field(default_factory=dict)
    reasons: list[dict[str, Any]] = field(default_factory=list)
    facts: list[Fact] = field(default_factory=list)
    links: dict[str, str] = field(default_factory=dict)
    deadlines: list[Deadline] = field(default_factory=list)
    programs: list[AidProgram] = field(default_factory=list)
    playbook: list[PlaybookStep] = field(default_factory=list)
    gaps: list[str] = field(default_factory=list)
    needs_covered: list[str] = field(default_factory=list)
    last_verified: str | None = None
    stale: bool = False

    @property
    def unitid(self) -> int:
        return self.institution.unitid

    @property
    def why(self) -> list[dict[str, Any]]:
        """Alias for :attr:`reasons` (kept for the documented ``match.why`` shape)."""
        return self.reasons

    def to_dict(self) -> dict[str, Any]:
        return {
            "institution": self.institution.to_dict(),
            "score": round(self.score, 1),
            "signals": {k: round(v, 3) for k, v in self.signals.items()},
            "why": self.reasons,
            "needs_covered": self.needs_covered,
            "links": self.links,
            "facts": [f.to_dict() for f in self.facts],
            "deadlines": [d.to_dict() for d in self.deadlines],
            "programs": [p.to_dict() for p in self.programs],
            "playbook": [asdict(s) for s in self.playbook],
            "gaps": self.gaps,
            "last_verified": self.last_verified,
            "stale": self.stale,
        }


@dataclass(slots=True)
class SearchQuery:
    """Normalised, cache-keyable request."""

    profile: str | None = None
    q: str | None = None
    needs: list[str] = field(default_factory=list)
    level: str | None = None
    state: str | None = None
    control: str | None = None
    stem_only: bool = False
    graduate: bool | None = None
    max_net_price: float | None = None
    min_aid_generosity: float | None = None
    require: list[str] = field(default_factory=list)
    exclude_unitids: list[int] = field(default_factory=list)
    limit: int = 20
    offset: int = 0
    live: bool = False  # allow network for this call (refresh on miss)
    include_stale: bool = True

    def fingerprint(self, epoch: str = "0") -> str:
        return util.fingerprint({"q": self, "epoch": epoch})

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class SearchReport:
    query: SearchQuery
    profile: str | None
    matches: list[SchoolMatch] = field(default_factory=list)
    national_programs: list[AidProgram] = field(default_factory=list)
    national_deadlines: list[Deadline] = field(default_factory=list)
    cache: CacheInfo | None = None
    generated_at: str = field(default_factory=lambda: util.iso())
    dataset_version: str | None = None
    universe_size: int = 0

    @property
    def count(self) -> int:
        return len(self.matches)

    def to_dict(self) -> dict[str, Any]:
        return {
            "profile": self.profile,
            "query": self.query.to_dict(),
            "generated_at": self.generated_at,
            "dataset_version": self.dataset_version,
            "universe_size": self.universe_size,
            "cache": self.cache.to_dict() if self.cache else None,
            "count": self.count,
            "results": [m.to_dict() for m in self.matches],
            "national_programs": [p.to_dict() for p in self.national_programs],
            "national_deadlines": [d.to_dict() for d in self.national_deadlines],
        }

    def to_json(self, *, indent: int | None = 2) -> str:
        import json

        return json.dumps(self.to_dict(), ensure_ascii=False, indent=indent)


@dataclass(slots=True)
class CacheInfo:
    hit: bool
    fingerprint: str
    age_seconds: float | None = None
    expires_at: str | None = None
    pages_fresh: int = 0
    pages_stale: int = 0
    note: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
