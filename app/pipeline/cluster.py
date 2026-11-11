"""事件聚类：把「同一件事」的多篇报道归到一个事件里。

对应 PRD 的 F05：标题 + 首段向量，同主题、时间窗内找最近的事件中心。
阈值与时间窗由 Topic.config_json 控制，换主题不用改代码。
"""

from __future__ import annotations

import json
import re
from datetime import datetime, timedelta

from sqlmodel import Session, select

from ..models import Article, ArticleEvent, Event, Topic
from ..config import LLM_API_KEY
from .vectors import TfidfSpace, centroid, cosine, tokens

DEFAULT_CONFIG = {
    # 直接判定的高置信阈值
    "cosine_threshold": 0.50,
    # 低于它就不再看；落在 [recall, cosine] 之间的灰色地带交给大模型裁决
    "recall_threshold": 0.18,
    "time_window_hours": 24,
}


def topic_config(topic: Topic) -> dict:
    try:
        raw = json.loads(topic.config_json or "{}")
    except json.JSONDecodeError:
        raw = {}
    return {**DEFAULT_CONFIG, **{k: v for k, v in raw.items() if k in DEFAULT_CONFIG}}


def _text(article: Article) -> str:
    """标题权重 ×3，正文只取前 80 字。

    正文一长就会混进站点模板（作者署名、往期推荐、"关注公众号"），
    同源文章之间因此虚高——实测不加限制时两篇无关的 InfoQ 文章能到 0.67。
    标题是最浓缩的语义单元，加权后同源不同事的相似度压到 0.42 以下。
    """
    return f"{article.title * 3} {article.content[:80]}"


def _when(article: Article) -> datetime:
    return article.published_at or article.fetched_at


def _members(session: Session, event_id: int) -> list[Article]:
    rows = session.exec(
        select(Article)
        .join(ArticleEvent, ArticleEvent.article_id == Article.id)
        .where(ArticleEvent.event_id == event_id)
    ).all()
    return list(rows)


DIGEST_PATTERN = re.compile(r"早报|晚报|午报|日报|周报|速览|要闻|一周回顾|新闻集锦")


def _is_digest(article: Article) -> bool:
    """资讯汇总类的稿子一次覆盖很多件事，不应该并进任何单一事件。"""
    return bool(DIGEST_PATTERN.search(article.title))


def _llm_same_event(a: Article, b: Article) -> bool | None:
    """灰色地带交给模型判定。返回 None 表示没法判断（无密钥或调用失败）。"""
    if not LLM_API_KEY:
        return None

    import httpx

    from ..config import LLM_BASE_URL, LLM_MODEL, LLM_TIMEOUT

    prompt = (
        "判断下面两条新闻标题及摘要是否在讲同一件事（同一事件、同一主体、同一动作）。"
        "同一件事的不同措辞算「是」；相关但不同的事（同一公司不同产品、同一主题不同事件）算「否」。"
        "如果其中有一条是资讯汇总（早报、晚报、速览、周报），一律回答「否」。"
        "只回答一个字：是 或 否。"
    )
    material = (
        f"A：{a.title}\n{a.content[:120]}\n\nB：{b.title}\n{b.content[:120]}"
    )
    try:
        resp = httpx.post(
            f"{LLM_BASE_URL.rstrip('/')}/chat/completions",
            headers={"Authorization": f"Bearer {LLM_API_KEY}"},
            json={
                "model": LLM_MODEL,
                "messages": [
                    {"role": "system", "content": prompt},
                    {"role": "user", "content": material},
                ],
                "temperature": 0,
                "max_tokens": 8,
            },
            timeout=LLM_TIMEOUT,
        )
        resp.raise_for_status()
        answer = resp.json()["choices"][0]["message"]["content"].strip()
        return answer.startswith("是")
    except Exception:  # noqa: BLE001
        return None


def cluster_pending(session: Session) -> dict[str, int]:
    assigned = {int(x) for x in session.exec(select(ArticleEvent.article_id)).all()}

    articles = list(session.exec(select(Article).where(Article.status == "ok")).all())
    pending = [a for a in articles if a.id not in assigned]

    # IDF 在整批语料上算一次，保证每次运行的判定可复现
    space = TfidfSpace([tokens(_text(a)) for a in articles])
    vectors = {a.id: space.vector(_text(a)) for a in articles}

    topics = {t.id: t for t in session.exec(select(Topic)).all()}
    stats = {"clustered": 0, "new_events": 0, "joined": 0, "llm_checked": 0, "llm_joined": 0}
    touched: set[int] = set()

    for article in pending:
        topic = topics.get(article.topic_id)
        if topic is None:
            continue
        cfg = topic_config(topic)
        window = timedelta(hours=cfg["time_window_hours"])
        threshold = float(cfg["cosine_threshold"])
        recall = float(cfg["recall_threshold"])
        moment = _when(article)
        vector = vectors[article.id]

        scored: list[tuple[float, Event]] = []
        for event in session.exec(select(Event).where(Event.topic_id == article.topic_id)).all():
            gap = abs(event.last_seen_at.replace(tzinfo=None) - moment.replace(tzinfo=None))
            if gap > window:
                continue
            member_vectors = [vectors[m.id] for m in _members(session, event.id) if m.id in vectors]
            centre = centroid(member_vectors)
            if not centre:
                continue
            scored.append((cosine(vector, centre), event))
        if _is_digest(article):
            scored = []
        scored.sort(key=lambda x: -x[0])

        best_sim, best_event = scored[0] if scored else (-1.0, None)
        accept = best_event is not None and best_sim >= threshold

        # 灰色地带：词面像但不够确定，请模型裁决，最多看三个候选
        if not accept and best_event is not None and best_sim >= recall:
            for sim, event in scored[:1]:
                if sim < recall:
                    break
                members = _members(session, event.id)
                if not members:
                    continue
                stats["llm_checked"] += 1
                anchor = max(members, key=lambda m: len(m.content))
                if _llm_same_event(article, anchor):
                    best_sim, best_event = sim, event
                    accept = True
                    stats["llm_joined"] += 1
                    break

        if accept:
            assert best_event is not None
            session.add(
                ArticleEvent(
                    article_id=article.id,
                    event_id=best_event.id,
                    similarity=round(best_sim, 4),
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
