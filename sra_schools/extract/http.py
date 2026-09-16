"""Low-level HTTP for the module - stdlib only (urllib), optional httpx.

Kept separate from provider semantics so tests can drive the JSON layer with an
in-memory transport.
"""

from __future__ import annotations

import json
import ssl
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from typing import Any

try:  # optional, only used if installed
    import httpx  # type: ignore
except ImportError:  # pragma: no cover
    httpx = None  # type: ignore[assignment]

DEFAULT_UA = "sra-schools/0.1 (+https://github.com/wraithen0/SRA; research tool)"


class HttpError(RuntimeError):
    def __init__(self, message: str, *, status: int | None = None, url: str | None = None,
                 body: str = "") -> None:
        super().__init__(message)
        self.status = status
        self.url = url
        self.body = body[:500]


@dataclass(slots=True)
class HttpResponse:
    url: str
    status: int | None
    headers: dict[str, str] = field(default_factory=dict)
    text: str = ""
    body_bytes: bytes = b""
    error: str | None = None
    elapsed_s: float = 0.0

    def json(self) -> Any:  # noqa: ANN401
        if not self.text:
            return None
        return json.loads(self.text)

    @property
    def ok(self) -> bool:
        return self.status is not None and 200 <= self.status < 400


def _decode(raw: bytes, charset: str | None) -> str:
    for enc in filter(None, (charset, "utf-8", "latin-1")):
        try:
            return raw.decode(enc, "replace" if enc == "latin-1" else "strict")
        except (UnicodeDecodeError, LookupError):
            continue
    return raw.decode("utf-8", "replace")


def request(
    url: str,
    *,
    method: str = "GET",
    params: dict[str, Any] | None = None,
    payload: dict[str, Any] | None = None,
    headers: dict[str, str] | None = None,
    timeout: float = 30.0,
    retries: int = 2,
    backoff: float = 1.5,
) -> HttpResponse:
    """One HTTP call with bounded retries; never raises on 4xx/5xx."""
    if params:
        clean = {k: v for k, v in params.items() if v is not None}
        sep = "&" if urllib.parse.urlparse(url).query else "?"
        url = f"{url}{sep}{urllib.parse.urlencode(clean, doseq=True)}"
    data = None
    req_headers = {"User-Agent": DEFAULT_UA, "Accept": "application/json, text/html;q=0.9, */*;q=0.5"}
    if payload is not None:
        data = json.dumps(payload).encode()
        req_headers["Content-Type"] = "application/json"
    req_headers.update(headers or {})

    last_error = ""
    for attempt in range(retries + 1):
        start = time.monotonic()
        if httpx is not None:
            resp = _via_httpx(url, method, data, req_headers, timeout)
            if resp is not None:
                resp.elapsed_s = time.monotonic() - start
                if resp.status and resp.status >= 500 and attempt < retries:
                    time.sleep(backoff * (attempt + 1))
                    continue
                return resp
        try:
            req = urllib.request.Request(url, data=data, headers=req_headers, method=method)
            ctx = ssl.create_default_context()
            with urllib.request.urlopen(req, timeout=timeout, context=ctx) as raw:  # noqa: S310
                body = raw.read()
                ctype = raw.headers.get("Content-Type", "") or ""
                charset = ctype.split("charset=")[-1].strip() if "charset=" in ctype else None
                return HttpResponse(
                    url=raw.geturl(),
                    status=raw.status,
                    headers={k.lower(): v for k, v in raw.headers.items()},
                    text=_decode(body, charset),
                    body_bytes=body,
                    elapsed_s=time.monotonic() - start,
                )
        except urllib.error.HTTPError as exc:
            body = exc.read() if hasattr(exc, "read") else b""
            resp = HttpResponse(
                url=url,
                status=exc.code,
                headers={k.lower(): v for k, v in (exc.headers or {}).items()},
                text=_decode(body, None),
                body_bytes=body,
                error=f"HTTP {exc.code}",
                elapsed_s=time.monotonic() - start,
            )
            if exc.code in (429, 402) and attempt < retries:
                retry_after = _retry_after(exc.headers)
                time.sleep(max(backoff, retry_after))
                last_error = resp.error or ""
                continue
            return resp
        except (urllib.error.URLError, TimeoutError, OSError, ssl.SSLError) as exc:
            last_error = str(exc)
            if attempt < retries:
                time.sleep(backoff * (attempt + 1))
                continue
        except Exception as exc:  # pragma: no cover - defensive
            last_error = f"{type(exc).__name__}: {exc}"
            if attempt < retries:
                time.sleep(backoff)
                continue
    return HttpResponse(url=url, status=None, error=last_error or "request failed")


def _retry_after(headers: Any) -> float:  # noqa: ANN401
    try:
        return float((headers or {}).get("Retry-After", "0") or 0)
    except (TypeError, ValueError):
        return 0.0


def _via_httpx(url: str, method: str, data: bytes | None, headers: dict[str, str],
               timeout: float) -> HttpResponse | None:
    if httpx is None:  # pragma: no cover
        return None
    try:
        with httpx.Client(timeout=timeout, follow_redirects=True, headers=headers) as client:
            resp = client.request(method, url, content=data)
        return HttpResponse(
            url=str(resp.url),
            status=resp.status_code,
            headers={k.lower(): v for k, v in resp.headers.items()},
            text=resp.text,
            body_bytes=resp.content,
            error=None if resp.is_success else f"HTTP {resp.status_code}",
        )
    except httpx.HTTPError:  # pragma: no cover - fall back to urllib
        return None


def post_json(url: str, payload: dict[str, Any], *, headers: dict[str, str] | None = None,
              timeout: float = 30.0, retries: int = 2) -> Any:  # noqa: ANN401
    resp = request(url, method="POST", payload=payload, headers=headers, timeout=timeout,
                   retries=retries)
    if resp.status is None or resp.status >= 400:
        raise HttpError(resp.error or "request failed", status=resp.status, url=url, body=resp.text)
    try:
        return resp.json()
    except json.JSONDecodeError as exc:
        raise HttpError(f"non-JSON response: {exc}", status=resp.status, url=url, body=resp.text) from exc


def get_json(url: str, params: dict[str, Any] | None = None, *,
             headers: dict[str, str] | None = None, timeout: float = 30.0,
             retries: int = 2) -> Any:  # noqa: ANN401
    resp = request(url, method="GET", params=params, headers=headers, timeout=timeout, retries=retries)
    if resp.status is None or resp.status >= 400:
        raise HttpError(resp.error or "request failed", status=resp.status, url=url, body=resp.text)
    try:
        return resp.json()
    except json.JSONDecodeError as exc:
        raise HttpError(f"non-JSON response: {exc}", status=resp.status, url=url, body=resp.text) from exc
