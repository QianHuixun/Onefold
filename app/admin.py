"""管理接口：数据源的增删改查、手动触发抓取、抓取日志。

全部挂在 /api/admin 下，统一走 require_admin 鉴权。
"""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from pydantic import BaseModel, field_validator
from sqlmodel import Session, func, select

from .auth import require_admin
from .db import engine, get_session
from .models import Article, FetchLog, Source, Topic, utcnow

router = APIRouter(prefix="/api/admin", dependencies=[Depends(require_admin)])


class SourceOut(BaseModel):
    id: int
    name: str
    feed_url: str
    topic_slug: str
    topic_name: str
    enabled: bool
    last_fetch_at: datetime | None
    fail_count: int
    article_count: int


class SourceCreate(BaseModel):
    name: str
    feed_url: str
    topic_slug: str

    @field_validator("feed_url")
    @classmethod
    def _check_url(cls, value: str) -> str:
        if not value.startswith(("http://", "https://")):
            raise ValueError("feed_url 必须以 http:// 或 https:// 开头")
        return value.strip()

    @field_validator("name")
    @classmethod
    def _check_name(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("名称不能为空")
        return value.strip()


class SourceUpdate(BaseModel):
    name: str | None = None
    feed_url: str | None = None
    topic_slug: str | None = None
    enabled: bool | None = None


class FetchLogOut(BaseModel):
    source_name: str
    started_at: datetime
    finished_at: datetime | None
    new_count: int
    dup_count: int
    error: str


def _to_out(session: Session, source: Source, topic: Topic) -> SourceOut:
    count = session.exec(
        select(func.count()).select_from(Article).where(Article.source_id == source.id)
    ).one()
    return SourceOut(
        id=source.id,
        name=source.name,
        feed_url=source.feed_url,
        topic_slug=topic.slug,
        topic_name=topic.name,
        enabled=source.enabled,
        last_fetch_at=source.last_fetch_at,
        fail_count=source.fail_count,
        article_count=int(count),
    )


def _topic_by_slug(session: Session, slug: str) -> Topic:
    topic = session.exec(select(Topic).where(Topic.slug == slug)).first()
    if topic is None:
        raise HTTPException(400, f"主题 {slug} 不存在")
    return topic


@router.get("/sources", response_model=list[SourceOut])
def list_sources(session: Session = Depends(get_session)):
    rows = session.exec(
        select(Source, Topic).join(Topic, Topic.id == Source.topic_id).order_by(Source.id)
    ).all()
    return [_to_out(session, s, t) for s, t in rows]


@router.post("/sources", response_model=SourceOut, status_code=201)
def create_source(payload: SourceCreate, session: Session = Depends(get_session)):
    topic = _topic_by_slug(session, payload.topic_slug)
    if session.exec(select(Source).where(Source.feed_url == payload.feed_url)).first():
        raise HTTPException(409, "这个 feed 已经加过了")
    source = Source(topic_id=topic.id, name=payload.name, feed_url=payload.feed_url)
    session.add(source)
    session.commit()
    session.refresh(source)
    return _to_out(session, source, topic)


@router.patch("/sources/{source_id}", response_model=SourceOut)
def update_source(source_id: int, payload: SourceUpdate, session: Session = Depends(get_session)):
    row = session.exec(
        select(Source, Topic).join(Topic, Topic.id == Source.topic_id).where(Source.id == source_id)
    ).first()
    if row is None:
        raise HTTPException(404, "数据源不存在")
    source, topic = row

    if payload.name is not None:
        source.name = payload.name.strip() or source.name
    if payload.feed_url is not None:
        if not payload.feed_url.startswith(("http://", "https://")):
            raise HTTPException(400, "feed_url 必须以 http:// 或 https:// 开头")
        source.feed_url = payload.feed_url.strip()
    if payload.topic_slug is not None:
        topic = _topic_by_slug(session, payload.topic_slug)
        source.topic_id = topic.id
    if payload.enabled is not None:
        source.enabled = payload.enabled
        if payload.enabled:
            source.fail_count = 0

    session.add(source)
    session.commit()
    session.refresh(source)
    return _to_out(session, source, topic)


@router.delete("/sources/{source_id}", status_code=204)
def delete_source(source_id: int, session: Session = Depends(get_session)):
    source = session.get(Source, source_id)
    if source is None:
        raise HTTPException(404, "数据源不存在")
    count = session.exec(
        select(func.count()).select_from(Article).where(Article.source_id == source_id)
    ).one()
    if count:
        raise HTTPException(409, f"这个源下还有 {count} 篇文章，先停用，不要删除")
    session.delete(source)
    session.commit()


def _run_fetch_job(limit: int) -> None:
    from .cli import _run_fetch

    with Session(engine) as session:
        _run_fetch(session, limit)


@router.post("/fetch", status_code=202)
def trigger_fetch(background: BackgroundTasks, limit: int = Query(default=10, ge=1, le=50)):
    background.add_task(_run_fetch_job, limit)
    return {"started": True, "limit": limit, "at": utcnow()}


@router.get("/fetch-log", response_model=list[FetchLogOut])
def fetch_log(limit: int = Query(default=20, ge=1, le=100), session: Session = Depends(get_session)):
    rows = session.exec(
        select(FetchLog, Source.name)
        .join(Source, Source.id == FetchLog.source_id)
        .order_by(FetchLog.started_at.desc())
        .limit(limit)
    ).all()
    return [
        FetchLogOut(
            source_name=name,
            started_at=log.started_at,
            finished_at=log.finished_at,
            new_count=log.new_count,
            dup_count=log.dup_count,
            error=log.error,
        )
        for log, name in rows
    ]
