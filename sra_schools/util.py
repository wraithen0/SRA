"""Pure helpers: text, urls, dates, hashing. No I/O, fully unit-testable."""

from __future__ import annotations

import hashlib
import json
import re
import time
import unicodedata
from collections.abc import Callable, Iterable, Sequence
from datetime import date, datetime, timedelta, timezone
from html import unescape
from typing import Any
from urllib.parse import urldefrag, urljoin, urlparse, urlunparse

MONTHS = {
    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
    "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12,
}
MONTH_RE = (
    r"jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|jun(?:e)?|jul(?:y)?|"
    r"aug(?:ust)?|sep(?:t(?:ember)?)?|sept|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?"
)
_FALLBACK = date(2000, 1, 1)


# --------------------------------------------------------------------------- text
_WS_RE = re.compile(r"[ \t\f\v]+")
_NL_RE = re.compile(r"\n{3,}")


def collapse_ws(text: str) -> str:
    text = _WS_RE.sub(" ", text)
    return _NL_RE.sub("\n\n", text).strip()


def normalize_space(text: str) -> str:
    return " ".join(text.split())


def slugify(text: str, maxlen: int = 60) -> str:
    raw = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    slug = re.sub(r"[^a-z0-9]+", "-", raw.lower()).strip("-")
    return slug[:maxlen]


def strip_html(html: str) -> str:
    """Cheap HTML -> text. TinyFish already returns markdown, this is the fallback."""
    html = re.sub(r"(?is)<(script|style|noscript|svg|head)[^>]*>.*?</\1>", " ", html)
    html = re.sub(r"(?i)<br\s*/?>|</p>|</div>|</li>|</h[1-6]>|</tr>", "\n", html)
    text = re.sub(r"(?s)<[^>]+>", " ", html)
    return collapse_ws(unescape(text))


def looks_like_html(text: str) -> bool:
    head = (text or "")[:400].lstrip().lower()
    return head.startswith(("<!doctype", "<html", "<head", "<?xml"))


def iso(dt: datetime | None = None) -> str:
    return (dt or utcnow()).astimezone(timezone.utc).replace(microsecond=0).isoformat()


def parse_iso(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def truncate(text: str, limit: int = 300) -> str:
    text = text.strip()
    if len(text) <= limit:
        return text
    cut = text[:limit]
    stop = max(cut.rfind(". "), cut.rfind("; "), cut.rfind(", "))
    if stop > limit // 2:
        cut = cut[: stop + 1]
    return cut.rstrip() + "…"


def clean_snippet(text: str, width: int = 260) -> str:
    """Whitespace-normalised, length-bounded quote of page text."""
    return truncate(normalize_space(text), width)


def keyword_snippets(
    text: str,
    keywords: Sequence[str],
    *,
    window: int = 150,
    max_hits: int = 3,
    require_all: bool = False,
) -> list[str]:
    """Verbatim windows around each keyword. This is the evidence we store."""
    lowered = text.lower()
    hits: list[str] = []
    for kw in keywords:
        idx = lowered.find(kw.lower())
        if idx < 0:
            if require_all:
                return []
            continue
        start = max(0, idx - window)
        stop = min(len(text), idx + len(kw) + window)
        hits.append(clean_snippet(text[start:stop]))
        if len(hits) >= max_hits:
            break
    return hits


def first_keyword(text: str, keywords: Iterable[str]) -> str | None:
    lowered = text.lower()
    for kw in keywords:
        if kw.lower() in lowered:
            return kw
    return None


# --------------------------------------------------------------------------- urls
def norm_url(url: str | None) -> str | None:
    """Canonical form used as a cache key: scheme+host(lower)+path, no trailing slash."""
    if not url:
        return None
    url = url.strip()
    if not re.match(r"^https?://", url, re.I):
        url = "https://" + url.lstrip("/")
    try:
        parsed = urlparse(urldefrag(url)[0])
    except ValueError:
        return url
    host = (parsed.hostname or "").lower()
    if host.startswith("www."):
        host = host[4:]
    path = re.sub(r"/{2,}", "/", parsed.path or "")
    if path.endswith("/") and path != "/":
        path = path[:-1]
    netloc = host + (f":{parsed.port}" if parsed.port and parsed.port not in (80, 443) else "")
    return urlunparse((parsed.scheme.lower() or "https", netloc, path, "", parsed.query, ""))


def abs_url(base: str, href: str | None) -> str | None:
    if not href:
        return None
    href = href.strip()
    if href.startswith(("mailto:", "tel:", "javascript:", "data:")):
        return None
    joined = urljoin(base, href)
    return norm_url(joined)


def domain_of(url: str | None, *, strip_www: bool = True) -> str:
    if not url:
        return ""
    try:
        host = (urlparse(url if "//" in url else f"//{url}").hostname or "").lower()
    except ValueError:
        return ""
    return host[4:] if strip_www and host.startswith("www.") else host


def is_same_site(page_url: str, site_url: str) -> bool:
    page_host, site_host = domain_of(page_url), domain_of(site_url)
    if not page_host or not site_host:
        return False
    return page_host == site_host or page_host.endswith("." + site_host)


MD_LINK_RE = re.compile(r"!?\[([^\]]{0,300})\]\((<?[^)\s>]+>?(?:\s+\"[^\"]*\")?)\)")


def extract_links(markdown: str) -> list[tuple[str, str]]:
    """Return [(anchor_text, url)] from markdown-ish text."""
    out: list[tuple[str, str]] = []
    for match in MD_LINK_RE.finditer(markdown):
        raw = match.group(2).strip().strip("<>")
        raw = raw.split(" ")[0]
        if raw.startswith(("http://", "https://", "/", ".")):
            out.append((normalize_space(match.group(1)), raw))
    return out


# --------------------------------------------------------------------------- dates
_DATE_PATTERNS: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(rf"\b({MONTH_RE})\.?\s+(\d{{1,2}})(?:st|nd|rd|th)?(?:,?\s*(\d{{4}}))?\b", re.I), "md"),
    (re.compile(rf"\b(\d{{1,2}})(?:st|nd|rd|th)?\s+({MONTH_RE})\.?(?:,?\s*(\d{{4}}))?\b", re.I), "dm"),
    (re.compile(r"\b(\d{1,2})[/-](\d{1,2})[/-](\d{2,4})\b"), "us"),
    (re.compile(r"\b(\d{4})-(\d{2})-(\d{2})\b"), "iso"),
    (re.compile(rf"\b({MONTH_RE})\.?\s+(\d{{4}})\b", re.I), "my"),
)


def _month_num(token: str) -> int | None:
    token = token.lower().rstrip(".")
    if token.startswith("sept"):
        return 9
    return MONTHS.get(token[:3])


def resolve_month_day(month: int, day: int, ref: date, *, horizon_days: int = 430) -> date | None:
    """Turn a bare "November 1" into the most plausible upcoming deadline."""
    for year in (ref.year - 1, ref.year, ref.year + 1, ref.year + 2):
        try:
            candidate = date(year, month, day)
        except ValueError:
            return None  # e.g. Feb 30
        delta = (candidate - ref).days
        if -45 <= delta <= horizon_days:
            return candidate
    return None


def parse_date_fragments(text: str, *, ref: date | None = None) -> list[tuple[str, date | None]]:
    """All (verbatim, resolved-date-or-None) pairs in a blob of page text."""
    ref = ref or date.today()
    found: list[tuple[str, date | None]] = []
    for pattern, kind in _DATE_PATTERNS:
        for m in pattern.finditer(text):
            g = m.groups()
            resolved: date | None = None
            try:
                if kind == "md":
                    month = _month_num(g[0])
                    day = int(g[1])
                    year = int(g[2]) if g[2] else None
                    if month:
                        resolved = date(year, month, day) if year else resolve_month_day(month, day, ref)
                elif kind == "dm":
                    month = _month_num(g[1])
                    day = int(g[0])
                    year = int(g[2]) if g[2] else None
                    if month:
                        resolved = date(year, month, day) if year else resolve_month_day(month, day, ref)
                elif kind == "us":
                    month, day, year = int(g[0]), int(g[1]), int(g[2])
                    year += 2000 if year < 100 else 0
                    resolved = date(year, month, day)
                elif kind == "iso":
                    resolved = date(int(g[0]), int(g[1]), int(g[2]))
                elif kind == "my":
                    month = _month_num(g[0])
                    if month:
                        resolved = date(int(g[1]), month, 1)
            except ValueError:
                resolved = None
            if resolved and resolved < date(2015, 1, 1):
                resolved = None
            found.append((normalize_space(m.group(0)), resolved))
    seen: set[str] = set()
    unique = []
    for verbatim, resolved in found:
        key = (verbatim + str(resolved)).lower()
        if key not in seen:
            seen.add(key)
            unique.append((verbatim, resolved))
    return unique


def iso_or_none(value: date | None) -> str | None:
    return value.isoformat() if value else None


def is_past(value: str | date | None, *, ref: date | None = None) -> bool:
    if isinstance(value, str):
        try:
            value = date.fromisoformat(value[:10])
        except ValueError:
            return False
    if not value:
        return False
    return value < (ref or date.today())


def academic_year_for(day: date | None = None) -> int:
    """FAFSA cycle label: Sep 2026 -> 2027 aid year."""
    day = day or date.today()
    return day.year + 1 if day.month >= 7 else day.year


# --------------------------------------------------------------------------- numbers
_MONEY_RE = re.compile(r"\$\s?(\d{1,3}(?:,\d{3})+(?:\.\d{2})?|\d+(?:\.\d{2})?)")


def parse_money(text: str | None) -> float | None:
    if text is None:
        return None
    match = _MONEY_RE.search(str(text))
    if not match:
        return None
    try:
        return float(match.group(1).replace(",", ""))
    except ValueError:
        return None


def to_float(value: object) -> float | None:
    """Scorecard-style tolerant number parsing ('35.2', 'NA', 'privacy-suppressed', '')."""
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).strip().replace(",", "").replace("$", "")
    if not text or text.startswith(("- ", "NA", "Privacy", "null", "Not available", "?")):
        return None
    try:
        return float(text)
    except ValueError:
        return None


def to_int(value: object) -> int | None:
    num = to_float(value)
    return None if num is None else int(round(num))


def to_bool(value: object) -> bool | None:
    if value is None or value == "":
        return None
    if isinstance(value, bool):
        return value
    text = str(value).strip().lower()
    if text in {"1", "true", "yes", "y"}:
        return True
    if text in {"0", "false", "no", "n"}:
        return False
    return None


def pct(value: float | None) -> str:
    return "-" if value is None else f"{value * 100:.1f}%" if value <= 1 else f"{value:.1f}%"


def usd(value: float | None) -> str:
    return "-" if value is None else f"${value:,.0f}"


# --------------------------------------------------------------------------- hashing
def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8", "replace")).hexdigest()


def short_hash(text: str, size: int = 16) -> str:
    return hashlib.sha256(text.encode("utf-8", "replace")).hexdigest()[:size]


def fingerprint(payload: object) -> str:
    """Stable hash for cache keys (dict order independent)."""
    blob = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(blob.encode()).hexdigest()


def dumps(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, default=str, separators=(",", ":"))


_UNSET = object()


def loads(value: str | None, default: Any = _UNSET) -> Any:  # noqa: ANN401
    """Decode JSON, returning ``default`` (empty list unless given) on failure.

    Pass ``default=None`` explicitly when an absent payload must stay absent.
    """
    fallback = [] if default is _UNSET else default
    if not value:
        return fallback
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return fallback


# --------------------------------------------------------------------------- misc
def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def chunks(items: Sequence[Any], size: int) -> Iterable[list[Any]]:
    for i in range(0, len(items), size):
        yield list(items[i : i + size])


def call_with_retry(
    fn: Callable[[], Any],  # noqa: ANN401
    *,
    attempts: int = 3,
    backoff: float = 1.5,
    sleep: Callable[[float], None] = time.sleep,
    retry_on: tuple[type[BaseException], ...] = (Exception,),
    on_error: Callable[[int, BaseException], None] | None = None,
) -> Any:  # noqa: ANN401
    last: BaseException | None = None
    for attempt in range(1, max(1, attempts) + 1):
        try:
            return fn()
        except retry_on as exc:  # pragma: no cover - network paths tested live
            last = exc
            if on_error:
                on_error(attempt, exc)
            if attempt >= attempts:
                break
            sleep(backoff * (2 ** (attempt - 1)))
    assert last is not None
    raise last
