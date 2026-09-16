"""Command line: build, enrich, refresh, search, show, status, seed, verify.

Read-only commands (search/school/programs/status) never touch the network.
Write commands (build/enrich/refresh/verify/seed import) do, and are budget bounded.
"""

from __future__ import annotations

import argparse
import gzip
import json
import sys
from pathlib import Path
from typing import Any

from . import __version__, util
from .api import SRA
from .config import Settings
from .profiles import PROFILES, describe_profiles, get_profile
from .taxonomy import TOPICS


def build_parser() -> argparse.ArgumentParser:
    # Options that work in either position: `sra-schools --offline search ...`
    # and `sra-schools search --offline ...`.
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--home", help="cache directory (default $SRA_HOME or ~/.cache/sra-schools)")
    common.add_argument("--db", help="explicit sqlite path")
    common.add_argument("--offline", action="store_true", help="never touch the network")
    common.add_argument("--max-pages", type=int, help="fetch budget for this run")
    common.add_argument("-v", "--verbose", action="store_true")

    parser = argparse.ArgumentParser(
        prog="sra-schools",
        parents=[common],
        description="US college/university aid intelligence: official links, deadlines, "
                    "programmes and profile-aware search over a refreshable cache.",
    )
    parser.add_argument("--version", action="version", version=f"sra-schools {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)

    # --- build ---------------------------------------------------------------
    p = sub.add_parser("build", parents=[common], help="load the federal institution universe + programme seed")
    p.add_argument("--source", help="local .zip/.csv (or a directory containing one)")
    p.add_argument("--url", help="override the bulk dataset URL")
    p.add_argument("--programs", nargs="*", help="explicit programme seed JSON files")
    p.add_argument("--no-programs", action="store_true")
    p.add_argument("--rebuild", action="store_true", help="clear the cache first")

    # --- enrich / refresh ----------------------------------------------------
    p = sub.add_parser("enrich", parents=[common], help="crawl campus pages to answer a profile's needs")
    p.add_argument("--profile", choices=[*PROFILES, *("first-gen", "disability", "international")],
                   default="first_generation")
    p.add_argument("--unitid", type=int, action="append", help="specific institution(s)")
    p.add_argument("--limit", type=int, default=5)
    p.add_argument("--force", action="store_true", help="re-crawl even answered topics")
    p.add_argument("--topics", nargs="*", help="restrict to these topic keys")
    p.add_argument("--json", action="store_true")

    p = sub.add_parser("refresh", parents=[common], help="re-crawl anything past its freshness window")
    p.add_argument("--unitid", type=int, action="append")
    p.add_argument("--profile", default=None)
    p.add_argument("--limit", type=int, default=100)
    p.add_argument("--purge", action="store_true", help="also drop long-expired cached pages")

    # --- search --------------------------------------------------------------
    p = sub.add_parser("search", parents=[common], help="rank schools for a profile")
    p.add_argument("profile", nargs="?", default=None, help="first_generation | disability | international")
    p.add_argument("-q", "--query", help="text filter (name, city, state)")
    p.add_argument("--needs", nargs="*", help="explicit needs instead of a profile")
    p.add_argument("--state", help="two-letter abbreviation")
    p.add_argument("--control", choices=["public", "private_nonprofit", "private_for_profit"])
    p.add_argument("--level", choices=["undergraduate", "graduate"])
    p.add_argument("--stem", action="store_true", help="STEM-strong institutions only")
    p.add_argument("--max-net-price", type=float)
    p.add_argument("--require", nargs="*", help="only schools with live facts for these topics")
    p.add_argument("--limit", type=int, default=10)
    p.add_argument("--offset", type=int, default=0)
    p.add_argument("-f", "--format", choices=["md", "json", "csv"], default="md")
    p.add_argument("--detailed", action="store_true", help="inline evidence per school (md)")
    p.add_argument("--live", action="store_true", help="allow network fill on cache misses")
    p.add_argument("--out", help="write to a file instead of stdout")

    # --- show ----------------------------------------------------------------
    p = sub.add_parser("school", parents=[common], help="everything held about one institution")
    p.add_argument("key", help="UnitID, OPEID or name fragment")
    p.add_argument("--profile", default=None)
    p.add_argument("-f", "--format", choices=["md", "json"], default="md")

    p = sub.add_parser("programs", parents=[common], help="list / show / verify the programme catalogue")
    p.add_argument("action", choices=["list", "show", "verify", "load"], nargs="?", default="list")
    p.add_argument("target", nargs="?", help="programme id for show")
    p.add_argument("--profile", default=None)
    p.add_argument("--kind", default=None)
    p.add_argument("--state", default=None)
    p.add_argument("--limit", type=int, default=60)
    p.add_argument("-f", "--format", choices=["md", "json"], default="md")
    p.add_argument("--files", nargs="*", help="programme seed files for `load`")
    p.add_argument("--dns-only", action="store_true",
                   help="verify by resolving hosts only (no HTTP, no key needed)")
    p.add_argument("--from-file", help="JSON verdicts to replay: [{url, ok, verdict, status, chars}]")
    p.add_argument("--retire-dead", action="store_true",
                   help="with --from-file: deactivate entries judged dead (default)")

    # --- meta ----------------------------------------------------------------
    p = sub.add_parser("status", parents=[common], help="cache contents, coverage and freshness")
    p.add_argument("-f", "--format", choices=["md", "json"], default="md")
    sub.add_parser("profiles", parents=[common], help="list the built-in student profiles")
    sub.add_parser("topics", parents=[common], help="list the fact topics the module can establish")

    p = sub.add_parser("seed", parents=[common], help="export/import a portable cache bundle")
    p.add_argument("action", choices=["export", "import"], nargs="?", default="export")
    p.add_argument("--path", help="bundle path (default data/seed/sra-seed.json.gz)")
    p.add_argument("--profile", action="append", help="restrict export to schools matched by a profile")
    p.add_argument("--limit", type=int, help="cap institutions in the export")

    p = sub.add_parser("sources", parents=[common], help="verify the curated source registry")
    p.add_argument("action", choices=["verify", "show"], nargs="?", default="show")
    p.add_argument("--topic", default=None)
    p.add_argument("--limit", type=int, default=10,
                   help="max national URLs to verify (default 10; use --limit 0 for all)")
    return parser


# ------------------------------------------------------------------------ main
def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    overrides: dict[str, Any] = {}
    if args.home:
        overrides["home"] = args.home
    if args.db:
        overrides["db_path"] = args.db
    if getattr(args, "offline", False):
        overrides["offline"] = True
    if getattr(args, "max_pages", None):
        overrides["max_pages_per_run"] = args.max_pages
    settings = Settings.from_env(**overrides)
    # Read paths must never surprise the caller with a network call.
    reads_cache = args.command in {"school", "status", "profiles", "topics"} or (
        args.command == "search" and not getattr(args, "live", False)
    ) or (
        args.command == "programs" and getattr(args, "action", "list") in {"list", "show"}
    )
    if reads_cache:
        settings = Settings.from_env(**{**overrides, "offline": True})
    sra = SRA(settings)
    try:
        handler = HANDLERS.get(args.command)
        if handler is None:  # pragma: no cover - argparse guards this
            print(f"unknown command {args.command}", file=sys.stderr)
            return 2
        return handler(sra, args) or 0
    finally:
        sra.db.close()


# ------------------------------------------------------------------- handlers
def cmd_build(sra: SRA, args: argparse.Namespace) -> int:
    if args.rebuild:
        sra.db.clear_all()
        sra.db.migrate()
    url = args.url or "https://ed-public-download.scorecard.network/downloads/Most-Recent-Cohorts-Institution_06102026.zip"
    print(f"building from {args.source or url} ...", file=sys.stderr)
    result = sra.build(source=args.source, url=url, seed_programs=not args.no_programs,
                       program_paths=args.programs)
    print(json.dumps(result, indent=2)[:4000])
    if result.get("programs_warning"):
        print(f"WARNING: {result['programs_warning']}", file=sys.stderr)
    print(f"\nuniverse: {sra.db.count('institutions'):,} institutions | "
          f"programmes: {sra.db.count('aid_programs', 'active = 1'):,}", file=sys.stderr)
    return 0


def cmd_enrich(sra: SRA, args: argparse.Namespace) -> int:
    if not sra.settings.live_enabled:
        print("no TINYFISH_API_KEY and offline mode is not enabled - falling back to direct HTTP. "
              "Set SRA_OFFLINE=1 to make this explicit.", file=sys.stderr)
    reports = sra.enrich(unitids=args.unitid, profile=args.profile, limit=args.limit,
                         force=args.force, topics=args.topics)
    if args.json:
        print(json.dumps(reports, indent=2))
    else:
        for item in reports:
            print(f"{item['unitid']:>7} {item['name'][:34]:34s} fetched={item['fetched']:2d} "
                  f"fresh={item['served_fresh']:2d} 304={item['not_modified']:2d} "
                  f"fail={item['failed']:2d} facts={item['facts_written']:3d} "
                  f"dates={item['deadlines_written']:2d} searches={item['searches']} "
                  f"gaps={len(item['gaps'])}")
            if item["gaps"] and args.verbose:
                print(f"        missing: {', '.join(item['gaps'][:8])}")
    total = sum(r["facts_written"] for r in reports)
    pages = sum(r["fetched"] + r["served_fresh"] for r in reports)
    failed = sum(r["failed"] for r in reports)
    print(f"\n{len(reports)} institutions, {pages} pages handled ({failed} failed), "
          f"{total} facts written.", file=sys.stderr)
    return 0


def cmd_refresh(sra: SRA, args: argparse.Namespace) -> int:
    outcome = sra.refresh(unitids=args.unitid, limit=args.limit, profile=args.profile)
    print(json.dumps(outcome, indent=2))
    saved = outcome["pages_served_fresh"] + outcome["not_modified"]
    print(f"\n{saved} of {saved + outcome['pages_fetched']} page reads answered without a "
          f"network transfer.", file=sys.stderr)
    if args.purge:
        removed = sra.pages.purge_expired()
        sra.queries.purge_expired()
        print(f"purged {removed} expired page(s)", file=sys.stderr)
    return 0


def cmd_search(sra: SRA, args: argparse.Namespace) -> int:
    profile = args.profile or (None if args.needs else "first_generation")
    if profile and not get_profile(profile) and not args.needs:
        print(f"unknown profile {profile!r} - expected one of: {', '.join(PROFILES)}",
              file=sys.stderr)
        return 2
    report = sra.search(
        profile,
        q=args.query, needs=args.needs, state=args.state, control=args.control,
        level=args.level, stem_only=args.stem, max_net_price=args.max_net_price,
        require=args.require, limit=args.limit, offset=args.offset, live=args.live,
    )
    if args.format == "json":
        payload = report.to_json()
    elif args.format == "csv":
        from .search.report import to_csv

        payload = to_csv(report)
    else:
        from .search.report import render_report

        payload = render_report(report, detailed=args.detailed)
    if args.out:
        Path(args.out).expanduser().write_text(payload, encoding="utf-8")
        print(f"wrote {args.out} ({len(payload):,} chars)", file=sys.stderr)
    else:
        print(payload)
    cache = report.cache
    if cache and args.verbose:
        print(f"[cache hit={cache.hit} note={cache.note} fp={cache.fingerprint[:10]}]", file=sys.stderr)
    return 0 if report.matches else 1


def cmd_school(sra: SRA, args: argparse.Namespace) -> int:
    if args.format == "json":
        match = sra.school(args.key, profile=args.profile)
        if match is None:
            print("not found", file=sys.stderr)
            return 1
        print(json.dumps(match.to_dict(), indent=2, ensure_ascii=False))
        return 0
    print(sra.render_school(args.key, profile=args.profile))
    return 0


def cmd_programs(sra: SRA, args: argparse.Namespace) -> int:
    from .search.report import render_program_list

    if args.action == "load":
        result = sra.load_programs(args.files)
        print(f"{result.summary()}")
        for ident, reason in result.rejected[:20]:
            print(f"  rejected {ident}: {reason}", file=sys.stderr)
        return 0
    if args.action == "verify":
        verdicts = None
        if args.from_file:
            verdicts = json.loads(Path(args.from_file).expanduser().read_text("utf-8"))
            if isinstance(verdicts, list):  # [{url, ok, status, ...}, ...]
                verdicts = {str(item.get("url")): item for item in verdicts if item.get("url")}
        verdict = sra.verify_programs(limit=args.limit, dns_only=args.dns_only, verdicts=verdicts)
        print(json.dumps(verdict, indent=2))
        return 0
    if args.action == "show":
        program = sra.program(args.target or "")
        if program is None:
            print("unknown programme id", file=sys.stderr)
            return 1
        print(json.dumps(program.to_dict(), indent=2, ensure_ascii=False))
        return 0
    programs = sra.programs(args.profile, kind=args.kind, state=args.state, limit=args.limit)
    if args.format == "json":
        print(json.dumps([p.to_dict() for p in programs], indent=2, ensure_ascii=False))
    else:
        print(render_program_list(programs))
        print(f"{len(programs)} programmes "
              f"({sra.db.count('aid_programs', 'active = 0')} retired/unverified held back)")
    return 0


def cmd_status(sra: SRA, args: argparse.Namespace) -> int:
    payload = sra.status()
    if args.format == "json":
        print(json.dumps(payload, indent=2, default=str, ensure_ascii=False))
        return 0
    from .search.report import render_status

    cache = payload.pop("cache", {})
    queries = payload.pop("query_cache", {})
    print(render_status(payload, cache=cache, queries=queries))
    return 0


def cmd_profiles(_: SRA, args: argparse.Namespace) -> int:  # noqa: ARG001
    print(json.dumps(describe_profiles(), indent=2))
    return 0


def cmd_topics(_: SRA, args: argparse.Namespace) -> int:  # noqa: ARG001
    for key, topic in sorted(TOPICS.items()):
        flag = " (critical)" if topic.critical else ""
        print(f"{key:38s} {topic.label:46s} need={topic.need.value:30s} "
              f"ttl={topic.freshness.value}{flag}")
    return 0


def cmd_seed(sra: SRA, args: argparse.Namespace) -> int:
    path = Path(args.path or (Path(__file__).resolve().parent / "data" / "seed" / "sra-seed.json.gz"))
    if args.action == "import":
        from .ingest.seed import import_seed

        outcome = import_seed(sra, path)
        print(json.dumps(outcome, indent=2))
        return 0
    from .ingest.seed import export_seed

    outcome = export_seed(sra, path, profiles=args.profile, limit=args.limit)
    print(json.dumps(outcome, indent=2))
    return 0


def cmd_sources(sra: SRA, args: argparse.Namespace) -> int:
    registry = sra.registry
    if args.action == "verify":
        urls = [src.url for src in registry.national
                if not args.topic or args.topic in src.needs]
        limit = getattr(args, "limit", 10) or 0
        if limit and len(urls) > limit:
            print(f"verifying {limit} of {len(urls)} national URLs "
                  f"(use --limit 0 for all, --topic to filter)...", file=sys.stderr)
            urls = urls[:limit]
        from .ingest.programs import verify_urls

        verdicts = verify_urls(urls, sra.fetcher)
        print(json.dumps({url: {"ok": v.ok, "status": v.status, "chars": v.chars, "why": v.reason}
                          for url, v in verdicts.items()}, indent=2))
        return 0
    payload = {
        "version": registry.version,
        "campus_paths": {k: v for k, v in registry.campus_paths.items()
                         if not args.topic or k == args.topic},
        "national": [src.to_dict() for src in registry.national
                     if not args.topic or args.topic in src.needs],
    }
    print(json.dumps(payload, indent=2))
    return 0


HANDLERS = {
    "build": cmd_build,
    "enrich": cmd_enrich,
    "refresh": cmd_refresh,
    "search": cmd_search,
    "school": cmd_school,
    "programs": cmd_programs,
    "status": cmd_status,
    "profiles": cmd_profiles,
    "topics": cmd_topics,
    "seed": cmd_seed,
    "sources": cmd_sources,
}


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
