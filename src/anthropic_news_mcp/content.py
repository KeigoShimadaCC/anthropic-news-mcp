"""Full-text retrieval and evidence excerpt helpers."""

from __future__ import annotations

import hashlib
import json
import re
from datetime import UTC, datetime

from selectolax.parser import HTMLParser

from .http import get_client
from .models import ContentDetail, EvidenceExcerpt, EvidenceTier, NewsItem, SourceType

_MAX_STORED_CHARS = 50_000
_MAX_RESPONSE_BYTES = 5_000_000
_BOILERPLATE_TAGS = "script,style,nav,footer,header,noscript,svg,form"
_WORD_RE = re.compile(r"[a-z0-9][a-z0-9-]{2,}", re.IGNORECASE)


def content_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def normalize_text(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def _json_text(value: object) -> str:
    if isinstance(value, dict):
        return " ".join(_json_text(v) for v in value.values())
    if isinstance(value, list):
        return " ".join(_json_text(v) for v in value)
    if isinstance(value, str):
        return value
    if value is None:
        return ""
    return str(value)


def extract_text(body: str, content_type: str) -> str:
    lowered = content_type.lower()
    if "json" in lowered:
        try:
            return normalize_text(_json_text(json.loads(body)))
        except json.JSONDecodeError:
            return normalize_text(body)
    if "html" not in lowered and "<html" not in body[:500].lower():
        return normalize_text(body)
    tree = HTMLParser(body)
    for node in tree.css(_BOILERPLATE_TAGS):
        node.decompose()
    text = (
        tree.body.text(separator=" ", strip=True)
        if tree.body
        else tree.text(separator=" ", strip=True)
    )
    return normalize_text(text)


async def fetch_content_detail(item: NewsItem) -> ContentDetail:
    warnings: list[str] = []
    async with get_client() as client:
        resp = await client.get(str(item.url))
        resp.raise_for_status()
    content_type = resp.headers.get("content-type", "text/plain").split(";", 1)[0].strip()
    if len(resp.content) > _MAX_RESPONSE_BYTES:
        warnings.append(
            f"Response body {len(resp.content) // 1024}KB exceeds limit; stored summary text only."
        )
        text = normalize_text(f"{item.title}\n\n{item.summary}")
    elif not (
        content_type.startswith("text/")
        or content_type in {"application/json", "application/vnd.github+json"}
    ):
        warnings.append(
            f"Skipped unsupported content type {content_type}; stored summary text only."
        )
        text = normalize_text(f"{item.title}\n\n{item.summary}")
    else:
        text = extract_text(resp.text, content_type)
    truncated = len(text) > _MAX_STORED_CHARS
    if truncated:
        warnings.append(f"Content truncated to {_MAX_STORED_CHARS} characters.")
        text = text[:_MAX_STORED_CHARS]
    if not text:
        text = normalize_text(f"{item.title}\n\n{item.summary}")
        warnings.append("No page text extracted; stored item title and summary.")
    return ContentDetail(
        item_id=item.id,
        url=item.url,
        normalized_text=text,
        retrieved_at=datetime.now(tz=UTC),
        content_hash=content_hash(text),
        content_type=content_type,
        truncated=truncated,
        warnings=warnings,
    )


def _terms(query: str | None) -> list[str]:
    if not query:
        return []
    return [term.lower() for term in _WORD_RE.findall(query) if len(term) >= 3]


def _window_for_match(text: str, start: int, size: int = 900) -> tuple[int, int]:
    half = size // 2
    left = max(0, start - half)
    right = min(len(text), start + half)
    if left > 0:
        left = text.find(" ", left)
        left = 0 if left < 0 else left + 1
    if right < len(text):
        next_space = text.rfind(" ", left, right)
        right = right if next_space <= left else next_space
    return left, right


def build_excerpts(
    item: NewsItem,
    detail: ContentDetail,
    *,
    source_type: SourceType,
    evidence_tier: EvidenceTier,
    query: str | None = None,
    max_excerpts: int = 3,
) -> list[EvidenceExcerpt]:
    text = detail.normalized_text
    terms = _terms(query)
    windows: list[tuple[int, int]] = []
    lowered = text.lower()
    for term in terms:
        idx = lowered.find(term)
        if idx >= 0:
            window = _window_for_match(text, idx)
            if window not in windows:
                windows.append(window)
        if len(windows) >= max_excerpts:
            break
    if not windows and text:
        windows.append((0, min(len(text), 900)))
    excerpts: list[EvidenceExcerpt] = []
    for start, end in windows[:max_excerpts]:
        excerpt_text = text[start:end].strip()
        seed = f"{item.id}:{detail.content_hash}:{start}:{end}"
        excerpts.append(
            EvidenceExcerpt(
                evidence_id=hashlib.sha256(seed.encode("utf-8")).hexdigest(),
                item_id=item.id,
                url=item.url,
                title=item.title,
                source_key=item.source_key,
                source_type=source_type,
                evidence_tier=evidence_tier,
                text=excerpt_text,
                start_char=start,
                end_char=end,
                retrieved_at=detail.retrieved_at,
                content_hash=detail.content_hash,
            )
        )
    return excerpts
