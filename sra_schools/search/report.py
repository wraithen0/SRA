"""Human-facing renderings of a search report: markdown, CSV, single-school view.

The frontend team should read ``SearchReport.to_dict()`` / ``SchoolMatch.to_dict()``;
these renderings exist so the same data is reviewable from a terminal and diffable
in a pull request.
"""

from __future__ import annotations

import csv
import io
import json
from collections.abc import Iterable, Sequence
from typing import Any

from .. import util
from ..models import AidProgram, Deadline, SchoolMatch, SearchReport
from ..profiles import PROFILES
from ..taxonomy import TOPICS

_MAX_TABLE_ROWS = 25


def _bool_text(value: Any) -> str:  # noqa: ANN401
    return "yes" if value else "no"


def render_report(report: SearchReport, *, detailed: bool = False,
                  max_results: int = _MAX_TABLE_ROWS) -> str:
    """Full markdown document for a search result."""
    out: list[str] = []
    profile = PROFILES.get(report.profile or "")
    title = profile.title if profile else (report.profile or "All institutions")
    out.append(f"# {title} - school search")
    out.append("")
    out.append(f"_Generated {report.generated_at[:19]}Z · dataset "
               f"{report.dataset_version or 'unknown'} · {report.universe_size:,} institutions "
               f"in the universe · {report.count} matches returned_")
    if report.cache:
        layer = "query cache" if report.cache.hit else "computed from cache"
        out.append(f"_Served by: {layer} ({report.cache.note or 'n/a'})_")
    out.append("")
    out.append(_filters_line(report))
    out.append("")
    out.append(_top_line_table(report.matches[:max_results]))
    if detailed:
        for match in report.matches[:max_results]:
            out.append("")
            out.append(render_match(match, profile_title=title))
    else:
        out.append("")
        out.append("_Run with `--detailed` (or `render_match`) for the per-school "
                   "evidence, deadlines and application playbook._")
    if report.national_programs:
        out.append("")
        out.append(render_programs(report.national_programs, heading="National and external programmes"))
    if report.national_deadlines:
        out.append("")
        out.append(render_deadlines(report.national_deadlines, heading="Upcoming dates", limit=12))
    return "\n".join(out).strip() + "\n"


def _filters_line(report: SearchReport) -> str:
    query = report.query
    bits: list[str] = []
    if query.q:
        bits.append(f"query `{query.q}`")
    if query.profile:
        bits.append(f"profile `{query.profile}`")
    if query.state:
        bits.append(f"state `{query.state}`")
    if query.control:
        bits.append(f"control `{query.control}`")
    if query.level:
        bits.append(f"level `{query.level}`")
    if query.stem_only:
        bits.append("STEM only")
    if query.max_net_price is not None:
        bits.append(f"net price <= {util.usd(query.max_net_price)}")
    if query.needs:
        bits.append("needs " + ", ".join(query.needs))
    return "**Filters:** " + (" · ".join(bits) if bits else "none")


def _top_line_table(matches: Sequence[SchoolMatch]) -> str:
    if not matches:
        return "_No schools matched. Try removing filters or run `sra-schools enrich`._"
    lines = [
        "| # | School | Match score | Aid signal | Net price | Verified topics | Gaps |",
        "|--:|---|---:|---|---:|---:|---:|",
    ]
    for index, match in enumerate(matches, start=1):
        inst = match.institution
        lines.append(
            f"| {index} | [{inst.name}]({inst.url_homepage or '#'}) "
            f"_{inst.state_abbr or '-'}_ | **{match.score:.0f}** | "
            f"{_aid_note(match)} | {util.usd(inst.avg_net_price)} | "
            f"{len(match.needs_covered)} | {len(match.gaps)} |"
        )
    return "\n".join(lines)


def _aid_note(match: SchoolMatch) -> str:
    signals = match.signals
    pieces = []
    if signals.get("aid_generosity"):
        pieces.append(f"grants {signals['aid_generosity'] * 100:.0f}")
    if signals.get("need_coverage"):
        pieces.append(f"evidence {signals['need_coverage'] * 100:.0f}")
    return " · ".join(pieces) if pieces else "-"


def render_match(match: SchoolMatch, *, profile_title: str | None = None) -> str:
    """Everything we can say about one school, with provenance."""
    inst = match.institution
    out: list[str] = [f"## {inst.name}", ""]
    facts_line = [
        f"{inst.city + ', ' if inst.city else ''}{inst.state_abbr or ''}",
        inst.control or "",
        inst.preddeg or "",
        f"undergrads {inst.enrollment_undergrad:,.0f}" if inst.enrollment_undergrad else "",
        f"admits {inst.admissions_rate:.0%}" if inst.admissions_rate else "",
        f"net price {util.usd(inst.avg_net_price)}" if inst.avg_net_price else "",
        f"pell {inst.pct_pell:.0%}" if inst.pct_pell else "",
        f"first-gen {inst.first_gen_pct:.0%}" if inst.first_gen_pct else "",
        f"median debt {util.usd(inst.median_debt_undergrad)}" if inst.median_debt_undergrad else "",
        f"STEM share {inst.stem_share:.0%}" if inst.stem_share else "",
        f"international {inst.international_share:.0%}" if inst.international_share else "",
    ]
    out.append(" · ".join(x for x in facts_line if x))
    out.append("")
    out.append(f"**Match score {match.score:.0f}/100**"
               + (f" for _{profile_title}_" if profile_title else "")
               + (" · some evidence is past its freshness window" if match.stale else ""))
    out.append("")
    if match.reasons:
        out.append("| Why it ranked | Strength |")
        out.append("|---|---:|")
        for row in match.reasons[:6]:
            out.append(f"| {row['label']} | {row['value'] * 100:.0f}/100 |")
        out.append("")
    if match.links:
        out.append("### Official links")
        for topic, url in match.links.items():
            label = TOPICS[topic].label if topic in TOPICS else topic.replace("_", " ").title()
            out.append(f"- **{label}:** <{url}>")
        out.append("")
    if match.deadlines:
        out.append("### Deadlines")
        for deadline in match.deadlines[:10]:
            state = "past" if deadline.is_past else (f"in {deadline.days_left}d"
                                                    if deadline.days_left is not None else "date unconfirmed")
            stamp = deadline.date_iso or deadline.date_text or "?"
            out.append(f"- **{stamp}** ({state}) - {deadline.label} "
                       f"[{deadline.category}] <{deadline.url}>")
        out.append("")
    if match.playbook:
        out.append("### How to apply successfully")
        for step in match.playbook:
            flag = " ⚠️" if step.status == "verify" else ""
            due = f" - _by {step.deadline}_" if step.deadline else ""
            out.append(f"{step.order}. **{step.title}**{due}{flag}")
            out.append(f"   {step.detail}")
        out.append("")
    if match.programs:
        out.append("### Money you can also pursue")
        for program in match.programs[:8]:
            amount = f" - {program.amount_text}" if program.amount_text else ""
            out.append(f"- [{program.name}]({program.official_url}){amount}")
        out.append("")
    evidence = [f for f in match.facts if f.evidence][:10]
    if evidence:
        out.append("### Evidence")
        for fact in evidence:
            topic = TOPICS.get(fact.topic)
            label = topic.label if topic else fact.topic
            out.append(f"- **{label}** ({fact.extractor}, conf {fact.confidence:.2f}, "
                       f"seen {fact.observed_at[:10]}): {fact.evidence}")
        out.append("")
    if match.gaps:
        out.append("### Not verified yet")
        out.append(" · ".join(match.gaps))
        out.append("")
        out.append("_Ask the financial aid or admissions office directly, or run "
                   "`sra-schools enrich <unitid>` to re-crawl these pages._")
    return "\n".join(out).rstrip() + "\n"


def render_programs(programs: Sequence[AidProgram], *, heading: str = "Programmes") -> str:
    out = [f"## {heading}", ""]
    for program in programs:
        out.append(f"### {program.name}")
        if program.provider:
            out.append(f"_{program.provider}_ · <{program.official_url}>")
        bits = [
            program.kind or "",
            "/".join(program.levels) or "",
            program.amount_text or program.coverage_text or "",
            f"verified {program.verified_at}" if program.verified_at else "",
        ]
        out.append(" · ".join(b for b in bits if b))
        out.append("")
        if program.eligibility:
            out.append("**Eligibility**")
            out.extend(f"- {item}" for item in program.eligibility[:6])
            out.append("")
        if program.apply_steps:
            out.append("**How to apply**")
            out.extend(f"{i}. {step}" for i, step in enumerate(program.apply_steps, start=1))
            out.append("")
        if program.how_to_win:
            out.append("**To actually win it**")
            out.extend(f"- {tip}" for tip in program.how_to_win[:6])
            out.append("")
        if program.deadlines:
            out.append("**Dates**")
            out.extend(
                f"- {d.date_iso or d.date_text or 'varies'} - {d.label}"
                for d in program.deadlines[:6]
            )
            out.append("")
        if program.notes:
            out.append(f"> {program.notes}")
            out.append("")
    return "\n".join(out).rstrip() + "\n"


def render_deadlines(deadlines: Sequence[Deadline], *, heading: str = "Deadlines",
                     limit: int = 25) -> str:
    future = [d for d in deadlines if not d.is_past][:limit]
    if not future:
        return f"## {heading}\n\n_No dated deadlines in the cache yet._\n"
    lines = [f"## {heading}", "", "| Date | What | Where | Days |", "|---|---|---|---:|"]
    for deadline in future:
        where = deadline.program_id or (f"school {deadline.unitid}" if deadline.unitid else "external")
        lines.append(f"| {deadline.date_iso or '?'} | {deadline.label} | {where} | "
                     f"{deadline.days_left if deadline.days_left is not None else '-'} |")
    return "\n".join(lines) + "\n"


def to_csv(report: SearchReport) -> str:
    """One row per school - feeds a spreadsheet or a Google Sheet."""
    buffer = io.StringIO()
    columns = [
        "rank", "unitid", "name", "state", "city", "control", "homepage", "score",
        "net_price", "tuition_in", "pct_pell", "first_gen_pct", "stem_share",
        "international_share", "fafsa_code", "priority_deadline", "application_deadline",
        "aid_office_url", "npc_url", "fee_waiver_url", "disability_url", "intl_office_url",
        "research_url", "deadlines_found", "programs_found", "gaps", "last_verified", "stale",
    ]
    writer = csv.writer(buffer)
    writer.writerow(columns)
    for rank, match in enumerate(report.matches, start=1):
        inst = match.institution
        facts = {f.topic: f for f in match.facts}
        writer.writerow([
            rank, inst.unitid, inst.name, inst.state_abbr, inst.city, inst.control,
            inst.url_homepage, match.score, inst.avg_net_price, inst.tuition_in_state,
            inst.pct_pell, inst.first_gen_pct, inst.stem_share, inst.international_share,
            _val(facts.get("fafsa_school_code")), _val(facts.get("priority_filing_deadline")),
            _val(facts.get("application_deadline_first_year")),
            match.links.get("financial_aid_office", ""), match.links.get("net_price_calculator", ""),
            match.links.get("application_fee_waiver", ""),
            match.links.get("disability_services_office", ""),
            match.links.get("international_student_office", ""),
            match.links.get("undergraduate_research_office", ""),
            len(match.deadlines), len(match.programs), "; ".join(match.gaps),
            match.last_verified or "", _bool_text(match.stale),
        ])
    return buffer.getvalue()


def _val(fact: Any) -> str:  # noqa: ANN401
    if fact is None:
        return ""
    return str(fact.value_date or fact.value_text or fact.value_num or fact.value_bool or "")


def to_json(report: SearchReport, *, indent: int | None = 2) -> str:
    return json.dumps(report.to_dict(), ensure_ascii=False, indent=indent, default=str)


def render_program_list(programs: Iterable[AidProgram]) -> str:
    lines = ["| Programme | Kind | Levels | Amount | Next date | Verified |",
             "|---|---|---|---|---|---|"]
    for program in programs:
        dates = sorted(d.date_iso for d in program.deadlines if d.date_iso)
        lines.append(
            f"| [{program.name}]({program.official_url}) | {program.kind or '-'} | "
            f"{', '.join(program.levels) or '-'} | {program.amount_text or program.coverage_text or '-'} | "
            f"{dates[0] if dates else '-'} | {program.verified_at or '-'} |"
        )
    return "\n".join(lines) + "\n"


def render_status(status: dict[str, Any], *, cache: dict[str, Any] | None = None,
                 queries: dict[str, Any] | None = None) -> str:
    out = ["# Cache status", ""]
    for key, value in status.items():
        if key in ("coverage", "last_crawl"):
            continue
        if isinstance(value, float):
            out.append(f"- **{key}:** {value:,.1f}")
        else:
            out.append(f"- **{key}:** {value:,}" if isinstance(value, int) else f"- **{key}:** {value}")
    if cache:
        out.append("")
        out.append("## Pages")
        for key, value in cache.items():
            out.append(f"- **{key}:** {value:,}" if isinstance(value, int) else f"- **{key}:** {value}")
    if queries:
        out.append("")
        out.append("## Query cache")
        for key, value in queries.items():
            out.append(f"- **{key}:** {value:,}" if isinstance(value, int) else f"- **{key}:** {value}")
    coverage = status.get("coverage") or {}
    if coverage:
        out.append("")
        out.append("## Topic coverage (institutions with at least one live fact)")
        out.append(f"- universe: {coverage.get('universe', 0):,}")
        for topic, count in sorted(coverage.get("by_topic", {}).items(), key=lambda kv: -kv[1]):
            label = TOPICS[topic].label if topic in TOPICS else topic
            out.append(f"- {label}: {count:,}")
    return "\n".join(out).strip() + "\n"
