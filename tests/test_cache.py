"""Cache behaviour: the reason a search does not re-scrape the internet."""

from __future__ import annotations

from datetime import timedelta

from sra_schools.db.cache import CacheStatus, FRESHNESS_TTL
from sra_schools.db.database import iso, now_utc
from sra_schools.extract.fetchers import PageResult
from sra_schools.extract.pipeline import Pipeline
from sra_schools.extract.rules import LinkFinding
from sra_schools.profiles import FIRST_GENERATION, get_profile
from sra_schools.sources import SourceRegistry
from sra_schools.taxonomy import Freshness
from tests.conftest import CannedFetcher

HOME = "https://state.example.edu/"
#: the exact path the curated registry tells the crawler to try first
URL = SourceRegistry.load().candidate_urls(HOME, "fafsa_school_code", limit=1)[0]


def _expire(cache, url, seconds=-10):
    cache.db.execute(
        "UPDATE web_pages SET expires_at = ? WHERE url = ?",
        (iso(now_utc() + timedelta(seconds=seconds)), url),
    )


# ------------------------------------------------------------------ page cache
def test_fresh_page_is_served_without_network(db, cache):
    cache.put(URL, status=200, body="hello world", ttl_seconds=3600)
    page = cache.get(URL)
    assert page is not None and page.fresh and page.body == "hello world"


def test_body_round_trips_compressed(db, cache):
    body = "FAFSA code 001234. " * 4000
    cache.put(URL, status=200, body=body, ttl_seconds=3600)
    assert cache.get(URL).body == body
    stored = cache.db.scalar("SELECT LENGTH(body_gzip) FROM web_pages WHERE url = ?", (URL,))
    assert stored < len(body.encode()) // 4


def test_expiry_makes_a_page_due(db, cache):
    cache.put(URL, status=200, body="x", ttl_seconds=60)
    assert URL not in cache.due_urls()
    _expire(cache, URL)
    assert URL in cache.due_urls()


def test_validators_are_kept_for_revalidation(db, cache):
    cache.put(URL, status=200, body="x", etag='"abc"', last_modified="Tue, 01 Sep 2026 00:00:00 GMT",
              ttl_seconds=60)
    assert cache.validators(URL) == ('"abc"', "Tue, 01 Sep 2026 00:00:00 GMT")
    _expire(cache, URL)
    cache.touch_validated(URL, 3600)
    assert cache.get(URL).fresh


def test_dead_urls_are_negatively_cached(db, cache):
    assert not cache.is_known_missing(URL)
    cache.put(URL, status=404, ttl_seconds=3600)
    assert cache.is_known_missing(URL)
    _expire(cache, URL, seconds=-7200)
    assert not cache.is_known_missing(URL)


def test_freshness_ttl_is_per_topic_class():
    assert FRESHNESS_TTL[Freshness.DATE_BOUND] < FRESHNESS_TTL[Freshness.POLICY]
    assert FRESHNESS_TTL[Freshness.STATIC] > FRESHNESS_TTL[Freshness.STRUCTURAL]


# ----------------------------------------------------------------- query cache
def test_query_cache_fresh_then_stale_then_purged(db, repo, institutions):
    from sra_schools.db.cache import QueryCache

    qc = QueryCache(db, default_ttl=60)
    assert qc.get("fp1")[0] is None
    qc.put("fp1", {"results": [{"a": 1}]}, profile="first_generation", params={})
    payload, status = qc.get("fp1")
    assert status == CacheStatus.FRESH and payload["results"][0]["a"] == 1
    db.execute("UPDATE query_cache SET expires_at = ? WHERE fingerprint = 'fp1'",
               (iso(now_utc() - timedelta(seconds=1)),))
    payload, status = qc.get("fp1")
    assert status == CacheStatus.STALE and payload is not None
    assert qc.purge_expired() == 1
    assert qc.get("fp1")[0] is None


# -------------------------------------------------------------------- pipeline
def _pipeline(db, repo, cache, pages):
    return Pipeline(repo, cache, fetcher=CannedFetcher(pages), max_pages=50,
                    max_new_pages_per_institution=4, request_delay_s=0.0)


def test_ensure_parses_pages_into_facts(db, repo, cache, institutions, aid_page):
    fetcher = CannedFetcher({URL: PageResult(url=URL, status=200, text=aid_page,
                                             title="Financial Aid")})
    pipe = Pipeline(repo, cache, fetcher=fetcher, max_pages=50,
                    max_new_pages_per_institution=4, request_delay_s=0.0)
    inst = repo.get_institution(100001)
    report = pipe.ensure(inst, topics=["fafsa_school_code"])
    assert report.facts_written >= 1
    grouped = repo.facts_by_topic(100001)
    assert grouped["fafsa_school_code"][0].value_text == "001234"
    assert grouped["priority_filing_deadline"][0].value_date == "2027-03-02"
    assert repo.db.count("web_pages") >= 1


def test_second_ensure_touches_the_network_zero_times(db, repo, cache, institutions, aid_page):
    fetcher = CannedFetcher({URL: PageResult(url=URL, status=200, text=aid_page)})
    pipe = Pipeline(repo, cache, fetcher=fetcher, max_pages=50,
                    max_new_pages_per_institution=2, request_delay_s=0.0)
    inst = repo.get_institution(100001)
    first = pipe.ensure(inst, topics=["fafsa_school_code"])
    calls_after_first = len(fetcher.calls)
    assert first.facts_written >= 1, "the first pass is the expensive one"

    # an answered topic is not even planned again
    second = pipe.ensure(inst, topics=["fafsa_school_code"])
    assert len(fetcher.calls) == calls_after_first, "a fresh page must not be re-fetched"
    assert second.planned == 0 and second.facts_written == 0

    # forcing a re-crawl must not re-download what is inside its TTL; it may still
    # try a path it has never probed before
    third = pipe.ensure(inst, topics=["fafsa_school_code"], force=True)
    newly_requested = [u for batch in fetcher.calls[calls_after_first:] for u in batch]
    assert URL not in newly_requested, "a fresh cached page must never be re-requested"
    assert third.served_fresh >= 1 and third.facts_written == 0


def test_answered_topics_are_not_replanned(db, repo, cache, institutions, aid_page):
    fetcher = CannedFetcher({URL: PageResult(url=URL, status=200, text=aid_page)})
    pipe = Pipeline(repo, cache, fetcher=fetcher, max_pages=50, request_delay_s=0.0)
    inst = repo.get_institution(100001)
    pipe.ensure(inst, topics=["fafsa_school_code"])
    before = [u for batch in fetcher.calls for u in batch]
    pipe.ensure(inst, topics=["fafsa_school_code"])
    assert [u for batch in fetcher.calls for u in batch] == before


def test_expired_page_is_revalidated_not_refetched(db, repo, cache, institutions, aid_page):
    fetcher = CannedFetcher({URL: PageResult(url=URL, status=200, text=aid_page)})
    pipe = Pipeline(repo, cache, fetcher=fetcher, max_pages=50, request_delay_s=0.0)
    inst = repo.get_institution(100001)
    pipe.ensure(inst, topics=["fafsa_school_code"])
    # make the cached copy due and give it a validator, as a real response would
    cache.db.execute("UPDATE web_pages SET etag = '\"v1\"' WHERE url = ?", (URL,))
    _expire(cache, URL)
    report = pipe.ensure(inst, topics=["fafsa_school_code"], force=True)
    assert report.not_modified >= 1, "a due page with a validator is revalidated, not refetched"
    assert report.facts_written == 0, "a 304 means the stored facts are still correct"
    assert repo.db.count("facts", "superseded_at IS NULL") >= 1


def test_budget_stops_a_run(db, repo, cache, institutions):
    pages = {f"https://state.example.edu/p{i}": PageResult(url=f"x{i}", status=200, text="y" * 900)
             for i in range(20)}
    fetcher = CannedFetcher(pages)
    pipe = Pipeline(repo, cache, fetcher=fetcher, max_pages=2,
                    max_new_pages_per_institution=25, request_delay_s=0.0)
    inst = repo.get_institution(100001)
    report = pipe.ensure(inst, profile=FIRST_GENERATION)
    assert len([u for batch in fetcher.calls for u in batch]) <= 3
    assert report.planned > report.fetched


def test_negative_results_do_not_repeat_within_ttl(db, repo, cache, institutions, aid_page):
    fetcher = CannedFetcher({URL: PageResult(url=URL, status=200, text=aid_page)})
    pipe = Pipeline(repo, cache, fetcher=fetcher, max_pages=50, request_delay_s=0.0)
    inst = repo.get_institution(100001)
    pipe.ensure(inst, topics=["fafsa_school_code", "mentorship_program"])
    asked = [u for batch in fetcher.calls for u in batch]
    assert asked.count("https://state.example.edu/mentorship") <= 1


def test_link_harvest_feeds_the_second_round(db, repo, cache, institutions, admissions_page):
    """Round 1 discovers links from the homepage; round 2 follows them."""
    home = "https://state.example.edu/"
    apply_page = "https://state.example.edu/join/apply"
    fetcher = CannedFetcher({
        home: PageResult(url=home, status=200, text=(
            "# State University\n"
            "Prospective students: [Apply now](" + apply_page + ") "
            "for admission and deadlines.\n" + "body text here. " * 20)),
        apply_page: PageResult(url=apply_page, status=200, text=admissions_page),
    })
    pipe = Pipeline(repo, cache, fetcher=fetcher, max_pages=50, request_delay_s=0.0)
    inst = repo.get_institution(100001)
    inst.url_homepage = home
    report = pipe.ensure(inst, profile=get_profile("first_generation"))
    fee = repo.facts_by_topic(100001).get("application_fee")
    assert fee, "the waiver/deadline page should have been reached through the homepage"
    assert fee[0].value_num == 70.0
    assert apply_page in [u for batch in fetcher.calls for u in batch] or report.served_fresh


def test_planned_pages_skip_known_dead_urls(db, repo, cache, institutions):
    cache.put("https://state.example.edu/dead", status=404, ttl_seconds=3600)
    pipe = _pipeline(db, repo, cache, {})
    pages = pipe.plan(repo.get_institution(100001), ["fafsa_school_code"])
    assert "https://state.example.edu/dead" not in [p.url for p in pages]


def test_replan_uses_discovered_links_only(db, repo, cache, institutions):
    pipe = _pipeline(db, repo, cache, {})
    inst = repo.get_institution(100001)
    repo.add_links(inst.unitid, [LinkFinding(url="https://state.example.edu/dss",
                                           topic="disability_services_office")])
    follow = pipe.replan(inst, ["disability_services_office"])
    assert [p.url for p in follow] == ["https://state.example.edu/dss"]
    assert follow[0].reason == "discovered"
