"""正文抽取：RSS 摘要不够用，要去原文页把正文拿回来。

对应 PRD 的 F03。探针结论：必须带浏览器 UA，且要允许失败降级。
"""

from __future__ import annotations

import httpx
import trafilatura
from sqlmodel import Session, select

from ..config import FETCH_TIMEOUT, USER_AGENT
from ..models import Article

MIN_CHARS = 200


def fetch_text(url: str) -> str:
    resp = httpx.get(
        url,
        headers={
            "User-Agent": USER_AGENT,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        },
        timeout=FETCH_TIMEOUT,
        follow_redirects=True,
    )
    resp.raise_for_status()
    text = trafilatura.extract(
        resp.text, url=url, include_comments=False, include_tables=False
    )
    return (text or "").strip()


def extract_pending(session: Session, limit: int = 50) -> dict[str, int]:
    """对仍有 RSS 摘要但正文过短的文章，回原文抓一次。"""
    articles = session.exec(
        select(Article).where(Article.status == "ok").order_by(Article.id.desc()).limit(limit)
    ).all()

    stats = {"tried": 0, "ok": 0, "short": 0, "failed": 0}
    for article in articles:
        if article.content_length >= MIN_CHARS:
            continue
        stats["tried"] += 1
        try:
            text = fetch_text(article.url)
        except Exception:  # noqa: BLE001 - 单篇失败不影响整批
            stats["failed"] += 1
            continue
        if len(text) < MIN_CHARS:
            stats["short"] += 1
            continue
        article.content = text
        article.content_length = len(text)
        session.add(article)
        stats["ok"] += 1

    session.commit()
    return stats
