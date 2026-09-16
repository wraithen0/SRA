"""FastAPI HTTP server for the SRA scholarship discovery engine.

Run with:
    uvicorn sra_schools.server:app --reload --port 8000

Or from Python:
    from sra_schools.server import app
    import uvicorn; uvicorn.run(app, host="0.0.0.0", port=8000)

All read endpoints are cache-only (no network). Write endpoints trigger
crawling and are budget-bounded by the SRA settings.
"""

from __future__ import annotations

import json
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from .api import SRA, get_sra
from .config import Settings
from .models import SearchQuery
from .profiles import PROFILES, describe_profiles, get_profile
from .taxonomy import TOPICS

# --------------------------------------------------------------------------- app
_settings = Settings.from_env()
_sra: SRA | None = None


def get_sra_instance() -> SRA:
    """Return the shared SRA instance, creating it on first use."""
    global _sra
    if _sra is None:
        _sra = get_sra()
    return _sra


@asynccontextmanager
async def lifespan(app: Any):  # noqa: ANN401
    """Create the SRA instance on startup, close it on shutdown."""
    get_sra_instance()
    yield
    global _sra
    if _sra is not None:
        _sra.db.close()
        _sra = None


try:
    from fastapi import FastAPI, HTTPException, Query, status
    from fastapi.middleware.cors import CORSMiddleware
    from fastapi.responses import JSONResponse, PlainTextResponse
    from pydantic import BaseModel, Field
except ImportError as exc:  # pragma: no cover - optional dependency
    raise ImportError(
        "FastAPI is required for the HTTP API. "
        "Install it with: pip install fastapi uvicorn"
    ) from exc

app = FastAPI(
    title="SRA — Scholarship Research Assistant",
    description=(
        "US college/university discovery with financial-aid intelligence. "
        "Search by student profile, browse programmes, and inspect the cache."
    ),
    version="0.1.0",
    lifespan=lifespan,
)

# CORS — allow the frontend to call this from any origin during development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ------------------------------------------------------------------- schemas
class SearchRequest(BaseModel):
    """Query parameters for the search endpoint."""

    profile: str | None = Field(None, description="Profile key (first_generation, student_with_disability, international_stem)")
    q: str | None = Field(None, description="Free-text query (name, city, state)")
    needs: list[str] | None = Field(None, description="Explicit need keys instead of a profile")
    level: str | None = Field(None, description="undergraduate | graduate | community")
    state: str | None = Field(None, description="Two-letter state abbreviation")
    control: str | None = Field(None, description="public | private_nonprofit | private_for_profit")
    stem_only: bool = Field(False, description="STEM-strong institutions only")
    graduate: bool | None = Field(None, description="Filter by graduate program availability")
    max_net_price: float | None = Field(None, description="Maximum average net price (USD)")
    min_aid_generosity: float | None = Field(None, description="Minimum aid generosity ratio (0-1)")
    require: list[str] | None = Field(None, description="Only schools with live facts for these topics")
    limit: int = Field(20, ge=1, le=100, description="Results per page")
    offset: int = Field(0, ge=0, description="Pagination offset")
    live: bool = Field(False, description="Allow on-demand crawling for this request")
    include_stale: bool = Field(True, description="Include stale (past-TTL) results")


class EnrichRequest(BaseModel):
    """Body for the enrich endpoint."""

    profile: str | None = Field(None, description="Profile key to enrich for")
    unitids: list[int] | None = Field(None, description="Specific institution UnitIDs")
    limit: int = Field(10, ge=1, le=200, description="Max institutions to enrich")
    force: bool = Field(False, description="Re-crawl even answered topics")
    topics: list[str] | None = Field(None, description="Restrict to these topic keys")


class RefreshRequest(BaseModel):
    """Body for the refresh endpoint."""

    unitids: list[int] | None = Field(None, description="Specific institution UnitIDs")
    limit: int = Field(100, ge=1, le=500, description="Max institutions to refresh")
    profile: str | None = Field(None, description="Profile key for topic selection")
    purge: bool = Field(False, description="Also drop long-expired cached pages")


class BuildRequest(BaseModel):
    """Body for the build endpoint."""

    source: str | None = Field(None, description="Local .zip/.csv path or directory")
    url: str | None = Field(None, description="Override the bulk dataset URL")
    no_programs: bool = Field(False, description="Skip programme seed loading")
    rebuild: bool = Field(False, description="Clear the cache first")


class VerifyProgramsRequest(BaseModel):
    """Body for the programs verify endpoint."""

    limit: int | None = Field(None, ge=1, le=1000, description="Max programmes to verify")
    dns_only: bool = Field(False, description="DNS-only audit (no HTTP)")


class SeedExportRequest(BaseModel):
    """Body for the seed export endpoint."""

    profiles: list[str] | None = Field(None, description="Restrict to schools matched by these profiles")
    limit: int | None = Field(None, ge=1, description="Cap institutions in the export")
    path: str | None = Field(None, description="Output file path")


# ------------------------------------------------------------------- helpers
def _sra_or_500() -> SRA:
    try:
        return get_sra_instance()
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to open cache: {exc}") from exc


def _json_response(data: dict[str, Any], status_code: int = 200) -> JSONResponse:
    return JSONResponse(content=data, status_code=status_code)


# ------------------------------------------------------------------- routes
@app.get("/")
async def root() -> dict[str, str]:
    """API root — basic info."""
    return {
        "name": "SRA — Scholarship Research Assistant",
        "version": "0.1.0",
        "docs": "/docs",
        "openapi": "/openapi.json",
    }


# ------------------------------------------------------------------- search
@app.get("/api/v1/search")
async def search(
    profile: str | None = None,
    q: str | None = None,
    needs: list[str] | None = None,
    level: str | None = None,
    state: str | None = None,
    control: str | None = None,
    stem_only: bool = False,
    graduate: bool | None = None,
    max_net_price: float | None = None,
    min_aid_generosity: float | None = None,
    require: list[str] | None = None,
    limit: int = 20,
    offset: int = 0,
    live: bool = False,
    include_stale: bool = True,
) -> JSONResponse:
    """Rank schools for a student profile (or explicit needs list).

    Cache-only by default. Set live=true to allow on-demand crawling.
    """
    sra = _sra_or_500()
    try:
        report = sra.search(
            profile,
            q=q,
            needs=needs,
            level=level,
            state=state,
            control=control,
            stem_only=stem_only,
            graduate=graduate,
            max_net_price=max_net_price,
            min_aid_generosity=min_aid_generosity,
            require=require,
            limit=limit,
            offset=offset,
            live=live,
            include_stale=include_stale,
        )
        return _json_response(report.to_dict())
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.post("/api/v1/search")
async def search_post(req: SearchRequest) -> JSONResponse:
    """Rank schools for a student profile with structured JSON payload."""
    sra = _sra_or_500()
    try:
        report = sra.search(
            req.profile,
            q=req.q,
            needs=req.needs,
            level=req.level,
            state=req.state,
            control=req.control,
            stem_only=req.stem_only,
            graduate=req.graduate,
            max_net_price=req.max_net_price,
            min_aid_generosity=req.min_aid_generosity,
            require=req.require,
            limit=req.limit,
            offset=req.offset,
            live=req.live,
            include_stale=req.include_stale,
        )
        return _json_response(report.to_dict())
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.get("/api/v1/schools/{key}")
async def school(
    key: str,
    profile: str | None = None,
) -> JSONResponse:
    """Everything we hold about one institution (by UnitID, OPEID, or name)."""
    sra = _sra_or_500()
    try:
        match = sra.school(key, profile=profile)
        if match is None:
            raise HTTPException(status_code=404, detail=f"No institution matching {key!r}")
        return _json_response(match.to_dict())
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


# ------------------------------------------------------------------- programs
@app.get("/api/v1/programs")
async def programs(
    profile: str | None = None,
    needs: list[str] | None = None,
    level: str | None = None,
    kind: str | None = None,
    state: str | None = None,
    limit: int = 50,
) -> JSONResponse:
    """Browse the national programme catalogue."""
    sra = _sra_or_500()
    try:
        items = sra.programs(
            profile,
            needs=needs,
            level=level,
            kind=kind,
            state=state,
            limit=limit,
        )
        return _json_response({"count": len(items), "results": [p.to_dict() for p in items]})
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.get("/api/v1/programs/{program_id}")
async def program(program_id: str) -> JSONResponse:
    """Single programme by ID."""
    sra = _sra_or_500()
    try:
        item = sra.program(program_id)
        if item is None:
            raise HTTPException(status_code=404, detail=f"Unknown programme {program_id!r}")
        return _json_response(item.to_dict())
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


# ------------------------------------------------------------------- deadlines
@app.get("/api/v1/deadlines")
async def deadlines(
    unitid: int | None = None,
    limit: int = 40,
) -> JSONResponse:
    """Upcoming deadlines (optionally filtered to one institution)."""
    sra = _sra_or_500()
    try:
        items = sra.deadlines(unitid=unitid, limit=limit)
        return _json_response({"count": len(items), "results": [d.to_dict() for d in items]})
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


# ------------------------------------------------------------------- meta
@app.get("/api/v1/status")
async def status() -> JSONResponse:
    """Cache contents, coverage, and freshness statistics."""
    sra = _sra_or_500()
    try:
        return _json_response(sra.status())
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.get("/api/v1/profiles")
async def profiles() -> JSONResponse:
    """List the built-in student profiles."""
    return _json_response({"count": len(PROFILES), "results": describe_profiles()})


@app.get("/api/v1/topics")
async def topics() -> JSONResponse:
    """List all fact topics the module can establish."""
    items = [
        {
            "key": key,
            "label": topic.label,
            "need": topic.need.value,
            "freshness": topic.freshness.value,
            "critical": topic.critical,
            "value_type": topic.value_type,
        }
        for key, topic in sorted(TOPICS.items())
    ]
    return _json_response({"count": len(items), "results": items})


# ------------------------------------------------------------------- writes
@app.post("/api/v1/build")
async def build(req: BuildRequest) -> JSONResponse:
    """Load the institution universe from the federal Scorecard dataset.

    This is a write operation — it downloads ~23 MB and inserts ~6,200 rows.
    """
    sra = _sra_or_500()
    try:
        result = sra.build(
            source=req.source,
            url=req.url or "https://ed-public-download.scorecard.network/downloads/Most-Recent-Cohorts-Institution_06102026.zip",
            seed_programs=not req.no_programs,
        )
        return _json_response(result, status_code=201)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.post("/api/v1/enrich")
async def enrich(req: EnrichRequest) -> JSONResponse:
    """Crawl campus pages to answer a profile's needs.

    Budget-bounded: max 200 pages per run, 6 new pages per institution.
    """
    sra = _sra_or_500()
    try:
        reports = sra.enrich(
            unitids=req.unitids,
            profile=req.profile,
            limit=req.limit,
            force=req.force,
            topics=req.topics,
        )
        return _json_response({"count": len(reports), "results": reports}, status_code=201)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.post("/api/v1/refresh")
async def refresh(req: RefreshRequest) -> JSONResponse:
    """Re-crawl only pages past their freshness window.

    Validators (ETag/Last-Modified) avoid re-transferring unchanged pages.
    """
    sra = _sra_or_500()
    try:
        outcome = sra.refresh(
            unitids=req.unitids,
            limit=req.limit,
            profile=req.profile,
        )
        if req.purge:
            removed = sra.pages.purge_expired()
            sra.queries.purge_expired()
            outcome["purged_pages"] = removed
        return _json_response(outcome)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.post("/api/v1/programs/verify")
async def verify_programs(req: VerifyProgramsRequest) -> JSONResponse:
    """Audit the programme catalogue's URLs.

    dns_only: resolve hosts only (no HTTP, no key needed).
    otherwise: live fetch through the configured fetcher (TinyFish recommended).
    """
    sra = _sra_or_500()
    try:
        verdict = sra.verify_programs(limit=req.limit, dns_only=req.dns_only)
        return _json_response(verdict)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


# ------------------------------------------------------------------- seed
@app.post("/api/v1/seed/export")
async def seed_export(req: SeedExportRequest) -> JSONResponse:
    """Export a portable cache bundle (gzipped JSON).

    Includes institutions, facts, deadlines, links, programmes, and page
    validators — but NOT page bodies (they are re-fetched on import).
    """
    sra = _sra_or_500()
    try:
        path = req.path or str(sra.settings.home / "seed.json.gz")
        outcome = sra.seed_export(
            path,
            profiles=req.profiles,
            limit=req.limit,
        )
        return _json_response(outcome, status_code=201)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.post("/api/v1/seed/import")
async def seed_import(path: str) -> JSONResponse:
    """Import a portable cache bundle (gzipped JSON).

    Replays institutions, facts, deadlines, links, programmes, and page
    validators into the SQLite cache. Bodies stay out — they are re-fetched
    with ETag validation on first use.
    """
    sra = _sra_or_500()
    try:
        outcome = sra.seed_import(path)
        return _json_response(outcome, status_code=201)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


# ------------------------------------------------------------------- markdown
@app.get("/api/v1/search/markdown")
async def search_markdown(
    profile: str | None = None,
    q: str | None = None,
    state: str | None = None,
    limit: int = 20,
    detailed: bool = False,
) -> PlainTextResponse:
    """Search results as a markdown document (for review or pasting)."""
    sra = _sra_or_500()
    try:
        report = sra.search(
            profile,
            q=q,
            state=state,
            limit=limit,
        )
        from .search.report import render_report

        return PlainTextResponse(content=render_report(report, detailed=detailed))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.get("/api/v1/schools/{key}/markdown")
async def school_markdown(
    key: str,
    profile: str | None = None,
) -> PlainTextResponse:
    """Single school detail as a markdown document."""
    sra = _sra_or_500()
    try:
        text = sra.render_school(key, profile=profile)
        return PlainTextResponse(content=text)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


# ------------------------------------------------------------------- run
def run(host: str = "0.0.0.0", port: int = 8000, reload: bool = False) -> None:
    """Entry point for the sra-server CLI command."""
    import uvicorn

    uvicorn.run("sra_schools.server:app", host=host, port=port, reload=reload)


if __name__ == "__main__":  # pragma: no cover
    run()
