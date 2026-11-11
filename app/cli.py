"""命令行入口：初始化、灌示例数据、抓取。

    python -m app.cli init
    python -m app.cli seed [--force]
    python -m app.cli fetch [--limit 10]
"""

from __future__ import annotations

import argparse
import hashlib
from datetime import UTC, datetime, timedelta

import feedparser
import httpx
from sqlalchemy import delete
from sqlmodel import Session, select

from .config import FETCH_TIMEOUT, USER_AGENT
from .db import engine, init_db
from .models import Article, ArticleEvent, Event, FetchLog, Source, Topic, utcnow

LOCAL_TZ = datetime.now().astimezone().tzinfo

TOPICS = [
    ("ai", "AI", "模型、产品、政策与算力"),
    ("tech", "综合科技", "芯片、硬件、机器人与互联网"),
]

SOURCES = [
    ("量子位", "https://www.qbitai.com/feed", "ai"),
    ("InfoQ 中文", "https://www.infoq.cn/feed", "ai"),
    ("TechCrunch", "https://techcrunch.com/feed/", "ai"),
    ("爱范儿", "https://www.ifanr.com/feed", "tech"),
    ("Solidot", "https://www.solidot.org/index.rss", "tech"),
]

# (来源, 原标题, 与事件中心的相似度)
DEMO_EVENTS = [
    {
        "topic": "ai",
        "when": (0, 8, 20),
        "title": "谷歌发布 Gemini 4 Carbon，面向开发者与企业开放",
        "summary": "谷歌发布 Gemini 4 Carbon，该模型在长上下文与工具调用上做了重构，"
                   "官方称推理成本下降四成，本轮面向开发者与企业开放，个人版暂不包含在内。",
        "articles": [
            ("爱范儿", "Gemini 4 Carbon 上线：上下文翻倍，价格砍四成", 0.94),
            ("量子位", "谷歌深夜放模型，Gemini 4 Carbon 主打工具调用", 0.91),
            ("The Information", "Google ships Gemini 4 Carbon to developers, not consumers", 0.88),
            ("路透社", "Alphabet 推出新一代模型，瞄准企业市场", 0.86),
            ("9to5Google", "Gemini 4 Carbon is here, but not for everyone", 0.83),
            ("InfoQ 中文", "Gemini 4 Carbon 发布：面向企业，个人版缺席", 0.79),
        ],
    },
    {
        "topic": "ai",
        "when": (0, 8, 47),
        "title": "OpenAI 收购旅行创业公司 Odessia",
        "summary": "交易未披露金额。Odessia 创始人称团队将并入 ChatGPT 的产品线，继续做行程规划能力。",
        "articles": [
            ("TechCrunch", "OpenAI acquires Odessia, a travel startup", 0.92),
            ("The Verge", "OpenAI buys its way into trip planning", 0.87),
            ("36氪", "OpenAI 收购 Odessia，补齐行程规划", 0.84),
            ("彭博", "OpenAI 继续并购，目标指向 Agent 场景", 0.80),
        ],
    },
    {
        "topic": "ai",
        "when": (0, 9, 12),
        "title": "微软宣布 .NET 11，为标准支持版本，提供两年维护",
        "summary": "该版本随 .NET 10 之后进入 STS 通道，主要变化集中在 AOT 编译与最小 API 的默认行为。",
        "articles": [
            ("InfoQ 中文", "微软宣布 .NET 11，为标准支持版本", 0.95),
            ("Solidot", "微软宣布 .NET 11", 0.90),
            ("微软开发者博客", ".NET 11 is now generally available", 0.86),
        ],
    },
    {
        "topic": "tech",
        "when": (0, 7, 58),
        "title": "超导量子计算从芯片走向千比特整机",
        "summary": "国内团队公布近亿元融资，并给出千比特整机的路线图，量产时间表仍未公开。",
        "articles": [
            ("量子位", "从芯片到千比特整机，超导量子计算还有一场硬仗", 0.93),
            ("Nature News", "China's superconducting quantum push moves to full machines", 0.81),
        ],
    },
    {
        "topic": "ai",
        "when": (1, 22, 31),
        "title": "纽约州启动 AI 安全法注册制度",
        "summary": "达到算力门槛的模型提供方须在州内登记，并披露训练数据来源与风险评估报告。",
        "articles": [
            ("TechCrunch", "New York opens AI safety registration", 0.91),
            ("纽约时报", "纽约州要求 AI 公司登记", 0.85),
            ("Ars Technica", "New York's AI law gets its first filings", 0.82),
        ],
    },
    {
        "topic": "tech",
        "when": (1, 21, 5),
        "title": "波士顿动力为人形机器人加入轮子",
        "summary": "官方视频展示了 Atlas 在轮式底盘上的移动能力，厂方称这是为工业场景做的形态扩展。",
        "articles": [
            ("Solidot", "波士顿动力为其人形机器人加入了轮子", 0.92),
            ("The Verge", "Boston Dynamics puts wheels on Atlas", 0.84),
        ],
    },
    {
        "topic": "ai",
        "when": (1, 18, 20),
        "title": "欧盟 AI 法案实施细则公布首批合规清单",
        "summary": "通用模型提供方需在明年二季度前提交系统性风险评估，训练数据摘要将首次对外公开。",
        "articles": [
            ("路透社", "EU publishes first compliance list under AI Act", 0.90),
            ("Politico", "Brussels details AI Act paperwork", 0.86),
            ("财新", "欧盟 AI 法案实施细则落地", 0.83),
            ("Euractiv", "AI Act implementation enters phase two", 0.79),
        ],
    },
    {
        "topic": "tech",
        "when": (1, 16, 2),
        "title": "三星宣布 HBM4 进入量产，良率仍未披露",
        "summary": "公司称首批产品将供应两家北美客户，业界关注其与 SK 海力士的份额变化。",
        "articles": [
            ("彭博", "Samsung starts HBM4 mass production", 0.89),
            ("日经", "三星 HBM4 进入量产", 0.85),
            ("The Elec", "Samsung's HBM4 yield still unclear", 0.81),
        ],
    },
]


def _local_dt(days_ago: int, hour: int, minute: int) -> datetime:
    day = datetime.now(LOCAL_TZ).date() - timedelta(days=days_ago)
    return datetime(day.year, day.month, day.day, hour, minute, tzinfo=LOCAL_TZ).astimezone(UTC)


def _hash(url: str) -> str:
    return hashlib.sha1(url.strip().split("#")[0].encode("utf-8")).hexdigest()


def tokenize(text: str) -> str:
    """jieba 分词，供 FTS5 使用；没装就原样返回。"""
    try:
        import jieba

        return " ".join(jieba.cut(text))
    except Exception:  # noqa: BLE001
        return text


def cmd_init(_: argparse.Namespace) -> None:
    init_db()
    print("建表完成")


def cmd_seed(args: argparse.Namespace) -> None:
    init_db()
    with Session(engine) as session:
        existing = session.exec(select(Event)).first()
        if existing and not args.force:
            print("库里已有事件，跳过。需要重灌请加 --force")
            return
        if args.force:
            for model in (ArticleEvent, Article, Event, FetchLog, Source, Topic):
                session.exec(delete(model))
            session.commit()

        topics: dict[str, Topic] = {}
        for slug, name, desc in TOPICS:
            t = Topic(slug=slug, name=name, description=desc, config_json="{}")
            session.add(t)
            topics[slug] = t
        session.commit()

        sources: dict[str, Source] = {}
        for name, feed, slug in SOURCES:
            s = Source(topic_id=topics[slug].id, name=name, feed_url=feed)
            session.add(s)
            sources[name] = s
        session.commit()

        for spec in DEMO_EVENTS:
            topic = topics[spec["topic"]]
            seen = _local_dt(*spec["when"])
            event = Event(
                topic_id=topic.id,
                title=spec["title"],
                summary=spec["summary"],
                first_seen_at=seen,
                last_seen_at=seen,
                article_count=len(spec["articles"]),
                source_count=len({a[0] for a in spec["articles"]}),
            )
            session.add(event)
            session.commit()

            for i, (src_name, title, sim) in enumerate(spec["articles"]):
                if src_name not in sources:
                    placeholder = Source(
                        topic_id=topic.id,
                        name=src_name,
                        feed_url="",
                        enabled=False,
                    )
                    session.add(placeholder)
                    session.commit()
                    sources[src_name] = placeholder

                url = f"https://example.com/{topic.slug}/{event.id}/{i}"
                article = Article(
                    topic_id=topic.id,
                    source_id=sources[src_name].id,
                    title=title,
                    url=url,
                    url_hash=_hash(url),
                    content=spec["summary"] * 3,
                    content_length=len(spec["summary"]) * 3,
                    published_at=seen + timedelta(minutes=i * 6),
                    search_text=tokenize(title + " " + spec["summary"]),
                )
                session.add(article)
                session.commit()
                session.add(ArticleEvent(article_id=article.id, event_id=event.id, similarity=sim))

            event.last_seen_at = seen + timedelta(minutes=(len(spec["articles"]) - 1) * 6)
            session.add(event)
            session.commit()

        print(f"灌入 {len(DEMO_EVENTS)} 个事件、{len(sources)} 个来源")


def cmd_fetch(args: argparse.Namespace) -> None:
    init_db()
    with Session(engine) as session:
        sources = session.exec(select(Source).where(Source.enabled == True)).all()  # noqa: E712
        if not sources:
            print("没有启用的源")
            return
        for src in sources:
            log = FetchLog(source_id=src.id)
            session.add(log)
            session.commit()
            try:
                resp = httpx.get(
                    src.feed_url,
                    headers={"User-Agent": USER_AGENT, "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8"},
                    timeout=FETCH_TIMEOUT,
                    follow_redirects=True,
                )
                resp.raise_for_status()
                feed = feedparser.parse(resp.content)
                new = dup = 0
                for entry in feed.entries[: args.limit]:
                    url = entry.get("link", "")
                    if not url:
                        continue
                    url_hash = _hash(url)
                    if session.exec(select(Article).where(Article.url_hash == url_hash)).first():
                        dup += 1
                        continue
                    summary = entry.get("summary", "") or ""
                    published = None
                    if entry.get("published_parsed"):
                        published = datetime(*entry.published_parsed[:6], tzinfo=UTC)
                    session.add(
                        Article(
                            topic_id=src.topic_id,
                            source_id=src.id,
                            title=entry.get("title", "").strip(),
                            url=url,
                            url_hash=url_hash,
                            content=summary,
                            content_length=len(summary),
                            published_at=published,
                            search_text=tokenize(entry.get("title", "") + " " + summary),
                        )
                    )
                    new += 1
                log.new_count, log.dup_count = new, dup
                log.finished_at = utcnow()
                src.last_fetch_at = utcnow()
                src.fail_count = 0
                session.add(log)
                session.add(src)
                session.commit()
                print(f"{src.name}: 新增 {new}，重复 {dup}")
            except Exception as exc:  # noqa: BLE001
                log.error = str(exc)[:200]
                log.finished_at = utcnow()
                src.fail_count += 1
                session.add(log)
                session.add(src)
                session.commit()
                print(f"{src.name}: 失败 {exc}")


def main() -> None:
    parser = argparse.ArgumentParser(prog="onefold")
    sub = parser.add_subparsers(dest="cmd", required=True)

    sub.add_parser("init", help="建表").set_defaults(func=cmd_init)

    seed = sub.add_parser("seed", help="灌示例数据")
    seed.add_argument("--force", action="store_true", help="清空后重灌")
    seed.set_defaults(func=cmd_seed)

    fetch = sub.add_parser("fetch", help="抓取所有启用的源")
    fetch.add_argument("--limit", type=int, default=10, help="每个源最多取几条")
    fetch.set_defaults(func=cmd_fetch)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
