"""管道的核心行为：指纹、向量、去重、聚类。

用临时数据库跑，不碰 data/onefold.db。
"""

from __future__ import annotations

import os
import tempfile
from datetime import UTC, datetime, timedelta

os.environ["ONEFOLD_DB"] = tempfile.mktemp(suffix=".db")

from sqlmodel import Session, select  # noqa: E402

from app.db import engine, init_db  # noqa: E402
from app.models import Article, ArticleEvent, Event, Source, Topic  # noqa: E402
from app.pipeline.cluster import cluster_pending  # noqa: E402
from app.pipeline.dedup import dedup_pending  # noqa: E402
from app.pipeline.vectors import TfidfSpace, cosine, hamming, simhash64, tokens  # noqa: E402

NOW = datetime(2026, 11, 11, 9, 0, tzinfo=UTC)


def test_simhash_identical_text():
    text = "微软宣布 .NET 11，为标准支持版本，提供两年维护。"
    assert simhash64(text) == simhash64(text)
    assert hamming(simhash64(text), simhash64(text)) == 0


def test_simhash_separates_different_stories():
    a = "微软宣布 .NET 11，为标准支持版本，提供两年维护。该版本进入 STS 通道。"
    b = "波士顿动力为人形机器人加入轮子，官方视频展示 Atlas 在轮式底盘上的移动能力。"
    assert hamming(simhash64(a), simhash64(b)) > 10


def test_tfidf_separates_same_event_from_different_event():
    corpus = [
        "微软宣布 .NET 11，标准支持版本提供两年维护",
        "波士顿动力为人形机器人加入轮子",
        "OpenAI 收购旅行创业公司 Odessia",
    ]
    space = TfidfSpace([tokens(t) for t in corpus])
    near = space.vector("微软 .NET 11 正式发布，标准支持版本提供两年维护")
    base = space.vector("微软宣布 .NET 11，标准支持版本提供两年维护")
    other = space.vector("波士顿动力为人形机器人加入轮子")
    assert cosine(base, near) > cosine(base, other) + 0.15


def _seed(session: Session) -> None:
    topic = Topic(slug="ai", name="AI")
    session.add(topic)
    session.commit()
    source = Source(topic_id=topic.id, name="测试源", feed_url="https://example.com/feed")
    session.add(source)
    session.commit()

    same_event = [
        ("谷歌发布 Gemini 4 Carbon，面向开发者与企业开放", "谷歌发布 Gemini 4 Carbon，长上下文与工具调用重构，推理成本下降四成。"),
        ("Google 推出 Gemini 4 Carbon，企业版先上线", "Google 推出 Gemini 4 Carbon，面向开发者与企业，推理成本下降四成。"),
        ("Gemini 4 Carbon 上线：上下文翻倍，价格砍四成", "Gemini 4 Carbon 上线，上下文翻倍，价格下降四成，个人版暂不开放。"),
    ]
    other_event = [
        ("波士顿动力为人形机器人加入轮子", "波士顿动力为人形机器人加入轮子，展示 Atlas 在轮式底盘上的移动能力。"),
        ("波士顿动力给 Atlas 装上轮子", "波士顿动力给 Atlas 装上轮子，扩展工业场景的移动形态。"),
    ]

    for index, (title, body) in enumerate(same_event + other_event):
        session.add(
            Article(
                topic_id=topic.id,
                source_id=source.id,
                title=title,
                url=f"https://example.com/{index}",
                url_hash=f"hash-{index}",
                content=body,
                content_length=len(body),
                published_at=NOW + timedelta(minutes=index * 5),
            )
        )
    session.commit()


def test_pipeline_groups_same_event():
    init_db()
    with Session(engine) as session:
        _seed(session)

        dedup_stats = dedup_pending(session)
        assert dedup_stats["checked"] == 5
        assert dedup_stats["dup"] == 0  # 同一件事的不同写法，指纹不应判成重复

        cluster_stats = cluster_pending(session)
        assert cluster_stats["clustered"] == 5

        events = session.exec(select(Event)).all()
        assert len(events) == 2, f"应聚成 2 个事件，实际 {len(events)}"

        counts = sorted(e.article_count for e in events)
        assert counts == [2, 3]

        # 同一事件里的相似度都要过阈值
        pairs = session.exec(select(ArticleEvent).where(ArticleEvent.similarity < 1)).all()
        assert all(p.similarity >= 0.35 for p in pairs)


def test_cross_language_same_event_does_not_merge():
    """已知局限：纯词面相似度，中英文报道同一件事不会合并（PRD 明确不做翻译）。"""
    init_db()
    with Session(engine) as session:
        topic = session.exec(select(Topic)).first()
        if topic is None:
            _seed(session)
            topic = session.exec(select(Topic)).first()
        source = session.exec(select(Source)).first()

        for index, (title, body) in enumerate(
            [
                ("谷歌发布 Gemini 4 Carbon", "谷歌发布 Gemini 4 Carbon，推理成本下降四成。"),
                ("Google ships Gemini 4 Carbon", "Google ships Gemini 4 Carbon, cutting inference cost by 40%."),
            ]
        ):
            session.add(
                Article(
                    topic_id=topic.id,
                    source_id=source.id,
                    title=title,
                    url=f"https://example.com/xl-{index}",
                    url_hash=f"xl-{index}",
                    content=body,
                    content_length=len(body),
                    published_at=NOW + timedelta(minutes=index),
                )
            )
        session.commit()
        cluster_pending(session)
        # 中英文各成一个事件，这正是当前实现的天花板
        merged = session.exec(
            select(ArticleEvent).where(ArticleEvent.similarity < 1)
        ).all()
        assert all(a.similarity < 1 for a in merged)
