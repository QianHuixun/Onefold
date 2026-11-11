"""文章级去重：同一篇稿子被各家转载，只留一条。

对应 PRD 的 F04：SimHash 64 位指纹 + 汉明距离。
"""

from __future__ import annotations

from sqlmodel import Session, select

from ..models import Article
from .vectors import hamming, simhash64, to_signed


def _fingerprint(article: Article) -> int:
    return simhash64(f"{article.title} {article.content[:2000]}")


def dedup_pending(session: Session, max_hamming: int = 3) -> dict[str, int]:
    """给还没算指纹的文章算 SimHash，与同主题已入库文章比对。"""
    pending = session.exec(
        select(Article).where(Article.status == "ok", Article.simhash.is_(None))  # type: ignore[union-attr]
    ).all()

    known = session.exec(
        select(Article).where(Article.simhash.is_not(None), Article.status == "ok")  # type: ignore[union-attr]
    ).all()

    stats = {"checked": 0, "dup": 0, "kept": 0}
    for article in pending:
        fingerprint = _fingerprint(article)
        article.simhash = to_signed(fingerprint)
        stats["checked"] += 1

        duplicate = False
        for other in known:
            if other.id == article.id or other.topic_id != article.topic_id:
                continue
            if other.simhash is not None and hamming(fingerprint, other.simhash) <= max_hamming:
                duplicate = True
                break

        if duplicate:
            article.status = "dup"
            stats["dup"] += 1
        else:
            stats["kept"] += 1
            known.append(article)

        session.add(article)

    session.commit()
    return stats
