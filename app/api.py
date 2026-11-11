"""HTTP 接口。前缀 /api，前端只读这些。"""

from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, or_
from sqlmodel import Session, select

from .db import get_session
from .models import Article, ArticleEvent, Event, Source, Topic
from .schemas import (
    ArticleOut,
    EventDetail,
    EventOut,
    EventPage,
    SearchHit,
    SearchOut,
    StatsOut,
    TopicOut,
)

router = APIRouter(prefix="/api")


def _sources_for(session: Session, event_ids: list[int]) -> dict[int, list[str]]:
    """一次查出这批事件涉及的所有来源名，避免逐条查。"""
    if not event_ids:
        return {}
    rows = session.exec(
        select(ArticleEvent.event_id, Source.name)
        .join(Article, Article.id == ArticleEvent.article_id)
        .join(Source, Source.id == Article.source_id)
        .where(ArticleEvent.event_id.in_(event_ids))
    ).all()
    out: dict[int, list[str]] = {}
    for event_id, name in rows:
        names = out.setdefault(int(event_id), [])
        if name not in names:
            names.append(name)
    return out


@router.get("/topics", response_model=list[TopicOut])
def list_topics(session: Session = Depends(get_session)):
    topics = session.exec(select(Topic).order_by(Topic.id)).all()
    return [TopicOut(slug=t.slug, name=t.name) for t in topics]


@router.get("/events", response_model=EventPage)
def list_events(
    topic: str | None = Query(default=None, description="主题 slug"),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    session: Session = Depends(get_session),
):
    stmt = select(Event, Topic).join(Topic, Topic.id == Event.topic_id)
    count_stmt = select(func.count()).select_from(Event).join(Topic, Topic.id == Event.topic_id)
    if topic:
        stmt = stmt.where(Topic.slug == topic)
        count_stmt = count_stmt.where(Topic.slug == topic)

    total = session.exec(count_stmt).one()
    rows = session.exec(
        stmt.order_by(Event.first_seen_at.desc()).offset(offset).limit(limit)
    ).all()

    ids = [e.id for e, _ in rows]
    sources = _sources_for(session, ids)
    items = [
        EventOut(
            id=e.id,
            title=e.title,
            summary=e.summary,
            summary_source=e.summary_source,
            topic_slug=t.slug,
            topic_name=t.name,
            first_seen_at=e.first_seen_at,
            last_seen_at=e.last_seen_at,
            article_count=e.article_count,
            source_count=e.source_count,
            sources=sources.get(e.id, []),
        )
        for e, t in rows
    ]
    return EventPage(items=items, total=total, offset=offset, limit=limit)


@router.get("/events/{event_id}", response_model=EventDetail)
def get_event(event_id: int, session: Session = Depends(get_session)):
    row = session.exec(
        select(Event, Topic).join(Topic, Topic.id == Event.topic_id).where(Event.id == event_id)
    ).first()
    if row is None:
        raise HTTPException(status_code=404, detail="event not found")
    event, topic = row

    arts = session.exec(
        select(Article, Source, ArticleEvent.similarity)
        .join(ArticleEvent, ArticleEvent.article_id == Article.id)
        .join(Source, Source.id == Article.source_id)
        .where(ArticleEvent.event_id == event_id)
        .order_by(ArticleEvent.similarity.desc())
    ).all()

    articles = [
        ArticleOut(
            id=a.id,
            title=a.title,
            url=a.url,
            source_name=s.name,
            published_at=a.published_at,
            content_length=a.content_length,
            similarity=round(sim, 2),
        )
        for a, s, sim in arts
    ]
    return EventDetail(
        id=event.id,
        title=event.title,
        summary=event.summary,
        summary_source=event.summary_source,
        topic_slug=topic.slug,
        topic_name=topic.name,
        first_seen_at=event.first_seen_at,
        last_seen_at=event.last_seen_at,
        article_count=event.article_count,
        source_count=event.source_count,
        sources=[a.source_name for a in articles],
        articles=articles,
    )


@router.get("/stats", response_model=StatsOut)
def stats(session: Session = Depends(get_session)):
    events = session.exec(select(func.count()).select_from(Event)).one()
    sources = session.exec(select(func.count()).select_from(Source)).one()
    articles = session.exec(select(func.count()).select_from(Article)).one()
    updated = session.exec(select(func.max(Event.last_seen_at))).one()
    return StatsOut(events=events, sources=sources, articles=articles, updated_at=updated)


@router.get("/search", response_model=SearchOut)
def search(
    q: str = Query(min_length=1, max_length=80),
    limit: int = Query(default=20, ge=1, le=50),
    session: Session = Depends(get_session),
):
    like = f"%{q}%"
    hits: list[SearchHit] = []

    events = session.exec(
        select(Event).where(or_(Event.title.like(like), Event.summary.like(like)))
        .order_by(Event.first_seen_at.desc()).limit(limit)
    ).all()
    for e in events:
        hits.append(
            SearchHit(kind="event", id=e.id, title=e.title, snippet=e.summary,
                      published_at=e.first_seen_at)
        )

    from .search import search_articles

    # 事件已经命中的话，它下面的文章不再重复出现
    linked: set[int] = set()
    if events:
        linked = {
            int(x)
            for x in session.exec(
                select(ArticleEvent.article_id).where(
                    ArticleEvent.event_id.in_([e.id for e in events])
                )
            ).all()
        }

    for a, s in search_articles(session, q, limit):
        if a.id in linked:
            continue
        hits.append(
            SearchHit(kind="article", id=a.id, title=a.title,
                      snippet=a.content[:160], source_name=s.name if s else "", url=a.url,
                      published_at=a.published_at)
        )

    # 事件按时间在前，文章按相关度在后：搜索里相关度比时间重要
    return SearchOut(q=q, hits=hits[:limit], total=len(hits))
