"""数据库连接与会话。单机 SQLite，WAL 模式。"""

from __future__ import annotations

from collections.abc import Generator

from sqlalchemy import event
from sqlmodel import Session, SQLModel, create_engine

from .config import DB_PATH

engine = create_engine(
    f"sqlite:///{DB_PATH}",
    connect_args={"check_same_thread": False},
    echo=False,
)


@event.listens_for(engine, "connect")
def _sqlite_pragmas(dbapi_connection, _record):  # noqa: ANN001
    cur = dbapi_connection.cursor()
    cur.execute("PRAGMA journal_mode=WAL")
    cur.execute("PRAGMA foreign_keys=ON")
    cur.close()


def init_db() -> None:
    from . import models  # noqa: F401  确保表已注册

    SQLModel.metadata.create_all(engine)
    _add_missing_columns()

    # 全文索引与三支同步触发器
    from .search import ensure_fts

    with Session(engine) as session:
        ensure_fts(session)


def _add_missing_columns() -> None:
    """create_all 不会给已有表加列，这里做一次轻量迁移。"""
    with engine.connect() as conn:
        existing = {row[1] for row in conn.exec_driver_sql("PRAGMA table_info('event')")}
        if existing and "summary_source" not in existing:
            conn.exec_driver_sql(
                "ALTER TABLE event ADD COLUMN summary_source VARCHAR NOT NULL DEFAULT ''"
            )
            conn.commit()


def get_session() -> Generator[Session, None, None]:
    with Session(engine) as session:
        yield session
