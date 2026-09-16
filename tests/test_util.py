"""Pure helpers: urls, dates, money, text."""

from __future__ import annotations

from datetime import date

from sra_schools import util


def test_norm_url_canonicalises():
    assert util.norm_url("http://WWW.Example.EDU/Path/?gclid=1#frag") == "http://example.edu/Path?gclid=1"
    assert util.norm_url("example.edu/aid/") == "https://example.edu/aid"
    assert util.norm_url("") is None


def test_domain_of_and_same_site():
    assert util.domain_of("https://aid.state.edu/x") == "aid.state.edu"
    assert util.is_same_site("https://finance.state.edu/aid", "https://state.edu/")
    assert not util.is_same_site("https://facebook.com/state", "https://state.edu/")


def test_abs_url_drops_non_http():
    assert util.abs_url("https://state.edu/x", "mailto:hi@state.edu") is None
    assert util.abs_url("https://state.edu/x", "/aid") == "https://state.edu/aid"


def test_parse_date_fragments_resolves_year_forward():
    ref = date(2026, 9, 15)
    hits = dict(util.parse_date_fragments("Deadline November 1, 2026", ref=ref))
    assert hits["November 1, 2026"] == date(2026, 11, 1)
    bare = dict(util.parse_date_fragments("Apply by March 2 to be considered", ref=ref))
    assert bare["March 2"] == date(2027, 3, 2), "a bare spring date must roll to next cycle"


def test_parse_date_fragments_us_and_iso():
    hits = util.parse_date_fragments("11/15/2026 and 2026-11-16", ref=date(2026, 1, 1))
    assert date(2026, 11, 15) in [d for _, d in hits]
    assert date(2026, 11, 16) in [d for _, d in hits]


def test_parse_date_fragments_rejects_impossible():
    assert [d for _, d in util.parse_date_fragments("Feb 30, 2026")] == [None]


def test_parse_money_and_float():
    assert util.parse_money("fee $1,450.00") == 1450.0
    assert util.to_float("Privacy-suppressed") is None
    assert util.to_float("NA") is None
    assert util.to_float(" 12,345 ") == 12345.0
    assert util.to_int("3") == 3
    assert util.to_bool("yes") is True and util.to_bool("no") is False


def test_extract_links_from_markdown():
    text = "see [Net Price Calculator](https://state.edu/npc) and ![img](x.png)"
    links = util.extract_links(text)
    assert ("Net Price Calculator", "https://state.edu/npc") in links


def test_fingerprint_is_order_independent():
    assert util.fingerprint({"a": 1, "b": 2}) == util.fingerprint({"b": 2, "a": 1})


def test_academic_year_rolls_in_july():
    assert util.academic_year_for(date(2026, 6, 30)) == 2026
    assert util.academic_year_for(date(2026, 10, 1)) == 2027


def test_clean_snippet_normalises_whitespace():
    assert util.clean_snippet("a\n\n   b\tc") == "a b c"


def test_strip_html_removes_scripts():
    html = "<html><head><script>bad()</script></head><body><h1>Hello</h1><p>World</p></body></html>"
    text = util.strip_html(html)
    assert "bad" not in text and "Hello" in text and "World" in text
