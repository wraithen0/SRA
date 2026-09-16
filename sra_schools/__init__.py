"""sra-schools - US institution discovery + financial-aid intelligence.

Public entry point is :class:`sra_schools.api.SRA`::

    from sra_schools import SRA

    sra = SRA.open()                       # uses the shared cache
    report = sra.search(profile="first_generation", state="CA", limit=10)
    for match in report.matches:
        print(match.institution.name, match.score, match.links.get("fafsa_school_code"))

See README.md for the CLI and the data model.
"""

from __future__ import annotations

from .api import SRA, get_sra
from .models import (
    AidProgram,
    CacheInfo,
    Deadline,
    Fact,
    Institution,
    PlaybookStep,
    SchoolMatch,
    SearchQuery,
    SearchReport,
)
from .profiles import (
    PROFILES,
    Profile,
    describe_profiles,
    get_profile,
)
from .taxonomy import TOPICS, Need, Topic
from .util import usd

__version__ = "0.1.0"

__all__ = [
    "PROFILES",
    "SRA",
    "TOPICS",
    "AidProgram",
    "CacheInfo",
    "Deadline",
    "Fact",
    "Institution",
    "Need",
    "PlaybookStep",
    "Profile",
    "SchoolMatch",
    "SearchQuery",
    "SearchReport",
    "Topic",
    "__version__",
    "describe_profiles",
    "get_profile",
    "get_sra",
    "usd",
]
