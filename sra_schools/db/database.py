"""SQLite access layer: connection handling, migrations, typed row helpers."""

from __future__ import annotations

import gzip
import json
import sqlite3
import threading
import zlib
from collections.abc import Iterable, Iterator, Sequence
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

SCHEMA_PATH = Path(__file__).resolve().parent / "schema.sql"
SCHEMA_VERSION = "2"
_MIN_SCHEMA = 4096
_COMPRESS_THRESHOLD = 1500  # bytes; below this gzip usually loses to raw


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def iso(dt: datetime | None = None) -> str:
    return (dt or now_utc()).astimezone(timezone.utc).replace(microsecond=0).isoformat()


def parse_iso(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def compress(text: str) -> bytes:
    return gzip.compress(text.encode("utf-8"), compresslevel=6)


def decompress(blob: bytes | None) -> str:
    if not blob:
        return ""
    try:
        return gzip.decompress(blob).decode("utf-8", "replace")
    except (OSError, zlib.error):
        # tolerate rows written uncompressed by hand/migrations
        return bytes(blob).decode("utf-8", "replace")


class Database:
    """Thin, long-lived SQLite handle. Safe for a thread-per-request backend."""

    def __init__(self, path: Path | str, *, read_only: bool = False) -> None:
        self.path = Path(path).expanduser()
        self.read_only = read_only
        if self.path != Path(":memory:"):
            self.path.parent.mkdir(parents=True, exist_ok=True)
        uri = f"file:{self.path.as_posix()}?mode=ro" if read_only and self.path != Path(":memory:") else None
        self._conn = sqlite3.connect(
            uri or str(self.path),
            timeout=30.0,
            isolation_level=None,
            check_same_thread=False,
            uri=bool(uri),
        )
        self._conn.row_factory = sqlite3.Row
        # One connection shared across threads (check_same_thread=False) needs a
        # serializer; SQLite connections are not safe for concurrent statements.
        self._lock = threading.RLock()
        self._configure()

    # -- setup ---------------------------------------------------------------
    def _configure(self) -> None:
        cur = self._conn.cursor()
        cur.execute("PRAGMA foreign_keys = ON")
        cur.execute("PRAGMA busy_timeout = 30000")
        if not self.read_only:
            cur.execute("PRAGMA journal_mode = WAL")
            cur.execute("PRAGMA synchronous = NORMAL")
        cur.execute("PRAGMA temp_store = MEMORY")
        cur.execute("PRAGMA cache_size = -32000")
        cur.close()

    def migrate(self) -> None:
        """Apply schema.sql idempotently, add any columns newer builds need, stamp version.

        ``executescript`` issues an implicit COMMIT around itself, so it must not
        be wrapped in our own transaction.
        """
        ddl = SCHEMA_PATH.read_text("utf-8")
        with self._lock:
            self._conn.executescript(ddl)
            for table, adds in _ADDED_COLUMNS.items():
                existing = {row[1] for row in
                            self._conn.execute(f"PRAGMA table_info({table})").fetchall()}
                for column, decl in adds:
                    if column not in existing:
                        self._conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {decl}")
        self.set_meta("schema_version", SCHEMA_VERSION)

    def init_memory(self) -> None:  # pragma: no cover - convenience for tests
        self.migrate()

    # -- primitives ----------------------------------------------------------
    @contextmanager
    def tx(self) -> Iterator[sqlite3.Cursor]:
        """Explicit transaction; nested ``tx()`` calls are serialised, not shared.

        Do not issue statements through :meth:`execute` while a ``tx()`` cursor is
        open from another thread -- take the cursor passed to the block instead.
        """
        with self._lock:
            cur = self._conn.cursor()
            try:
                cur.execute("BEGIN IMMEDIATE")
                yield cur
                self.commit_safe(cur)
            except BaseException:
                try:
                    cur.execute("ROLLBACK")
                except sqlite3.Error:
                    pass
                raise
            finally:
                cur.close()

    def commit_safe(self, cur: sqlite3.Cursor) -> None:
        """COMMIT, tolerating statements that ended the transaction themselves."""
        try:
            cur.execute("COMMIT")
        except sqlite3.OperationalError as exc:
            if "no transaction is active" not in str(exc):
                raise

    def execute(self, sql: str, params: Sequence[Any] = ()) -> sqlite3.Cursor:
        with self._lock:
            return self._conn.execute(sql, params)

    def executemany(self, sql: str, seq: Iterable[Sequence[Any]]) -> None:
        with self._lock:
            self._conn.executemany(sql, list(seq))

    def query(self, sql: str, params: Sequence[Any] = ()) -> list[sqlite3.Row]:
        with self._lock:
            return self._conn.execute(sql, params).fetchall()

    def one(self, sql: str, params: Sequence[Any] = ()) -> sqlite3.Row | None:
        with self._lock:
            return self._conn.execute(sql, params).fetchone()

    def scalar(self, sql: str, params: Sequence[Any] = (), default: Any = None) -> Any:
        with self._lock:
            row = self._conn.execute(sql, params).fetchone()
        if row is None:
            return default
        return row[0]

    def count(self, table: str, where: str = "", params: Sequence[Any] = ()) -> int:
        sql = f"SELECT COUNT(*) FROM {table}" + (f" WHERE {where}" if where else "")
        return int(self.scalar(sql, params, 0) or 0)

    # -- meta ----------------------------------------------------------------
    def has_table(self, name: str) -> bool:
        return self.scalar(
            "SELECT 1 FROM sqlite_master WHERE type IN ('table', 'view') AND name = ?", (name,)
        ) is not None

    def get_meta(self, key: str, default: Any = None) -> Any:
        if not self.has_table("meta"):
            return default
        raw = self.scalar("SELECT value FROM meta WHERE key = ?", (key,))
        if raw is None:
            return default
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            return raw

    def set_meta(self, key: str, value: Any) -> None:
        payload = value if isinstance(value, str) else json.dumps(value)
        with self.tx() as cur:
            cur.execute(
                "INSERT INTO meta(key, value, updated_at) VALUES(?,?,?) "
                "ON CONFLICT(key) DO UPDATE SET value=excluded.value, updated_at=excluded.updated_at",
                (key, payload, iso()),
            )

    @property
    def is_seeded(self) -> bool:
        return self.count("institutions") > 0

    def clear_all(self) -> None:  # pragma: no cover - admin helper
        with self.tx() as cur:
            for table in ("facts", "links", "deadlines", "web_pages", "extractions",
                          "query_cache", "institution_programs", "institutions", "aid_programs"):
                cur.execute(f"DELETE FROM {table}")

    # -- page bodies ---------------------------------------------------------
    def store_page_body(self, url: str, text: str) -> None:
        blob = compress(text)
        self.execute("UPDATE web_pages SET body_gzip = ?, body_chars = ? WHERE url = ?",
                     (sqlite3.Binary(blob), len(text), url))

    def read_page_body(self, url: str) -> str:
        blob = self.scalar("SELECT body_gzip FROM web_pages WHERE url = ?", (url,))
        return decompress(blob)

    def close(self) -> None:
        self._conn.close()

    def __enter__(self) -> Database:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()


def ttl_deadline(seconds: float) -> str:
    return iso(now_utc() + timedelta(seconds=seconds))


#: columns introduced after v1 that older caches must gain in place
_ADDED_COLUMNS: dict[str, tuple[tuple[str, str], ...]] = {
    "aid_programs": (
        ("verification_status", "TEXT"),
        ("verification_note", "TEXT"),
    ),
}
