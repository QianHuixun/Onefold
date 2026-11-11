"""阈值实验台（F13）。

三件事：
    1. 生成候选文章对，供人工标注「是否同一事件」
    2. 按给定阈值算精确率 / 召回率 / F1
    3. 扫一遍阈值，给出曲线和最佳 F1 点

论文第五章的主图就来自这里。
"""

from __future__ import annotations

import json
from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlmodel import Session, func, select

from .auth import require_admin
from .db import get_session
from .models import Article, EvalPair, Source, Topic
from .pipeline.vectors import TfidfSpace, cosine, tokens

router = APIRouter(prefix="/api/admin/eval", dependencies=[Depends(require_admin)])

THRESHOLDS = [round(0.05 * i, 2) for i in range(1, 20)]  # 0.05 … 0.95


class PairOut(BaseModel):
    id: int
    similarity: float
    label: int | None
    auto: bool
    a_title: str
    a_source: str
    a_time: str | None
    a_excerpt: str
    b_title: str
    b_source: str
    b_time: str | None
    b_excerpt: str


class SummaryOut(BaseModel):
    total: int
    labeled: int
    auto_labeled: int
    positives: int
    negatives: int
    topics: list[str]


class LabelIn(BaseModel):
    label: int

    def validate(self) -> None:
        if self.label not in (0, 1):
            raise HTTPException(400, "label 只能是 0 或 1")


class MetricPoint(BaseModel):
    threshold: float
    precision: float
    recall: float
    f1: float
    tp: int
    fp: int
    fn: int


class MetricsOut(BaseModel):
    points: list[MetricPoint]
    best_threshold: float | None
    best_f1: float
    labeled: int
    positives: int


def _excerpt(article: Article) -> str:
    text = (article.content or "").replace("\n", " ")
    return text[:180]


@router.get("/summary", response_model=SummaryOut)
def summary(session: Session = Depends(get_session)):
    total = session.exec(select(func.count()).select_from(EvalPair)).one()
    labeled = session.exec(
        select(func.count()).select_from(EvalPair).where(EvalPair.label.is_not(None))
    ).one()
    auto_labeled = session.exec(
        select(func.count()).select_from(EvalPair).where(EvalPair.auto == True)  # noqa: E712
    ).one()
    positives = session.exec(
        select(func.count()).select_from(EvalPair).where(EvalPair.label == 1)
    ).one()
    topics = [t.name for t in session.exec(select(Topic)).all()]
    return SummaryOut(
        total=int(total),
        labeled=int(labeled),
        auto_labeled=int(auto_labeled),
        positives=int(positives),
        negatives=int(labeled) - int(positives),
        topics=topics,
    )


@router.get("/pairs", response_model=list[PairOut])
def list_pairs(
    limit: int = Query(default=10, ge=1, le=50),
    only_unlabeled: bool = True,
    session: Session = Depends(get_session),
):
    stmt = select(EvalPair)
    if only_unlabeled:
        stmt = stmt.where(EvalPair.label.is_(None))
    pairs = session.exec(stmt.order_by(EvalPair.similarity.desc()).limit(limit)).all()

    out: list[PairOut] = []
    for pair in pairs:
        a = session.get(Article, pair.article_a)
        b = session.get(Article, pair.article_b)
        if a is None or b is None:
            continue
        sa = session.get(Source, a.source_id)
        sb = session.get(Source, b.source_id)
        out.append(
            PairOut(
                id=pair.id,
                similarity=round(pair.similarity, 3),
                label=pair.label,
                auto=pair.auto,
                a_title=a.title,
                a_source=sa.name if sa else "",
                a_time=a.published_at.isoformat() if a.published_at else None,
                a_excerpt=_excerpt(a),
                b_title=b.title,
                b_source=sb.name if sb else "",
                b_time=b.published_at.isoformat() if b.published_at else None,
                b_excerpt=_excerpt(b),
            )
        )
    return out


@router.post("/pairs/{pair_id}", response_model=PairOut | None)
def label_pair(pair_id: int, payload: LabelIn, session: Session = Depends(get_session)):
    payload.validate()
    pair = session.get(EvalPair, pair_id)
    if pair is None:
        raise HTTPException(404, "这一对不存在")
    pair.label = payload.label
    pair.auto = False
    session.add(pair)
    session.commit()
    return None


@router.get("/metrics", response_model=MetricsOut)
def metrics(session: Session = Depends(get_session)):
    pairs = session.exec(
        select(EvalPair).where(EvalPair.label.is_not(None))
    ).all()

    positives = sum(1 for p in pairs if p.label == 1)
    points: list[MetricPoint] = []
    for threshold in THRESHOLDS:
        tp = sum(1 for p in pairs if p.label == 1 and p.similarity >= threshold)
        fp = sum(1 for p in pairs if p.label == 0 and p.similarity >= threshold)
        fn = positives - tp
        precision = tp / (tp + fp) if tp + fp else 0.0
        recall = tp / (tp + fn) if tp + fn else 0.0
        f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
        points.append(
            MetricPoint(
                threshold=threshold,
                precision=round(precision, 4),
                recall=round(recall, 4),
                f1=round(f1, 4),
                tp=tp,
                fp=fp,
                fn=fn,
            )
        )

    best = max(points, key=lambda p: p.f1) if points else None
    return MetricsOut(
        points=points,
        best_threshold=best.threshold if best else None,
        best_f1=best.f1 if best else 0.0,
        labeled=len(pairs),
        positives=positives,
    )


# ── 候选对生成（离线跑，不在请求里做）────────────────────────

def build_pairs(session: Session, max_pairs: int = 300, min_similarity: float = 0.08) -> dict[str, int]:
    articles = list(
        session.exec(select(Article).where(Article.status.in_(("ok", "eval")))).all()
    )
    if len(articles) < 2:
        return {"candidates": 0, "created": 0}

    space = TfidfSpace([tokens(f"{a.title} {a.content[:300]}") for a in articles])
    vectors = {a.id: space.vector(f"{a.title} {a.content[:300]}") for a in articles}

    existing = {
        (min(p.article_a, p.article_b), max(p.article_a, p.article_b))
        for p in session.exec(select(EvalPair)).all()
    }

    candidates: list[tuple[float, Article, Article]] = []
    for i, a in enumerate(articles):
        for b in articles[i + 1 :]:
            if a.topic_id != b.topic_id:
                continue
            ta, tb = a.published_at or a.fetched_at, b.published_at or b.fetched_at
            if abs((ta - tb).total_seconds()) > timedelta(hours=48).total_seconds():
                continue
            sim = cosine(vectors[a.id], vectors[b.id])
            if sim >= min_similarity:
                candidates.append((sim, a, b))

    candidates.sort(key=lambda x: -x[0])
    created = 0
    for sim, a, b in candidates[:max_pairs]:
        key = (min(a.id, b.id), max(a.id, b.id))
        if key in existing:
            continue
        session.add(
            EvalPair(
                topic_id=a.topic_id,
                article_a=key[0],
                article_b=key[1],
                similarity=round(sim, 4),
            )
        )
        existing.add(key)
        created += 1

    session.commit()
    return {"candidates": len(candidates), "created": created}


def autolabel(session: Session, threshold: float = 0.55) -> int:
    """按标题词重叠度做自动预标注，只用于占位，必须人工复核。

    刻意不按相似度本身标注，否则曲线是自己证明自己。
    """
    def token_set(article: Article) -> set[str]:
        return set(tokens(article.title))

    pairs = session.exec(select(EvalPair).where(EvalPair.label.is_(None))).all()
    labeled = 0
    for pair in pairs:
        a = session.get(Article, pair.article_a)
        b = session.get(Article, pair.article_b)
        if a is None or b is None:
            continue
        ta, tb = token_set(a), token_set(b)
        if not ta or not tb:
            continue
        overlap = len(ta & tb) / len(ta | tb)
        pair.label = 1 if overlap >= threshold else 0
        pair.auto = True
        session.add(pair)
        labeled += 1
    session.commit()
    return labeled


def export_metrics(session: Session) -> str:
    """把曲线导出成 JSON，方便贴进论文。"""
    data = metrics(session).model_dump()
    return json.dumps(data, ensure_ascii=False, indent=2)


# ── 评测夹具：造已知答案的重复稿，给实验台做冒烟测试 ─────────────

_SYNONYMS = [("宣布", "发布"), ("发布", "推出"), ("收购", "买下"), ("推出", "上线")]


def _variant_title(title: str) -> str:
    for old, new in _SYNONYMS:
        if old in title:
            return title.replace(old, new, 1)
    return "快讯｜" + title


def make_fixture(session: Session, count: int = 12) -> dict[str, int]:
    """从真实文章里挑几篇，各造一条「另一家媒体的同题报道」。

    这些文章 status=eval，不进聚类、不上首页，只参与标注与评估。
    """
    from datetime import timedelta

    from .models import Source

    originals = list(
        session.exec(
            select(Article).where(Article.status == "ok").order_by(Article.fetched_at.desc()).limit(count)
        ).all()
    )
    created = 0
    for article in originals:
        if session.exec(select(Article).where(Article.url_hash == f"eval-{article.id}")).first():
            continue
        others = session.exec(
            select(Source).where(Source.topic_id == article.topic_id, Source.id != article.source_id)
        ).all()
        if not others:
            continue

        dup = Article(
            topic_id=article.topic_id,
            source_id=others[0].id,
            title=_variant_title(article.title),
            url=f"eval://{article.id}",
            url_hash=f"eval-{article.id}",
            content=article.content[:1200],
            content_length=min(article.content_length, 1200),
            published_at=(article.published_at or article.fetched_at) + timedelta(minutes=7),
            status="eval",
        )
        session.add(dup)
        session.commit()

        a, b = sorted((article.id, dup.id))
        sim = cosine(
            TfidfSpace([tokens(article.title)]).vector(article.title),
            TfidfSpace([tokens(article.title)]).vector(dup.title),
        ) if False else None  # 占位，真实相似度由 build_pairs 统一计算

        session.add(
            EvalPair(
                topic_id=article.topic_id,
                article_a=a,
                article_b=b,
                similarity=0.0,
                label=1,
                auto=True,
            )
        )
        created += 1

    session.commit()

    # 用统一空间重算全部分布的相似度，避免夹具与正式数据口径不一致
    _recompute_similarities(session)
    return {"created": created}


def _recompute_similarities(session: Session) -> None:
    articles = list(
        session.exec(select(Article).where(Article.status.in_(("ok", "eval")))).all()
    )
    space = TfidfSpace([tokens(f"{a.title} {a.content[:300]}") for a in articles])
    vectors = {a.id: space.vector(f"{a.title} {a.content[:300]}") for a in articles}
    for pair in session.exec(select(EvalPair)).all():
        va, vb = vectors.get(pair.article_a), vectors.get(pair.article_b)
        if va and vb:
            pair.similarity = round(cosine(va, vb), 4)
            session.add(pair)
    session.commit()
