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
