"""中文全文检索（F09）。

SQLite 的 FTS5 不带中文分词，所以索引列存的是 jieba 预分词后的字符串
（`article.search_text`），查询时同样先分词，再拼成 FTS5 的 MATCH 表达式。

为了不重复存储正文，用的是 external content 表：FTS 只存倒排索引，
原文还在 `article` 里。三支触发器负责保持同步。
"""

from __future__ import annotations

from sqlalchemy import text
from sqlmodel import Session

from .models import Article, Source

FTS_TABLE = "article_fts"

DDL = [
    f"""
    CREATE VIRTUAL TABLE IF NOT EXISTS {FTS_TABLE} USING fts5(
        search_text,
        content='article',
        content_rowid='id',
        tokenize='unicode61'
    )
    """,
    f"""
    CREATE TRIGGER IF NOT EXISTS article_fts_ai AFTER INSERT ON article BEGIN
        INSERT INTO {FTS_TABLE}(rowid, search_text) VALUES (new.id, new.search_text);
    END
    """,
    f"""
    CREATE TRIGGER IF NOT EXISTS article_fts_ad AFTER DELETE ON article BEGIN
        INSERT INTO {FTS_TABLE}({FTS_TABLE}, rowid, search_text)
        VALUES ('delete', old.id, old.search_text);
    END
    """,
    f"""
    CREATE TRIGGER IF NOT EXISTS article_fts_au AFTER UPDATE OF search_text ON article BEGIN
        INSERT INTO {FTS_TABLE}({FTS_TABLE}, rowid, search_text)
        VALUES ('delete', old.id, old.search_text);
        INSERT INTO {FTS_TABLE}(rowid, search_text) VALUES (new.id, new.search_text);
    END
    """,
]


def ensure_fts(session: Session) -> None:
    for statement in DDL:
        session.execute(text(statement))
    session.commit()


def reindex(session: Session) -> int:
    """全量重建索引，导完历史数据或改了分词口径之后跑一次。"""
    ensure_fts(session)
    session.execute(text(f"INSERT INTO {FTS_TABLE}({FTS_TABLE}) VALUES ('rebuild')"))
    session.commit()
    return int(session.execute(text(f"SELECT count(*) FROM {FTS_TABLE}")).one()[0])


def _query_expression(query: str) -> str:
    """把用户输入变成 FTS5 的 MATCH 表达式：逐词加引号，词之间是 AND。"""
    from .pipeline.vectors import tokens

    words = [w for w in tokens(query) if w.strip()]
    if not words:
        return ""
    # 双引号包住每个词，避免 - * : 等被当成 FTS5 语法
    return " ".join('"' + w.replace('"', '""') + '"' for w in words)


def search_articles(
    session: Session, query: str, limit: int = 20
) -> list[tuple[Article, Source | None]]:
    """优先走 FTS5；表达式为空或查询报错时退回 LIKE。"""
    expression = _query_expression(query)
    if expression:
        try:
            rows = session.execute(
                text(
                    f"""
                    SELECT rowid FROM {FTS_TABLE}
                    WHERE {FTS_TABLE} MATCH :expr
                    ORDER BY bm25({FTS_TABLE})
                    LIMIT :limit
                    """
                ),
                {"expr": expression, "limit": limit},
            ).all()
            ids = [int(r[0]) for r in rows]
            if ids:
                found = (
                    session.query(Article)
                    .filter(Article.id.in_(ids), Article.status == "ok")
                    .all()
                )
                by_id = {a.id: a for a in found}
                sources = {
                    s.id: s
                    for s in session.query(Source)
                    .filter(Source.id.in_({a.source_id for a in found}))
                    .all()
                }
                ordered = [(by_id[i], sources.get(by_id[i].source_id)) for i in ids if i in by_id]
                if ordered:
                    return ordered
        except Exception:  # noqa: BLE001 - 索引没建好时不要连累搜索
            pass

    like = f"%{query}%"
    rows = (
        session.query(Article, Source)
        .join(Source, Source.id == Article.source_id, isouter=True)
        .filter(Article.title.like(like), Article.status == "ok")
        .order_by(Article.published_at.desc())
        .limit(limit)
        .all()
    )
    return [(a, s) for a, s in rows]
