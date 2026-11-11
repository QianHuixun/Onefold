"""六张表：Topic / Source / Article / Event / ArticleEvent / FetchLog。

字段与 docs/PRD.md 第 8 节一一对应，新增字段请同步改 PRD。
"""

from __future__ import annotations

from datetime import UTC, datetime

from sqlmodel import Field, SQLModel


def utcnow() -> datetime:
    return datetime.now(UTC)


class Topic(SQLModel, table=True):
    __tablename__ = "topic"

    id: int | None = Field(default=None, primary_key=True)
    slug: str = Field(index=True, unique=True, max_length=40)
    name: str = Field(max_length=80)
    description: str = ""
    # {simhash_threshold, cosine_threshold, time_window_hours, summary_prompt}
    config_json: str = "{}"
    created_at: datetime = Field(default_factory=utcnow)


class Source(SQLModel, table=True):
    __tablename__ = "source"

    id: int | None = Field(default=None, primary_key=True)
    topic_id: int = Field(foreign_key="topic.id", index=True)
    name: str = Field(max_length=80)
    feed_url: str
    type: str = Field(default="rss", max_length=20)
    enabled: bool = True
    last_fetch_at: datetime | None = None
    fail_count: int = 0


class Article(SQLModel, table=True):
    __tablename__ = "article"

    id: int | None = Field(default=None, primary_key=True)
    topic_id: int = Field(foreign_key="topic.id", index=True)
    source_id: int = Field(foreign_key="source.id", index=True)
    title: str
    url: str
    # URL 归一化后的哈希，幂等键
    url_hash: str = Field(index=True, unique=True, max_length=40)
    author: str = ""
    content: str = ""
    content_length: int = 0
    published_at: datetime | None = None
    fetched_at: datetime = Field(default_factory=utcnow)
    simhash: int | None = None
    # jieba 预分词结果，供 FTS5 索引
    search_text: str = ""
    status: str = Field(default="ok", max_length=20)


class Event(SQLModel, table=True):
    __tablename__ = "event"

    id: int | None = Field(default=None, primary_key=True)
    topic_id: int = Field(foreign_key="topic.id", index=True)
    title: str
    summary: str = ""
    first_seen_at: datetime = Field(default_factory=utcnow, index=True)
    last_seen_at: datetime = Field(default_factory=utcnow)
    article_count: int = 0
    source_count: int = 0
    status: str = Field(default="ok", max_length=20)


class ArticleEvent(SQLModel, table=True):
    __tablename__ = "article_event"

    article_id: int = Field(foreign_key="article.id", primary_key=True)
    event_id: int = Field(foreign_key="event.id", primary_key=True, index=True)
    similarity: float = 0.0


class FetchLog(SQLModel, table=True):
    __tablename__ = "fetch_log"

    id: int | None = Field(default=None, primary_key=True)
    source_id: int = Field(foreign_key="source.id", index=True)
    started_at: datetime = Field(default_factory=utcnow)
    finished_at: datetime | None = None
    new_count: int = 0
    dup_count: int = 0
    error: str = ""
