"""The public surface: one object, a handful of methods, cache behind all of them.

    from sra_schools import SRA

    sra = SRA.open()                       # shared cache under $SRA_HOME
    report = sra.search(profile="first_generation", state="CA", limit=10)
    report.matches[0].links["fafsa_school_code"]

Every read method is cache-only and safe on a request path: no network, no
blocking. Anything that touches the internet is explicit (``enrich``, ``refresh``,
``build``, or ``search(..., live=True)``) and budget-bounded.
"""

from __future__ import annotations

import threading
from collections.abc import Iterable, Sequence
from pathlib import Path
from typing import Any

from . import util
from .config import Settings
from .db.cache import PageCache, QueryCache
from .db.database import Database
from .db.repository import Repository
from .extract.fetchers import Fetcher, make_fetcher
from .extract.pipeline import Pipeline
from .extract.search import Searcher, make_searcher
from .ingest.programs import ProgramLoader, audit_programs
from .ingest.scorecard import (
    DEFAULT_URL,
    ScorecardLoader,
    dataset_version_from_url,
    sha256_of,
)
from .models import AidProgram, Deadline, Institution, SchoolMatch, SearchQuery, SearchReport
from .profiles import PROFILES, Profile, all_topic_keys, get_profile
from .search.engine import SearchEngine, resolve_links
from .search.report import render_match, render_report
from .sources import SourceRegistry
from .taxonomy import TOPICS

_LOCK = threading.RLock()
_INSTANCE: SRA | None = None


class SRA:
    """Facade over the cache, the crawler and the search engine."""

    def __init__(
        self,
        settings: Settings | None = None,
        *,
        db: Database | None = None,
        fetcher: Fetcher | None = None,
        searcher: Searcher | None = None,
        registry: SourceRegistry | None = None,
    ) -> None:
        self.settings = settings or Settings.from_env()
        self.db = db or Database(self.settings.resolved_db_path)
        if not self.db.read_only:
            # idempotent: creates what is missing, adds columns newer builds need
            self.db.migrate()
        self.repo = Repository(self.db)
        self.pages = PageCache(self.db)
        self.queries = QueryCache(self.db, default_ttl=self.settings.search_cache_ttl_s)
        self.registry = registry or SourceRegistry.load()
        self._fetcher = fetcher
        self._searcher = searcher
        self._pipeline: Pipeline | None = None
        self.engine = SearchEngine(self.repo, query_cache=self.queries, registry=self.registry)

    # ---------------------------------------------------------------- lifecycle
    @classmethod
    def open(cls, *, home: str | Path | None = None, db_path: str | Path | None = None,
             offline: bool | None = None, **overrides: Any) -> SRA:
        """Open (or reuse) the shared instance for this process."""
        global _INSTANCE  # noqa: PLW0603
        with _LOCK:
            settings = Settings.from_env(
                home=home, db_path=db_path,
                offline=cls._flag(offline, default=None),
                **overrides,
            )
            requested_db = str(settings.resolved_db_path.resolve())
            if _INSTANCE is not None:
                current_db = str(_INSTANCE.settings.resolved_db_path.resolve())
                if requested_db == current_db:
                    return _INSTANCE
            _INSTANCE = cls(settings)
            return _INSTANCE

    @staticmethod
    def _flag(value: bool | None, *, default: bool | None) -> bool | None:
        return default if value is None else value

    @classmethod
    def reset(cls) -> None:
        """Drop the shared instance (tests)."""
        global _INSTANCE  # noqa: PLW0603
        with _LOCK:
            if _INSTANCE is not None:
                _INSTANCE.db.close()
            _INSTANCE = None

    @property
    def fetcher(self) -> Fetcher:
        if self._fetcher is None:
            # TinyFish when a key is present (renders JS, clears WAFs), plain HTTP
            # otherwise. Only an explicit offline setting stops us reaching the net.
            self._fetcher = make_fetcher(self.settings.tinyfish, offline=self.settings.offline)
        return self._fetcher

    @property
    def searcher(self) -> Searcher:
        if self._searcher is None:
            self._searcher = make_searcher(self.settings.tinyfish,
                                           offline=not self.settings.live_enabled)
        return self._searcher

    def pipeline(self, *, required: bool = False) -> Pipeline | None:
        """Build the crawler on demand. ``None`` in offline mode unless ``required``."""
        if self._pipeline is not None:
            return self._pipeline
        if not self.settings.network_enabled:
            if required:
                raise RuntimeError(
                    "this command needs the network but SRA_OFFLINE is set; "
                    "unset it (and optionally set TINYFISH_API_KEY for JS-rendered pages)"
                )
            return None
        self._pipeline = Pipeline(
            self.repo, self.pages,
            fetcher=self.fetcher,
            searcher=self.searcher if self.settings.live_enabled else None,
            registry=self.registry,
            llm=self._llm(),
            max_pages=self.settings.max_pages_per_run,
            max_new_pages_per_institution=self.settings.max_new_pages_per_institution,
            request_delay_s=self.settings.request_delay_s,
        )
        self.engine.pipeline = self._pipeline
        return self._pipeline

    def _llm(self) -> Any | None:  # noqa: ANN401
        if not (self.settings.use_llm and self.settings.llm.enabled):
            return None
        from .extract.llm import LlmExtractor  # optional path, imported lazily

        try:
            return LlmExtractor(self.settings.llm)
        except RuntimeError:
            return None

    # ------------------------------------------------------------------- reads
    def search(
        self,
        profile: str | Profile | None = None,
        *,
        q: str | None = None,
        needs: Sequence[str] | None = None,
        level: str | None = None,
        state: str | None = None,
        control: str | None = None,
        stem_only: bool = False,
        graduate: bool | None = None,
        max_net_price: float | None = None,
        min_aid_generosity: float | None = None,
        require: Sequence[str] | None = None,
        exclude_unitids: Sequence[int] | None = None,
        limit: int = 20,
        offset: int = 0,
        live: bool = False,
        include_stale: bool = True,
    ) -> SearchReport:
        """Rank schools for a profile (or for an explicit list of needs)."""
        query = SearchQuery(
            profile=get_profile(profile).key if get_profile(profile) else (profile or None),
            q=q,
            needs=_validated_needs(needs),
            level=level,
            state=state,
            control=control,
            stem_only=stem_only,
            graduate=graduate,
            max_net_price=max_net_price,
            min_aid_generosity=min_aid_generosity,
            require=_validated_topics(require),
            exclude_unitids=[int(u) for u in (exclude_unitids or [])],
            limit=max(1, min(int(limit), 100)),
            offset=max(0, int(offset)),
            live=bool(live),
            include_stale=include_stale,
        )
        if live:
            self.pipeline(required=True)
        report = self.engine.search(query)
        if live and self._pipeline is not None:
            self._live_fill(report, profile=get_profile(profile) if profile else None)
        return report

    def school(self, key: int | str, *, profile: str | Profile | None = None) -> SchoolMatch | None:
        """Everything we hold about one institution, as a ranked-match view."""
        inst = self.institution(key)
        if inst is None:
            return None
        prof = get_profile(profile)
        facts = self.repo.facts_by_topic(inst.unitid)
        deadlines = self.repo.deadlines_for(inst.unitid)
        programs = [p for p, _ in self.repo.programs_for_institution(inst.unitid)]
        if prof:
            programs = self.repo.programs(profile=prof.key, needs=list(prof.program_needs),
                                          level=prof.program_levels[0] if prof.program_levels else None,
                                          citizenship=list(prof.program_citizenship), limit=8) + programs
        from .search.engine import build_playbook
        from .search.ranking import Scorer, describe_signals

        resolved = resolve_links(inst, facts, self.registry)
        if prof:
            score, signals = Scorer(prof).score(inst, facts, deadlines, programs)
            reasons = describe_signals(signals, prof.weights, top=6)
            wanted = list(all_topic_keys(prof))
            gaps = [TOPICS[t].label for t in prof.required_topics if not _live(facts.get(t))]
            playbook = build_playbook(prof, resolved, deadlines, facts)
            covered = [t for t in wanted if _live(facts.get(t))]
        else:
            score, signals, reasons, gaps, playbook, covered = 0.0, {}, {}, [], [], list(facts)
        observed = [f.observed_at for entries in facts.values() for f in entries if f.observed_at]
        return SchoolMatch(
            institution=inst,
            score=round(score, 1),
            signals=signals,
            reasons=reasons,
            facts=[f for entries in facts.values() for f in entries],
            links=resolved,
            deadlines=sorted(deadlines, key=lambda d: d.date_iso or "9999"),
            programs=_unique(programs),
            playbook=playbook,
            gaps=gaps,
            needs_covered=covered,
            last_verified=max(observed) if observed else None,
            stale=any(f.is_stale() for entries in facts.values() for f in entries),
        )

    def institution(self, key: int | str) -> Institution | None:
        text = str(key).strip()
        if text.isdigit():
            return self.repo.get_institution(int(text)) or self.repo.find_institution(text)
        return self.repo.find_institution(text)

    def programs(
        self,
        profile: str | Profile | None = None,
        *,
        needs: Sequence[str] | None = None,
        level: str | None = None,
        kind: str | None = None,
        state: str | None = None,
        limit: int = 50,
    ) -> list[AidProgram]:
        prof = get_profile(profile)
        return self.repo.programs(
            profile=prof.key if prof else None,
            needs=_validated_needs(needs) or (list(prof.program_needs) if prof else None),
            level=level or (prof.program_levels[0] if prof and prof.program_levels else None),
            citizenship=list(prof.program_citizenship) if prof else None,
            kind=kind,
            state=state,
            limit=limit,
        )

    def program(self, program_id: str) -> AidProgram | None:
        return self.repo.get_program(program_id)

    def deadlines(self, *, unitid: int | None = None, limit: int = 40) -> list[Deadline]:
        if unitid is not None:
            return self.repo.deadlines_for(unitid)
        return self.repo.upcoming_deadlines(limit=limit)

    def status(self) -> dict[str, Any]:
        payload = self.repo.status()
        last = payload.get("last_crawl")
        payload["last_crawl"] = dict(last) if last is not None else None
        payload["cache"] = self.pages.stats()
        payload["query_cache"] = self.queries.stats()
        payload["settings"] = self.settings.describe()
        payload["profiles"] = list(PROFILES)
        return payload

    def describe(self) -> str:
        from .search.report import render_status

        payload = self.status()
        return render_status(payload, cache=payload.pop("cache"), queries=payload.pop("query_cache"))

    # ------------------------------------------------------------------- writes
    def build(
        self,
        *,
        source: str | Path | None = None,
        url: str = DEFAULT_URL,
        seed_programs: bool = True,
        program_paths: Sequence[Path | str] | None = None,
    ) -> dict[str, Any]:
        """Load the institution universe (+ optional programme seed) from a file.

        ``source`` may be the bulk zip, the extracted csv, or a directory holding
        either. With no ``source`` the dataset is downloaded from the federal
        endpoint and its hash recorded in the cache metadata.
        """
        result: dict[str, Any] = {"institutions": 0, "programs": 0}
        loader = ScorecardLoader()
        path = self._resolve_source(source or url)
        version = dataset_version_from_url(str(url)) if not source else \
            dataset_version_from_url(Path(path).name) or f"local-{Path(path).stem[:32]}"
        rows = loader.iter_rows(Path(path))
        result["institutions"] = self.repo.upsert_institutions(rows, dataset_version=version)
        self.db.set_meta("dataset_version", version)
        self.db.set_meta("dataset_source", str(source or url))
        self.db.set_meta("dataset_sha256", sha256_of(Path(path)) if Path(path).exists() else None)
        self.db.set_meta("data_epoch", util.short_hash(version + str(self.repo.db.count("institutions")), 10))
        if seed_programs:
            loaded = self.load_programs(program_paths)
            result["programs"] = len(loaded.programs)
            result["programs_rejected"] = loaded.rejected[:20]
            result["program_files"] = [str(p) for p in (loaded.files or [])]
            if not loaded.files:
                result["programs_warning"] = (
                    "no programme seed files found in sra_schools/data/programs/*.json; "
                    "catalogue is empty (pass explicit paths or restore the shipped seed)"
                )
        self.bump_epoch()
        return result

    def _resolve_source(self, source: str | Path) -> Path:
        candidate = Path(source).expanduser()
        if candidate.is_dir():
            for suffix in (".zip", ".csv"):
                matches = sorted(candidate.glob(f"*{suffix}"))
                if matches:
                    return matches[0]
            raise FileNotFoundError(f"no .zip/.csv under {candidate}")
        if candidate.exists():
            return candidate
        downloaded = ScorecardLoader.download(str(source), self.settings.home / "downloads")
        return downloaded

    def load_programs(self, paths: Sequence[Path | str] | None = None) -> Any:  # noqa: ANN401
        """Load the curated programme seed (defaults to ``data/programs/*.json``)."""
        files = [Path(p) for p in (paths or [])]
        if not files:
            package_dir = Path(__file__).resolve().parent / "data" / "programs"
            files = sorted(package_dir.glob("*.json"))
            research = self.settings.home.parent / ".sra_research"
            files += sorted(research.glob("p*.json")) if research.exists() else []
        origin_map = _origin_map(files)
        loader = ProgramLoader(self.repo)
        return loader.load_files(files, origin_map=origin_map)

    def verify_programs(self, *, limit: int | None = None, dns_only: bool = False,
                        verdicts: dict[str, Any] | None = None) -> dict[str, Any]:
        """Audit the catalogue's URLs.

        * ``dns_only`` - resolve hosts, no HTTP (catches invented domains anywhere)
        * ``verdicts`` - pre-computed ``{url: {ok, verdict, status, chars, reason}}``,
          e.g. produced by an agent-side browser fetch and replayed here
        * otherwise - live fetch through the configured fetcher, which must be able
          to get past WAFs (TinyFish) or results are recorded as ``blocked``
        """
        from .ingest.programs import apply_verdicts, verify_offline, verify_urls

        if verdicts:
            return apply_verdicts(self.repo, verdicts)
        if dns_only:
            return verify_offline(self.repo)
        return audit_programs(self.repo, self.fetcher, limit=limit)

    def enrich(
        self,
        *,
        unitids: Sequence[int] | None = None,
        profile: str | Profile | None = None,
        limit: int = 10,
        force: bool = False,
        topics: Sequence[str] | None = None,
    ) -> list[dict[str, Any]]:
        """Crawl/refresh the pages that answer a profile's needs for schools."""
        prof = get_profile(profile)
        pipeline = self.pipeline(required=True)
        reports: list[dict[str, Any]] = []
        if pipeline is not None:
            pipeline.reset_budget()
        targets = self._targets(unitids, prof, limit)
        for inst in targets:
            report = pipeline.ensure(inst, profile=prof, topics=_validated_topics(topics),
                                     force=force)
            self._link_programs(inst, prof)
            reports.append(report.to_dict())
        return reports

    def refresh(self, *, unitids: Sequence[int] | None = None, limit: int = 100,
                profile: str | Profile | None = None) -> dict[str, Any]:
        """Re-crawl anything past its freshness window (validators avoid re-transfer)."""
        prof = get_profile(profile)
        pipeline = self.pipeline(required=True)
        due = self.repo.institutions_due(limit=limit, unitids=unitids)
        if pipeline is not None:
            pipeline.reset_budget()
        outcomes = [pipeline.ensure(inst, profile=prof).to_dict() for inst in due]
        finished = util.iso()
        with self.db.tx() as cur:
            cur.execute(
                "INSERT INTO crawl_runs(started_at, finished_at, trigger, pages_fetched, "
                "pages_fresh, pages_revalidated, pages_failed, facts_written, llm_calls) "
                "VALUES(?,?,?,?,?,?,?,?,?)",
                (started, finished, "refresh",
                 sum(o["fetched"] for o in outcomes), sum(o["served_fresh"] for o in outcomes),
                 sum(o["not_modified"] for o in outcomes), sum(o["failed"] for o in outcomes),
                 sum(o["facts_written"] for o in outcomes), sum(o["llm_calls"] for o in outcomes)),
            )
        return {
            "institutions": len(outcomes),
            "pages_fetched": sum(o["fetched"] for o in outcomes),
            "pages_served_fresh": sum(o["served_fresh"] for o in outcomes),
            "not_modified": sum(o["not_modified"] for o in outcomes),
            "facts_written": sum(o["facts_written"] for o in outcomes),
            "failures": sum(o["failed"] for o in outcomes),
        }

    def bump_epoch(self) -> str:
        """Invalidate the query cache after the data underneath it changed."""
        epoch = util.short_hash(util.iso() + str(self.db.count("institutions")), 10)
        self.db.set_meta("data_epoch", epoch)
        return epoch

    # ------------------------------------------------------------------ helpers
    def _targets(self, unitids: Sequence[int] | None, profile: Profile | None,
                 limit: int) -> list[Institution]:
        if unitids:
            return [inst for inst in (self.repo.get_institution(int(u)) for u in unitids) if inst]
        report = self.engine.search(SearchQuery(profile=profile.key if profile else None,
                                                limit=limit, live=False))
        if report.matches:
            return [m.institution for m in report.matches]
        rows = self.db.query(
            "SELECT * FROM institutions WHERE COALESCE(currently_operating,1) = 1 "
            "ORDER BY COALESCE(avg_net_price, 1e9) LIMIT ?", (int(limit),))
        return [Institution.from_row(row) for row in rows]

    def _link_programs(self, inst: Institution, profile: Profile | None) -> None:
        if profile is None:
            return
        facts = self.repo.facts_by_topic(inst.unitid)
        for program in self.repo.programs(profile=profile.key, limit=100):
            if program.kind in {"services", "support_program"} and any(
                topic in facts for topic in ("trio_student_support_services",
                                             "disability_services_office",
                                             "international_student_office")
            ):
                self.repo.link_program_to_institution(
                    inst.unitid, program.program_id, relationship="eligible_applicant",
                    evidence=f"campus evidence topics: {', '.join(sorted(facts))[:200]}",
                    url=inst.url_homepage,
                )

    def _live_fill(self, report: SearchReport, *, profile: Profile | None) -> None:
        """Best-effort: enrich the top few results that came back with gaps."""
        pipeline = self.engine.pipeline
        if pipeline is None or profile is None:
            return
        for match in [m for m in report.matches if m.gaps][:3]:
            outcome = pipeline.ensure(match.institution, profile=profile)
            if outcome.facts_written:
                refreshed = self.school(match.institution.unitid, profile=profile)
                if refreshed:
                    match.facts = refreshed.facts
                    match.links = refreshed.links
                    match.deadlines = refreshed.deadlines
                    match.gaps = refreshed.gaps
                    match.playbook = refreshed.playbook
                    match.score = max(match.score, refreshed.score)

    def seed_export(self, path: Path | str, *, profiles: list[str] | None = None,
                    limit: int | None = None) -> dict[str, Any]:
        from .ingest.seed import export_seed

        return export_seed(self, path, profiles=profiles, limit=limit)

    def seed_import(self, path: Path | str) -> dict[str, Any]:
        from .ingest.seed import import_seed

        return import_seed(self, path)

    # ------------------------------------------------------------------ renders
    def render(self, report: SearchReport, *, detailed: bool = False) -> str:
        return render_report(report, detailed=detailed)

    def render_school(self, key: int | str, *, profile: str | Profile | None = None) -> str:
        match = self.school(key, profile=profile)
        if match is None:
            return f"No institution matching {key!r} in the cache."
        prof = get_profile(profile)
        return render_match(match, profile_title=prof.title if prof else None)


# --------------------------------------------------------------------- helpers
def _live(entries: Sequence[Any] | None) -> bool:
    return any(not f.is_stale() for f in (entries or []))
def _validated_needs(needs: Sequence[str] | None) -> list[str]:
    from .taxonomy import Need

    valid = {n.value for n in Need}
    return [n for n in (needs or []) if n in valid]


def _validated_topics(topics: Sequence[str] | None) -> list[str]:
    return [t for t in (topics or []) if t in TOPICS]


def _unique(programs: Iterable[AidProgram]) -> list[AidProgram]:
    out: dict[str, AidProgram] = {}
    for program in programs:
        out.setdefault(program.program_id, program)
    return list(out.values())


def _origin_map(files: Sequence[Path]) -> dict[str, str]:
    """Guess which profile a seed file belongs to, from its filename."""
    mapping: dict[str, str] = {}
    hints = {"first_gen": "first_generation", "p1": "first_generation",
             "disab": "student_with_disability", "p2": "student_with_disability",
             "inter": "international_stem", "p3": "international_stem", "intl": "international_stem"}
    for path in files:
        stem = path.stem.lower()
        for hint, profile in hints.items():
            if hint in stem:
                mapping[path.name] = profile
                break
    return mapping


def get_sra(**kwargs: Any) -> SRA:  # noqa: ANN401
    """Module-level accessor for the shared instance."""
    return SRA.open(**kwargs)
