"""Curated source registry: where to look, in what order, for how long.

This is the "don't wander aimlessly" layer. For each fact topic we know:

* ``campus_paths`` - URL paths that US campuses really use, tried in order against
  the institution's own domain (cheapest, most authoritative).
* ``topic_hints``  - path/anchor keywords used to classify links found on a page.
* ``national``     - federal/state/foundation reference pages that answer the
  profile-level questions (FAFSA timing, fee-waiver programmes, VR, visa rules).
* ``search_templates`` - the *last* resort, one bounded query per unanswered topic.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Any

from .config import DATA_DIR
from .taxonomy import TOPICS
from .util import domain_of, norm_url

SOURCES_FILE = DATA_DIR / "sources.json"


@dataclass(frozen=True)
class NationalSource:
    source_id: str
    title: str
    url: str
    needs: tuple[str, ...] = ()
    profiles: tuple[str, ...] = ()
    authority: str = "reference"
    ttl_days: int = 60
    note: str | None = None
    apply_url: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.source_id,
            "title": self.title,
            "url": self.url,
            "needs": list(self.needs),
            "profiles": list(self.profiles),
            "authority": self.authority,
            "ttl_days": self.ttl_days,
            "note": self.note,
            "apply_url": self.apply_url,
        }


@dataclass
class SourceRegistry:
    """Loaded view of ``data/sources.json``."""

    version: str = "0"
    campus_paths: dict[str, list[str]] = field(default_factory=dict)
    topic_hints: dict[str, list[str]] = field(default_factory=dict)
    search_templates: list[str] = field(default_factory=list)
    national: list[NationalSource] = field(default_factory=list)
    raw: dict[str, Any] = field(default_factory=dict)

    # -- construction --------------------------------------------------------
    @staticmethod
    def load(path: Path | str | None = None) -> SourceRegistry:
        file = Path(path) if path else SOURCES_FILE
        payload = json.loads(file.read_text("utf-8"))
        national = [
            NationalSource(
                source_id=item["id"],
                title=item["title"],
                url=item["url"],
                needs=tuple(item.get("needs", ())),
                profiles=tuple(item.get("profiles", ())),
                authority=item.get("authority", "reference"),
                ttl_days=int(item.get("ttl_days", 60)),
                note=item.get("note"),
                apply_url=item.get("apply_url"),
            )
            for item in payload.get("national", [])
        ]
        return SourceRegistry(
            version=str(payload.get("version", "0")),
            campus_paths={k: list(v) for k, v in payload.get("campus_paths", {}).items()},
            topic_hints={k: [s.lower() for s in v] for k, v in payload.get("topic_hints", {}).items()},
            search_templates=list(payload.get("search_templates", [])),
            national=national,
            raw=payload,
        )

    # -- queries -------------------------------------------------------------
    def national_for(
        self,
        *,
        profile: str | None = None,
        needs: tuple[str, ...] | list[str] | None = None,
    ) -> list[NationalSource]:
        out: list[NationalSource] = []
        need_set = set(needs or ())
        for src in self.national:
            if profile and src.profiles and profile not in src.profiles:
                continue
            if need_set and src.needs and not (need_set & set(src.needs)):
                continue
            out.append(src)
        return out

    def hints_for(self, topic: str) -> list[str]:
        return self.topic_hints.get(topic, [])

    def candidate_urls(self, institution_url: str | None, topic: str, *, limit: int = 6) -> list[str]:
        """Deterministic same-domain URL guesses for a topic on this campus."""
        base = norm_url(institution_url)
        if not base or topic not in self.campus_paths:
            return []
        parsed = re.match(r"^(https?://[^/]+)(/.*)?$", base)
        if not parsed:
            return []
        origin, existing = parsed.group(1), (parsed.group(2) or "").rstrip("/")
        out: list[str] = []
        seen: set[str] = set()
        paths = self.campus_paths[topic][:limit]
        for path in paths:
            for prefix in ([existing] if existing and existing != "" else []) + [""]:
                url = norm_url(f"{origin}{prefix}{path}")
                if url and url not in seen and domain_of(url) == domain_of(base):
                    seen.add(url)
                    out.append(url)
                if len(out) >= limit:
                    return out
        return out

    def search_query(self, topic: str, name: str, url: str | None, *, index: int = 0) -> str | None:
        """Bounded discovery query, scoped to the institution's own domain first."""
        if not self.search_templates:
            return None
        template = self.search_templates[min(index, len(self.search_templates) - 1)]
        topic_obj = TOPICS.get(topic)
        return template.format(
            name=name,
            domain=domain_of(url) or name,
            topic=topic,
            topic_label=(topic_obj.label.lower() if topic_obj else topic.replace("_", " ")),
        )

    def topics_for_text(self, text: str) -> list[str]:
        """Reverse map: given anchor text or a URL, which topics might it answer?"""
        lowered = text.lower()
        scored: list[tuple[int, str]] = []
        for topic, hints in self.topic_hints.items():
            score = sum(1 for hint in hints if hint in lowered)
            if score:
                scored.append((score, topic))
        scored.sort(reverse=True)
        return [topic for _, topic in scored]


@lru_cache(maxsize=2)
def get_registry(path: str | None = None) -> SourceRegistry:
    return SourceRegistry.load(path) if path else SourceRegistry.load(SOURCES_FILE)
