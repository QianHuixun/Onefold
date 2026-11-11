"""人工纠错：拆分、移动、合并事件（F14）。

算法判错是常态，这里提供三个动作：
    detach  把一篇文章从事件里拆出来，单独成为一个新事件
    move    把一篇文章挪到另一个事件
    merge   把整个事件并进另一个事件

每个动作都会重算受影响事件的计数与时间范围，保证列表页立刻正确。
"""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlmodel import Session, select

from .auth import require_admin
from .db import get_session
from .models import Article, ArticleEvent, Event

router = APIRouter(prefix="/api/admin", dependencies=[Depends(require_admin)])


class MergeIn(BaseModel):
    target_id: int


class MoveIn(BaseModel):
    event_id: int


def _when(article: Article) -> datetime:
    return article.published_at or article.fetched_at


def _recount(session: Session, event: Event) -> int:
    """按当前成员重算事件，返回剩余文章数。"""
    links = session.exec(select(ArticleEvent).where(ArticleEvent.event_id == event.id)).all()
    members = [session.get(Article, link.article_id) for link in links]
    members = [m for m in members if m is not None]

    event.article_count = len(members)
    event.source_count = len({m.source_id for m in members})
    if members:
        times = sorted(_when(m) for m in members)
        event.first_seen_at = times[0]
        event.last_seen_at = times[-1]
        event.title = max(members, key=lambda m: len(m.content)).title
    session.add(event)
    return len(members)


def _get_event(session: Session, event_id: int) -> Event:
    event = session.get(Event, event_id)
    if event is None:
        raise HTTPException(404, f"事件 {event_id} 不存在")
    return event


@router.post("/events/{event_id}/articles/{article_id}/detach", status_code=201)
def detach_article(event_id: int, article_id: int, session: Session = Depends(get_session)):
    """拆出来，单独成一个事件。"""
    event = _get_event(session, event_id)
    article = session.get(Article, article_id)
    if article is None:
        raise HTTPException(404, "文章不存在")
    link = session.get(ArticleEvent, (article_id, event_id))
    if link is None:
        raise HTTPException(400, "这篇文章不在该事件下")

    session.delete(link)
    session.commit()

    new_event = Event(
        topic_id=article.topic_id,
        title=article.title,
        summary="",
        first_seen_at=_when(article),
        last_seen_at=_when(article),
        article_count=1,
        source_count=1,
    )
    session.add(new_event)
    session.commit()
    session.add(ArticleEvent(article_id=article_id, event_id=new_event.id, similarity=1.0))
    session.commit()

    _recount(session, event)
    session.commit()
    return {"event_id": new_event.id, "detached": article_id}


@router.post("/events/{event_id}/merge")
def merge_event(event_id: int, payload: MergeIn, session: Session = Depends(get_session)):
    """把 event_id 整体并进 target_id，然后删掉自己。"""
    if event_id == payload.target_id:
        raise HTTPException(400, "不能合并到自己")

    source = _get_event(session, event_id)
    target = _get_event(session, payload.target_id)

    links = session.exec(select(ArticleEvent).where(ArticleEvent.event_id == event_id)).all()
    for link in links:
        session.delete(link)
    session.commit()

    existing = {
        l.article_id
        for l in session.exec(select(ArticleEvent).where(ArticleEvent.event_id == target.id)).all()
    }
    moved = 0
    for link in links:
        if link.article_id in existing:
            continue
        session.add(
            ArticleEvent(article_id=link.article_id, event_id=target.id, similarity=link.similarity)
        )
        moved += 1
    session.commit()

    session.delete(source)
    session.commit()

    remaining = _recount(session, target)
    session.commit()
    return {"target_id": target.id, "moved": moved, "articles": remaining}


@router.post("/events/{event_id}/articles/{article_id}/move")
def move_article(
    event_id: int, article_id: int, payload: MoveIn, session: Session = Depends(get_session)
):
    """把一篇文章挪到另一个事件（跨事件时目标必须在同一主题）。"""
    if payload.event_id == event_id:
        raise HTTPException(400, "目标事件就是当前事件")

    source = _get_event(session, event_id)
    target = _get_event(session, payload.event_id)
    article = session.get(Article, article_id)
    if article is None:
        raise HTTPException(404, "文章不存在")
    if target.topic_id != article.topic_id:
        raise HTTPException(400, "只能在同一主题内移动")

    link = session.get(ArticleEvent, (article_id, event_id))
    if link is None:
        raise HTTPException(400, "这篇文章不在该事件下")

    session.delete(link)
    session.commit()
    session.add(ArticleEvent(article_id=article_id, event_id=target.id, similarity=1.0))
    session.commit()

    _recount(session, source)
    remaining = _recount(session, target)
    session.commit()

    # 源事件空了就删掉
    if source.article_count == 0:
        session.delete(source)
        session.commit()

    return {"event_id": target.id, "articles": remaining}
