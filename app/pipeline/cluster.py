"""事件聚类：把「同一件事」的多篇报道归到一个事件里。

对应 PRD 的 F05：标题 + 首段向量，同主题、时间窗内找最近的事件中心。
阈值与时间窗由 Topic.config_json 控制，换主题不用改代码。
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta

from sqlmodel import Session, select

from ..models import Article, ArticleEvent, Event, Topic
from .vectors import TfidfSpace, centroid, cosine, tokens

DEFAULT_CONFIG = {
    "cosine_threshold": 0.35,
    "time_window_hours": 24,
}


def topic_config(topic: Topic) -> dict:
    try:
        raw = json.loads(topic.config_json or "{}")
    except json.JSONDecodeError:
        raw = {}
    return {**DEFAULT_CONFIG, **{k: v for k, v in raw.items() if k in DEFAULT_CONFIG}}


def _text(article: Article) -> str:
    return f"{article.title} {article.content[:300]}"


def _when(article: Article) -> datetime:
    return article.published_at or article.fetched_at


def _members(session: Session, event_id: int) -> list[Article]:
    rows = session.exec(
        select(Article)
        .join(ArticleEvent, ArticleEvent.article_id == Article.id)
        .where(ArticleEvent.event_id == event_id)
    ).all()
    return list(rows)


def cluster_pending(session: Session) -> dict[str, int]:
    assigned = {int(x) for x in session.exec(select(ArticleEvent.article_id)).all()}

    articles = list(session.exec(select(Article).where(Article.status == "ok")).all())
    pending = [a for a in articles if a.id not in assigned]

    # IDF 在整批语料上算一次，保证每次运行的判定可复现
    space = TfidfSpace([tokens(_text(a)) for a in articles])
    vectors = {a.id: space.vector(_text(a)) for a in articles}

    topics = {t.id: t for t in session.exec(select(Topic)).all()}
    stats = {"clustered": 0, "new_events": 0, "joined": 0}
    touched: set[int] = set()

    for article in pending:
        topic = topics.get(article.topic_id)
        if topic is None:
            continue
        cfg = topic_config(topic)
        window = timedelta(hours=cfg["time_window_hours"])
        threshold = float(cfg["cosine_threshold"])
        moment = _when(article)
        vector = vectors[article.id]

        best_sim, best_event = -1.0, None
        for event in session.exec(select(Event).where(Event.topic_id == article.topic_id)).all():
            gap = abs(event.last_seen_at.replace(tzinfo=None) - moment.replace(tzinfo=None))
            if gap > window:
                continue
            member_vectors = [vectors[m.id] for m in _members(session, event.id) if m.id in vectors]
            centre = centroid(member_vectors)
            if not centre:
                continue
            sim = cosine(vector, centre)
            if sim > best_sim:
                best_sim, best_event = sim, event

        if best_event is not None and best_sim >= threshold:
            session.add(
                ArticleEvent(
                    article_id=article.id, event_id=best_event.id, similarity=round(best_sim, 4)
                )
            )
            stats["joined"] += 1
            touched.add(best_event.id)
        else:
            event = Event(
                topic_id=article.topic_id,
                title=article.title,
                summary="",
                first_seen_at=moment,
                last_seen_at=moment,
                article_count=0,
                source_count=0,
            )
            session.add(event)
            session.commit()
            session.add(ArticleEvent(article_id=article.id, event_id=event.id, similarity=1.0))
            stats["new_events"] += 1
            touched.add(event.id)

        stats["clustered"] += 1
        session.commit()

    for event_id in touched:
        event = session.get(Event, event_id)
        if event is None:
            continue
        members = _members(session, event_id)
        event.article_count = len(members)
        event.source_count = len({m.source_id for m in members})
        if members:
            times = sorted(_when(m) for m in members)
            event.first_seen_at = times[0]
            event.last_seen_at = times[-1]
            event.title = max(members, key=lambda m: len(m.content)).title
        session.add(event)

    session.commit()
    stats["touched_events"] = len(touched)
    return stats
