"""Deterministic extractor: what it must find, and what it must refuse to invent."""

from __future__ import annotations

from sra_schools.extract.rules import extract_page

HOME = "https://state.example.edu/"


def _values(facts, topic):
    return [f.value_text for f in facts.by_topic(topic)]


def test_fafsa_school_code_is_extracted(aid_page):
    facts = extract_page(aid_page, url=HOME + "financial-aid", unitid=1, homepage=HOME)
    code = facts.best("fafsa_school_code")
    assert code is not None and code.value_text == "001234"
    assert code.confidence >= 0.85


def test_priority_deadline_is_parsed_with_iso_date(aid_page):
    facts = extract_page(aid_page, url=HOME + "financial-aid", unitid=1, homepage=HOME)
    deadline = facts.best("priority_filing_deadline")
    assert deadline is not None and deadline.value_date == "2027-03-02"


def test_net_price_calculator_keeps_the_url(aid_page):
    facts = extract_page(aid_page, url=HOME + "financial-aid", unitid=1, homepage=HOME)
    npc = facts.best("net_price_calculator")
    assert npc is not None
    assert npc.value_text and npc.value_text.startswith("https://state.example.edu/")


def test_work_study_and_scholarship_signals(aid_page):
    facts = extract_page(aid_page, url=HOME + "financial-aid", unitid=1, homepage=HOME)
    assert facts.best("work_study") is not None
    auto = facts.best("scholarship_auto_consideration")
    assert auto is not None and auto.value_bool is True


def test_application_fee_amount_and_waiver(admissions_page):
    facts = extract_page(admissions_page, url=HOME + "apply", unitid=1, homepage=HOME)
    fee = facts.best("application_fee")
    assert fee is not None and fee.value_num == 70.0
    waiver = facts.best("application_fee_waiver")
    assert waiver is not None and waiver.value_bool is True
    eligibility = facts.best("fee_waiver_eligibility")
    assert eligibility is not None
    assert "first-generation" in (eligibility.value_json or {}).get("criteria", [])


def test_deadlines_are_categorised_and_labelled(admissions_page):
    facts = extract_page(admissions_page, url=HOME + "apply", unitid=1, homepage=HOME)
    dates = {f.value_date for f in facts.by_topic("application_deadline_first_year")}
    assert {"2026-11-01", "2027-01-15"} <= dates


def test_disability_office_and_accommodation_types(admissions_page):
    facts = extract_page(admissions_page, url=HOME + "dss", unitid=1, homepage=HOME)
    assert facts.best("disability_services_office") is not None
    assert facts.best("accommodation_request_process") is not None
    assert facts.best("documentation_requirements") is not None
    types = facts.best("accommodation_types")
    assert types is not None
    named = set(types.value_json)
    assert {"extended test time", "ASL interpreting", "assistive technology lab"} <= named


def test_test_optional_policy_detected(admissions_page):
    facts = extract_page(admissions_page, url=HOME + "apply", unitid=1, homepage=HOME)
    assert facts.best("standardized_test_policy") is not None


def test_international_negation_is_recorded_as_negative(intl_page):
    facts = extract_page(intl_page, url=HOME + "intl", unitid=1, homepage=HOME)
    policy = facts.best("aid_for_international_students")
    assert policy is not None and "not eligible" in policy.value_text.lower()
    blind = facts.best("need_blind_for_international")
    assert blind is not None and blind.value_bool is False


def test_tuition_waiver_and_cpt_opt(intl_page):
    facts = extract_page(intl_page, url=HOME + "intl", unitid=1, homepage=HOME)
    assert facts.best("tuition_waiver") is not None
    assert facts.best("cpt_opt_support") is not None
    assert facts.best("financial_certification") is not None
    assert facts.best("i20_and_document_process") is not None
    assert facts.best("english_proficiency_requirements") is not None


def test_boilerplate_does_not_create_facts(aid_page):
    """Footer social/privacy chrome must never become 'evidence'."""
    facts = extract_page(aid_page, url=HOME, unitid=1, homepage=HOME)
    for finding in facts.findings:
        assert "All rights reserved" not in (finding.evidence or "")
        assert "Follow us on Facebook" not in (finding.evidence or "")


def test_short_keywords_use_word_boundaries():
    page = "We restart the carts annually. The casual ASL cluster meets.\n" + "x" * 40
    facts = extract_page(page, url=HOME, unitid=1, homepage=HOME)
    types = facts.best("accommodation_types")
    assert types is None or "captioning / CART" not in set(types.value_json or [])


def test_no_invention_from_empty_or_junk_input():
    assert extract_page("", url=HOME, unitid=1, homepage=HOME).findings == []
    junk = extract_page("lorem ipsum dolor sit amet consectetur adipiscing elit sed do",
                        url=HOME, unitid=1, homepage=HOME)
    assert not any(f.topic == "fafsa_school_code" for f in junk.findings)


def test_five_digit_number_is_not_a_fafsa_code():
    page = "Over 12345 students each year attend our campus and its programs widely."
    facts = extract_page(page, url=HOME, unitid=1, homepage=HOME)
    assert facts.best("fafsa_school_code") is None


def test_zip_code_is_not_a_fafsa_code():
    page = "FAFSA office, address: 12345 Zip, Some Town, CA. Send mail there today only."
    facts = extract_page(page, url=HOME, unitid=1, homepage=HOME)
    code = facts.best("fafsa_school_code")
    assert code is None or "zip" not in (code.evidence or "").lower()


def test_contacts_captured(aid_page):
    facts = extract_page(aid_page, url=HOME + "financial-aid", unitid=1, homepage=HOME)
    contacts = facts.best("office_contacts")
    assert contacts is not None
    assert "financialaid@state.example.edu" in (contacts.value_json or {}).get("emails", [])
