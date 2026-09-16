"""Profile-aware scoring.

Every signal is a number in ``[0, 1]`` computed from data we actually hold, and
each one is reported back with the score so the frontend can say *why* a school
ranked where it did. Weights come from the profile (:mod:`sra_schools.profiles`).

Normalization uses fixed, domain-meaningful bands (a $0 net price and a $60k net
price are the endpoints) rather than percentiles over the current cache, so the
same school gets the same score whether the cache holds 50 or 5,000 enriched
institutions.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from statistics import mean

from .. import util
from ..models import AidProgram, Deadline, Fact, Institution
from ..profiles import Profile
from ..taxonomy import TOPICS

#: cost bands used to turn dollars into a 0..1 signal
NET_PRICE_CEILING = 58_000.0
TUITION_CEILING = 65_000.0
EARNINGS_CEILING = 110_000.0
STEM_BAND = (0.05, 0.55)
INTL_BAND = (0.0, 0.30)
FIRSTGEN_BAND = (0.30, 0.85)

SIGNAL_LABELS: dict[str, str] = {
    "need_coverage": "Answers the needs you listed",
    "aid_generosity": "Grants and net-price generosity",
    "first_gen_community": "First-generation student body and programs",
    "fee_waiver": "Application fee waiver route",
    "mentorship": "Mentoring / TRIO / bridge programs",
    "scholarship_richness": "Institutional scholarships",
    "deadline_clarity": "Known, unexpired deadlines",
    "outcomes": "Graduation and earnings outcomes",
    "disability_support": "Disability office and accommodation process",
    "assistive_tech": "Assistive technology provision",
    "inclusive_programs": "Structured inclusive programs",
    "access_geography": "Campus physical accessibility",
    "intl_funding": "Aid that international students can actually get",
    "stem_strength": "STEM depth",
    "graduate_programs": "Graduate programs and their funding",
    "research_access": "Undergraduate research and internships",
    "work_authorization": "CPT/OPT work-authorization support",
    "cost_value": "Sticker cost (lower is better)",
    "international_community": "Existing international student community",
    "evidence_freshness": "How recently the evidence was verified",
    "external_programs": "Matching national programmes",
    "credibility": "Real, degree-granting campus with reported outcomes",
}

DEFAULT_WEIGHT = 1.0


def _clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, value))


def _band(value: float | None, low: float, high: float) -> float:
    if value is None or high <= low:
        return 0.0
    return _clamp((value - low) / (high - low))


def _has(facts: Mapping[str, list[Fact]], topic: str) -> bool:
    entries = facts.get(topic) or []
    return any(not f.is_stale() for f in entries)


def _first(facts: Mapping[str, list[Fact]], topic: str) -> Fact | None:
    entries = [f for f in (facts.get(topic) or []) if not f.is_stale()]
    return max(entries, key=lambda f: f.confidence, default=None)


def _bool(facts: Mapping[str, list[Fact]], topic: str) -> bool | None:
    fact = _first(facts, topic)
    return None if fact is None else fact.value_bool


# --------------------------------------------------------------------- signals
def coverage(profile: Profile, facts: Mapping[str, list[Fact]]) -> float:
    """Required topics count twice; preferred count once."""
    weights = [(t, 2.0) for t in profile.required_topics] + [(t, 1.0) for t in profile.preferred_topics]
    if not weights:
        return 0.0
    earned = sum(w for topic, w in weights if _has(facts, topic))
    return _clamp(earned / sum(w for _, w in weights))


def aid_generosity(inst: Institution, facts: Mapping[str, list[Fact]]) -> float:
    """How much of the sticker price grants actually erase.

    A missing (or $0) net price is treated as *unknown*, not as free school: without
    a cost to compare against, the signal falls back to Pell density and what the
    campus pages say about grant aid.
    """
    parts: list[float] = []
    net, cost = inst.avg_net_price, inst.cost_attending
    known = net is not None and net > 0
    if known and cost and cost > 0 and net <= cost:
        discount = _clamp(1.0 - (net / cost))
        # a $60k sticker with a $58k net price is not generosity; cap the shape
        parts.append(_clamp(discount * 1.15) if cost >= 20_000 else discount)
    elif known:
        parts.append(_clamp(1.0 - net / NET_PRICE_CEILING))
    if inst.pct_pell is not None:
        pell = inst.pct_pell / 100.0 if inst.pct_pell > 1 else inst.pct_pell
        parts.append(_clamp(pell / 0.45) * 0.9)
    if _has(facts, "institutional_grant"):
        parts.append(0.85)
    if _bool(facts, "work_study"):
        parts.append(0.5)
    if _has(facts, "priority_filing_deadline"):
        parts.append(0.35)
    if not parts:
        return 0.2
    return _clamp(mean(parts))


def fee_waiver(facts: Mapping[str, list[Fact]]) -> float:
    score = 0.0
    available = _bool(facts, "application_fee_waiver")
    if available is True:
        score += 0.55
    elif available is None and _has(facts, "fee_waiver_eligibility"):
        score += 0.3
    if _has(facts, "fee_waiver_eligibility"):
        score += 0.25
    if _has(facts, "application_portal"):
        score += 0.1
    if _has(facts, "application_fee"):
        score += 0.1
    return _clamp(score)


def mentorship(facts: Mapping[str, list[Fact]]) -> float:
    score = 0.0
    for topic, weight in (("mentorship_program", 0.35), ("trio_student_support_services", 0.3),
                          ("first_gen_program", 0.25), ("summer_bridge_program", 0.15)):
        if _has(facts, topic):
            score += weight
    return _clamp(score)


def first_gen_community(inst: Institution, facts: Mapping[str, list[Fact]]) -> float:
    density = _band(inst.first_gen_pct / 100.0 if (inst.first_gen_pct or 0) > 1 else inst.first_gen_pct,
                    *FIRSTGEN_BAND)
    programs = 0.55 if _has(facts, "trio_student_support_services") else 0.0
    programs += 0.30 if _has(facts, "first_gen_program") else 0.0
    programs += 0.15 if _has(facts, "mentorship_program") else 0.0
    return _clamp(0.45 * density + 0.55 * _clamp(programs))


def scholarship_richness(facts: Mapping[str, list[Fact]], programs: Sequence[AidProgram]) -> float:
    score = 0.0
    if _has(facts, "merit_scholarship"):
        score += 0.4
    if _bool(facts, "scholarship_auto_consideration"):
        score += 0.3
    score += _clamp(len(programs) / 5.0) * 0.3
    return _clamp(score)


def disability_support(facts: Mapping[str, list[Fact]]) -> float:
    score = 0.0
    for topic, weight in (
        ("disability_services_office", 0.25),
        ("accommodation_request_process", 0.3),
        ("documentation_requirements", 0.15),
        ("deaf_hard_of_hearing_services", 0.1),
        ("campus_accessibility", 0.1),
    ):
        if _has(facts, topic):
            score += weight
    types_fact = _first(facts, "accommodation_types")
    if types_fact and isinstance(types_fact.value_json, list):
        score += _clamp(len(types_fact.value_json) / 8.0) * 0.1
    return _clamp(score)


def assistive_tech(facts: Mapping[str, list[Fact]]) -> float:
    score = 0.6 if _has(facts, "assistive_technology") else 0.0
    types = _first(facts, "accommodation_types")
    if types and isinstance(types.value_json, list):
        named = [t for t in types.value_json if t in {"assistive technology lab",
                                                      "screen reader / text-to-speech",
                                                      "accessible materials / alternative formats",
                                                      "captioning / CART"}]
        score += _clamp(len(named) / 3.0) * 0.4
    return _clamp(score)


def inclusive_programs(facts: Mapping[str, list[Fact]]) -> float:
    score = 0.7 if _has(facts, "inclusive_program") else 0.0
    if _has(facts, "campus_accessibility"):
        score += 0.3
    return _clamp(score)


def intl_funding(inst: Institution, facts: Mapping[str, list[Fact]]) -> float:
    policy = _bool(facts, "need_blind_for_international")
    score = 0.0
    if policy is True:
        score += 0.5
    elif policy is False:
        score -= 0.35
    if _has(facts, "aid_for_international_students"):
        score += 0.2
    if _has(facts, "graduate_funding_package"):
        score += 0.15
    if _has(facts, "tuition_waiver"):
        score += 0.1
    if inst.has_graduate_programs:
        score += 0.05
    return _clamp(score)


def stem_strength(inst: Institution, facts: Mapping[str, list[Fact]]) -> float:
    share = inst.stem_share
    if share is not None and share > 1:
        share /= 100.0
    score = _band(share, *STEM_BAND) * 0.65
    if _has(facts, "stem_programs"):
        score += 0.15
    if _has(facts, "undergraduate_research_office"):
        score += 0.2
    return _clamp(score)


def graduate_programs(inst: Institution, facts: Mapping[str, list[Fact]]) -> float:
    if not inst.has_graduate_programs:
        return 0.0
    score = 0.55
    if _has(facts, "application_deadline_graduate"):
        score += 0.2
    if _has(facts, "graduate_funding_package") or _has(facts, "tuition_waiver"):
        score += 0.25
    return _clamp(score)


def research_access(facts: Mapping[str, list[Fact]]) -> float:
    score = 0.0
    for topic, weight in (("undergraduate_research_office", 0.45), ("reu_program", 0.25),
                          ("internship_career_office", 0.2), ("mcnair_scholars", 0.1)):
        if _has(facts, topic):
            score += weight
    return _clamp(score)


def work_authorization(facts: Mapping[str, list[Fact]]) -> float:
    score = 0.7 if _has(facts, "cpt_opt_support") else 0.0
    if _has(facts, "international_student_office"):
        score += 0.3
    return _clamp(score)


def deadline_clarity(deadlines: Sequence[Deadline], profile: Profile) -> float:
    future = [d for d in deadlines if not d.is_past and d.date_iso]
    wanted = set(profile.required_topics) | set(profile.preferred_topics)
    dated = [d for d in future if d.label]
    score = _clamp(len(dated) / 4.0) * 0.7
    if any(_topic_matches_deadline(d, wanted) for d in dated):
        score += 0.3
    return _clamp(score)


def _topic_matches_deadline(deadline: Deadline, wanted: set[str]) -> bool:
    label = (deadline.label or "").lower()
    category = (deadline.category or "").lower()
    if "aid" in wanted and category in {"aid", "scholarship"}:
        return True
    if any(t in category for t in ("application", "graduate", "transfer")):
        return True
    return any(word in label for word in ("fafsa", "priority", "decision", "action", "apply"))


def outcomes(inst: Institution) -> float:
    parts: list[float] = []
    if inst.grad_rate_150 is not None:
        rate = inst.grad_rate_150 / 100.0 if inst.grad_rate_150 > 1 else inst.grad_rate_150
        parts.append(_clamp(rate))
    if inst.median_earnings is not None:
        parts.append(_clamp(inst.median_earnings / EARNINGS_CEILING))
    if inst.retention_ft is not None:
        retention = inst.retention_ft / 100.0 if inst.retention_ft > 1 else inst.retention_ft
        parts.append(_clamp(retention))
    return _clamp(mean(parts)) if parts else 0.0


def cost_value(inst: Institution) -> float:
    if inst.avg_net_price is not None:
        return _clamp(1.0 - inst.avg_net_price / NET_PRICE_CEILING)
    if inst.tuition_in_state is not None:
        return _clamp(1.0 - inst.tuition_in_state / TUITION_CEILING)
    if inst.cost_attending is not None:
        return _clamp(1.0 - inst.cost_attending / NET_PRICE_CEILING)
    return 0.0


def international_community(inst: Institution) -> float:
    share = inst.international_share
    if share is None:
        return 0.0
    if share > 1:
        share /= 100.0
    return _clamp(_band(share, *INTL_BAND))


def evidence_freshness(facts: Mapping[str, list[Fact]]) -> float:
    stamps = [util.parse_iso(f.observed_at) for entry in facts.values() for f in entry]
    stamps = [s for s in stamps if s]
    if not stamps:
        return 0.0
    newest = max(stamps)
    age_days = max(0.0, (util.utcnow() - newest).total_seconds() / 86400.0)
    return _clamp(1.0 - age_days / 240.0)


def external_programs(programs: Sequence[AidProgram]) -> float:
    return _clamp(len(programs) / 6.0)


def credibility(inst: Institution, facts: Mapping[str, list[Fact]]) -> float:
    """Is this a real campus a student could plausibly attend and finish?

    Small, url-less, or for-profit operations with no reported outcomes should not
    outrank a state university on a $0 net-price quirk in the federal file.
    """
    score = 0.0
    if inst.url_homepage:
        score += 0.15
    total = inst.enrollment_total or 0
    if total >= 2000:
        score += 0.30
    elif total >= 500:
        score += 0.20
    elif total > 0:
        score += 0.08
    if inst.control == "public":
        score += 0.20
    elif inst.control == "private_nonprofit":
        score += 0.15
    elif inst.control == "private_for_profit":
        score += 0.02
    if inst.preddeg == "4_year":
        score += 0.15
    elif inst.preddeg == "2_year":
        score += 0.10
    if inst.grad_rate_150:
        score += 0.10
    if inst.url_net_price_calc or _has(facts, "net_price_calculator"):
        score += 0.10
    if not inst.currently_operating:
        score -= 0.5
    return _clamp(score)


# ------------------------------------------------------------------ the scorer
class Scorer:
    """Combines signals with profile weights into a 0-100 score."""

    def __init__(self, profile: Profile) -> None:
        self.profile = profile

    def signals(self, inst: Institution, facts: Mapping[str, list[Fact]],
                deadlines: Sequence[Deadline], programs: Sequence[AidProgram]) -> dict[str, float]:
        return {
            "need_coverage": coverage(self.profile, facts),
            "aid_generosity": aid_generosity(inst, facts),
            "first_gen_community": first_gen_community(inst, facts),
            "fee_waiver": fee_waiver(facts),
            "mentorship": mentorship(facts),
            "scholarship_richness": scholarship_richness(facts, programs),
            "deadline_clarity": deadline_clarity(deadlines, self.profile),
            "outcomes": outcomes(inst),
            "disability_support": disability_support(facts),
            "assistive_tech": assistive_tech(facts),
            "inclusive_programs": inclusive_programs(facts),
            "access_geography": disability_support(facts) * 0.3 + (0.4 if _has(facts, "campus_accessibility") else 0.0),
            "intl_funding": intl_funding(inst, facts),
            "stem_strength": stem_strength(inst, facts),
            "graduate_programs": graduate_programs(inst, facts),
            "research_access": research_access(facts),
            "work_authorization": work_authorization(facts),
            "cost_value": cost_value(inst),
            "international_community": international_community(inst),
            "evidence_freshness": evidence_freshness(facts),
            "external_programs": external_programs(programs),
        }

    def score(self, inst: Institution, facts: Mapping[str, list[Fact]],
              deadlines: Sequence[Deadline], programs: Sequence[AidProgram]) -> tuple[float, dict[str, float]]:
        values = self.signals(inst, facts, deadlines, programs)
        values["credibility"] = credibility(inst, facts)
        weights = self.profile.weights or {"need_coverage": 1.0}
        total_weight = sum(weights.values()) or 1.0
        raw = sum(values.get(name, 0.0) * weight for name, weight in weights.items())
        score = 100.0 * raw / total_weight
        # a school with nothing verified must not look like a strong match
        live_topics = {t for t, entries in facts.items() if entries and t in TOPICS}
        if not live_topics:
            score *= 0.45
        # ...and a marginal operator must not outrank a real campus on a data quirk
        score *= 0.40 + 0.60 * values["credibility"]
        return round(_clamp(score / 100.0) * 100.0, 1), values


def describe_signals(values: Mapping[str, float], weights: Mapping[str, float],
                     *, top: int = 5) -> list[dict[str, object]]:
    """Human-readable 'why this school' rows, strongest weighted signal first."""
    ranked = sorted(
        ((name, value, float(weights.get(name, 0.0))) for name, value in values.items()),
        key=lambda item: item[2] * item[1],
        reverse=True,
    )
    return [
        {
            "signal": name,
            "label": SIGNAL_LABELS.get(name, name.replace("_", " ").title()),
            "value": round(value, 3),
            "weight": weight,
            "detail": util.usd(None),
        }
        for name, value, weight in ranked[:top]
    ]
