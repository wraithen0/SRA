"""Deterministic page -> facts extraction. No LLM, no network.

Input is the markdown/text of one page plus the institution it belongs to.
Output is a list of :class:`Finding` records, each carrying the verbatim evidence
snippet and the URL it came from, so a human (or the frontend) can audit the claim.

Why rules first: a school's aid page says the same handful of things with a
predictable vocabulary, and every fact we ship must be traceable to a quote.
The LLM path (:mod:`sra_schools.extract.llm`) only fills genuine gaps.
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from functools import lru_cache
from typing import Any

from .. import util
from ..sources import SourceRegistry
from ..taxonomy import Freshness, Topic, TOPICS

RULES_VERSION = "rules-2026.09-2"

# ------------------------------------------------------------------ lexicons
_BLOCK_SPLIT = re.compile(r"\n(?=(?:#{1,6} )|(?:[-*+] )|(?:\d+\. ))|(?<=\S)\n\s*\n+")

#: navigation / banner chrome that reads like content but proves nothing
_BOILERPLATE = (
    "a new version of this site", "skip back to", "skip to main content", "cookie",
    "all rights reserved", "privacy statement", "accessibility statement", "sitemap",
    "emergency information", "report a concern", "powered by", "jump to", "site index",
)
_SOCIAL = ("facebook", "instagram", "youtube", "linkedin", "twitter", "tiktok", "x.com", "follow us")


@lru_cache(maxsize=512)
def _needle_regex(needles: tuple[str, ...]) -> re.Pattern[str]:
    parts: list[str] = []
    for needle in needles:
        core = re.escape(needle)
        if len(needle) <= 8 and " " not in needle:
            core = rf"\b{core}\b"  # 'cart' must not match 'restart', 'asl' not 'casual'
        parts.append(f"(?:{core})")
    return re.compile("|".join(parts), re.I)


def has_any(lowered: str, needles: Sequence[str]) -> bool:
    """Boundary-aware keyword test over an already-lowercased block."""
    return bool(_needle_regex(tuple(needles)).search(lowered))


def is_boilerplate(block: str) -> bool:
    lowered = block.lower()
    if any(marker in lowered for marker in _BOILERPLATE):
        return True
    return sum(1 for site in _SOCIAL if site in lowered) >= 2

DISABILITY_OFFICE = (
    "disability services", "disability support services", "accessibility resources",
    "accessibility services", "office of students with disabilities", "disability resource",
    "student disability", "accommodation services", "disabled student services",
)
ACCOM_PROCESS = (
    "request accommodations", "requesting accommodations", "accommodation request",
    "requests for accommodation", "self-identify", "self identify", "intake appointment",
    "new student intake", "register with us", "how to register", "accommodation form",
    "myaccessibility", "accessibility portal", "accommodations portal",
)
DOCUMENTATION = (
    "documentation", "psychoeducational", "diagnostic", "evaluation letter", "current evaluation",
    "verification form", "qualified professional", "licensed professional", "iep", "504 plan",
    "medical records", "functional limitation",
)
ACCOMMODATION_LEXICON: dict[str, tuple[str, ...]] = {
    "extended test time": ("extended time", "extended test time", "extra time on tests",
                           "test time extension", "time-and-a-half", "double time"),
    "testing in a reduced-distraction setting": ("quiet room", "reduced distraction", "separate testing room", "alternative testing"),
    "note-taking support": ("note tap", "note-taking", "note taker", "peer note"),
    "ASL interpreting": ("asl", "interpreter", "interpreting service"),
    "captioning / CART": ("cart", "captioning", "real-time caption", "transcription service"),
    "screen reader / text-to-speech": ("screen reader", "jaws", "nvda", "text to speech", "voiceover", "read&write"),
    "accessible materials / alternative formats": ("alternative format", "accessible format", "braille", "large print", "e-text", "disability-friendly materials"),
    "assistive technology lab": ("assistive technology lab", "adaptive technology lab", "at lab", "assistive tech lab", "accessibility lab"),
    "accessible housing": ("accessible housing", "single room for medical", "ADA housing", "wheelchair accessible room", "medical housing"),
    "priority registration": ("priority registration", "early registration", "priority scheduling"),
    "course substitution or waiver": ("course substitution", "curricular accommodation", "academic adjustment", "course waiver"),
    "flexible attendance / deadline policy": ("flexible attendance", "attendance agreement", "extension of deadlines", "deadline flexibility"),
    "lecture recording": ("recording of lectures", "record lectures", "audio recording permission", "panopto access"),
    "mobility and transportation support": ("paratransit", "shuttle for students with disabilities", "mobility assistance", "accessible transport"),
    "service animal policy": ("service animal", "assistance animal"),
    "autism/social support program": ("autism support", "social learning", "project switch",
                                      "campus living skills", "threshold program", "aspire program"),
    "IDD transition program": ("intellectual disability", "comprehensive transition", "inclusive postsecondary", "think college"),
}
FIRST_GEN_LEXICON = ("first generation", "first-generation", "first gen", "generation college")
MENTORSHIP_LEXICON = ("mentorship", "mentoring program", "peer mentor", "faculty mentor", "mentor matching", "big brothers", "one-on-one mentoring")
TRIO_LEXICON = ("trio", "student support services", "sss program", "upward bound", "talent search", "support services program")
BRIDGE_LEXICON = ("summer bridge", "bridge program", "transition program", "summer institute", "orientation program for", "summer enrichment", "mavy")
RESEARCH_LEXICON = ("undergraduate research", "reu", "research experience for undergraduates", "summer research", "research fellowship", "postbacc", "honors thesis research", "surface")
INTERN_LEXICON = ("international student", "f-1", "j-1", "issps", "oiss", "isss",
                  "non-us citizen", "non-u.s. citizen", "visa", "i-20", "ds-2019", "sevis",
                  "cpt", "opt", "practical training", "on-campus employment")
FUNDING_LEXICON = ("tuition waiver", "full tuition", "teaching assistantship", "graduate assistantship", "research assistantship", "stipend", "fellowship", "fully funded", "funding package", "guaranteed funding", "four-year funding", "financial guarantee")
WORK_STUDY_LEXICON = ("work-study", "work study", "fws", "federal work study", "student employment", "campus employment")
SCHOLARSHIP_LEXICON = ("merit scholarship", "automatic consideration", "president's scholarship", "trustee scholar", "honors scholarship", "dean's scholarship", "freshman scholarship", "no separate application", "academic scholarship")
AUTO_CONSIDER_PHRASES = ("automatic consideration", "no separate application", "automatically considered", "included with your application", "without a separate application")
TEST_OPTIONAL_PHRASES = ("test-optional", "test optional", "test-blind", "test flexible", "not required to submit sat", "standardized tests are not required")
NEED_BLIND_PHRASES = ("need-blind", "need blind", "meet 100 percent of demonstrated need", "meet full demonstrated need",
                      "meet full financial need", "meets full need", "guarantee to meet full need")
NEED_AWARE_PHRASES = ("need-aware", "need aware", "does affect admission", "consider financial need in admission")

DEADLINE_HEADWORDS = ("deadline", "due", "apply by", "apply before", "priority", "closing date",
                      "file by", "postmarked", "submission date", "opens", "closes", "final filing")
AID_DEADLINE_HINTS = ("fafsa", "financial aid", "priority date", "aid application", "verification",
                      "scholarship", "grant", "work-study", "tuition waiver")
APP_DEADLINE_HINTS = ("application", "admission", "early decision", "early action", "regular decision",
                      "priority deadline", "transfer application", "first-year", "freshman", "graduate")

_NEGATIONS = ("do not", "don't", "does not", "doesn't", "cannot", "can not", "unable to",
              "not eligible", "not offered", "no aid", "not provide", "not able to offer",
              "unfortunately", "not required for", "are not considered", "is not available")

FAFSA_CODE_RE = re.compile(
    r"(?i)(?:fafsa|federal school code|school code|title iv code|ope.?id)[^0-9]{0,45}"
    r"\b(\d{6})\b(?:\s*[-–]\s*(?:\d{6}|[A-Za-z][\w ]{2,60}))?"
)
CSS_PROFILE_CODE_RE = re.compile(
    r"(?i)(?:css\s*profile(?:\s*school)?\s*code|college\s*board\s*code|css\s*code)[^0-9]{0,30}"
    r"\b(\d{4})\b"
)
CSS_PROFILE_MENTION_RE = re.compile(
    r"(?i)\bcss\s*profile\b"
)
ANY_SIX_DIGIT_RE = re.compile(r"\b\d{6}\b")
APPLICATION_FEE_RE = re.compile(
    r"(?i)(application|admission|apply(?:ing)?)\s+(?:fee|charge)s?\b[^.$\n]{0,60}?"
    r"\$\s?(\d{1,3}(?:,\d{3})*(?:\.\d{2})?)"
)
FEE_WAIVER_RE = re.compile(
    r"(?i)\b(fee waiver|waive (?:the )?(?:application|admission) fee|waiver of the application fee|"
    r"application fee waiver|request a waiver|fee exemption)\b"
)
EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]{2,}")
PHONE_RE = re.compile(r"(?<!\d)(?:\+?1[\s.-]?)?\(?\d{3}\)?[\s.-]\d{3}[\s.-]\d{4}(?!\d)")


@dataclass(slots=True)
class Finding:
    topic: str
    value_text: str | None = None
    value_json: Any = None  # noqa: ANN401
    value_date: str | None = None
    value_num: float | None = None
    value_bool: bool | None = None
    evidence: str | None = None
    confidence: float = 0.6
    label: str | None = None
    category: str | None = None
    url: str | None = None
    observed_at: str | None = None
    expires_at: str | None = None

    @property
    def topic_obj(self) -> Topic | None:
        return TOPICS.get(self.topic)

    def ttl_seconds(self) -> int:
        topic = self.topic_obj
        freshness = topic.freshness if topic else Freshness.POLICY
        return FRESHNESS_SECONDS[freshness]


FRESHNESS_SECONDS = {
    Freshness.STATIC: 365 * 86400,
    Freshness.STRUCTURAL: 180 * 86400,
    Freshness.POLICY: 90 * 86400,
    Freshness.DATE_BOUND: 30 * 86400,
    Freshness.VOLATILE: 14 * 86400,
}


@dataclass(slots=True)
class LinkFinding:
    url: str
    topic: str
    anchor: str = ""
    score: float = 0.5
    kind: str = "discovery"


@dataclass(slots=True)
class PageFacts:
    url: str
    unitid: int | None
    findings: list[Finding] = field(default_factory=list)
    links: list[LinkFinding] = field(default_factory=list)
    text_chars: int = 0
    notes: list[str] = field(default_factory=list)

    @property
    def topics(self) -> set[str]:
        return {f.topic for f in self.findings if f.value_text or f.value_json or
                f.value_date or f.value_num is not None or f.value_bool is not None}

    def by_topic(self, topic: str) -> list[Finding]:
        return [f for f in self.findings if f.topic == topic]

    def best(self, topic: str) -> Finding | None:
        candidates = [f for f in self.by_topic(topic) if f is not None]
        return max(candidates, key=lambda f: f.confidence, default=None)


def _topic(key: str) -> Topic:
    topic = TOPICS.get(key)
    if topic is None:  # pragma: no cover - guards taxonomy drift
        raise KeyError(f"unknown topic {key}")
    return topic


def iter_blocks(text: str) -> Iterable[str]:
    """Paragraph / list / heading chunks that keep keywords in local context."""
    for raw in _BLOCK_SPLIT.split(text or ""):
        block = raw.strip()
        if len(block) >= 25 and not is_boilerplate(block):
            yield block


# --------------------------------------------------------------------- scoring
def _is_negated(window: str) -> bool:
    lowered = window.lower()
    return any(neg in lowered for neg in _NEGATIONS)


def _dedupe(findings: Sequence[Finding]) -> list[Finding]:
    best: dict[tuple[str, str], Finding] = {}
    for finding in findings:
        key = (finding.topic, (finding.label or "") + (finding.value_text or "")[:60])
        current = best.get(key)
        if current is None or finding.confidence > current.confidence:
            best[key] = finding
    return list(best.values())


# ------------------------------------------------------------------ the engine
def extract_page(
    text: str,
    *,
    url: str,
    unitid: int | None = None,
    institution_name: str = "",
    homepage: str | None = None,
    registry: SourceRegistry | None = None,
) -> PageFacts:
    """Run every rule over one page. Never raises on messy input."""
    reg = registry or SourceRegistry.load()
    body = util.collapse_ws(text or "")
    body_for_search = text or ""
    facts = PageFacts(url=url, unitid=unitid, text_chars=len(body))
    if not body:
        facts.notes.append("empty page")
        return facts

    findings: list[Finding] = []
    findings.extend(_extract_links(body_for_search, url=url, homepage=homepage, registry=reg, facts=facts))
    findings.extend(_extract_codes(body_for_search, url=url))
    findings.extend(_extract_fees(body_for_search, url=url))
    findings.extend(_extract_deadlines(body_for_search, url=url))
    findings.extend(_extract_aid(body_for_search, url=url))
    findings.extend(_extract_first_gen(body_for_search, url=url))
    findings.extend(_extract_disability(body_for_search, url=url))
    findings.extend(_extract_international(body_for_search, url=url))
    findings.extend(_extract_research(body_for_search, url=url))
    findings.extend(_extract_contacts(body_for_search, url=url))

    facts.findings = _dedupe(findings)
    return facts


# ----------------------------------------------------------------- link rules
URL_TOPICS = {
    "net_price_calculator": TOPICS["net_price_calculator"],
    "financial_aid_office": TOPICS["financial_aid_office"],
    "admissions_office": TOPICS["admissions_office"],
    "application_portal": TOPICS["application_portal"],
    "application_fee_waiver": TOPICS["application_fee_waiver"],
    "merit_scholarship": TOPICS["merit_scholarship"],
    "disability_services_office": TOPICS["disability_services_office"],
    "accommodation_request_process": TOPICS["accommodation_request_process"],
    "assistive_technology": TOPICS["assistive_technology"],
    "campus_accessibility": TOPICS["campus_accessibility"],
    "international_student_office": TOPICS["international_student_office"],
    "i20_and_document_process": TOPICS["i20_and_document_process"],
    "aid_for_international_students": TOPICS["aid_for_international_students"],
    "undergraduate_research_office": TOPICS["undergraduate_research_office"],
    "reu_program": TOPICS["reu_program"],
    "internship_career_office": TOPICS["internship_career_office"],
    "trio_student_support_services": TOPICS["trio_student_support_services"],
    "first_gen_program": TOPICS["first_gen_program"],
    "mentorship_program": TOPICS["mentorship_program"],
    "summer_bridge_program": TOPICS["summer_bridge_program"],
    "work_study": TOPICS["work_study"],
    "graduate_funding_package": TOPICS["graduate_funding_package"],
    "tuition_waiver": TOPICS["tuition_waiver"],
    "priority_filing_deadline": TOPICS["priority_filing_deadline"],
    "financial_certification": TOPICS["financial_certification"],
    "english_proficiency_requirements": TOPICS["english_proficiency_requirements"],
    "cpt_opt_support": TOPICS["cpt_opt_support"],
}


def _extract_links(
    markdown: str,
    *,
    url: str,
    homepage: str | None,
    registry: SourceRegistry,
    facts: PageFacts,
) -> list[Finding]:
    findings: list[Finding] = []
    base = homepage or url
    for anchor, href in util.extract_links(markdown):
        absolute = util.abs_url(url, href)
        if not absolute or absolute == url:
            continue
        haystack = f"{anchor} {absolute}".lower()
        candidates = registry.topics_for_text(haystack)
        if not candidates:
            continue
        topic_key = candidates[0]
        topic = URL_TOPICS.get(topic_key)
        if topic is None:
            continue
        same_site = util.is_same_site(absolute, base)
        # a nav link on our own site about the topic is strong; a link that merely
        # mentions the word in a footer is weak.
        score = 0.55 if same_site else 0.35
        if anchor and any(h in f"{anchor}".lower() for h in registry.hints_for(topic_key)):
            score += 0.25
        if len(anchor) < 4:
            score -= 0.15
        if "/archive" in absolute or "javascript" in absolute:
            continue
        facts.links.append(LinkFinding(url=absolute, topic=topic_key, anchor=anchor[:200],
                                       score=round(min(score, 0.95), 2)))
        if topic.value_type == "url" and score >= 0.5:
            findings.append(
                Finding(
                    topic=topic_key,
                    value_text=absolute,
                    value_json={"url": absolute, "anchor": anchor[:200]},
                    evidence=util.clean_snippet(f"link: {anchor or absolute}", 200),
                    confidence=score,
                    url=url,
                )
            )
    return findings


# -------------------------------------------------------------------- code rules
def _extract_codes(markdown: str, *, url: str) -> list[Finding]:
    findings: list[Finding] = []
    for block in iter_blocks(markdown):
        match = FAFSA_CODE_RE.search(block)
        if match:
            code = match.group(1)
            window = block[max(0, match.start() - 60): match.end() + 60]
            if not any(word in window.lower() for word in ("zip", "postal", "phone", "fax")):
                findings.append(
                    Finding(
                        topic="fafsa_school_code",
                        value_text=code,
                        value_json={"code": code, "label": util.truncate(util.normalize_space(match.group(0)), 120)},
                        evidence=util.clean_snippet(window),
                        confidence=0.9,
                        url=url,
                    )
                )
        css_match = CSS_PROFILE_CODE_RE.search(block)
        if css_match:
            css_code = css_match.group(1)
            window = block[max(0, css_match.start() - 60): css_match.end() + 60]
            findings.append(
                Finding(
                    topic="css_profile_code",
                    value_text=css_code,
                    value_json={"code": css_code, "label": util.truncate(util.normalize_space(css_match.group(0)), 120)},
                    evidence=util.clean_snippet(window),
                    confidence=0.88,
                    url=url,
                )
            )
        if CSS_PROFILE_MENTION_RE.search(block):
            lowered = block.lower()
            req = any(w in lowered for w in ("require", "must submit", "necessary", "submit the css profile", "file the css profile"))
            neg = _is_negated(block)
            findings.append(
                Finding(
                    topic="css_profile_required",
                    value_bool=req and not neg,
                    evidence=util.clean_snippet(block, 240),
                    confidence=0.75,
                    url=url,
                )
            )
    return findings


# --------------------------------------------------------------------- fee rules
def _extract_fees(markdown: str, *, url: str) -> list[Finding]:
    findings: list[Finding] = []
    for block in iter_blocks(markdown):
        fee_match = APPLICATION_FEE_RE.search(block)
        if fee_match:
            amount = util.parse_money(fee_match.group(0))
            if amount and amount <= 500:
                findings.append(
                    Finding(topic="application_fee", value_num=amount,
                            value_text=util.usd(amount),
                            evidence=util.clean_snippet(block[max(0, fee_match.start() - 80): fee_match.end() + 80]),
                            confidence=0.85, url=url)
                )
        if FEE_WAIVER_RE.search(block):
            window = block[max(0, block.lower().find("waiv") - 120):][:320] if "waiv" in block.lower() else block[:320]
            neg = _is_negated(window)
            findings.append(
                Finding(topic="application_fee_waiver", value_bool=not neg,
                        value_text=util.clean_snippet(window, 240),
                        evidence=util.clean_snippet(window),
                        confidence=0.85 if not neg else 0.8, url=url)
            )
            if neg and "not" in window.lower():
                continue
            eligibility = [kw for kw in ("free or reduced lunch", "nacsu", "nacac", "trio", "upward bound",
                                         "foster youth", "homeless", "first-generation", "first generation",
                                         "participate in a federal program", "low-income", "public assistance",
                                         "$", "income") if kw in window.lower() or kw in block.lower()]
            if eligibility:
                findings.append(
                    Finding(topic="fee_waiver_eligibility",
                            value_text=util.clean_snippet(block, 300),
                            value_json={"criteria": sorted(set(eligibility))},
                            evidence=util.clean_snippet(block, 300),
                            confidence=0.7, url=url)
                )
    return findings


# ---------------------------------------------------------------- deadline rules
def _extract_deadlines(markdown: str, *, url: str) -> list[Finding]:
    findings: list[Finding] = []
    today = util.utcnow().date()
    for block in iter_blocks(markdown):
        lowered = block.lower()
        if not any(word in lowered for word in DEADLINE_HEADWORDS):
            continue
        fragments = util.parse_date_fragments(block, ref=today)
        if not fragments:
            continue
        aid = has_any(lowered, AID_DEADLINE_HINTS)
        app = has_any(lowered, APP_DEADLINE_HINTS)
        grad = "graduate" in lowered or "master" in lowered or "m.s." in lowered
        transfer = "transfer" in lowered
        scholarship = "scholarship" in lowered
        category = ("aid" if aid and not app else
                    "scholarship" if scholarship else
                    "graduate_application" if grad else
                    "transfer_application" if transfer else
                    "application" if app else "other")
        for verbatim, resolved in fragments:
            topic = _deadline_topic(category)
            findings.append(
                Finding(
                    topic=topic,
                    value_date=util.iso_or_none(resolved),
                    value_text=verbatim,
                    label=_deadline_label(block, verbatim),
                    category=category,
                    evidence=util.clean_snippet(block, 300),
                    confidence=0.85 if resolved else 0.55,
                    url=url,
                )
            )
    return findings


def _deadline_topic(category: str) -> str:
    return {
        "aid": "priority_filing_deadline",
        "scholarship": "priority_filing_deadline",
        "graduate_application": "application_deadline_graduate",
        "transfer_application": "application_deadline_transfer",
        "application": "application_deadline_first_year",
    }.get(category, "application_deadline_first_year")


_LABEL_PATTERNS = (
    "early decision", "early action", "regular decision", "priority deadline", "final deadline",
    "fafsa priority", "financial aid deadline", "transfer deadline", "graduate deadline",
    "application deadline", "scholarship deadline", "housing accommodation deadline",
    "international applicant deadline", "fall admission", "spring admission", "rolling",
)


def _deadline_label(block: str, verbatim: str) -> str:
    lowered = block.lower()
    idx = lowered.find(verbatim.lower())
    window = lowered[max(0, idx - 120): idx + 40]
    best = None
    for pattern in _LABEL_PATTERNS:
        pos = window.rfind(pattern)
        if pos >= 0 and (best is None or pos > best[0]):
            best = (pos, pattern)
    if best:
        return best[1].title()
    head = util.normalize_space(block.split(":")[0])[:60]
    return head or "Deadline"


# --------------------------------------------------------------------- aid rules
def _extract_aid(markdown: str, *, url: str) -> list[Finding]:
    findings: list[Finding] = []
    for block in iter_blocks(markdown):
        lowered = block.lower()
        if "net price" in lowered:
            match = re.search(r"(?i)https?://[^\s)\]\"']*(?:net|npc|price)[^\s)\]\"']*", block)
            npc_url = util.norm_url(match.group(0)) if match else None
            findings.append(
                Finding(topic="net_price_calculator", value_text=npc_url,
                        value_json={"url": npc_url} if npc_url else None,
                        evidence=util.clean_snippet(block), confidence=0.75 if npc_url else 0.55, url=url)
            )
        if has_any(lowered, ("grant", "need-based", "need based", "pell")) and any(
            p in lowered for p in ("institutional", "university grant", "college grant", "endowed", "pell")
        ):
            findings.append(
                Finding(topic="institutional_grant", value_text=util.clean_snippet(block, 280),
                        evidence=util.clean_snippet(block, 280), confidence=0.6, url=url)
            )
        if has_any(lowered, SCHOLARSHIP_LEXICON):
            findings.append(
                Finding(topic="merit_scholarship", value_text=util.clean_snippet(block, 280),
                        evidence=util.clean_snippet(block, 280), confidence=0.65, url=url)
            )
        if has_any(lowered, AUTO_CONSIDER_PHRASES):
            findings.append(
                Finding(topic="scholarship_auto_consideration", value_bool=True,
                        value_text=util.clean_snippet(block, 240),
                        evidence=util.clean_snippet(block, 240), confidence=0.8, url=url)
            )
        if has_any(lowered, WORK_STUDY_LEXICON):
            findings.append(
                Finding(topic="work_study", value_bool=True, evidence=util.clean_snippet(block, 220),
                        value_text=util.clean_snippet(block, 220), confidence=0.7, url=url)
            )
        if has_any(lowered, ("renewal", "renew", "maintain", "satisfactory academic progress")) and any(
            p in lowered for p in ("scholarship", "grant", "aid")
        ) and has_any(lowered, ("gpa", "credits", "hours", "full-time", "semester")):
            findings.append(
                Finding(topic="aid_renewal_requirements", value_text=util.clean_snippet(block, 300),
                        evidence=util.clean_snippet(block, 300), confidence=0.65, url=url)
            )
        if has_any(lowered, FUNDING_LEXICON) and ("graduate" in lowered or "assistantship" in lowered
                                                           or "phd" in lowered or "master" in lowered or "ph.d." in lowered):
            topic = "tuition_waiver" if "tuition waiver" in lowered else "graduate_funding_package"
            findings.append(
                Finding(topic=topic, value_text=util.clean_snippet(block, 300),
                        evidence=util.clean_snippet(block, 300), confidence=0.7, url=url)
            )
        if has_any(lowered, TEST_OPTIONAL_PHRASES):
            findings.append(
                Finding(topic="standardized_test_policy", value_text=util.clean_snippet(block, 240),
                        evidence=util.clean_snippet(block, 240), confidence=0.8, url=url)
            )
        if "early action" in lowered or "early decision" in lowered:
            findings.append(
                Finding(topic="early_action_or_decision", value_text=util.clean_snippet(block, 240),
                        evidence=util.clean_snippet(block, 240), confidence=0.7, url=url)
            )
    return findings


# -------------------------------------------------------------- first-gen rules
def _extract_first_gen(markdown: str, *, url: str) -> list[Finding]:
    findings: list[Finding] = []
    for block in iter_blocks(markdown):
        lowered = block.lower()
        if has_any(lowered, TRIO_LEXICON) and ("trio" in lowered or "support services" in lowered):
            findings.append(Finding(topic="trio_student_support_services", value_bool=True,
                                    value_text=util.clean_snippet(block, 280),
                                    evidence=util.clean_snippet(block, 280), confidence=0.75, url=url))
        if has_any(lowered, FIRST_GEN_LEXICON):
            findings.append(Finding(topic="first_gen_program", value_text=util.clean_snippet(block, 300),
                                    evidence=util.clean_snippet(block, 300), confidence=0.7, url=url))
        if has_any(lowered, MENTORSHIP_LEXICON):
            findings.append(Finding(topic="mentorship_program", value_text=util.clean_snippet(block, 280),
                                    evidence=util.clean_snippet(block, 280), confidence=0.65, url=url))
        if has_any(lowered, BRIDGE_LEXICON):
            findings.append(Finding(topic="summer_bridge_program", value_text=util.clean_snippet(block, 240),
                                    evidence=util.clean_snippet(block, 240), confidence=0.6, url=url))
        if "mcnair" in lowered:
            findings.append(Finding(topic="mcnair_scholars", value_text=util.clean_snippet(block, 240),
                                    evidence=util.clean_snippet(block, 240), confidence=0.8, url=url))
    return findings


# ---------------------------------------------------------------- disability
def _extract_disability(markdown: str, *, url: str) -> list[Finding]:
    findings: list[Finding] = []
    accom_types: list[str] = []
    for block in iter_blocks(markdown):
        lowered = block.lower()
        if has_any(lowered, DISABILITY_OFFICE):
            findings.append(Finding(topic="disability_services_office",
                                    value_text=util.clean_snippet(block, 280),
                                    evidence=util.clean_snippet(block, 280), confidence=0.75, url=url))
        if has_any(lowered, ACCOM_PROCESS):
            findings.append(Finding(topic="accommodation_request_process",
                                    value_text=util.clean_snippet(block, 300),
                                    evidence=util.clean_snippet(block, 300), confidence=0.75, url=url))
        if "accommodat" in lowered and has_any(lowered, DOCUMENTATION):
            findings.append(Finding(topic="documentation_requirements",
                                    value_text=util.clean_snippet(block, 320),
                                    evidence=util.clean_snippet(block, 320), confidence=0.7, url=url))
        if has_any(lowered, ("assistive technolog", "adaptive technolog", "at lab", "assistive tech")):
            findings.append(Finding(topic="assistive_technology", value_text=util.clean_snippet(block, 300),
                                    evidence=util.clean_snippet(block, 300), confidence=0.75, url=url))
        if has_any(lowered, ("interpreter", "cart", "captioning", "hard of hearing", "deaf and")):
            findings.append(Finding(topic="deaf_hard_of_hearing_services",
                                    value_text=util.clean_snippet(block, 280),
                                    evidence=util.clean_snippet(block, 280), confidence=0.7, url=url))
        if has_any(lowered, ("wheelchair", "accessible route", "physical accessib", "ada transition",
                                      "elevator", "accessible map")):
            findings.append(Finding(topic="campus_accessibility", value_text=util.clean_snippet(block, 240),
                                    evidence=util.clean_snippet(block, 240), confidence=0.6, url=url))
        for name, needles in ACCOMMODATION_LEXICON.items():
            if has_any(lowered, needles):
                accom_types.append(name)
    if accom_types:
        unique = sorted(dict.fromkeys(accom_types))
        findings.append(
            Finding(topic="accommodation_types", value_json=unique,
                    value_text=", ".join(unique), confidence=0.7, url=url,
                    evidence=f"{len(unique)} accommodation types named on page")
        )
    return findings


# --------------------------------------------------------------- international
INTL_AID_PHRASES = ("no financial aid", "not eligible for financial aid", "external funding",
                    "citizenship requirement", "unable to offer aid", "international applicants",
                    "cannot be considered for need-based", "must demonstrate financial support",
                    "meets full need for", "need-blind for")


def _extract_international(markdown: str, *, url: str) -> list[Finding]:
    findings: list[Finding] = []
    for block in iter_blocks(markdown):
        lowered = block.lower()
        if not has_any(lowered, INTERN_LEXICON):
            continue
        findings.append(Finding(topic="international_student_office", value_bool=True,
                                value_text=util.clean_snippet(block, 240),
                                evidence=util.clean_snippet(block, 240), confidence=0.6, url=url))
        if has_any(lowered, ("i-20", "sevis", "ds-2019", "immigration advising", "port of entry")):
            findings.append(Finding(topic="i20_and_document_process", value_text=util.clean_snippet(block, 300),
                                    evidence=util.clean_snippet(block, 300), confidence=0.75, url=url))
        if has_any(lowered, ("proof of funds", "financial statement", "certification of finance",
                                      "bank statement", "affidavit of support", "demonstrate funding")):
            findings.append(Finding(topic="financial_certification", value_text=util.clean_snippet(block, 300),
                                    evidence=util.clean_snippet(block, 300), confidence=0.75, url=url))
        if has_any(lowered, ("toefl", "ielts", "duolingo", "english proficiency")):
            findings.append(Finding(topic="english_proficiency_requirements",
                                    value_text=util.clean_snippet(block, 280),
                                    evidence=util.clean_snippet(block, 280), confidence=0.75, url=url))
        if has_any(lowered, ("opt", "cpt", "practical training", "on-campus employment",
                                      "20 hours per week")):
            findings.append(Finding(topic="cpt_opt_support", value_text=util.clean_snippet(block, 300),
                                    evidence=util.clean_snippet(block, 300), confidence=0.7, url=url))
        if has_any(lowered, INTL_AID_PHRASES) and any(
            k in lowered for k in ("aid", "grant", "scholarship", "need", "funding")
        ):
            window = util.clean_snippet(block, 340)
            positive = has_any(lowered, ("meet full", "meet 100", "need-blind", "will award",
                                                  "are eligible for institutional", "competes for the same",
                                                  "no different"))
            negative = _is_negated(window)
            findings.append(Finding(topic="aid_for_international_students", value_text=window,
                                    evidence=window, confidence=0.8 if (positive or negative) else 0.6, url=url))
            if positive and not negative:
                findings.append(Finding(topic="need_blind_for_international", value_bool=True,
                                        value_text=window, evidence=window, confidence=0.75, url=url))
            elif negative:
                findings.append(Finding(topic="need_blind_for_international", value_bool=False,
                                        value_text=window, evidence=window, confidence=0.7, url=url))
    return findings


# ------------------------------------------------------------------- research
def _extract_research(markdown: str, *, url: str) -> list[Finding]:
    findings: list[Finding] = []
    for block in iter_blocks(markdown):
        lowered = block.lower()
        if has_any(lowered, RESEARCH_LEXICON):
            topic = "reu_program" if re.search(r"(?i)\breu\b", block) else "undergraduate_research_office"
            findings.append(Finding(topic=topic, value_text=util.clean_snippet(block, 280),
                                    evidence=util.clean_snippet(block, 280), confidence=0.7, url=url))
        if has_any(lowered, ("internship", "co-op", "cooperative education", "career center",
                                      "career services")):
            findings.append(Finding(topic="internship_career_office", value_text=util.clean_snippet(block, 240),
                                    evidence=util.clean_snippet(block, 240), confidence=0.6, url=url))
    return findings


# ------------------------------------------------------------------- contacts
def _extract_contacts(markdown: str, *, url: str) -> list[Finding]:
    emails = sorted({m.group(0).lower() for m in EMAIL_RE.finditer(markdown)})[:8]
    phones = sorted({util.normalize_space(m.group(0)) for m in PHONE_RE.finditer(markdown)})[:4]
    if not emails and not phones:
        return []
    value = {"emails": emails, "phones": phones}
    return [
        Finding(
            topic="office_contacts",
            value_json=value,
            value_text=", ".join(emails + phones)[:300],
            evidence=f"contacts on page: {', '.join((emails + phones)[:4])}",
            confidence=0.5,
            url=url,
        )
    ]
