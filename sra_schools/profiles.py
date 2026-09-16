"""The three student profiles (plus aliases) that drive search and ranking.

A profile is declarative: which needs it has, which institution-level facts prove
those needs are met, how to weight the ranking signals, what discovery queries to
issue when the cache is cold, and what the apply-playbook should contain.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .taxonomy import Need
from .util import usd

P1 = "first_generation"
P2 = "student_with_disability"
P3 = "international_stem"


@dataclass(frozen=True)
class StepSpec:
    """Template for one line of the 'how to apply successfully' checklist."""

    id: str
    title: str
    detail: str
    topics: tuple[str, ...] = ()
    need: Need | None = None
    when_missing: str | None = None
    blocking: bool = True


@dataclass(frozen=True)
class Profile:
    key: str
    title: str
    logline: str
    needs: tuple[Need, ...]
    required_topics: tuple[str, ...]
    preferred_topics: tuple[str, ...] = ()
    weights: dict[str, float] = field(default_factory=dict)
    program_needs: tuple[str, ...] = ()
    program_levels: tuple[str, ...] = ("undergraduate",)
    program_citizenship: tuple[str, ...] = ()
    default_filters: dict[str, Any] = field(default_factory=dict)
    discovery_queries: tuple[str, ...] = ()
    steps: tuple[StepSpec, ...] = ()
    example_needs: tuple[str, ...] = ()

    def describe(self) -> dict[str, Any]:
        return {
            "key": self.key,
            "title": self.title,
            "logline": self.logline,
            "needs": [n.value for n in self.needs],
            "required_topics": list(self.required_topics),
            "example_needs": list(self.example_needs),
            "default_filters": self.default_filters,
        }


# --------------------------------------------------------------------------- P1
FIRST_GENERATION = Profile(
    key=P1,
    title="First-generation student",
    logline="No parent with a four-year degree: needs money, a fee waiver, and people who know the system.",
    needs=(
        Need.UNDERGRADUATE_SCHOLARSHIP,
        Need.FINANCIAL_AID,
        Need.APPLICATION_FEE_WAIVER,
        Need.MENTORSHIP,
        Need.DEADLINE_CALENDAR,
        Need.NET_PRICE_ESTIMATE,
    ),
    required_topics=(
        "fafsa_school_code",
        "priority_filing_deadline",
        "net_price_calculator",
        "financial_aid_office",
        "application_fee_waiver",
        "application_deadline_first_year",
        "mentorship_program",
    ),
    preferred_topics=(
        "trio_student_support_services",
        "first_gen_program",
        "summer_bridge_program",
        "merit_scholarship",
        "scholarship_auto_consideration",
        "institutional_grant",
        "work_study",
        "fee_waiver_eligibility",
        "application_portal",
        "standardized_test_policy",
        "aid_renewal_requirements",
        "admissions_office",
    ),
    weights={
        "need_coverage": 26,
        "aid_generosity": 22,
        "first_gen_community": 14,
        "fee_waiver": 10,
        "mentorship": 10,
        "scholarship_richness": 8,
        "deadline_clarity": 6,
        "outcomes": 4,
    },
    program_needs=(
        "financial_aid",
        "undergraduate_scholarship",
        "application_fee_waiver",
        "mentorship",
    ),
    program_levels=("undergraduate",),
    program_citizenship=("us_citizen", "permanent_resident", "daca", "eligible_noncitizen", "any"),
    default_filters={"level": "undergraduate"},
    discovery_queries=(
        "{name} financial aid office FAFSA school code",
        "{name} application fee waiver first-generation",
        "{name} TRIO Student Support Services",
        "{name} first generation student programs mentoring",
        "{name} admission deadline freshman apply",
        "{name} net price calculator scholarship automatic consideration",
    ),
    example_needs=(
        "undergraduate scholarship",
        "financial aid",
        "application-fee waiver",
        "mentorship",
    ),
    steps=(
        StepSpec("estimate", "Estimate your real price before you apply",
                 "Run the net price calculator with your parent's tax numbers. "
                 "That figure - not the sticker - is what your family pays.",
                 topics=("net_price_calculator",), need=Need.NET_PRICE_ESTIMATE,
                 when_missing="No net price calculator found on this campus; ask the aid office for an estimate in writing."),
        StepSpec("waiver", "Get the application fee waived",
                 "First-generation applicants qualify for a fee waiver on almost every campus. "
                 "You usually need a counselor signature or a TRIO/NSC form - not your parents' tax return.",
                 topics=("application_fee_waiver", "fee_waiver_eligibility"),
                 need=Need.APPLICATION_FEE_WAIVER,
                 when_missing="No published waiver route: email admissions and cite first-generation status plus NACAC/Common App waiver eligibility."),
        StepSpec("apply", "Submit the application before the earliest deadline you can meet",
                 "Priority/early deadlines are where the institutional scholarships and grant dollars sit; "
                 "regular decision is often need-aware money only.",
                 topics=("application_deadline_first_year", "application_portal"),
                 need=Need.DEADLINE_CALENDAR),
        StepSpec("fafsa", "File the FAFSA with this school code on day one",
                 "Use the federal school code listed below. Many states and colleges have a priority "
                 "date months before the federal June 30 cutoff - miss it and the grant money is gone.",
                 topics=("fafsa_school_code", "priority_filing_deadline"), need=Need.FINANCIAL_AID),
        StepSpec("verify", "Answer every verification request within 10 days",
                 "First-return FAFSAs are verified more often. Gather W-2s/tax transcripts (IRS Data "
                 "Retrieval) and any untaxed-income documentation before the aid office asks."),
        StepSpec("compare", "Compare award letters as net cost, not as scholarships",
                 "Add grant + scholarship (free money), subtract that from net price, and check whether a "
                 "merit award renews all four years and what GPA protects it.",
                 topics=("aid_renewal_requirements", "merit_scholarship"), need=Need.UNDERGRADUATE_SCHOLARSHIP),
        StepSpec("support", "Name your mentor before move-in",
                 "TRIO/SSS, First-Gen centers and summer bridge programs give you a human who answers "
                 "'is this normal?' - the highest-retention factor for first-generation students.",
                 topics=("trio_student_support_services", "first_gen_program", "mentorship_program"),
                 need=Need.MENTORSHIP,
                 when_missing="No first-gen program published; ask the orientation office about mentoring and residential learning communities."),
        StepSpec("outside", "Apply to 5-10 external scholarships the school cannot displace",
                 "Choose portable awards with no school restriction; tell the aid office about each one so "
                 "it reduces loan rather than grant."),
    ),
)

# --------------------------------------------------------------------------- P2
DISABILITY = Profile(
    key=P2,
    title="Student with a disability",
    logline="Needs the accommodation funded and in place before day one, not negotiated in week three.",
    needs=(
        Need.ACCOMMODATION_FUNDING,
        Need.ACCESSIBLE_UNIVERSITY_PROGRAMS,
        Need.DISABILITY_SCHOLARSHIPS,
        Need.ASSISTIVE_TECHNOLOGY_GRANTS,
        Need.FINANCIAL_AID,
        Need.DEADLINE_CALENDAR,
    ),
    required_topics=(
        "disability_services_office",
        "accommodation_request_process",
        "documentation_requirements",
        "assistive_technology",
        "fafsa_school_code",
        "financial_aid_office",
    ),
    preferred_topics=(
        "accommodation_types",
        "deaf_hard_of_hearing_services",
        "campus_accessibility",
        "inclusive_program",
        "priority_filing_deadline",
        "net_price_calculator",
        "institutional_grant",
        "work_study",
    ),
    weights={
        "need_coverage": 28,
        "disability_support": 24,
        "assistive_tech": 10,
        "aid_generosity": 16,
        "inclusive_programs": 8,
        "deadline_clarity": 6,
        "outcomes": 4,
        "access_geography": 4,
    },
    program_needs=(
        "accommodation_funding",
        "accessible_university_programs",
        "disability_scholarships",
        "assistive_technology_grants",
        "financial_aid",
    ),
    program_levels=("undergraduate", "graduate"),
    program_citizenship=("us_citizen", "permanent_resident", "daca", "eligible_noncitizen", "any"),
    default_filters={},
    discovery_queries=(
        "{name} disability support services office accommodations request",
        "{name} assistive technology lab accessibility services documentation",
        "{name} deaf hard of hearing interpreter services blind low vision",
        "{name} inclusive campus program intellectual disability transition",
        "{name} housing meal accommodations disability request deadline",
        "{name} financial aid students with disabilities vocational rehabilitation",
    ),
    example_needs=(
        "accommodation funding",
        "accessible university programs",
        "disability scholarships",
        "assistive-technology grants",
    ),
    steps=(
        StepSpec("register", "Register with the disability office before orientation",
                 "Colleges do not auto-enrol you; accommodation only starts after you self-identify. "
                 "Do it in the admitted-student window so housing, note-taking and testing are set for week 1.",
                 topics=("disability_services_office", "accommodation_request_process"),
                 need=Need.ACCOMMODATION_FUNDING),
        StepSpec("docs", "Assemble documentation to that office's exact standard",
                 "Most campuses want a current evaluation by a qualified professional stating diagnosis, "
                 "functional limitation and recommended accommodation - request it from your clinician early.",
                 topics=("documentation_requirements",),
                 when_missing="Documentation standards unpublished; call the office and ask for their form."),
        StepSpec("vr", "Open a vocational rehabilitation case for the equipment and services",
                 "State VR will pay for assistive technology, interpreters, note-takers and sometimes "
                 "tuition once you have an IPE (Plan for Employment). Apply the spring of senior year.",
                 need=Need.ACCOMMODATION_FUNDING,
                 topics=("assistive_technology",)),
        StepSpec("aid", "File the FAFSA - disability can change dependency and need",
                 "Students receiving SSI/SSDI for their own disability are often independent for federal "
                 "aid, which removes parent income from the calculation. Report the disability questions.",
                 topics=("fafsa_school_code", "priority_filing_deadline"), need=Need.FINANCIAL_AID),
        StepSpec("tech", "Inventory campus assistive technology against your own toolkit",
                 "Testing, text-to-speech, CART, alt-format library services, adaptive hardware - "
                 "know what the campus provides so you can request what it does not.",
                 topics=("assistive_technology", "accommodation_types"),
                 need=Need.ASSISTIVE_TECHNOLOGY_GRANTS),
        StepSpec("money", "Apply to disability-specific scholarships in the fall",
                 "Blind/low-vision, hearing loss, mobility, LD, chronic illness and psychosocial "
                 "disability awards are small, portable and stackable - and mostly open Oct-Jan."),
        StepSpec("program", "Check the accessibility of the actual building and major",
                 "Lab, studio, clinical placement and study-abroad accessibility are decided "
                 "department by department. Get answers in writing before you enrol.",
                 topics=("campus_accessibility", "inclusive_program"),
                 need=Need.ACCESSIBLE_UNIVERSITY_PROGRAMS),
        StepSpec("appeal", "Escalate through the ADA coordinator if a request is refused",
                 "Every school receiving federal money has one. An academic-adjustment denial is an "
                 "institutional decision, not the end of the conversation."),
    ),
)

# --------------------------------------------------------------------------- P3
INTERNATIONAL_STEM = Profile(
    key=P3,
    title="International STEM student",
    logline="Full funding plus a visa-legal path to research work - a small set of campuses actually offer both.",
    needs=(
        Need.FULLY_FUNDED_DEGREE,
        Need.TUITION_WAIVER,
        Need.VISA_AND_ELIGIBILITY_INFO,
        Need.RESEARCH_OR_INTERNSHIP,
        Need.DEADLINE_CALENDAR,
    ),
    required_topics=(
        "aid_for_international_students",
        "international_student_office",
        "i20_and_document_process",
        "financial_certification",
        "application_deadline_graduate",
    ),
    preferred_topics=(
        "need_blind_for_international",
        "tuition_waiver",
        "graduate_funding_package",
        "english_proficiency_requirements",
        "cpt_opt_support",
        "undergraduate_research_office",
        "reu_program",
        "stem_programs",
        "internship_career_office",
        "scholarship_auto_consideration",
    ),
    weights={
        "intl_funding": 28,
        "need_coverage": 20,
        "stem_strength": 16,
        "graduate_programs": 10,
        "research_access": 10,
        "work_authorization": 6,
        "deadline_clarity": 6,
        "cost_value": 4,
    },
    program_needs=(
        "fully_funded_degree",
        "tuition_waiver",
        "visa_and_eligibility_info",
        "research_or_internship",
    ),
    program_levels=("undergraduate", "graduate"),
    program_citizenship=("international", "any"),
    default_filters={},
    discovery_queries=(
        "{name} financial aid international students undergraduate policy",
        "{name} graduate funding tuition waiver teaching assistantship stipend",
        "{name} international student and scholar services I-20 new student",
        "{name} CPT OPT practical training services",
        "{name} undergraduate research office STEM REU",
        "{name} international student proof of funds financial statement requirement",
    ),
    example_needs=(
        "fully funded bachelor's or master's",
        "tuition waiver",
        "visa and eligibility information",
        "research or internship",
    ),
    steps=(
        StepSpec("fit", "Shortlist only campuses whose stated policy covers international need",
                 "A small number of colleges are need-blind and meet full need for internationals; "
                 "far more say explicitly that international students get no aid. Read the sentence, not the FAQ title.",
                 topics=("aid_for_international_students", "need_blind_for_international"),
                 need=Need.FULLY_FUNDED_DEGREE),
        StepSpec("funding", "For a master's, chase the package - not the scholarship",
                 "Fully funded usually means tuition waiver + graduate/teaching assistantship + stipend, "
                 "awarded by the graduate school/department on a deadline earlier than the university's.",
                 topics=("graduate_funding_package", "tuition_waiver"), need=Need.TUITION_WAIVER),
        StepSpec("deadline", "Note the earliest of: university, graduate school, department, fellowship",
                 "International rounds close first (often Dec 1-Jan 15) and assistantships are gone by spring.",
                 topics=("application_deadline_graduate",), need=Need.DEADLINE_CALENDAR),
        StepSpec("test", "Confirm English proficiency and any waiver route",
                 "TOEFL/IELTS/Duolingo minimums differ by department; waivers are usually degree-country "
                 "based, not request-based.", topics=("english_proficiency_requirements",),
                 need=Need.VISA_AND_ELIGIBILITY_INFO),
        StepSpec("money-doc", "Prepare the certification of funds the I-20 requires",
                 "The school must document one year of tuition + living costs before issuing the I-20; "
                 "an award letter counts as proof, so the funding email must come first.",
                 topics=("financial_certification", "i20_and_document_process"),
                 need=Need.VISA_AND_ELIGIBILITY_INFO),
        StepSpec("visa", "Interview with the SEVIS fee, I-20 and funding letter, then plan for the 30-day window",
                 "Consular appointments in your country can be months out; do not book at the last minute.",
                 need=Need.VISA_AND_ELIGIBILITY_INFO),
        StepSpec("research", "Line up research that is visa-legal",
                 "On-campus work (20 hrs) and funded lab work in your program are usually fine; "
                 "off-campus needs CPT (curricular) or OPT, and STEM designations unlock the 24-month extension.",
                 topics=("undergraduate_research_office", "reu_program", "cpt_opt_support"),
                 need=Need.RESEARCH_OR_INTERNSHIP),
        StepSpec("outside", "Apply to external fellowships that accept international students",
                 "Humphrey, Fulbright (home-country), AAUW, World Bank and foundation awards are portable "
                 "and can be the difference in a funding appeal to the department."),
    ),
)

PROFILES: dict[str, Profile] = {
    FIRST_GENERATION.key: FIRST_GENERATION,
    DISABILITY.key: DISABILITY,
    INTERNATIONAL_STEM.key: INTERNATIONAL_STEM,
}

_ALIASES = {
    "p1": P1, "first-gen": P1, "first_gen": P1, "firstgen": P1, "first-generation": P1,
    "first generation": P1, "firstgeneration": P1, "1": P1, "profile1": P1,
    "p2": P2, "disability": P2, "disabled": P2, "disabled-student": P2, "handicap": P2,
    "student_with_disabilities": P2, "special_needs": P2, "2": P2, "profile2": P2, "ada": P2,
    "p3": P3, "international": P3, "intl": P3, "international-stem": P3, "international_stem": P3,
    "foreign": P3, "f1": P3, "f-1": P3, "3": P3, "profile3": P3, "study_abroad": P3,
}


def get_profile(key: str | Profile | None) -> Profile | None:
    """Resolve a profile from key, alias or a fuzzy label."""
    if key is None:
        return None
    if isinstance(key, Profile):
        return key
    raw = str(key).strip().lower()
    if raw in PROFILES:
        return PROFILES[raw]
    if raw in _ALIASES:
        return PROFILES[_ALIASES[raw]]
    squashed = raw.replace(" ", "_").replace("-", "_")
    if squashed in PROFILES:
        return PROFILES[squashed]
    for profile in PROFILES.values():
        if squashed.startswith(profile.key.split("_")[0]) and len(squashed) > 4:
            return profile
    return None


def list_profiles() -> list[Profile]:
    return list(PROFILES.values())


def all_topic_keys(profile: Profile) -> tuple[str, ...]:
    return tuple(dict.fromkeys((*profile.required_topics, *profile.preferred_topics)))


def describe_profiles() -> list[dict[str, Any]]:
    return [p.describe() for p in PROFILES.values()]


# re-exported for report rendering
__all__ = ["Profile", "StepSpec", "PROFILES", "P1", "P2", "P3", "get_profile",
           "list_profiles", "describe_profiles", "all_topic_keys", "usd"]
