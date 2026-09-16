"""Cache policy: page cache (raw responses) + query cache (whole searches).

Rules of the house
------------------
* A fresh page is never re-fetched. A due page is revalidated with its stored
  ETag/Last-Modified so the upstream can answer 304 and we re-parse nothing.
* Extraction results are keyed by ``(url, content_sha256, extractor, version)`` so an
  unchanged page never re-runs the rules - and never re-bills an optional LLM.
* Failed fetches are cached briefly (negative caching) so a crawl does not hammer
  a 404 six times across six topics.
* A whole search report is cached by fingerprint of the query + dataset epoch.
"""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from datetime import timedelta
from typing import Any

from .. import util
from ..taxonomy import Freshness
from .database import Database, iso, now_utc, parse_iso

#: seconds an entry stays usable before it must be revalidated
FRESHNESS_TTL: dict[Freshness, int] = {
    Freshness.STATIC: 365 * 86400,
    Freshness.STRUCTURAL: 180 * 86400,
    Freshness.POLICY: 90 * 86400,
    Freshness.DATE_BOUND: 30 * 86400,
    Freshness.VOLATILE: 14 * 86400,
}
NEGATIVE_TTL = 6 * 3600       # don't re-probe a dead URL for 6h
ERROR_TTL = 30 * 60           # transient failure back-off


@dataclass(slots=True)
class CachedPage:
    url: str
    status: int | None
    body: str
    title: str | None
    content_sha256: str | None
    etag: str | None
    last_modified: str | None
    fetched_at: str
    expires_at: str
    from_cache: bool = True
    not_modified: bool = False

    @property
    def age_seconds(self) -> float:
        stamp = parse_iso(self.fetched_at)
        return max(0.0, (now_utc() - stamp).total_seconds()) if stamp else 0.0

    @property
    def fresh(self) -> bool:
        stamp = parse_iso(self.expires_at)
        return bool(stamp and stamp > now_utc())


class PageCache:
    def __init__(self, db: Database) -> None:
        self.db = db

    # -- read path -----------------------------------------------------------
    def get(self, url: str, *, max_age_seconds: int | None = None) -> CachedPage | None:
        row = self.db.one("SELECT * FROM web_pages WHERE url = ?", (url,))
        if row is None:
            return None
        page = self._to_page(row, url)
        if max_age_seconds is not None and page.age_seconds > max_age_seconds:
            return page  # stale copy: caller decides stale-while-revalidate
        return page

    def _to_page(self, row: sqlite3.Row, url: str) -> CachedPage:
        return CachedPage(
            url=url,
            status=row["status"],
            body="" if row["body_gzip"] is None else _decompress(row["body_gzip"]),
            title=row["title"],
            content_sha256=row["content_sha256"],
            etag=row["etag"],
            last_modified=row["last_modified"],
            fetched_at=row["fetched_at"],
            expires_at=row["expires_at"],
        )

    def fresh_for_topic(self, url: str, topic: str | None) -> bool:
        page = self.get(url)
        if page is None or not page.body:
            return False
        return page.fresh

    def is_known_missing(self, url: str) -> bool:
        """True when we probed this URL recently and it was a dead end (404/410)."""
        row = self.db.one(
            "SELECT expires_at, status FROM web_pages WHERE url = ? AND status IN (404, 410)",
            (url,),
        )
        if row is None:
            return False
        stamp = parse_iso(row["expires_at"])
        return bool(stamp and stamp > now_utc())

    # -- write path ----------------------------------------------------------
    def put(
        self,
        url: str,
        *,
        status: int | None,
        body: str = "",
        title: str | None = None,
        etag: str | None = None,
        last_modified: str | None = None,
        final_url: str | None = None,
        content_type: str | None = None,
        topic: str | None = None,
        unitid: int | None = None,
        ttl_seconds: int = FRESHNESS_TTL[Freshness.POLICY],
        error: str | None = None,
    ) -> CachedPage:
        sha = util.sha256_text(body) if body else None
        fetched_at = iso()
        expires_at = iso(now_utc() + timedelta(seconds=max(1, ttl_seconds)))
        with self.db.tx() as cur:
            cur.execute(
                """
                INSERT INTO web_pages(url, url_hash, institution_unitid, topic, final_url, title,
                                      status, error, content_type, etag, last_modified,
                                      content_sha256, body_gzip, body_chars, attempts,
                                      fetched_at, ttl_seconds, expires_at, last_http_status)
                VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                ON CONFLICT(url) DO UPDATE SET
                    url_hash=excluded.url_hash,
                    institution_unitid=COALESCE(excluded.institution_unitid, web_pages.institution_unitid),
                    topic=COALESCE(excluded.topic, web_pages.topic),
                    final_url=COALESCE(excluded.final_url, web_pages.final_url),
                    title=COALESCE(excluded.title, web_pages.title),
                    status=excluded.status,
                    error=excluded.error,
                    content_type=excluded.content_type,
                    etag=COALESCE(excluded.etag, web_pages.etag),
                    last_modified=COALESCE(excluded.last_modified, web_pages.last_modified),
                    content_sha256=COALESCE(excluded.content_sha256, web_pages.content_sha256),
                    body_gzip=COALESCE(excluded.body_gzip, web_pages.body_gzip),
                    body_chars=excluded.body_chars,
                    attempts=web_pages.attempts + 1,
                    fetched_at=excluded.fetched_at,
                    ttl_seconds=excluded.ttl_seconds,
                    expires_at=excluded.expires_at,
                    last_http_status=excluded.last_http_status
                """,
                (
                    url,
                    util.short_hash(url),
                    unitid,
                    topic,
                    final_url,
                    (title or "")[:300] or None,
                    status,
                    (error or "")[:500] or None,
                    content_type,
                    etag,
                    last_modified,
                    sha,
                    _compress(body) if body else None,
                    len(body),
                    1,                      # attempts (incremented by the upsert)
                    fetched_at,
                    ttl_seconds,
                    expires_at,
                    str(status) if status else None,
                ),
            )
        return CachedPage(
            url=url, status=status, body=body, title=title, content_sha256=sha,
            etag=etag, last_modified=last_modified, fetched_at=fetched_at,
            expires_at=expires_at, from_cache=False,
        )

    def touch_validated(self, url: str, ttl_seconds: int) -> None:
        """Upstream said 304: keep the body, push the expiry out."""
        self.db.execute(
            "UPDATE web_pages SET fetched_at = ?, expires_at = ?, ttl_seconds = ? WHERE url = ?",
            (iso(), iso(now_utc() + timedelta(seconds=ttl_seconds)), ttl_seconds, url),
        )

    def note_attempt(self, url: str) -> None:
        self.db.execute("UPDATE web_pages SET attempts = attempts + 1 WHERE url = ?", (url,))

    def validators(self, url: str) -> tuple[str | None, str | None]:
        row = self.db.one("SELECT etag, last_modified FROM web_pages WHERE url = ?", (url,))
        return (row[0], row[1]) if row else (None, None)

    # -- analytics -----------------------------------------------------------
    def stats(self) -> dict[str, Any]:
        total = self.db.count("web_pages")
        fresh = self.db.count("web_pages", "expires_at > ?", (iso(),))
        dead = self.db.count("web_pages", "status >= 400")
        chars = self.db.scalar("SELECT COALESCE(SUM(body_chars), 0) FROM web_pages") or 0
        blobs = self.db.scalar("SELECT COALESCE(SUM(LENGTH(body_gzip)), 0) FROM web_pages") or 0
        return {
            "pages_total": total,
            "pages_fresh": fresh,
            "pages_stale": total - fresh,
            "pages_failed": dead,
            "body_chars": int(chars),
            "stored_bytes": int(blobs),
        }

    def due_urls(self, *, limit: int = 500, unitids: tuple[int, ...] | None = None) -> list[str]:
        sql = "SELECT url FROM web_pages WHERE expires_at <= ?"
        params: list[Any] = [iso()]
        if unitids:
            sql += f" AND institution_unitid IN ({','.join('?' * len(unitids))})"
            params.extend(unitids)
        sql += " ORDER BY expires_at LIMIT ?"
        params.append(limit)
        return [row[0] for row in self.db.query(sql, params)]

    def purge_expired(self, *, grace_days: int = 180) -> int:
        cutoff = iso(now_utc() - timedelta(days=grace_days))
        with self.db.tx() as cur:
            cur.execute("DELETE FROM web_pages WHERE expires_at < ?", (cutoff,))
            return cur.rowcount or 0


# ------------------------------------------------------------------ query cache
class QueryCache:
    def __init__(self, db: Database, *, default_ttl: int = 6 * 3600) -> None:
        self.db = db
        self.default_ttl = default_ttl

    def put(
        self,
        fingerprint: str,
        payload: dict[str, Any],
        *,
        profile: str | None,
        params: dict[str, Any],
        ttl: int | None = None,
    ) -> None:
        seconds = ttl or self.default_ttl
        with self.db.tx() as cur:
            cur.execute(
                """
                INSERT INTO query_cache(fingerprint, profile, params_json, results_json,
                                        result_count, created_at, expires_at, hit_count)
                VALUES(?,?,?,?,?,?,?,0)
                ON CONFLICT(fingerprint) DO UPDATE SET
                    results_json=excluded.results_json,
                    result_count=excluded.result_count,
                    created_at=excluded.created_at,
                    expires_at=excluded.expires_at
                """,
                (
                    fingerprint,
                    profile,
                    util.dumps(params),
                    util.dumps(payload),
                    len(payload.get("results", []) or []),
                    iso(),
                    iso(now_utc() + timedelta(seconds=seconds)),
                ),
            )

    def get(self, fingerprint: str) -> tuple[dict[str, Any] | None, CacheStatus]:
        row = self.db.one("SELECT * FROM query_cache WHERE fingerprint = ?", (fingerprint,))
        if row is None:
            return None, CacheStatus.MISS
        payload = util.loads(row["results_json"], {})
        stamp = parse_iso(row["expires_at"])
        try:
            self.db.execute("UPDATE query_cache SET hit_count = hit_count + 1 WHERE fingerprint = ?",
                            (fingerprint,))
        except Exception:
            pass  # read-only database or concurrency lock contention
        age = (now_utc() - parse_iso(row["created_at"])).total_seconds() if row["created_at"] else None
        if stamp and stamp > now_utc():
            return payload, CacheStatus.FRESH
        return payload, CacheStatus.STALE

    def stats(self) -> dict[str, Any]:
        return {
            "entries": self.db.count("query_cache"),
            "fresh": self.db.count("query_cache", "expires_at > ?", (iso(),)),
            "hits": int(self.db.scalar("SELECT COALESCE(SUM(hit_count),0) FROM query_cache") or 0),
        }

    def purge_expired(self) -> int:
        with self.db.tx() as cur:
            cur.execute("DELETE FROM query_cache WHERE expires_at < ?", (iso(),))
            return cur.rowcount or 0


class CacheStatus:
    MISS = "miss"
    FRESH = "fresh"
    STALE = "stale"


def _compress(text: str) -> bytes:
    import gzip

    return gzip.compress(text.encode("utf-8", "replace"), compresslevel=6)


def _decompress(blob: Any) -> str:  # noqa: ANN401
    import gzip
    import zlib

    if not blob:
        return ""
    try:
        return gzip.decompress(blob).decode("utf-8", "replace")
    except (OSError, zlib.error):
        return bytes(blob).decode("utf-8", "replace")


def json_default(obj: Any) -> Any:  # noqa: ANN401
    if isinstance(obj, (set, tuple)):
        return list(obj)
    if hasattr(obj, "value"):  # Enum
        return obj.value
    return str(obj)


def as_json(payload: dict[str, Any]) -> str:
    return json.dumps(payload, ensure_ascii=False, default=json_default)
