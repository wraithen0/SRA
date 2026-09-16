"""Page fetchers.

Two interchangeable transports, same contract:

* :class:`TinyFishFetcher` - ``POST https://api.fetch.tinyfish.ai`` (free at any
  balance, renders JavaScript, returns markdown + outbound links + validators).
* :class:`DirectFetcher` - stdlib urllib for plain HTML pages; used when no API key
  is configured so the module still works in a bare backend container.

Both are *dumb*: freshness/cache policy lives in
:class:`~sra_schools.db.cache.PageCache`, not here.
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Any, Protocol

from ..config import TinyFishSettings
from ..util import norm_url
from . import http


@dataclass(slots=True)
class PageResult:
    url: str
    status: int | None = None
    text: str = ""
    title: str | None = None
    final_url: str | None = None
    content_type: str | None = None
    etag: str | None = None
    last_modified: str | None = None
    error: str | None = None
    not_modified: bool = False
    #: (anchor, absolute url) pairs the fetcher discovered
    links: list[tuple[str, str]] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return self.status == 200 and bool(self.text) and not self.error

    @property
    def chars(self) -> int:
        return len(self.text)


class Fetcher(Protocol):
    name: str

    def fetch(
        self,
        urls: Sequence[str],
        *,
        ttl_seconds: int | None = None,
        purpose: str | None = None,
        validators: dict[str, tuple[str | None, str | None]] | None = None,
    ) -> list[PageResult]:
        ...


class TinyFishFetcher:
    """TinyFish Fetch API. Up to 10 URLs per request, all processed in parallel."""

    name = "tinyfish-fetch"

    def __init__(self, settings: TinyFishSettings | None = None, *, max_urls: int = 10) -> None:
        self.settings = settings or TinyFishSettings.from_env()
        self.max_urls = max_urls
        if not self.settings.api_key:
            raise RuntimeError("TinyFishFetcher needs TINYFISH_API_KEY")

    # -- internals -----------------------------------------------------------
    def _headers(self) -> dict[str, str]:
        return {
            "X-API-Key": self.settings.api_key or "",
            "Content-Type": "application/json",
            "User-Agent": self.settings.user_agent,
        }

    def _one(self, urls: Sequence[str], ttl_seconds: int | None, purpose: str | None,
             validators: dict[str, tuple[str | None, str | None]] | None) -> list[PageResult]:
        body: dict[str, Any] = {
            "urls": list(urls),
            "format": "markdown",
            "links": True,
            "image_links": False,
            "page_metadata": False,
            "include_etag_and_last_modified": True,
        }
        if purpose:
            body["purpose"] = purpose[:2000]
        if ttl_seconds is not None:
            body["ttl"] = int(ttl_seconds)
        if validators and len(urls) == 1:
            etag, last_modified = validators.get(urls[0], (None, None))
            if etag:
                body["if_none_match"] = etag
            elif last_modified:
                body["if_modified_since"] = last_modified
        try:
            payload = http.post_json(self.settings.fetch_url, body, headers=self._headers(),
                                     timeout=self.settings.timeout_s,
                                     retries=self.settings.retry_attempts - 1)
        except http.HttpError as exc:
            return [PageResult(url=u, status=exc.status, error=str(exc)) for u in urls]
        return _parse_fetch_payload(payload, urls)

    # -- public --------------------------------------------------------------
    def fetch(
        self,
        urls: Sequence[str],
        *,
        ttl_seconds: int | None = None,
        purpose: str | None = None,
        validators: dict[str, tuple[str | None, str | None]] | None = None,
    ) -> list[PageResult]:
        out: list[PageResult] = []
        cleaned = [u for u in urls if u]
        for i in range(0, len(cleaned), self.max_urls):
            out.extend(self._one(cleaned[i : i + self.max_urls], ttl_seconds, purpose, validators))
        return out


def _parse_fetch_payload(payload: dict[str, Any], requested: Sequence[str]) -> list[PageResult]:
    results: list[PageResult] = []
    seen: set[str] = set()
    for item in payload.get("results", []) or []:
        url = norm_url(item.get("url") or item.get("final_url") or "") or ""
        links = [
            (str(link.get("text") or link.get("title") or ""), str(link.get("url") or link.get("href") or ""))
            for link in (item.get("links") or [])
            if isinstance(link, dict)
        ]
        results.append(
            PageResult(
                url=url,
                status=200 if not item.get("not_modified") else 304,
                text=str(item.get("text") or ""),
                title=item.get("title"),
                final_url=item.get("final_url"),
                content_type=item.get("content_type"),
                etag=item.get("etag"),
                last_modified=item.get("last_modified"),
                not_modified=bool(item.get("not_modified")),
                links=[(a, u) for a, u in links if u],
            )
        )
        seen.add(url)
    for err in payload.get("errors", []) or []:
        url = norm_url(err.get("url") if isinstance(err, dict) else str(err)) or ""
        if url in seen:
            continue
        results.append(
            PageResult(
                url=url,
                status=err.get("status") if isinstance(err, dict) else None,
                error=(err.get("error") or err.get("code") or "fetch failed")
                if isinstance(err, dict) else str(err),
            )
        )
        seen.add(url)
    missing = [u for u in requested if norm_url(u) not in seen]
    results.extend(PageResult(url=norm_url(u) or u, error="no result returned") for u in missing)
    return results


class DirectFetcher:
    """Plain HTTP GET + HTML->text. No JS rendering, no bot-wall survival."""

    name = "direct-http"

    def __init__(self, *, timeout: float = 25.0, retries: int = 1, user_agent: str = http.DEFAULT_UA,
                 max_bytes: int = 1_500_000) -> None:
        self.timeout = timeout
        self.retries = retries
        self.user_agent = user_agent
        self.max_bytes = max_bytes

    def fetch(
        self,
        urls: Sequence[str],
        *,
        ttl_seconds: int | None = None,
        purpose: str | None = None,
        validators: dict[str, tuple[str | None, str | None]] | None = None,
    ) -> list[PageResult]:
        results: list[PageResult] = []
        for url in urls:
            headers = {"User-Agent": self.user_agent, "Accept": "text/html,application/xhtml+xml"}
            etag, last_modified = (validators or {}).get(url, (None, None))
            if etag:
                headers["If-None-Match"] = etag
            elif last_modified:
                headers["If-Modified-Since"] = last_modified
            resp = http.request(url, headers=headers, timeout=self.timeout, retries=self.retries)
            if resp.status == 304:
                results.append(PageResult(url=url, status=304, not_modified=True,
                                          etag=etag, last_modified=last_modified))
                continue
            ctype = (resp.headers or {}).get("content-type", "")
            text = resp.text
            if "pdf" in ctype.lower() or "zip" in ctype.lower():
                results.append(PageResult(url=norm_url(url) or url, status=resp.status,
                                          error=f"unsupported content-type {ctype}"))
                continue
            if len(text) > self.max_bytes:
                text = text[: self.max_bytes]
            from ..util import looks_like_html, strip_html

            body = strip_html(text) if looks_like_html(text) else text
            results.append(
                PageResult(
                    url=norm_url(resp.url or url) or url,
                    status=resp.status,
                    text=body,
                    title=_title_from_html(text),
                    final_url=norm_url(resp.url) if resp.url else None,
                    content_type=ctype or None,
                    etag=(resp.headers or {}).get("etag"),
                    last_modified=(resp.headers or {}).get("last-modified"),
                    error=resp.error,
                    links=html_links(text, base=resp.url or url) if looks_like_html(text) else [],
                )
            )
        return results


def _title_from_html(html: str) -> str | None:
    import re
    from html import unescape

    from ..util import normalize_space

    match = re.search(r"(?is)<title[^>]*>(.*?)</title>", html or "")
    if not match:
        return None
    return normalize_space(unescape(match.group(1)))[:300] or None


_ANCHOR_RE = re.compile(r"(?is)<a\b([^>]*)>(.*?)(?:</a>|$)")
_HREF_RE = re.compile(r"""(?i)\bhref\s*=\s*(?:"([^"]*)"|'([^']*)'|([^\s"'>]+))""")


def html_links(html: str, *, base: str, limit: int = 300) -> list[tuple[str, str]]:
    """``[(anchor text, absolute url)]`` from raw HTML.

    Markdown extraction cannot be reused here: by the time the tags are stripped the
    hrefs are gone, and the homepage harvest depends on them.
    """
    from ..util import abs_url, normalize_space, strip_html

    out: list[tuple[str, str]] = []
    seen: set[str] = set()
    for attrs, inner in _ANCHOR_RE.findall(html or ""):
        href_match = _HREF_RE.search(attrs)
        if not href_match:
            continue
        href = next((g for g in href_match.groups() if g), "").strip()
        absolute = abs_url(base, href)
        if not absolute or absolute in seen:
            continue
        if not absolute.startswith("http"):
            continue
        seen.add(absolute)
        anchor = normalize_space(strip_html(inner))[:200]
        out.append((anchor, absolute))
        if len(out) >= limit:
            break
    return out


class OfflineFetcher:
    name = "offline"

    def fetch(self, urls: Sequence[str], **_: Any) -> list[PageResult]:  # noqa: ANN401
        return [PageResult(url=u, error="offline: no fetcher configured") for u in urls]


def make_fetcher(settings: TinyFishSettings | None = None, *, offline: bool = False) -> Fetcher:
    """TinyFish when a key exists, direct HTTP when not, nothing when offline."""
    cfg = settings or TinyFishSettings.from_env()
    if offline:
        return OfflineFetcher()
    if cfg.enabled:
        try:
            return TinyFishFetcher(cfg)
        except RuntimeError:
            pass
    return DirectFetcher(user_agent=cfg.user_agent)
