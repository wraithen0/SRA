"""Web search client (TinyFish Search API - free at any balance).

Used only as the *last* resort in discovery: after campus URL guesses and
on-page link classification have failed to answer a required topic, the pipeline
issues one bounded, domain-scoped query per unanswered topic.
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any, Protocol

from ..config import TinyFishSettings
from ..util import domain_of, norm_url
from . import http


@dataclass(slots=True)
class SearchHit:
    url: str
    title: str = ""
    snippet: str = ""
    site_name: str = ""
    position: int = 0

    @property
    def domain(self) -> str:
        return domain_of(self.url)

    def to_dict(self) -> dict[str, Any]:
        return {
            "url": self.url,
            "title": self.title,
            "snippet": self.snippet,
            "site": self.site_name,
            "position": self.position,
        }


class Searcher(Protocol):
    name: str

    def search(self, query: str, *, purpose: str | None = None,
               include_domains: Sequence[str] | None = None, num: int = 10) -> list[SearchHit]:
        ...


class TinyFishSearcher:
    """``GET https://api.search.tinyfish.ai`` with ``X-API-Key``."""

    name = "tinyfish-search"

    def __init__(self, settings: TinyFishSettings | None = None) -> None:
        self.settings = settings or TinyFishSettings.from_env()
        if not self.settings.api_key:
            raise RuntimeError("TinyFishSearcher needs TINYFISH_API_KEY")

    def search(self, query: str, *, purpose: str | None = None,
               include_domains: Sequence[str] | None = None, num: int = 10) -> list[SearchHit]:
        params: dict[str, Any] = {"query": query, "page": 0}
        if purpose:
            params["purpose"] = purpose[:2000]
        if include_domains:
            params["include_domains"] = ",".join(include_domains)
        try:
            payload = http.get_json(
                self.settings.search_url,
                params,
                headers={"X-API-Key": self.settings.api_key or "",
                         "User-Agent": self.settings.user_agent},
                timeout=self.settings.timeout_s,
                retries=max(0, self.settings.retry_attempts - 1),
            )
        except http.HttpError:
            return []
        hits = _parse_search_payload(payload)
        return hits[: max(1, num)]


def _parse_search_payload(payload: Any) -> list[SearchHit]:  # noqa: ANN401
    if isinstance(payload, list):
        items = payload
    elif isinstance(payload, dict):
        items = payload.get("results") or payload.get("data") or payload.get("organic") or []
    else:
        items = []
    out: list[SearchHit] = []
    for idx, item in enumerate(items):
        if not isinstance(item, dict):
            continue
        url = norm_url(item.get("url") or item.get("link") or item.get("display_url") or "")
        if not url:
            continue
        out.append(
            SearchHit(
                url=url,
                title=str(item.get("title") or "")[:300],
                snippet=re.sub(r"\s+", " ", str(item.get("snippet") or item.get("description") or ""))[:600],
                site_name=str(item.get("site_name") or domain_of(url))[:120],
                position=int(item.get("position") or idx + 1),
            )
        )
    return out


class NullSearcher:
    name = "none"

    def search(self, query: str, **_: Any) -> list[SearchHit]:  # noqa: ANN401, ARG002
        return []


def make_searcher(settings: TinyFishSettings | None = None, *, offline: bool = False) -> Searcher:
    cfg = settings or TinyFishSettings.from_env()
    if offline or not cfg.enabled:
        return NullSearcher()
    try:
        return TinyFishSearcher(cfg)
    except RuntimeError:
        return NullSearcher()
