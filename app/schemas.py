"""接口出参。只暴露前端需要的字段，正文不进列表。"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class TopicOut(BaseModel):
    slug: str
    name: str


class EventOut(BaseModel):
    id: int
    title: str
    summary: str
    summary_source: str = ""
    topic_slug: str
    topic_name: str
    first_seen_at: datetime
    last_seen_at: datetime
    article_count: int
    source_count: int
    sources: list[str] = []


class EventPage(BaseModel):
    items: list[EventOut]
    total: int
    offset: int
    limit: int


class ArticleOut(BaseModel):
    id: int
    title: str
    url: str
    source_name: str
    published_at: datetime | None
    content_length: int
    similarity: float = 0.0


class EventDetail(EventOut):
    articles: list[ArticleOut] = []


class StatsOut(BaseModel):
    events: int
    sources: int
    articles: int
    updated_at: datetime | None


class SearchHit(BaseModel):
    kind: str  # event | article
    id: int
    title: str
    snippet: str
    source_name: str = ""
    url: str = ""
    published_at: datetime | None = None


class SearchOut(BaseModel):
    q: str
    hits: list[SearchHit]
    total: int
