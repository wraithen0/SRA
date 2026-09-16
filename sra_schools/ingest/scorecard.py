"""Ingest the federal institution backbone.

Source: US Dept of Education **College Scorecard** bulk file
``Most-Recent-Cohorts-Institution.zip`` (built from IPEDS + Title IV + IRS data).
It carries the IPEDS ``UNITID``, the OPEID, the institution's own URL, its net
price calculator URL and the aid/cost/outcomes series we rank on. One download,
~6.3k operating Title IV institutions, no API key, refreshed once a year.

The loader streams the CSV, so a 100 MB file never lands fully in memory.
"""

from __future__ import annotations

import csv
import hashlib
import io
import re
import zipfile
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from .. import util
from ..config import default_data_home
from ..util import norm_url

csv.field_size_limit(10_000_000)


def default_home() -> Path:
    return default_data_home()

DATASET_NAME = "College Scorecard - Most Recent Cohorts (Institution)"
DEFAULT_URL = (
    "https://ed-public-download.scorecard.network/downloads/"
    "Most-Recent-Cohorts-Institution_06102026.zip"
)
DISCOVERY_PAGE = "https://collegescorecard.ed.gov/data/"

CONTROL = {"1": "public", "2": "private_nonprofit", "3": "private_for_profit"}
PREDDEG = {"0": "less_than_2_year", "1": "less_than_2_year", "2": "2_year", "3": "4_year", "4": "4_year"}
HIGHDEG = {"0": "non_degree", "1": "certificate", "2": "associates", "3": "bachelors", "4": "graduates"}
REGION = {
    "0": "US Service Schools", "1": "New England", "2": "Mid East", "3": "Great Lakes",
    "4": "Plains", "5": "Southeast", "6": "Southwest", "7": "Rocky Mountain",
    "8": "Far West", "9": "Outlying Areas",
}
LOCALE = {
    # NCES locale codes (IPEDS): 11-13 city, 21-23 suburb, 31-33 town, 41-43 rural
    "11": "City: Large",
    "12": "City: Midsize",
    "13": "City: Small",
    "21": "Suburb: Large",
    "22": "Suburb: Midsize",
    "23": "Suburb: Small",
    "31": "Town: Fringe",
    "32": "Town: Distant",
    "33": "Town: Remote",
    "41": "Rural: Fringe",
    "42": "Rural: Distant",
    "43": "Rural: Remote",
}
#: CIP-2 digit families counted as STEM (NCES/IPEDS convention)
STEM_CIPS = ("01", "03", "04", "10", "11", "12", "14", "15", "24", "26", "27", "30", "31", "40",
             "41", "42", "43", "44", "45", "46")
_STATE_NAMES = {
    "AL": "Alabama", "AK": "Alaska", "AZ": "Arizona", "AR": "Arkansas", "CA": "California",
    "CO": "Colorado", "CT": "Connecticut", "DE": "Delaware", "DC": "District of Columbia",
    "FL": "Florida", "GA": "Georgia", "GU": "Guam", "HI": "Hawaii", "ID": "Idaho",
    "IL": "Illinois", "IN": "Indiana", "IA": "Iowa", "KS": "Kansas", "KY": "Kentucky",
    "LA": "Louisiana", "ME": "Maine", "MD": "Maryland", "MA": "Massachusetts", "MI": "Michigan",
    "MN": "Minnesota", "MS": "Mississippi", "MO": "Missouri", "MT": "Montana", "NE": "Nebraska",
    "NV": "Nevada", "NH": "New Hampshire", "NJ": "New Jersey", "NM": "New Mexico", "NY": "New York",
    "NC": "North Carolina", "ND": "North Dakota", "OH": "Ohio", "OK": "Oklahoma", "OR": "Oregon",
    "PA": "Pennsylvania", "PR": "Puerto Rico", "RI": "Rhode Island", "SC": "South Carolina",
    "SD": "South Dakota", "TN": "Tennessee", "TX": "Texas", "UT": "Utah", "VT": "Vermont",
    "VA": "Virginia", "VI": "Virgin Islands", "WA": "Washington", "WV": "West Virginia",
    "WI": "Wisconsin", "WY": "Wyoming", "AS": "American Samoa", "MP": "Northern Mariana Islands",
}


@dataclass(slots=True)
class DatasetInfo:
    url: str
    sha256: str | None = None
    etag: str | None = None
    downloaded_at: str | None = None
    rows: int = 0
    label: str = DATASET_NAME
    version: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "label": self.label, "url": self.url, "sha256": self.sha256, "etag": self.etag,
            "downloaded_at": self.downloaded_at, "rows": self.rows, "version": self.version,
        }


class ScorecardLoader:
    """Streams the Scorecard institution CSV into institution dicts."""

    def __init__(self, *, include_closed: bool = False) -> None:
        self.include_closed = include_closed

    # -- sources -------------------------------------------------------------
    @staticmethod
    def download(url: str = DEFAULT_URL, dest: Path | None = None, *, timeout: float = 180.0) -> Path:
        """Fetch the bulk zip (idempotent: a cached copy is reused)."""
        from ..extract import http

        directory = Path(dest or (default_home() / "downloads"))
        directory.mkdir(parents=True, exist_ok=True)
        target = directory / (Path(urlparse(url).path or "scorecard").name or "scorecard.zip")
        if target.exists() and target.stat().st_size > 1_000_000:
            return target
        resp = http.request(url, timeout=timeout, retries=1)
        if not resp.ok or not resp.body_bytes:
            raise RuntimeError(f"could not download {url}: {resp.error or resp.status}")
        target.write_bytes(resp.body_bytes)
        return target

    # -- parsing -------------------------------------------------------------
    def iter_rows(self, source: Path | io.IOBase | bytes) -> Iterator[dict[str, Any]]:
        with _open_csv(source) as handle:
            reader = csv.DictReader(handle)
            for raw in reader:
                row = self.map_row(raw)
                if row and (self.include_closed or row.get("currently_operating", 1)):
                    yield row

    def map_row(self, raw: dict[str, str | None]) -> dict[str, Any] | None:
        get: Callable[[str], Any] = lambda key: (raw.get(key) if key in raw else None)
        unitid = util.to_int(get("UNITID"))
        name = util.normalize_space(str(get("INSTNM") or ""))
        if not unitid or not name:
            return None
        control_code = str(get("CONTROL") or "").strip()
        stabbr = (str(get("STABBR") or "")).strip().upper() or None
        stem_share, stem_exact = _stem_share(raw)
        sat_mid = _mid(get("SATVRMID"), get("SATMTMID"))
        act_mid = util.to_float(get("ACTCMMID"))
        if act_mid is None:
            act_mid = _mid(get("ACTCM25"), get("ACTCM75"))
        grad = _first_num(get("C150_4_POOLED"), get("C150_L4_POOLED"), get("C150_4"), get("C150_L4"))
        homepage = _http_url(get("INSTURL"))
        ug_enroll = util.to_float(get("UGDS"))
        grad_enroll = util.to_float(get("GRADS"))
        return {
            "unitid": int(unitid),
            "opeid": _clean_str(get("OPEID")),
            "opeid6": _clean_str(get("OPEID6")),
            "name": util.truncate(name, 200),
            "slug": util.slugify(name),
            "city": _clean_str(get("CITY")),
            "state_abbr": stabbr,
            "state_name": _STATE_NAMES.get(stabbr or ""),
            "zip": _clean_str(get("ZIP")),
            "lat": util.to_float(get("LATITUDE")),
            "lon": util.to_float(get("LONGITUDE")),
            "url_homepage": homepage,
            "url_net_price_calc": _http_url(get("NPCURL")),
            "control": CONTROL.get(control_code),
            "preddeg": PREDDEG.get(str(get("PREDDEG") or "").strip()),
            "highdeg": HIGHDEG.get(str(get("HIGHDEG") or "").strip()),
            "carnegie": _clean_str(get("CCBASIC")),
            "locale": LOCALE.get(str(get("LOCALE") or "").strip()),
            "region": REGION.get(str(get("REGION") or "").strip()),
            "accreditor": _clean_str(get("ACCREDAGENCY")),
            "hbcu": _flag(get("HBCU")),
            "pbi": _flag(get("PBI")),
            "aanapii": _flag(get("AANAPII")),
            "tribally_controlled": _flag(get("TRIBAL")),
            "women_only": _flag(get("WOMENONLY")),
            "men_only": _flag(get("MENONLY")),
            "religious_affiliation": _relaffil(get("RELAFFIL")),
            "distance_only": _flag(get("DISTANCEONLY")),
            # YEARROUNDP was retired from the Scorecard file: None = unknown,
            # not "not year-round".
            "year_round": _flag(get("YEARROUNDP"), default=None) if get("YEARROUNDP") is not None else None,
            # No dedicated Scorecard column: graduate-only when there are no
            # undergrads but there are graduate enrolments.
            "graduate_only": 1 if (ug_enroll in (None, 0) and (grad_enroll or 0) > 0) else 0,
            "currently_operating": _flag(get("CURROPER"), default=1),
            "enrollment_undergrad": ug_enroll,
            "enrollment_graduate": grad_enroll,
            "enrollment_total": _sum_or_none(get("UGDS"), get("GRADS")),
            "admissions_rate": util.to_float(get("ADM_RATE")),
            "open_admissions": _flag(get("OPENADMP")),
            "sat_mid": sat_mid,
            "act_mid": act_mid,
            "tuition_in_state": util.to_float(get("TUITIONFEE_IN")),
            "tuition_out_state": util.to_float(get("TUITIONFEE_OUT")),
            "cost_attending": util.to_float(get("COSTT4_A")),
            "avg_net_price": util.to_float(_first_num(get("NPT4_PUB"), get("NPT4_PRIV"), get("COSTT4_P"), get("COSTT4_A"))),
            "median_family_income": util.to_float(get("MD_FAMINC")),
            "pct_pell": util.to_float(get("PCTPELL")),
            "median_debt_undergrad": util.to_float(get("DEBT_MDN")),
            "median_debt_graduate": util.to_float(get("GRAD_DEBT_MDN")),
            "median_earnings": util.to_float(get("MN_EARN_WNE_P10")),
            "grad_rate_150": grad,
            "retention_ft": _first_num(get("RET_FT4_POOLED"), get("RET_FT4")),
            "first_gen_pct": util.to_float(get("PAR_ED_PCT_1STGEN")),
            "parent_ed_pct_hs": util.to_float(get("PAR_ED_PCT_HS")),
            "stem_share": stem_share,
            "stem_share_exact": stem_exact,
            "international_share": util.to_float(get("UGDS_NRA")),
            "pct_grad_prof": util.to_float(get("PCT_GRAD_PROF")),
            "application_count": util.to_float(get("APPLIERS")),
        }

    # -- convenience ---------------------------------------------------------
    def load_all(self, source: Path | io.IOBase | bytes) -> list[dict[str, Any]]:
        return list(self.iter_rows(source))


# --------------------------------------------------------------------- helpers
def _clean_str(value: Any) -> str | None:  # noqa: ANN401
    if value is None:
        return None
    text = util.normalize_space(str(value))
    return text or None


def _flag(value: Any, *, default: int | None = 0) -> int | None:  # noqa: ANN401
    num = util.to_float(value)
    if num is None:
        return default
    return 1 if num else 0


def _relaffil(value: Any) -> str | None:  # noqa: ANN401
    """Scorecard RELAFFIL is a numeric affiliation code ('NA' = none)."""
    if value is None:
        return None
    text = util.normalize_space(str(value))
    if not text or text.upper() in {"NA", "N/A", "NULL", "-2"}:
        return None
    return text


def _first_num(*values: Any) -> float | None:
    for value in values:
        num = util.to_float(value)
        if num is not None:
            return num
    return None


def _mid(low: Any, high: Any) -> float | None:
    lo, hi = util.to_float(low), util.to_float(high)
    if lo is not None and hi is not None:
        return round((lo + hi) / 2, 1)
    return lo if lo is not None else hi


def _sum_or_none(*values: Any) -> float | None:
    total = 0.0
    found = False
    for value in values:
        num = util.to_float(value)
        if num is not None:
            total += num
            found = True
    return total if found else None


def _http_url(value: Any) -> str | None:  # noqa: ANN401
    text = _clean_str(value)
    if not text or text.lower().startswith(("n/a", "na", "http://na")):
        return None
    if "://" not in text:
        text = "https://" + text
    return norm_url(text)


def _stem_share(raw: dict[str, str | None]) -> tuple[float | None, float | None]:
    """Share of degrees in STEM CIP families, + the physical-science slice."""
    total = 0.0
    counted = False
    for cip in STEM_CIPS:
        num = util.to_float(raw.get(f"PCIP{cip}"))
        if num is not None:
            total += num
            counted = True
    exact = util.to_float(raw.get("PCIP26"))
    return (round(total, 4) if counted else None, exact)


@contextmanager
def _open_csv(source: Path | io.IOBase | bytes):
    """Yield a text stream from a path, raw zip bytes, or a plain CSV file."""
    if isinstance(source, bytes):
        with _ZipStream(io.BytesIO(source)) as handle:
            yield handle
        return
    path = Path(source)
    if path.suffix.lower() == ".zip":
        with _ZipStream(path) as handle:
            yield handle
    else:
        with path.open("r", newline="", encoding="utf-8-sig", errors="replace") as handle:
            yield handle


class _ZipStream:
    """Opens the largest .csv inside the Scorecard bulk archive."""

    def __init__(self, source: Path | io.IOBase) -> None:
        self._zip = zipfile.ZipFile(source)
        candidates = [
            info for info in self._zip.infolist()
            if info.filename.lower().endswith(".csv") and "__MACOSX" not in info.filename
        ]
        if not candidates:
            self._zip.close()
            raise RuntimeError("no .csv inside the Scorecard archive")
        self._name = max(candidates, key=lambda info: info.file_size).filename

    def __enter__(self) -> io.TextIOWrapper:
        return io.TextIOWrapper(self._zip.open(self._name), encoding="utf-8-sig",
                                errors="replace", newline="")

    def __exit__(self, *exc: object) -> None:
        self._zip.close()


def sha256_of(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def dataset_version_from_url(url: str) -> str:
    match = re.search(r"(\d{8})", url or "")
    return f"scorecard-{match.group(1)}" if match else "scorecard-unknown"
