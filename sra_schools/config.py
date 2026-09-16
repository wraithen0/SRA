"""Runtime configuration.

Everything is overridable by environment variable (``SRA_*``). A simple local
``.env`` file is loaded automatically for development, without overriding
variables already provided by the process or deployment environment.
"""

from __future__ import annotations

import dataclasses
import os
from dataclasses import dataclass, field
from pathlib import Path

_PKG_DIR = Path(__file__).resolve().parent
DATA_DIR = _PKG_DIR / "data"
SEED_DIR = DATA_DIR / "seed"
DEFAULT_SCHEMA = _PKG_DIR / "db" / "schema.sql"

OPENAI_BASE_URL = "https://api.openai.com/v1"
OPENAI_DEFAULT_MODEL = "gpt-4o-mini"
GROQ_BASE_URL = "https://api.groq.com/openai/v1"
GROQ_DEFAULT_MODEL = "llama-3.3-70b-versatile"


def _load_dotenv(path: Path) -> None:
    """Load simple ``KEY=VALUE`` pairs without overriding process environment.

    This deliberately supports only the small, predictable subset needed for a
    local ``.env`` file: comments, optional ``export`` prefixes, and quoted or
    unquoted values. It is not a shell-script evaluator.
    """
    try:
        lines = path.read_text("utf-8").splitlines()
    except OSError:
        return
    for raw in lines:
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[7:].lstrip()
        if "=" not in line:
            continue
        key, value = (part.strip() for part in line.split("=", 1))
        if not key or not key.replace("_", "").isalnum():
            continue
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
            value = value[1:-1]
        if value:
            os.environ.setdefault(key, value)


def _load_local_env() -> None:
    """Load an explicit env file, or a local development ``.env`` when present."""
    explicit_path = os.environ.get("SRA_ENV_FILE")
    if explicit_path:
        _load_dotenv(Path(explicit_path).expanduser())
        return
    candidates = (Path.cwd() / ".env", _PKG_DIR.parent / ".env")
    seen: set[Path] = set()
    for path in candidates:
        resolved = path.resolve()
        if resolved not in seen:
            _load_dotenv(resolved)
            seen.add(resolved)


_load_local_env()


def _env(name: str, default: str | None = None) -> str | None:
    val = os.environ.get(f"SRA_{name}")
    return val if val not in (None, "") else default


def _env_int(name: str, default: int) -> int:
    raw = _env(name)
    try:
        return int(raw) if raw is not None else default
    except ValueError:
        return default


def _env_bool(name: str, default: bool = False) -> bool:
    raw = _env(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def default_data_home() -> Path:
    """Cache location: $SRA_HOME > $XDG_CACHE_HOME/sra-schools > ~/.cache/..."""
    override = _env("HOME")
    if override:
        return Path(override).expanduser()
    xdg = os.environ.get("XDG_CACHE_HOME")
    base = Path(xdg).expanduser() if xdg else Path.home() / ".cache"
    return base / "sra-schools"


@dataclass(frozen=True)
class TinyFishSettings:
    """TinyFish Search + Fetch are free at any balance (including $0).

    * Search: ``GET https://api.search.tinyfish.ai?query=...``
    * Fetch:  ``POST https://api.fetch.tinyfish.ai {"urls": [...]}``
    Both take ``X-API-Key``.
    """

    api_key: str | None = None
    search_url: str = "https://api.search.tinyfish.ai"
    fetch_url: str = "https://api.fetch.tinyfish.ai"
    timeout_s: int = 30
    max_fetch_urls: int = 10
    retry_attempts: int = 3
    backoff_s: float = 1.5
    user_agent: str = "sra-schools/0.1 (+https://github.com/wraithen0/SRA)"

    @property
    def enabled(self) -> bool:
        return bool(self.api_key)

    @staticmethod
    def from_env() -> TinyFishSettings:
        key = _env("TINYFISH_API_KEY") or os.environ.get("TINYFISH_API_KEY")
        return TinyFishSettings(
            api_key=key,
            search_url=_env("SEARCH_URL", "https://api.search.tinyfish.ai") or "",
            fetch_url=_env("FETCH_URL", "https://api.fetch.tinyfish.ai") or "",
            timeout_s=_env_int("HTTP_TIMEOUT", 30),
            retry_attempts=_env_int("RETRY_ATTEMPTS", 3),
        )


@dataclass(frozen=True)
class LlmSettings:
    """Optional OpenAI-compatible extractor, including Groq, used only when rules under-fire."""

    api_key: str | None = None
    base_url: str = OPENAI_BASE_URL
    model: str = OPENAI_DEFAULT_MODEL
    max_tokens: int = 1200
    timeout_s: int = 60

    @property
    def enabled(self) -> bool:
        return bool(self.api_key)

    @staticmethod
    def from_env() -> LlmSettings:
        """Read an explicit OpenAI-compatible configuration or auto-configure Groq.

        ``SRA_LLM_API_KEY`` remains the highest-priority generic provider setting.
        When it is absent, a Groq key selects Groq's OpenAI-compatible endpoint and
        model defaults; ``SRA_LLM_BASE_URL`` and ``SRA_LLM_MODEL`` always override
        those defaults.
        """
        explicit_key = _env("LLM_API_KEY")
        groq_key = _env("GROQ_API_KEY") or os.environ.get("GROQ_API_KEY")
        openai_key = os.environ.get("OPENAI_API_KEY")
        use_groq = not explicit_key and bool(groq_key)
        return LlmSettings(
            api_key=explicit_key or groq_key or openai_key,
            base_url=_env("LLM_BASE_URL", GROQ_BASE_URL if use_groq else OPENAI_BASE_URL) or "",
            model=_env("LLM_MODEL", GROQ_DEFAULT_MODEL if use_groq else OPENAI_DEFAULT_MODEL) or "",
        )


@dataclass(frozen=True)
class Settings:
    """Aggregate settings object handed to :class:`~sra_schools.api.SRA`."""

    home: Path = field(default_factory=default_data_home)
    db_path: Path | None = None
    seed_dir: Path = field(default_factory=lambda: SEED_DIR)
    # --- crawling budget / politeness -----------------------------------------
    max_pages_per_run: int = 200
    max_new_pages_per_institution: int = 6
    request_delay_s: float = 0.35
    fetch_ttl_floor_s: int = 3600
    # --- caching -------------------------------------------------------------
    search_cache_ttl_s: int = 6 * 3600
    allow_stale: bool = True
    # --- providers ------------------------------------------------------------
    offline: bool = False
    use_llm: bool = False

    tinyfish: TinyFishSettings = field(default_factory=TinyFishSettings.from_env)
    llm: LlmSettings = field(default_factory=LlmSettings.from_env)

    @staticmethod
    def from_env(**overrides) -> Settings:
        base = Settings(tinyfish=TinyFishSettings.from_env(), llm=LlmSettings.from_env())
        patch: dict[str, object] = {
            "max_pages_per_run": _env_int("MAX_PAGES", base.max_pages_per_run),
            "request_delay_s": float(_env("REQUEST_DELAY", str(base.request_delay_s))),
            "search_cache_ttl_s": _env_int("SEARCH_CACHE_TTL", base.search_cache_ttl_s),
            "offline": _env_bool("OFFLINE", base.offline),
            "use_llm": _env_bool("USE_LLM", base.use_llm),
            "allow_stale": _env_bool("ALLOW_STALE", base.allow_stale),
        }
        return replace_settings(dataclasses.replace(base, **patch), **overrides)

    @property
    def resolved_db_path(self) -> Path:
        return self.db_path or (self.home / "sra.sqlite")

    @property
    def network_enabled(self) -> bool:
        """May we make any HTTP request at all (direct fetcher included)?"""
        return not self.offline

    @property
    def live_enabled(self) -> bool:
        """May we use the TinyFish APIs? Needs a key; implies network."""
        return not self.offline and self.tinyfish.enabled

    def describe(self) -> dict[str, object]:
        return {
            "home": str(self.home),
            "db_path": str(self.resolved_db_path),
            "live": self.live_enabled,
            "offline": self.offline,
            "tinyfish_key": bool(self.tinyfish.enabled),
            "llm": self.llm.enabled and self.use_llm,
            "max_pages_per_run": self.max_pages_per_run,
            "search_cache_ttl_s": self.search_cache_ttl_s,
        }


def replace_settings(s: Settings, **overrides) -> Settings:
    """``dataclasses.replace`` that ignores ``None`` overrides and coerces paths."""
    clean: dict[str, object] = {}
    for key, val in overrides.items():
        if val is None:
            continue
        clean[key] = Path(val).expanduser() if key in {"home", "db_path", "seed_dir"} else val
    return dataclasses.replace(s, **clean) if clean else s
