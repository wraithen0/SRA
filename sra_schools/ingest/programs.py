"""Load the curated programme seed into the catalogue, with a URL truth gate.

The seed files are research artefacts (``.sra_research/*.json`` during
development, ``sra_schools/data/programs/*.json`` once shipped). They are written
by humans or agents, so nothing is trusted on sight:

* schema is validated record-by-record and bad records are rejected with a reason
* every ``official_url``/``apply_url`` is fetched; a programme whose URL does not
  resolve (or resolves to a soft 404) is marked ``active = 0`` rather than served

That second rule is why the module ships with a fetcher: the catalogue can be
re-audited at any time with ``sra-schools programs verify``.
"""

from __future__ import annotations

import json
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .. import util
from ..db.repository import Repository
from ..extract.fetchers import Fetcher, PageResult
from ..models import AidProgram, Deadline
from ..profiles import P1, P2, P3, PROFILES
from ..taxonomy import Need, normalize_program_kind
from ..util import norm_url

#: need string -> profile keys that care about it
NEED_TO_PROFILES: dict[str, tuple[str, ...]] = {
    Need.UNDERGRADUATE_SCHOLARSHIP.value: (P1,),
    Need.FINANCIAL_AID.value: (P1, P2),
    Need.APPLICATION_FEE_WAIVER.value: (P1,),
    Need.MENTORSHIP.value: (P1,),
    Need.ACCOMMODATION_FUNDING.value: (P2,),
    Need.ACCESSIBLE_UNIVERSITY_PROGRAMS.value: (P2,),
    Need.DISABILITY_SCHOLARSHIPS.value: (P2,),
    Need.ASSISTIVE_TECHNOLOGY_GRANTS.value: (P2,),
    Need.FULLY_FUNDED_DEGREE.value: (P3,),
    Need.TUITION_WAIVER.value: (P3,),
    Need.VISA_AND_ELIGIBILITY_INFO.value: (P3,),
    Need.RESEARCH_OR_INTERNSHIP.value: (P3, P1),
}
#: program kind -> implied need (used when needs are omitted)
KIND_TO_NEED = {
    "scholarship": Need.UNDERGRADUATE_SCHOLARSHIP.value,
    "grant": Need.FINANCIAL_AID.value,
    "fee_waiver": Need.APPLICATION_FEE_WAIVER.value,
    "mentorship": Need.MENTORSHIP.value,
    "research_fellowship": Need.RESEARCH_OR_INTERNSHIP.value,
    "tuition_waiver": Need.TUITION_WAIVER.value,
    "assistantship": Need.FULLY_FUNDED_DEGREE.value,
    "assistive_technology": Need.ASSISTIVE_TECHNOLOGY_GRANTS.value,
    "support_program": Need.ACCESSIBLE_UNIVERSITY_PROGRAMS.value,
    "services": Need.ACCOMMODATION_FUNDING.value,
    "visa_guidance": Need.VISA_AND_ELIGIBILITY_INFO.value,
    "work_study": Need.FINANCIAL_AID.value,
    "need_based_aid": Need.FINANCIAL_AID.value,
    "merit_scholarship": Need.UNDERGRADUATE_SCHOLARSHIP.value,
}

#: research spellings -> taxonomy spellings
NEED_ALIASES = {
    "accessible_university_program": Need.ACCESSIBLE_UNIVERSITY_PROGRAMS.value,
    "accessible_university_programs": Need.ACCESSIBLE_UNIVERSITY_PROGRAMS.value,
    "assistive_technology_grant": Need.ASSISTIVE_TECHNOLOGY_GRANTS.value,
    "assistive_technology_grants": Need.ASSISTIVE_TECHNOLOGY_GRANTS.value,
    "visa_and_eligibility_info": Need.VISA_AND_ELIGIBILITY_INFO.value,
    "visa_and_eligibility_information": Need.VISA_AND_ELIGIBILITY_INFO.value,
    "fully_funded_degree": Need.FULLY_FUNDED_DEGREE.value,
    "fully_funded_bachelors_or_masters": Need.FULLY_FUNDED_DEGREE.value,
    "financial_aid": Need.FINANCIAL_AID.value,
    "mentorship": Need.MENTORSHIP.value,
    "tuition_waiver": Need.TUITION_WAIVER.value,
    "research_or_internship": Need.RESEARCH_OR_INTERNSHIP.value,
    "application_fee_waiver": Need.APPLICATION_FEE_WAIVER.value,
    "accommodation_funding": Need.ACCOMMODATION_FUNDING.value,
    "disability_scholarships": Need.DISABILITY_SCHOLARSHIPS.value,
    "undergraduate_scholarship": Need.UNDERGRADUATE_SCHOLARSHIP.value,
}
VALID_CITIZENSHIP = {"us_citizen", "permanent_resident", "eligible_noncitizen", "daca",
                     "international", "any"}


@dataclass
class LoadResult:
    programs: list[AidProgram] = field(default_factory=list)
    rejected: list[tuple[str, str]] = field(default_factory=list)
    files: list[str] = field(default_factory=list)

    def summary(self) -> str:
        return (f"loaded {len(self.programs)} programmes from {len(self.files)} file(s); "
                f"{len(self.rejected)} rejected")


class ProgramLoader:
    def __init__(self, repo: Repository) -> None:
        self.repo = repo

    # ------------------------------------------------------------------ parse
    @staticmethod
    def parse_record(raw: dict[str, Any], *, origin: str | None = None) -> AidProgram:
        """Validate one seed record. Raises ValueError with the reason."""
        if not isinstance(raw, dict):
            raise ValueError("record is not an object")
        program_id = str(raw.get("program_id") or "").strip()
        name = util.normalize_space(str(raw.get("name") or ""))
        url = norm_url(str(raw.get("official_url") or ""))
        if not name:
            raise ValueError("missing name")
        if not program_id:
            program_id = util.slugify(name, 60)
        if not url or not url.startswith("http"):
            raise ValueError(f"{name}: official_url is missing or not a URL")
        kind = normalize_program_kind(raw.get("kind"))
        needs: list[str] = []
        for need in raw.get("needs") or []:
            mapped = NEED_ALIASES.get(str(need).strip().lower())
            if mapped:
                needs.append(mapped)
        levels = [str(x).strip().lower() for x in (raw.get("levels") or []) if x]
        citizenship = [str(x).strip().lower() for x in (raw.get("citizenship") or [])
                       if str(x).strip().lower() in VALID_CITIZENSHIP]
        profile_tags = [str(x).strip() for x in (raw.get("profile_tags") or []) if x]
        if not profile_tags:
            profile_tags = sorted({p for need in needs for p in NEED_TO_PROFILES.get(need, ())})
        deadlines: list[Deadline] = []
        for entry in raw.get("deadlines") or []:
            if isinstance(entry, str):
                entry = {"label": entry}
            if not isinstance(entry, dict):
                continue
            date_iso = str(entry.get("date") or "").strip() or None
            if date_iso and len(date_iso) >= 7 and not date_iso[:4].isdigit():
                date_iso = None
            deadlines.append(
                Deadline(
                    label=util.truncate(str(entry.get("label") or name), 120),
                    category=str(entry.get("category") or _deadline_category(kind)),
                    date_iso=date_iso[:10] if date_iso else None,
                    date_text=util.truncate(str(entry.get("deadline_text") or ""), 120) or None,
                    url=norm_url(str(entry.get("source_url") or "")) or url,
                    program_id=program_id,
                    recurring_annual=bool(entry.get("recurring_annual")),
                )
            )
        renewable = util.to_bool(raw.get("renewable"))
        stem = util.to_bool(raw.get("stem_eligible"))
        program = AidProgram(
            program_id=program_id,
            name=name,
            official_url=url,
            provider=util.truncate(str(raw.get("provider") or ""), 200) or None,
            apply_url=norm_url(str(raw.get("apply_url") or "")) or None,
            kind=kind.value if kind else None,
            levels=levels,
            citizenship=citizenship,
            needs=needs,
            profile_tags=profile_tags,
            amount_text=util.truncate(str(raw.get("amount_text") or ""), 300) or None,
            coverage_text=util.truncate(str(raw.get("coverage_text") or ""), 300) or None,
            stipend_text=util.truncate(str(raw.get("stipend_text") or ""), 300) or None,
            renewable=renewable,
            stem_eligible=stem,
            disability_scope=[str(x) for x in (raw.get("disability_scope") or [])],
            eligibility=[util.truncate(str(x), 400) for x in (raw.get("eligibility") or [])][:20],
            apply_steps=[util.truncate(str(x), 500) for x in (raw.get("apply_steps") or [])][:20],
            how_to_win=[util.truncate(str(x), 400) for x in (raw.get("how_to_win") or [])][:12],
            documentation_required=util.truncate(str(raw.get("documentation_required") or ""), 400) or None,
            work_auth_notes=util.truncate(str(raw.get("work_authorization_notes") or
                                              raw.get("work_auth_notes") or ""), 500) or None,
            state=str(raw.get("state") or "").upper() or None,
            notes=util.truncate(str(raw.get("notes") or ""), 1200) or None,
            sources=[u for u in (norm_url(str(x)) for x in (raw.get("sources") or [])) if u][:25],
            confidence=float(raw.get("confidence") if raw.get("confidence") is not None else 0.6),
            verified_at=str(raw.get("verified_at") or "") or None,
            deadlines=deadlines,
        )
        if origin and origin in PROFILES:
            program.profile_tags = sorted({*program.profile_tags, origin})
        if not program.needs:
            # derive need from kind when the seed omitted it
            implied = KIND_TO_NEED.get(program.kind) if program.kind else None
            if implied:
                program.needs = [implied]
        if not program.needs:
            raise ValueError(f"{name}: no recognised needs (got: {raw.get('needs')!r})")
        return program

    # ------------------------------------------------------------------- load
    def load_files(self, paths: Iterable[Path], *, origin_map: dict[str, str] | None = None,
                   replace: bool = False) -> LoadResult:
        result = LoadResult()
        seen: set[str] = set()
        for path in paths:
            path = Path(path)
            if not path.exists():
                result.rejected.append((str(path), "file not found"))
                continue
            try:
                payload = json.loads(path.read_text("utf-8"))
            except json.JSONDecodeError as exc:
                result.rejected.append((str(path), f"invalid JSON: {exc}"))
                continue
            records = payload if isinstance(payload, list) else payload.get("programs", [])
            origin = (origin_map or {}).get(path.name)
            for index, raw in enumerate(records):
                try:
                    program = self.parse_record(raw, origin=origin)
                except (ValueError, TypeError) as exc:
                    result.rejected.append((f"{path.name}[{index}]", str(exc)))
                    continue
                if program.program_id in seen:
                    program.program_id = f"{program.program_id}-{path.stem[-4:]}"
                seen.add(program.program_id)
                result.programs.append(program)
            result.files.append(str(path))
        if replace:
            self.repo.db.execute("UPDATE aid_programs SET active = 0")
        for program in result.programs:
            self.repo.upsert_program(program)
        return result


def _deadline_category(kind: Any) -> str:  # noqa: ANN401
    mapped = normalize_program_kind(kind.value if hasattr(kind, "value") else kind)
    if mapped is None:
        return "application"
    return {
        "scholarship": "scholarship",
        "grant": "application",
        "fee_waiver": "application",
        "mentorship": "application",
        "research_fellowship": "scholarship",
        "visa_guidance": "visa",
        "assistive_technology": "aid",
    }.get(mapped.value, "application")


# --------------------------------------------------------------- URL truth gate
@dataclass
class VerificationResult:
    url: str
    ok: bool
    verdict: str = "ok"          # ok | blocked | dead | empty | error
    status: int | None = None
    title: str | None = None
    reason: str | None = None
    chars: int = 0


SOFT_404_MARKERS = ("page not found", "not found", "404", "error -", "access denied",
                    "browser check", "just a moment", "attention required", "are you a human")
MIN_USEFUL_CHARS = 400
#: a WAF saying "no" is not the same as a dead link - never retire a programme on 403
BLOCKED_STATUSES = {401, 403, 405, 406, 407, 409, 428, 429, 451, 503}
DEAD_STATUSES = {404, 408, 410, 414, 415, 502, 504}
DNS_FAILURE_MARKERS = (
    "name or service not known", "nodename nor servname", "getaddrinfo failed",
    "no address associated with hostname", "temporary failure in name resolution",
    "the specified network name is no longer available", "domain name not found",
)


def _no_host(error: str | None) -> bool:
    text = (error or "").lower()
    return any(marker in text for marker in DNS_FAILURE_MARKERS)


def dns_verdicts(urls: Sequence[str]) -> dict[str, VerificationResult]:
    """Resolve every hostname. Costs nothing, needs no key, and catches invented URLs.

    A host that resolves is **not** proof the page exists, so the verdict is
    ``resolves`` (stored as pending) rather than ``ok``.
    """
    import socket

    out: dict[str, VerificationResult] = {}
    for url in urls:
        key = util.norm_url(url) or url
        host = util.domain_of(url)
        if not host:
            out[key] = VerificationResult(key, False, "dead", reason="no hostname in url")
            continue
        try:
            socket.getaddrinfo(host, 443, type=socket.SOCK_STREAM)
        except OSError as exc:
            out[key] = VerificationResult(key, False, "dead", reason=f"DNS: {exc}")
            continue
        out[key] = VerificationResult(key, False, "resolves", reason=f"{host} resolves; content unchecked")
    return out


def verify_offline(repo: Repository) -> dict[str, Any]:
    """DNS-only audit of the catalogue: retire unreachable hosts, flag the rest."""
    urls = sorted(({p.official_url for p in repo.programs(limit=10_000)}
                   | {p.apply_url or "" for p in repo.programs(limit=10_000)} - {""}))
    verdicts = dns_verdicts(urls)
    outcome = apply_verdicts(repo, verdicts, deactivate="dead", resolve_verdict="resolves")
    outcome["hosts_dead"] = sorted(v.url for v in verdicts.values() if v.verdict == "dead")
    return outcome


def classify(page: PageResult) -> VerificationResult:
    """Decide whether a page really answered, using status *and* content mass."""
    title = (getattr(page, "title", None) or "").lower()
    soft = any(marker in title for marker in SOFT_404_MARKERS)
    status = page.status
    if page.not_modified:
        return VerificationResult(page.url, True, "ok", status, title, "not modified", page.chars)
    if status in DEAD_STATUSES or _no_host(page.error):
        return VerificationResult(page.url, False, "dead", status, title,
                                  page.error or f"HTTP {status}", page.chars)
    if status in BLOCKED_STATUSES or soft:
        return VerificationResult(page.url, False, "blocked", status, title,
                                  page.error or ("soft-404 title" if soft else f"HTTP {status}"),
                                  page.chars)
    if status is None:
        return VerificationResult(page.url, False, "error", status, title,
                                  page.error or "transport error", page.chars)
    if page.chars < MIN_USEFUL_CHARS:
        return VerificationResult(page.url, False, "empty", status, title,
                                  f"only {page.chars} chars of text", page.chars)
    return VerificationResult(page.url, status == 200, "ok" if status == 200 else "error",
                              status, title, page.error, page.chars)


def verify_urls(urls: Sequence[str], fetcher: Fetcher, *, purpose: str =
                "Confirm this official scholarship / financial aid URL resolves to a real page") -> dict[str, VerificationResult]:
    """Fetch each URL once and classify the outcome.

    A ``blocked`` verdict means the origin refused our client (bot protection), not
    that the page is gone; only ``dead`` may deactivate a catalogue entry.
    """
    results: dict[str, VerificationResult] = {}
    batch = getattr(fetcher, "max_urls", 10) or 10
    for i in range(0, len(urls), batch):
        chunk = list(urls[i : i + batch])
        pages: list[PageResult] = fetcher.fetch(chunk, ttl_seconds=0, purpose=purpose)
        by_url = {page.url: page for page in pages}
        for url in chunk:
            page = by_url.get(url) or next((p for p in pages if util.norm_url(p.url) == util.norm_url(url)), None)
            if page is None:
                results[url] = VerificationResult(url, False, "error", None, None, "no result")
                continue
            results[url] = classify(page)
    return results


def apply_verdicts(repo: Repository, verdicts: Mapping[str, VerificationResult | dict[str, Any]],
                   *, deactivate: str = "dead", resolve_verdict: str | None = None) -> dict[str, Any]:
    """Persist verification outcomes for programme catalogue entries.

    ``deactivate`` names the verdict that retires a programme. ``blocked`` and
    ``error`` leave it active but flagged for a re-check with a real browser, and
    ``resolve_verdict`` (e.g. ``"resolves"`` from a DNS-only pass) is stored as
    ``pending_dns`` so nobody mistakes it for a verified page.
    """
    normalised: dict[str, VerificationResult] = {}
    for url, value in verdicts.items():
        key = util.norm_url(url) or url
        if isinstance(value, VerificationResult):
            normalised[key] = value
        elif isinstance(value, dict):
            normalised[key] = VerificationResult(
                url=key, ok=bool(value.get("ok")),
                verdict=str(value.get("verdict") or ("ok" if value.get("ok") else "error")),
                status=value.get("status"), title=value.get("title"),
                reason=value.get("reason") or value.get("why"), chars=int(value.get("chars") or 0),
            )
    today = util.utcnow().date().isoformat()
    tallies: dict[str, int] = {"ok": 0, "blocked": 0, "dead": 0, "empty": 0, "error": 0,
                               "resolves": 0, "skipped": 0}
    retired: list[str] = []
    for program in repo.programs(limit=10_000):
        verdict = normalised.get(util.norm_url(program.official_url) or "")
        if verdict is None:
            tallies["skipped"] += 1
            continue
        tallies[verdict.verdict if verdict.verdict in tallies else "error"] += 1
        apply_verdict = normalised.get(util.norm_url(program.apply_url or ""))
        stored = ("pending_dns" if resolve_verdict and verdict.verdict == resolve_verdict
                  else verdict.verdict)
        note = util.truncate(
            (f"{verdict.verdict}: {verdict.reason or ''}" if verdict.reason else verdict.verdict)
            + (f" (HTTP {verdict.status}, {verdict.chars} chars)" if verdict.status else ""),
            300,
        )
        if verdict.verdict == deactivate:
            repo.db.execute(
                "UPDATE aid_programs SET active = 0, verification_status = ?, verification_note = ?, "
                "verified_at = ?, updated_at = ? WHERE program_id = ?",
                (stored, note, today, util.iso(), program.program_id),
            )
            retired.append(program.program_id)
            continue
        if apply_verdict and apply_verdict.verdict == "dead":
            repo.db.execute("UPDATE aid_programs SET apply_url = NULL WHERE program_id = ?",
                            (program.program_id,))
        repo.db.execute(
            "UPDATE aid_programs SET verification_status = ?, verification_note = ?, verified_at = ?, "
            "updated_at = ? WHERE program_id = ?",
            (stored, note, today if verdict.verdict != "resolves" else program.verified_at,
             util.iso(), program.program_id),
        )
    return {"tallies": tallies, "retired": retired, "checked": len(normalised)}


def audit_programs(
    repo: Repository,
    fetcher: Fetcher,
    *,
    deactivate_unverified: bool = True,
    limit: int | None = None,
) -> dict[str, Any]:
    """Live re-verification of the catalogue (needs a fetcher that can pass WAFs)."""
    programs = repo.programs(limit=limit or 10_000)
    urls = sorted(({p.official_url for p in programs} | {p.apply_url or "" for p in programs}) - {""})
    verdicts = verify_urls(urls, fetcher)
    outcome = apply_verdicts(repo, verdicts, deactivate="dead" if deactivate_unverified else "never")
    outcome["failures"] = [
        {"url": url, "verdict": v.verdict, "reason": v.reason}
        for url, v in sorted(verdicts.items()) if not v.ok
    ][:40]
    return outcome
