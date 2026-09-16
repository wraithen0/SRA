"""Optional LLM extractor - used only when the rules under-fire.

Off unless ``Settings.use_llm`` is set and an OpenAI-compatible key is present
(`SRA_LLM_API_KEY`, `OPENAI_API_KEY`, or `GROQ_API_KEY`). It is a
gap-filler, not the primary path: it only sees pages the cache already
holds, and it may only assert topics that are in the taxonomy. Anything it says
that the rule engine cannot corroborate is stored with a lower confidence and is
reported to the user as "model-inferred, verify on the page".
"""

from __future__ import annotations

import json
import re
from typing import Any

from ..config import LlmSettings
from ..taxonomy import TOPICS
from ..util import clean_snippet, norm_url, truncate
from .http import HttpError, request
from .rules import RULES_VERSION, Finding, PageFacts

LLM_MIN_CONFIDENCE = 0.45
#: bump when the prompt or its JSON contract changes, so cached extractions rerun
PROMPT_VERSION = "llm-2026.09-1"
MAX_PAGE_CHARS = 14_000

SYSTEM_PROMPT = """\
You extract factual admissions/financial-aid information from a single page of an
official US college website. You are given the page text and the list of topics that
matter to the asker.

Rules you must not break:
- Return ONLY facts that are explicitly stated on the page. Never infer from general
  knowledge about colleges, never fill a gap because it is typical.
- For every fact, quote up to 200 characters of the page verbatim in "evidence".
- Dates as YYYY-MM-DD when the year is stated or unambiguous; otherwise leave date null
  and put the page's wording in "text". A bare month/day may be resolved to the next
  occurrence only if the page names a specific year elsewhere.
- Money as a number in dollars, without commas.
- "bool" facts: true/false only when the page states it; omit the fact otherwise.
- If the page says the school does NOT offer something, return the fact with
  "bool": false and quote the sentence that says so.
- Output JSON only: {"facts": [...]} with objects of shape
  {"topic","text","date","num","bool","url","evidence","confidence"}.
- confidence is your certainty that the page really states this: 0.5-0.9.
"""


class LlmExtractor:
    """OpenAI-compatible ``/chat/completions`` with a JSON-only contract."""

    name = "llm"

    def __init__(self, settings: LlmSettings | None = None) -> None:
        self.settings = settings or LlmSettings.from_env()
        if not self.settings.enabled:
            raise RuntimeError(
                "LlmExtractor needs SRA_LLM_API_KEY, OPENAI_API_KEY, or GROQ_API_KEY"
            )

    # -- request -------------------------------------------------------------
    def _endpoint(self) -> str:
        base = (self.settings.base_url or "").rstrip("/")
        return f"{base}/chat/completions"

    def build_prompt(self, text: str, *, page_url: str, school: str, missing_topics: list[str]) -> list[dict[str, str]]:
        topic_lines = "\n".join(
            f"- {key}: {TOPICS[key].label}" for key in missing_topics if key in TOPICS
        )
        user = (
            f"INSTITUTION: {school}\n"
            f"PAGE URL: {page_url}\n"
            f"TOPICS TO EXTRACT (only these keys):\n{topic_lines}\n\n"
            f"PAGE TEXT:\n<<<\n{truncate(text, MAX_PAGE_CHARS)}\n>>>"
        )
        return [{"role": "system", "content": SYSTEM_PROMPT}, {"role": "user", "content": user}]

    def complete(self, messages: list[dict[str, str]]) -> str:
        payload = {
            "model": self.settings.model,
            "messages": messages,
            "temperature": 0,
            "max_tokens": self.settings.max_tokens,
            "response_format": {"type": "json_object"},
        }
        resp = request(
            self._endpoint(),
            method="POST",
            payload=payload,
            headers={"Authorization": f"Bearer {self.settings.api_key}"},
            timeout=self.settings.timeout_s,
            retries=1,
        )
        if resp.status is None or resp.status >= 400:
            raise HttpError(resp.error or "llm request failed", status=resp.status, body=resp.text)
        data = resp.json() or {}
        try:
            return data["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise HttpError(f"unexpected llm payload: {truncate(str(data), 200)}") from exc

    # -- extraction ----------------------------------------------------------
    def extract(
        self,
        page: PageFacts,
        text: str,
        *,
        school: str,
        missing_topics: list[str],
        page_url: str,
    ) -> list[Finding]:
        if not missing_topics:
            return []
        try:
            raw = self.complete(self.build_prompt(text, page_url=page_url, school=school,
                                                 missing_topics=missing_topics))
        except (HttpError, ValueError):
            return []
        return parse_llm_findings(raw, allowed_topics=set(missing_topics), page_url=page_url)


def parse_llm_findings(raw: str, *, allowed_topics: set[str], page_url: str) -> list[Finding]:
    """Validate model output; reject unknown topics and unsourced claims."""
    payload = _loose_json(raw)
    if not payload:
        return []
    items = payload.get("facts") if isinstance(payload, dict) else payload
    if not isinstance(items, list):
        return []
    out: list[Finding] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        topic = str(item.get("topic") or "").strip()
        if topic not in allowed_topics or topic not in TOPICS:
            continue
        evidence = str(item.get("evidence") or "").strip()
        if len(evidence) < 12:  # no quote, no fact
            continue
        topic_obj = TOPICS[topic]
        try:
            confidence = float(item.get("confidence") or 0.5)
        except (TypeError, ValueError):
            confidence = 0.5
        confidence = max(0.0, min(confidence, 0.9))
        if confidence < LLM_MIN_CONFIDENCE:
            continue
        text_val = item.get("text")
        date_val = item.get("date")
        num_val = item.get("num")
        bool_val = item.get("bool")
        url_val = norm_url(str(item.get("url"))) if item.get("url") else None
        value_text = str(text_val)[:400] if text_val else (url_val or None)
        out.append(
            Finding(
                topic=topic,
                value_text=value_text or (str(bool_val).lower() if isinstance(bool_val, bool) else None),
                value_date=str(date_val)[:10] if re.match(r"^\d{4}-\d{2}-\d{2}", str(date_val or "")) else None,
                value_num=float(num_val) if isinstance(num_val, (int, float)) else None,
                value_bool=bool(bool_val) if isinstance(bool_val, bool) else None,
                evidence=clean_snippet(f"[model-inferred] {evidence}", 240),
                confidence=round(confidence, 2),
                label="llm",
                url=page_url,
            )
        )
        _ = topic_obj  # keeps the taxonomy lookup explicit for reviewers
    return out


def _loose_json(raw: str) -> Any | None:  # noqa: ANN401
    candidates = [raw.strip()]
    fenced = re.search(r"```(?:json)?\s*(.*?)```", raw, re.S)
    if fenced:
        candidates.insert(0, fenced.group(1).strip())
    brace = re.search(r"\{.*\}", raw, re.S)
    if brace:
        candidates.append(brace.group(0))
    for candidate in candidates:
        try:
            return json.loads(candidate)
        except json.JSONDecodeError:
            continue
    return None


def should_call_llm(page: PageFacts, *, required: list[str], min_rule_findings: int = 3) -> bool:
    """Cheap heuristic: only pay for a model when the rules left a required gap."""
    answered = page.topics
    gaps = [t for t in required if t not in answered]
    if not gaps:
        return False
    if len(answered) < min_rule_findings and page.text_chars > 1200:
        return True
    return bool(gaps)


__all__ = ["LlmExtractor", "parse_llm_findings", "should_call_llm", "RULES_VERSION"]
