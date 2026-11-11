"""一句话摘要：调用 DeepSeek（OpenAI 兼容接口）。

没有密钥或调用失败时降级为抽取式，并把来源写进 summary_source，
前端据此显示「AI 摘要」还是「抽取式摘要」，不冒充。
"""

from __future__ import annotations

import re

import httpx
from sqlmodel import Session, select

from ..config import (
    LLM_API_KEY,
    LLM_BASE_URL,
    LLM_MODEL,
    LLM_PRICE_IN,
    LLM_PRICE_OUT,
    LLM_TIMEOUT,
)
from ..models import Article, ArticleEvent, Event

SYSTEM_PROMPT = (
    "你是新闻编辑，负责把同一事件的多篇报道压缩成一句中文摘要。要求：\n"
    "1. 不超过 60 字，只写一句话；\n"
    "2. 只陈述材料里出现过的事实，不推断、不评价、不补充背景；\n"
    "3. 保留关键实体（公司、产品、数字）；\n"
    "4. 直接输出这一句，不要引号、不要前缀、不要「据报道」。"
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
    body = (rows[0].content or "").strip()
    first = next((s.strip() for s in _SENTENCE.findall(body) if len(s.strip()) >= 12), "")
    return (first or rows[0].title)[:60]


def _material(articles: list[Article]) -> str:
    return "\n\n".join(f"【{a.title}】\n{(a.content or '')[:700]}" for a in articles[:6])


def _call_llm(material: str) -> tuple[str, dict[str, int]]:
    resp = httpx.post(
        f"{LLM_BASE_URL.rstrip('/')}/chat/completions",
        headers={"Authorization": f"Bearer {LLM_API_KEY}", "Content-Type": "application/json"},
        json={
            "model": LLM_MODEL,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": material},
            ],
            "temperature": 0.2,
            "max_tokens": 150,
        },
        timeout=LLM_TIMEOUT,
    )
    resp.raise_for_status()
    payload = resp.json()
    text = payload["choices"][0]["message"]["content"].strip().strip("“”\"'")
    usage = payload.get("usage", {}) or {}
    return text, {
        "in": int(usage.get("prompt_tokens", 0)),
        "out": int(usage.get("completion_tokens", 0)),
    }


def estimate_cost(tokens_in: int, tokens_out: int) -> float:
    return tokens_in / 1e6 * LLM_PRICE_IN + tokens_out / 1e6 * LLM_PRICE_OUT


def summarize_pending(session: Session, force: bool = False) -> dict[str, float]:
    """给没有摘要的事件补摘要；force=True 时重写全部非种子事件。"""
    query = select(Event)
    if not force:
        query = query.where(Event.summary == "")
    events = session.exec(query).all()

    stats = {"events": 0, "llm": 0, "extractive": 0, "tokens_in": 0, "tokens_out": 0, "cost": 0.0}

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

        text, source = "", "extractive"
        if LLM_API_KEY:
            try:
                text, usage = _call_llm(_material(articles))
                source = LLM_MODEL
                stats["tokens_in"] += usage["in"]
                stats["tokens_out"] += usage["out"]
                stats["llm"] += 1
            except Exception as exc:  # noqa: BLE001 - 模型失败就降级，不中断整批
                print(f"  事件 {event.id} 调用失败：{type(exc).__name__}")
                text = ""

        if not text:
            text = _extractive(session, event)
            stats["extractive"] += 1

        event.summary = text
        event.summary_source = source
        session.add(event)
        stats["events"] += 1

    session.commit()
    stats["cost"] = round(estimate_cost(int(stats["tokens_in"]), int(stats["tokens_out"])), 4)
    return stats
