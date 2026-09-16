"""Shared vocabulary: needs, fact topics, program kinds, freshness classes.

Everything downstream (profiles, rules, sources, ranking, the DB) keys off these
enums so that a fact written by the crawler can be matched by the search engine
without string-typing drift.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class Need(str, Enum):
    """What a student is looking for. Profile definitions map onto these."""

    # Profile 1 - first-generation undergraduate
    UNDERGRADUATE_SCHOLARSHIP = "undergraduate_scholarship"
    FINANCIAL_AID = "financial_aid"
    APPLICATION_FEE_WAIVER = "application_fee_waiver"
    MENTORSHIP = "mentorship"
    # Profile 2 - disabled student
    ACCOMMODATION_FUNDING = "accommodation_funding"
    ACCESSIBLE_UNIVERSITY_PROGRAMS = "accessible_university_programs"
    DISABILITY_SCHOLARSHIPS = "disability_scholarships"
    ASSISTIVE_TECHNOLOGY_GRANTS = "assistive_technology_grants"
    # Profile 3 - international STEM student
    FULLY_FUNDED_DEGREE = "fully_funded_degree"
    TUITION_WAIVER = "tuition_waiver"
    VISA_AND_ELIGIBILITY_INFO = "visa_and_eligibility_info"
    RESEARCH_OR_INTERNSHIP = "research_or_internship"
    # Cross-cutting
    DEADLINE_CALENDAR = "deadline_calendar"
    OFFICIAL_CONTACTS = "official_contacts"
    NET_PRICE_ESTIMATE = "net_price_estimate"


class Freshness(str, Enum):
    """How stale a piece of information is allowed to get before refresh."""

    STATIC = "static"  # street address, institution ids            -> 365d
    STRUCTURAL = "structural"  # office exists, URL layout           -> 180d
    POLICY = "policy"  # need-blind, waiver eligibility        -> 90d
    DATE_BOUND = "date_bound"  # deadlines, FAFSA codes            -> 30d
    VOLATILE = "volatile"  # amounts, open/closed calls            -> 14d


@dataclass(frozen=True)
class Topic:
    """A single kind of fact we try to establish about an institution."""

    key: str
    label: str
    need: Need
    freshness: Freshness
    # Critical topics are expected to be answerable for a real match; missing
    # ones are reported as gaps and cost ranking score.
    critical: bool = False
    value_type: str = "text"  # text | url | money | date | bool | code | list


TOPICS: dict[str, Topic] = {}


def _t(key: str, label: str, need: Need, freshness: Freshness, *, critical: bool = False,
       value_type: str = "text") -> Topic:
    topic = Topic(key, label, need, freshness, critical, value_type)
    if topic.key in TOPICS:
        raise ValueError(f"duplicate topic {topic.key}")
    TOPICS[topic.key] = topic
    return topic


# --- Financial aid office -----------------------------------------------------
FAFSA_SCHOOL_CODE = _t("fafsa_school_code", "FAFSA federal school code", Need.FINANCIAL_AID,
                       Freshness.DATE_BOUND, critical=True, value_type="code")
PRIORITY_FILING_DEADLINE = _t("priority_filing_deadline", "FAFSA / aid priority filing date",
                              Need.FINANCIAL_AID, Freshness.DATE_BOUND, critical=True,
                              value_type="date")
CSS_PROFILE_CODE = _t("css_profile_code", "CSS Profile school code", Need.FINANCIAL_AID,
                      Freshness.DATE_BOUND, value_type="code")
CSS_PROFILE_DEADLINE = _t("css_profile_deadline", "CSS Profile deadline", Need.FINANCIAL_AID,
                          Freshness.DATE_BOUND, value_type="date")
CSS_PROFILE_REQUIRED = _t("css_profile_required", "CSS Profile required for institutional aid",
                          Need.FINANCIAL_AID, Freshness.POLICY, value_type="bool")
NET_PRICE_CALCULATOR = _t("net_price_calculator", "Net price calculator", Need.NET_PRICE_ESTIMATE,
                          Freshness.STRUCTURAL, critical=True, value_type="url")
FINANCIAL_AID_OFFICE = _t("financial_aid_office", "Financial aid office", Need.FINANCIAL_AID,
                          Freshness.STATIC, critical=True, value_type="url")
INSTITUTIONAL_GRANT = _t("institutional_grant", "Institutional grant aid", Need.FINANCIAL_AID,
                         Freshness.POLICY, value_type="text")
MERIT_SCHOLARSHIP = _t("merit_scholarship", "Merit/institutional scholarship",
                       Need.UNDERGRADUATE_SCHOLARSHIP, Freshness.POLICY, value_type="url")
SCHOLARSHIP_AUTO_CONSIDER = _t("scholarship_auto_consideration",
                               "Automatic scholarship consideration",
                               Need.UNDERGRADUATE_SCHOLARSHIP, Freshness.POLICY, value_type="bool")
WORK_STUDY = _t("work_study", "Federal work-study participation", Need.FINANCIAL_AID,
                Freshness.POLICY, value_type="bool")
AID_RENEWAL = _t("aid_renewal_requirements", "Renewal requirements for institutional aid",
                 Need.FINANCIAL_AID, Freshness.POLICY, value_type="text")
GRADUATE_FUNDING = _t("graduate_funding_package", "Graduate funding (waiver + assistantship)",
                      Need.FULLY_FUNDED_DEGREE, Freshness.POLICY, value_type="text")
TUITION_WAIVER = _t("tuition_waiver", "Tuition waiver programme", Need.TUITION_WAIVER,
                    Freshness.POLICY, value_type="text")

# --- Admissions / applying ----------------------------------------------------
APPLICATION_DEADLINE_FY = _t("application_deadline_first_year", "First-year application deadline",
                             Need.DEADLINE_CALENDAR, Freshness.DATE_BOUND, critical=True,
                             value_type="date")
APPLICATION_DEADLINE_TRANSFER = _t("application_deadline_transfer", "Transfer application deadline",
                                   Need.DEADLINE_CALENDAR, Freshness.DATE_BOUND, value_type="date")
APPLICATION_DEADLINE_GRAD = _t("application_deadline_graduate", "Graduate application deadline",
                               Need.DEADLINE_CALENDAR, Freshness.DATE_BOUND, value_type="date")
ADMISSIONS_OFFICE = _t("admissions_office", "Admissions office", Need.OFFICIAL_CONTACTS,
                       Freshness.STATIC, critical=True, value_type="url")
APPLICATION_PORTAL = _t("application_portal", "Where to apply", Need.DEADLINE_CALENDAR,
                        Freshness.STRUCTURAL, value_type="url")
APPLICATION_FEE = _t("application_fee", "Application fee amount", Need.APPLICATION_FEE_WAIVER,
                     Freshness.POLICY, value_type="money")
APPLICATION_FEE_WAIVER = _t("application_fee_waiver", "Application fee waiver route",
                            Need.APPLICATION_FEE_WAIVER, Freshness.POLICY, critical=True,
                            value_type="text")
FEE_WAIVER_ELIGIBILITY = _t("fee_waiver_eligibility", "Who qualifies for a fee waiver",
                            Need.APPLICATION_FEE_WAIVER, Freshness.POLICY, value_type="text")
TEST_POLICY = _t("standardized_test_policy", "SAT/ACT policy", Need.DEADLINE_CALENDAR,
                 Freshness.POLICY, value_type="text")
EARLY_OPTIONS = _t("early_action_or_decision", "Early action / early decision option",
                   Need.DEADLINE_CALENDAR, Freshness.POLICY, value_type="text")

# --- First-generation / mentorship -------------------------------------------
TRIO_SSS = _t("trio_student_support_services", "TRIO Student Support Services on campus",
              Need.MENTORSHIP, Freshness.POLICY, value_type="url")
FIRST_GEN_PROGRAM = _t("first_gen_program", "First-generation program or center", Need.MENTORSHIP,
                       Freshness.POLICY, critical=True, value_type="url")
MENTORSHIP_PROGRAM = _t("mentorship_program", "Mentorship program", Need.MENTORSHIP,
                        Freshness.POLICY, critical=True, value_type="url")
SUMMER_BRIDGE = _t("summer_bridge_program", "Summer bridge / orientation program", Need.MENTORSHIP,
                   Freshness.POLICY, value_type="url")
MCNAIR = _t("mcnair_scholars", "McNair Scholars (research + grad prep)",
            Need.RESEARCH_OR_INTERNSHIP, Freshness.POLICY, value_type="url")

# --- Disability ---------------------------------------------------------------
DISABILITY_OFFICE = _t("disability_services_office", "Disability/accessibility services office",
                       Need.ACCOMMODATION_FUNDING, Freshness.STATIC, critical=True, value_type="url")
ACCOMMODATION_PROCESS = _t("accommodation_request_process", "How to request accommodations",
                           Need.ACCOMMODATION_FUNDING, Freshness.POLICY, critical=True,
                           value_type="url")
DOCUMENTATION_REQUIREMENTS = _t("documentation_requirements", "Documentation required",
                                Need.ACCOMMODATION_FUNDING, Freshness.POLICY, value_type="text")
ACCOMMODATION_TYPES = _t("accommodation_types", "Accommodations offered",
                         Need.ACCESSIBLE_UNIVERSITY_PROGRAMS, Freshness.POLICY, value_type="list")
ASSISTIVE_TECH = _t("assistive_technology", "Assistive technology lab/services",
                    Need.ASSISTIVE_TECHNOLOGY_GRANTS, Freshness.POLICY, critical=True,
                    value_type="url")
DEAF_SERVICES = _t("deaf_hard_of_hearing_services", "Deaf/hard-of-hearing services (interpreters)",
                   Need.ACCOMMODATION_FUNDING, Freshness.POLICY, value_type="text")
ACCESSIBILITY_CAMPUS = _t("campus_accessibility", "Campus accessibility / physical access info",
                          Need.ACCESSIBLE_UNIVERSITY_PROGRAMS, Freshness.POLICY, value_type="url")
INCLUSIVE_PROGRAM = _t("inclusive_program", "Inclusive/supports program (IDD etc.)",
                       Need.ACCESSIBLE_UNIVERSITY_PROGRAMS, Freshness.POLICY, value_type="url")
DISABILITY_SCHOLARSHIP = _t("disability_scholarship", "Disability-specific scholarship programmes",
                            Need.DISABILITY_SCHOLARSHIPS, Freshness.POLICY, value_type="url")
VOC_REHAB_REFERRAL = _t("vocational_rehabilitation_referral", "Vocational rehabilitation referral",
                        Need.DISABILITY_SCHOLARSHIPS, Freshness.POLICY, value_type="bool")

# --- International ------------------------------------------------------------
INTL_OFFICE = _t("international_student_office", "International student office (ISSS)",
                 Need.VISA_AND_ELIGIBILITY_INFO, Freshness.STATIC, critical=True, value_type="url")
I20_PROCESS = _t("i20_and_document_process", "I-20 / visa document process",
                 Need.VISA_AND_ELIGIBILITY_INFO, Freshness.POLICY, critical=True, value_type="url")
FINANCIAL_CERTIFICATION = _t("financial_certification", "Proof-of-funds requirement",
                             Need.VISA_AND_ELIGIBILITY_INFO, Freshness.POLICY, value_type="text")
ENGLISH_PROFICIENCY = _t("english_proficiency_requirements", "English proficiency requirement",
                         Need.VISA_AND_ELIGIBILITY_INFO, Freshness.POLICY, value_type="text")
INTL_AID_POLICY = _t("aid_for_international_students", "Aid policy for international students",
                     Need.FULLY_FUNDED_DEGREE, Freshness.POLICY, critical=True, value_type="text")
NEED_BLIND_INTL = _t("need_blind_for_international", "Need-blind / full-need for internationals",
                     Need.FULLY_FUNDED_DEGREE, Freshness.POLICY, value_type="bool")
CPT_OPT = _t("cpt_opt_support", "CPT/OPT support (incl. STEM OPT)", Need.RESEARCH_OR_INTERNSHIP,
             Freshness.POLICY, value_type="text")

# --- Research / internships ---------------------------------------------------
UNDERGRAD_RESEARCH = _t("undergraduate_research_office", "Undergraduate research office",
                        Need.RESEARCH_OR_INTERNSHIP, Freshness.STRUCTURAL, critical=True,
                        value_type="url")
REU_PROGRAM = _t("reu_program", "NSF REU site", Need.RESEARCH_OR_INTERNSHIP, Freshness.POLICY,
                 value_type="url")
RESEARCH_CENTERS = _t("research_centers", "Named research centres/instances",
                      Need.RESEARCH_OR_INTERNSHIP, Freshness.STRUCTURAL, value_type="list")
INTERNSHIP_OFFICE = _t("internship_career_office", "Career/internship office",
                       Need.RESEARCH_OR_INTERNSHIP, Freshness.STRUCTURAL, value_type="url")
STEM_COLLEGE = _t("stem_programs", "STEM degree offerings", Need.RESEARCH_OR_INTERNSHIP,
                  Freshness.STATIC, critical=True, value_type="text")
OFFICE_CONTACTS = _t("office_contacts", "Direct contact details (email/phone)",
                     Need.OFFICIAL_CONTACTS, Freshness.STATIC, value_type="list")

TOPICS_BY_NEED: dict[Need, list[Topic]] = {}
for _topic in TOPICS.values():
    TOPICS_BY_NEED.setdefault(_topic.need, []).append(_topic)
for _v in TOPICS_BY_NEED.values():
    _v.sort(key=lambda t: t.key)

CRITICAL_TOPICS: tuple[Topic, ...] = tuple(
    t for t in sorted(TOPICS.values(), key=lambda t: t.key) if t.critical
)


class ProgramKind(str, Enum):
    GRANT = "grant"
    SCHOLARSHIP = "scholarship"
    TUITION_WAIVER = "tuition_waiver"
    ASSISTANTSHIP = "assistantship"
    FEE_WAIVER = "fee_waiver"
    ASSISTIVE_TECHNOLOGY = "assistive_technology"
    MENTORSHIP = "mentorship"
    RESEARCH_FELLOWSHIP = "research_fellowship"
    SUPPORT_PROGRAM = "support_program"
    SERVICES = "services"
    WORK_STUDY = "work_study"
    VISA_GUIDANCE = "visa_guidance"
    FEDERAL_AID_RULE = "federal_aid_rule"
    EMPLOYMENT_RULE = "employment_rule"
    NEED_BASED_AID = "need_based_aid"
    MERIT_SCHOLARSHIP = "merit_scholarship"
    BENEFIT = "benefit"


#: program `kind` strings produced by the research seed -> ProgramKind
PROGRAM_KIND_ALIASES = {
    "benefit": ProgramKind.BENEFIT,
    "federal_aid_rule": ProgramKind.FEDERAL_AID_RULE,
    "employment_rule": ProgramKind.EMPLOYMENT_RULE,
    "merit_scholarship": ProgramKind.MERIT_SCHOLARSHIP,
    "need_based_aid": ProgramKind.NEED_BASED_AID,
    "scholarship": ProgramKind.SCHOLARSHIP,
    "support_program": ProgramKind.SUPPORT_PROGRAM,
    "services": ProgramKind.SERVICES,
    "support": ProgramKind.SUPPORT_PROGRAM,
    "tuition_waiver": ProgramKind.TUITION_WAIVER,
    "assistantship": ProgramKind.ASSISTANTSHIP,
    "grant": ProgramKind.GRANT,
    "fee_waiver": ProgramKind.FEE_WAIVER,
    "assistive_technology": ProgramKind.ASSISTIVE_TECHNOLOGY,
    "assistive_tech": ProgramKind.ASSISTIVE_TECHNOLOGY,
    "mentorship": ProgramKind.MENTORSHIP,
    "research_fellowship": ProgramKind.RESEARCH_FELLOWSHIP,
    "work_study": ProgramKind.WORK_STUDY,
    "visa_guidance": ProgramKind.VISA_GUIDANCE,
}


def normalize_program_kind(raw: str | None) -> ProgramKind | None:
    if not raw:
        return None
    return PROGRAM_KIND_ALIASES.get(raw.strip().lower().replace("-", "_"))


class Level(str, Enum):
    UNDERGRADUATE = "undergraduate"
    GRADUATE = "graduate"
    BOTH = "both"
    COMMUNITY = "community"  # 2-year / certificate


class Citizenship(str, Enum):
    US_CITIZEN = "us_citizen"
    PERMANENT_RESIDENT = "permanent_resident"
    ELIGIBLE_NONCITIZEN = "eligible_noncitizen"
    DACA = "daca"
    INTERNATIONAL = "international"
    ANY = "any"
