"""一句话摘要。

有 LLM 密钥就走模型；没有就退化成抽取式（取最接近事件中心那篇的首句），
保证管道离线也能跑通。降级结果显示时请标注来源，别假装是模型写的。
"""

from __future__ import annotations

import os
import re

import httpx
from sqlmodel import Session, select

from ..models import Article, ArticleEvent, Event

LLM_BASE_URL = os.getenv("ONEFOLD_LLM_BASE_URL", "https://api.deepseek.com/v1")
LLM_MODEL = os.getenv("ONEFOLD_LLM_MODEL", "deepseek-chat")
LLM_KEY = os.getenv("ONEFOLD_LLM_API_KEY", "")

PROMPT = (
    "下面是一个事件的若干篇报道。请用一句中文概括这件事，不超过 60 字。"
    "只陈述这些报道里出现过的事实，不要推断、不要评价、不要补充背景。"
    "直接输出这一句，不要加引号或前缀。"
)

_SENTENCE = re.compile(r"[^。！？!?]+[。！？!?]?")


def _extractive(session: Session, event: Event) -> str:
    rows = session.exec(
        select(Article)
        .join(ArticleEvent, ArticleEvent.article_id == Article.id)
        .where(ArticleEvent.event_id == event.id)
        .order_by(ArticleEvent.similarity.desc())
        .limit(1)
    ).all()
    if not rows:
        return event.title
    article = rows[0]
    body = (article.content or "").strip()
    first = next((s.strip() for s in _SENTENCE.findall(body) if len(s.strip()) >= 12), "")
    if not first:
        return article.title
    return first[:60]


def _llm(event: Event, articles: list[Article]) -> str:
    material = "\n\n".join(
        f"【{a.title}】\n{(a.content or '')[:800]}" for a in articles[:6]
    )
    resp = httpx.post(
        f"{LLM_BASE_URL.rstrip('/')}/chat/completions",
        headers={"Authorization": f"Bearer {LLM_KEY}"},
        json={
            "model": LLM_MODEL,
            "messages": [
                {"role": "system", "content": PROMPT},
                {"role": "user", "content": material},
            ],
            "temperature": 0.2,
            "max_tokens": 120,
        },
        timeout=60,
    )
    resp.raise_for_status()
    data = resp.json()
    return data["choices"][0]["message"]["content"].strip().strip("“”\"")


def summarize_pending(session: Session) -> dict[str, int]:
    """给还没有摘要、或刚合并了新报道的事件补摘要。"""
    events = session.exec(select(Event).where(Event.summary == "")).all()

    stats = {"summarized": 0, "llm": 0, "extractive": 0}
    for event in events:
        articles = list(
            session.exec(
                select(Article)
                .join(ArticleEvent, ArticleEvent.article_id == Article.id)
                .where(ArticleEvent.event_id == event.id)
            ).all()
        )
        if not articles:
            continue

        text = ""
        if LLM_KEY:
            try:
                text = _llm(event, articles)
                stats["llm"] += 1
            except Exception:  # noqa: BLE001 - 模型失败就降级
                text = ""
        if not text:
            text = _extractive(session, event)
            stats["extractive"] += 1

        event.summary = text
        session.add(event)
        stats["summarized"] += 1

    session.commit()
    return stats
