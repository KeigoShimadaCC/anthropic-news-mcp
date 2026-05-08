from datetime import datetime
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, Field, HttpUrl


class Category(StrEnum):
    MODELS = "models"
    CLAUDE_CODE = "claude-code"
    RESEARCH = "research"
    POLICY = "policy"
    BUSINESS = "business"
    COMMUNITY = "community"
    OPS = "ops"
    ENGINEERING = "engineering"
    ECONOMICS = "economics"


class Source(StrEnum):
    ANTHROPIC = "anthropic"
    GITHUB = "github"
    REDDIT = "reddit"
    HACKERNEWS = "hackernews"


class SourceStatus(StrEnum):
    LIVE = "live"
    CACHE = "cache"
    STALE = "stale"
    DOWN = "down"


class SourceType(StrEnum):
    OFFICIAL = "official"
    DOCS = "docs"
    GITHUB = "github"
    COMMUNITY = "community"


class EvidenceTier(StrEnum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class ClaimSupport(StrEnum):
    STRONG = "strong_support"
    WEAK = "weak_support"
    UNSUPPORTED = "unsupported"
    NEEDS_REVIEW = "needs_review"


class NewsItem(BaseModel):
    """A single news/changelog/release item."""

    id: str = Field(..., description="Stable ID, format: '<source_key>-<hash-or-native-id>'")
    title: str
    summary: str = Field(default="", description="Short description, max ~400 chars")
    url: HttpUrl
    source: Source
    source_key: str = Field(..., description="Specific fetcher key, e.g. 'anthropic-newsroom'")
    category: list[Category] = Field(default_factory=list)
    published_at: datetime
    importance: Literal[1, 2, 3] = 1
    tags: list[str] = Field(default_factory=list)
    author: str | None = None


class SourceHealth(BaseModel):
    key: str
    status: SourceStatus
    fetched_at: datetime
    expires_at: datetime
    item_count: int
    error: str | None = None


class ContentDetail(BaseModel):
    item_id: str
    url: HttpUrl
    normalized_text: str
    retrieved_at: datetime
    content_hash: str
    content_type: str
    truncated: bool = False
    warnings: list[str] = Field(default_factory=list)


class EvidenceExcerpt(BaseModel):
    evidence_id: str
    item_id: str
    url: HttpUrl
    title: str
    source_key: str
    source_type: SourceType
    evidence_tier: EvidenceTier
    text: str
    start_char: int
    end_char: int
    retrieved_at: datetime
    content_hash: str


class DedupCluster(BaseModel):
    cluster_id: str
    representative_item_id: str
    item_ids: list[str]
    canonical_url: str
    evidence_tier: EvidenceTier


class TimelineGroup(BaseModel):
    date: str
    items: list[NewsItem]
    clusters: list[DedupCluster] = Field(default_factory=list)


class ResearchSession(BaseModel):
    session_id: str
    title: str
    topic: str | None = None
    filters: dict[str, object] = Field(default_factory=dict)
    created_at: datetime
    updated_at: datetime


class ResearchNote(BaseModel):
    note_id: str
    session_id: str
    text: str
    evidence_ids: list[str] = Field(default_factory=list)
    follow_up: bool = False
    created_at: datetime


class ResearchReport(BaseModel):
    report_id: str
    session_id: str
    title: str
    markdown: str
    evidence_ids: list[str] = Field(default_factory=list)
    created_at: datetime


class ClaimEvaluationResult(BaseModel):
    claim: str
    support: ClaimSupport
    evidence: list[EvidenceExcerpt] = Field(default_factory=list)
    reason: str
