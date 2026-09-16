"""The enrich/refresh pipeline: plan -> fetch -> extract -> store.

Ordering is deliberate and cheap-first, so a search never triggers a wander:

1. **campus URL guesses** from the curated source registry (same domain, known paths)
2. **links already discovered** on this institution's pages, by topic
3. **one bounded search** per still-unanswered critical topic (domain-scoped first)

Every layer checks the page cache first: a fresh page is never re-fetched, a due
page is revalidated with its ETag/Last-Modified, and an unchanged body is never
re-parsed - which is also what keeps the optional LLM from being billed twice for
the same document.
"""

from __future__ import annotations

import time
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from typing import Any

from .. import util
from ..db.cache import FRESHNESS_TTL, PageCache
from ..db.database import iso
from ..db.repository import Repository
from ..models import Deadline, Institution
from ..profiles import Profile, all_topic_keys
from ..sources import SourceRegistry
from ..taxonomy import Freshness, TOPICS, Topic
from .fetchers import Fetcher, PageResult
from .llm import PROMPT_VERSION
from .rules import RULES_VERSION, Finding, LinkFinding, extract_page
from .search import Searcher


@dataclass(slots=True)
class PlannedPage:
    url: str
    topics: list[str] = field(default_factory=list)
    reason: str = "candidate"  # candidate | discovered | search | retry

    def key(self) -> str:
        return self.url


@dataclass(slots=True)
class EnrichReport:
    unitid: int
    name: str = ""
    planned: int = 0
    fetched: int = 0
    served_fresh: int = 0
    not_modified: int = 0
    failed: int = 0
    facts_written: int = 0
    links_written: int = 0
    deadlines_written: int = 0
    llm_calls: int = 0
    searches: int = 0
    topics_answered: list[str] = field(default_factory=list)
    gaps: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    seconds: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "unitid": self.unitid, "name": self.name, "planned": self.planned,
            "fetched": self.fetched, "served_fresh": self.served_fresh,
            "not_modified": self.not_modified, "failed": self.failed,
            "facts_written": self.facts_written, "links_written": self.links_written,
            "deadlines_written": self.deadlines_written, "llm_calls": self.llm_calls,
            "searches": self.searches, "topics_answered": self.topics_answered,
            "gaps": self.gaps, "notes": self.notes, "seconds": round(self.seconds, 2),
        }

    def summary_line(self) -> str:
        return (f"{self.unitid} {self.name[:38]:38s} pages={self.fetched + self.served_fresh} "
                f"fresh={self.served_fresh} facts={self.facts_written} gaps={len(self.gaps)}")


class Pipeline:
    def __init__(
        self,
        repo: Repository,
        cache: PageCache,
        *,
        fetcher: Fetcher,
        searcher: Searcher | None = None,
        registry: SourceRegistry | None = None,
        llm: Any | None = None,  # noqa: ANN401
        max_pages: int = 200,
        max_new_pages_per_institution: int = 6,
        request_delay_s: float = 0.35,
    ) -> None:
        self.repo = repo
        self.cache = cache
        self.fetcher = fetcher
        self.searcher = searcher
        self.registry = registry or SourceRegistry.load()
        self.llm = llm
        self.max_pages = max_pages
        self.max_new_pages_per_institution = max_new_pages_per_institution
        self.request_delay_s = request_delay_s
        self._budget_left = max_pages

    def reset_budget(self, pages: int | None = None) -> None:
        """Reset the remaining fetch budget to max_pages or the given amount."""
        self._budget_left = self.max_pages if pages is None else max(0, int(pages))

    # ------------------------------------------------------------------ planning
    def plan(self, institution: Institution, topics: Sequence[str] | None = None,
             *, include_search_results: bool = True) -> list[PlannedPage]:
        """Deterministic page list for an institution, cheapest-and-most-certain first."""
        wanted = list(topics or all_topics())
        planned: dict[str, PlannedPage] = {}

        def add(url: str | None, topic: str | None, reason: str) -> None:
            if not url:
                return
            entry = planned.get(url)
            if entry is None:
                planned[url] = PlannedPage(url=url, topics=[t for t in (topic,) if t], reason=reason)
            elif topic and topic not in entry.topics:
                entry.topics.append(topic)

        # 1. the front door: it always exists and it links to everything else
        if institution.url_homepage:
            add(institution.url_homepage, None, "homepage")
        # 2. links we already harvested from previous crawls of this campus
        for topic in wanted:
            for link in self.repo.links_for(institution.unitid, topic=topic)[:1]:
                add(link.url, topic, "discovered")
        # 3. curated path guesses on the same domain
        if include_search_results:
            for topic in wanted:
                for url in self.registry.candidate_urls(institution.url_homepage, topic, limit=2):
                    add(url, topic, "candidate")
        revalidatable = self._revalidatable_urls(planned)

        def rank(page: PlannedPage) -> tuple[int, str]:
            if page.reason == "homepage":
                return (0, page.url)
            if page.url in revalidatable:
                return (1, page.url)          # a 304 is far cheaper than a new document
            if page.reason == "discovered":
                return (2, page.url)
            return (3, page.url)

        ordered = sorted(planned.values(), key=rank)
        # a URL we probed hours ago and found dead must not eat the budget twice
        return [page for page in ordered if not self.cache.is_known_missing(page.url)]

    def _revalidatable_urls(self, candidate_urls: Iterable[str]) -> set[str]:
        """Pages we already hold a validator for and whose TTL has lapsed.

        On a refresh pass these go before unseen URLs: revalidation costs one header
        and usually a 304, while a new document costs a transfer, a parse and the
        storage of another body.
        """
        urls = [url for url in candidate_urls if url]
        if not urls:
            return set()
        found: set[str] = set()
        for chunk in util.chunks(urls, 200):
            rows = self.repo.db.query(
                f"SELECT url FROM web_pages WHERE url IN ({','.join('?' * len(chunk))}) "
                "AND status = 200 AND expires_at <= ? "
                "AND (etag IS NOT NULL OR last_modified IS NOT NULL)",
                [*chunk, iso()],
            )
            found.update(row[0] for row in rows)
        return found

    def replan(self, institution: Institution, missing: Sequence[str]) -> list[PlannedPage]:
        """Second round: follow what the first round's links told us about.

        Links keyed to an unanswered topic come first, but a campus page answers many
        topics at once, so the strongest unvisited links are followed as well - that
        is how a homepage whose nav says "Financial Aid" reaches the deadline table.
        """
        planned: list[PlannedPage] = []
        visited = {row[0] for row in self.repo.db.query(
            "SELECT url FROM web_pages WHERE institution_unitid = ?", (institution.unitid,))}
        seen = set(visited)
        if institution.url_homepage:
            seen.add(util.norm_url(institution.url_homepage))

        def take(url: str | None, topic: str | None, force: bool = False) -> None:
            if not url or url in seen:
                return
            if not force and url in visited:
                return
            seen.add(url)
            planned.append(PlannedPage(url=url, topics=[t for t in (topic,) if t],
                                       reason="discovered"))

        for topic in missing:
            for link in self.repo.links_for(institution.unitid, topic=topic)[:1]:
                take(link.url, topic)
        if len(planned) < self.max_new_pages_per_institution:
            for link in self.repo.links_for(institution.unitid)[: self.max_new_pages_per_institution]:
                take(link.url, link.topic)
        return planned[: self.max_new_pages_per_institution]

    # ------------------------------------------------------------------ running
    def ensure(
        self,
        institution: Institution,
        *,
        profile: Profile | None = None,
        topics: Sequence[str] | None = None,
        force: bool = False,
    ) -> EnrichReport:
        """Bring the cache up to date for one institution (bounded by budget)."""
        started = time.monotonic()
        report = EnrichReport(unitid=institution.unitid, name=institution.name)
        wanted = list(topics or (all_topic_keys(profile) if profile else all_topics()))
        live = self.repo.facts_by_topic(institution.unitid)
        if not force:
            wanted = [t for t in wanted if t not in live]
        if not wanted and not force:
            report.topics_answered = sorted(live)
            self.repo.recompute_due(institution.unitid)
            report.seconds = time.monotonic() - started
            return report

        # round 1: homepage + already-known links + curated path guesses
        pages = self.plan(institution, wanted)
        report.planned = len(pages)
        self._consume(pages[: self.max_new_pages_per_institution], institution, report, wanted)

        # round 2: follow what the homepage actually links to
        missing = [t for t in wanted if t not in self._answered(institution.unitid)]
        if missing:
            follow = self.replan(institution, missing)
            report.planned += len(follow)
            self._consume(follow, institution, report, missing)

        # round 3: critical topics still unanswered -> bounded, domain-scoped search
        missing = [t for t in wanted if t not in self._answered(institution.unitid)]
        if self.searcher is not None and missing and self._budget_left > 0:
            report.searches += self._search_and_harvest(institution, missing, report)

        if self.llm is not None and missing:
            report.llm_calls += self._llm_gapfill(institution, missing, report)

        answered = self._answered(institution.unitid)
        report.topics_answered = sorted(answered)
        report.gaps = _missing(wanted, answered)
        self.repo.recompute_due(institution.unitid)
        report.seconds = time.monotonic() - started
        return report

    def refresh(self, urls: Iterable[str]) -> EnrichReport:
        """Revalidate specific URLs (used by ``sra-schools refresh --stale``)."""
        report = EnrichReport(unitid=0, name="refresh")
        pages = [PlannedPage(url=url, topics=[]) for url in urls if url]
        report.planned = len(pages)
        dummy = Institution(unitid=0, name="")
        self._consume(pages, dummy, report, [])
        return report

    # ------------------------------------------------------------- page consume
    def _consume(self, pages: Sequence[PlannedPage], institution: Institution,
                 report: EnrichReport, wanted: Sequence[str]) -> None:
        due: list[PlannedPage] = []
        validators: dict[str, tuple[str | None, str | None]] = {}
        for page in pages:
            if self._budget_left <= 0:
                report.notes.append("budget exhausted")
                break
            cached = self.cache.get(page.url)
            if cached and cached.body and cached.fresh and not _is_error_page(cached):
                report.served_fresh += 1
                self._apply(cached.url, cached.body, cached.title, institution, report,
                            cached.content_sha256 or util.sha256_text(cached.body), cached.status or 200)
                continue
            due.append(page)
            etag, last_modified = self.cache.validators(page.url)
            if etag or last_modified:
                validators[page.url] = (etag, last_modified)
        if not due:
            return
        # the budget is enforced *before* dispatch, not after: one batch of 40 URLs
        # would otherwise blow a 5-page limit
        due = due[: max(0, self._budget_left)]
        urls = [p.url for p in due]
        results = self.fetcher.fetch(urls, ttl_seconds=self._ttl_for(due),
                                     purpose=_purpose_for(due, institution),
                                     validators=validators)
        for result in results:
            self._budget_left -= 1
            planned = next((p for p in due if p.url == result.url), None)
            topic = (planned.topics[0] if planned and planned.topics else None)
            if result.not_modified:
                report.not_modified += 1
                self.cache.touch_validated(result.url, self._ttl_for(due))
                continue
            if not result.ok:
                report.failed += 1
                self.cache.put(result.url, status=result.status or 0, body="", error=result.error,
                               topic=topic, unitid=institution.unitid or None,
                               ttl_seconds=FRESHNESS_TTL[TOPICS[topic].freshness] if topic in TOPICS else 3600)
                continue
            report.fetched += 1
            ttl = self._ttl_for(due, only=topic)
            stored = self.cache.put(
                result.url, status=result.status, body=result.text, title=result.title,
                etag=result.etag, last_modified=result.last_modified, final_url=result.final_url,
                content_type=result.content_type, topic=topic, unitid=institution.unitid or None,
                ttl_seconds=ttl,
            )
            self._store_links(result, institution, report)
            self._apply(stored.url, stored.body, stored.title, institution, report,
                        stored.content_sha256 or util.sha256_text(stored.body), result.status or 200)
            if self.request_delay_s:
                time.sleep(self.request_delay_s)

    def _apply(self, url: str, body: str, title: str | None, institution: Institution,
               report: EnrichReport, sha: str, status: int) -> None:
        """Parse a document unless we already parsed this exact bytes+rules combo."""
        if self.repo.extraction_done(url, sha, "rule", RULES_VERSION):
            report.notes.append(f"skip re-parse {url}")
            return
        facts = extract_page(
            body,
            url=url,
            unitid=institution.unitid or None,
            institution_name=institution.name,
            homepage=institution.url_homepage,
            registry=self.registry,
        )
        findings = [f for f in facts.findings if _acceptable(f, status)]
        written = self.repo.replace_url_facts(
            institution.unitid or 0, url, findings, extractor="rule", version=RULES_VERSION,
            content_sha=sha, notes=f"topics={len(facts.topics)}")
        report.facts_written += written
        report.links_written += self.repo.add_links(institution.unitid or None, facts.links,
                                                    source_url=url)
        deadlines = _deadlines_from(findings, url, institution.unitid)
        report.deadlines_written += self.repo.add_deadlines(institution.unitid or None, deadlines)

    def _store_links(self, result: PageResult, institution: Institution, report: EnrichReport) -> None:
        links = [
            LinkFinding(url=util.norm_url(href) or href, topic=topic, anchor=anchor, score=0.4)
            for anchor, href in result.links[:40]
            for topic in self.registry.topics_for_text(f"{anchor} {href}")[:1]
            if util.is_same_site(href, institution.url_homepage or href)
        ]
        if links:
            report.links_written += self.repo.add_links(institution.unitid or None, links,
                                                        source_url=result.url)

    def _ttl_for(self, pages: Sequence[PlannedPage], only: str | None = None) -> int:
        topics = [only] if only else [t for p in pages for t in p.topics]
        ttls = [FRESHNESS_TTL[TOPICS[t].freshness] for t in topics if t in TOPICS]
        return min(ttls) if ttls else FRESHNESS_TTL[TOPIC_DEFAULT_FRESHNESS]

    def _answered(self, unitid: int) -> set[str]:
        return {topic for topic, facts in self.repo.facts_by_topic(unitid).items() if facts}

    # ---------------------------------------------------------------- searching
    def _search_and_harvest(self, institution: Institution, missing: Sequence[str],
                            report: EnrichReport) -> int:
        assert self.searcher is not None
        queries = 0
        harvest: list[PlannedPage] = []
        for topic in missing[:4]:
            template_index = 0 if institution.url_homepage else 1
            query = self.registry.search_query(topic, institution.name, institution.url_homepage,
                                               index=template_index)
            if not query:
                continue
            hits = self.searcher.search(
                query,
                purpose=f"Find the official {TOPICS[topic].label.lower()} page for {institution.name}",
                num=5,
            )
            queries += 1
            for hit in hits:
                if not _plausible(hit.url, institution, topic):
                    continue
                entry = next((p for p in harvest if p.url == hit.url), None)
                if entry is None:
                    harvest.append(PlannedPage(url=hit.url, topics=[topic], reason="search"))
                elif topic not in entry.topics:
                    entry.topics.append(topic)
            if self._budget_left <= 0:
                break
        if harvest:
            self._consume(harvest[: self.max_new_pages_per_institution], institution, report, [])
        report.searches += queries
        return queries

    # -------------------------------------------------------------------- LLM
    def _llm_gapfill(self, institution: Institution, missing: Sequence[str],
                     report: EnrichReport) -> int:
        if not missing or self.llm is None:
            return 0
        calls = 0
        for url, body in self._recent_pages(institution.unitid, limit=3):
            page_facts = extract_page(body, url=url, unitid=institution.unitid,
                                      institution_name=institution.name,
                                      homepage=institution.url_homepage, registry=self.registry)
            from .llm import should_call_llm  # local import keeps llm optional

            if not should_call_llm(page_facts, required=list(missing)):
                continue
            findings = self.llm.extract(page_facts, body, school=institution.name,
                                        missing_topics=list(missing), page_url=url)
            calls += 1
            if findings:
                report.facts_written += self.repo.add_facts(institution.unitid, url, findings,
                                                            extractor="llm", version=PROMPT_VERSION)
                report.llm_calls += 1
        return calls

    def _recent_pages(self, unitid: int, *, limit: int) -> list[tuple[str, str]]:
        rows = self.repo.db.query(
            "SELECT url, body_gzip FROM web_pages WHERE institution_unitid = ? "
            "AND status = 200 ORDER BY fetched_at DESC LIMIT ?",
            (int(unitid), limit),
        )
        from ..db.database import decompress

        return [(row[0], decompress(row[1])) for row in rows if row[1]]


# ------------------------------------------------------------------------ utils
TOPIC_DEFAULT_FRESHNESS = Freshness.POLICY


def _acceptable(finding: Finding, status: int) -> bool:
    if status != 200:
        return False
    if finding.topic not in TOPICS:
        return False
    topic: Topic = TOPICS[finding.topic]
    if topic.value_type == "url":
        return bool(finding.value_text and str(finding.value_text).startswith("http"))
    if topic.value_type == "code":
        return bool(finding.value_text and str(finding.value_text).isdigit())
    if topic.value_type == "bool":
        return finding.value_bool is not None
    if topic.value_type == "money":
        return finding.value_num is not None or bool(finding.value_text)
    return bool(finding.value_text or finding.value_json or finding.value_date)


def _missing(wanted: Sequence[str], answered: dict[str, list[Any]] | set[str]) -> list[str]:
    done = set(answered) if isinstance(answered, set) else set(answered.keys())
    return [topic for topic in wanted if topic not in done]


def _is_error_page(cached: Any) -> bool:  # noqa: ANN401
    return bool(cached.status and cached.status >= 400)


BLOCKED_HOSTS = ("facebook.com", "instagram.com", "youtube.com", "linkedin.com", "twitter.com",
                 "x.com", "wikipedia.org", "reddit.com", "glassdoor.com", "niche.com",
                 "collegeboard.org/blog", "careervoycies", "bestcolleges")


def _plausible(url: str, institution: Institution, topic: str) -> bool:
    """Search-result filter: official domains only, no directories or social media."""
    if not url:
        return False
    host = util.domain_of(url)
    if not host or any(bad in url.lower() for bad in BLOCKED_HOSTS):
        return False
    homepage_host = util.domain_of(institution.url_homepage or "")
    if homepage_host and util.is_same_site(url, institution.url_homepage or ""):
        return True
    # federal / programme-level sources are acceptable when the campus page is missing
    return host.endswith((".gov", ".edu")) or (homepage_host and host.endswith(homepage_host))


def _deadlines_from(findings: Sequence[Finding], url: str, unitid: int | None) -> list[Deadline]:
    out: list[Deadline] = []
    for finding in findings:
        topic = TOPICS.get(finding.topic)
        if topic is None or topic.value_type != "date":
            continue
        out.append(
            Deadline(
                label=finding.label or topic.label,
                category=finding.category or ("aid" if "aid" in finding.topic else "application"),
                date_iso=finding.value_date,
                date_text=util.truncate(finding.value_text or "", 120) or None,
                url=url,
                unitid=unitid,
            )
        )
    return out


class _AnyProfile:
    """Sentinel profile meaning 'every topic we know how to establish'."""

    required_topics: tuple[str, ...] = ()
    preferred_topics: tuple[str, ...] = ()


def all_topics() -> list[str]:
    return sorted(TOPICS)


def _purpose_for(pages: Sequence[PlannedPage], institution: Institution) -> str:
    labels = ", ".join(
        sorted({TOPICS[t].label for p in pages for t in p.topics if t in TOPICS})
    )[:400]
    return (f"Evidence for {institution.name or 'a US institution'}: "
            f"{labels or 'financial aid, admissions deadlines, support services'}")
