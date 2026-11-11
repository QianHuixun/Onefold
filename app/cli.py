"""命令行入口：初始化、灌示例数据、抓取。

    python -m app.cli init
    python -m app.cli seed [--force]
    python -m app.cli fetch [--limit 10]
"""

from __future__ import annotations

import argparse
import hashlib
from pathlib import Path
import time
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
    """jieba 分词，供 FTS5 与向量化共用；没装就原样返回。"""
    from .pipeline.vectors import tokens

    return " ".join(tokens(text))


def cmd_init(_: argparse.Namespace) -> None:
    init_db()
    print("建表完成")


def cmd_bootstrap(_: argparse.Namespace) -> None:
    """生产环境初始化：只建主题和数据源，不灌演示数据。"""
    init_db()
    with Session(engine) as session:
        for slug, name, desc in TOPICS:
            if not session.exec(select(Topic).where(Topic.slug == slug)).first():
                session.add(Topic(slug=slug, name=name, description=desc, config_json="{}"))
        session.commit()

        topics = {t.slug: t for t in session.exec(select(Topic)).all()}
        added = 0
        for name, feed, slug in SOURCES:
            if session.exec(select(Source).where(Source.name == name)).first():
                continue
            session.add(Source(topic_id=topics[slug].id, name=name, feed_url=feed))
            added += 1
        session.commit()

        total = len(session.exec(select(Source)).all())
        print(f"主题 {len(topics)} 个，数据源 {total} 个（本次新增 {added}）")


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

                url = f"demo://{topic.slug}/{event.id}/{i}"
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
                    status="demo",
                )
                session.add(article)
                session.commit()
                session.add(ArticleEvent(article_id=article.id, event_id=event.id, similarity=sim))

            event.last_seen_at = seen + timedelta(minutes=(len(spec["articles"]) - 1) * 6)
            session.add(event)
            session.commit()

        print(f"灌入 {len(DEMO_EVENTS)} 个事件、{len(sources)} 个来源")


def _get_feed(url: str) -> "httpx.Response":
    """带一次重试的 GET：新闻站的超时和 5xx 大多是瞬时的。"""
    last: Exception | None = None
    for attempt in range(2):
        try:
            return httpx.get(
                url,
                headers={"User-Agent": USER_AGENT, "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8"},
                timeout=FETCH_TIMEOUT,
                follow_redirects=True,
            )
        except httpx.HTTPError as exc:
            last = exc
            time.sleep(1.5 * (attempt + 1))
    assert last is not None
    raise last


def _fetch_source(session: Session, src: Source, limit: int) -> tuple[int, int]:
    """抓一个源，返回 (新增, 重复)。失败会抛异常，由调用方记账。"""
    resp = _get_feed(src.feed_url)
    resp.raise_for_status()
    feed = feedparser.parse(resp.content)

    new = dup = 0
    for entry in feed.entries[:limit]:
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
    session.commit()
    return new, dup


def _run_fetch(session: Session, limit: int) -> dict[str, int]:
    sources = session.exec(select(Source).where(Source.enabled == True)).all()  # noqa: E712
    stats = {"sources": len(sources), "new": 0, "dup": 0, "failed": 0}
    if not sources:
        print("没有启用的源")
        return stats

    for src in sources:
        log = FetchLog(source_id=src.id)
        session.add(log)
        session.commit()
        try:
            new, dup = _fetch_source(session, src, limit)
            log.new_count, log.dup_count = new, dup
            src.last_fetch_at = utcnow()
            src.fail_count = 0
            stats["new"] += new
            stats["dup"] += dup
            print(f"  {src.name}: 新增 {new}，重复 {dup}")
        except Exception as exc:  # noqa: BLE001
            log.error = str(exc)[:200]
            src.fail_count += 1
            stats["failed"] += 1
            print(f"  {src.name}: 失败 {type(exc).__name__} {str(exc)[:80]}")
        finally:
            log.finished_at = utcnow()
            session.add(log)
            session.add(src)
            session.commit()
    return stats


def cmd_eval_build(args: argparse.Namespace) -> None:
    from .eval import build_pairs

    init_db()
    with Session(engine) as session:
        stats = build_pairs(session, args.max_pairs, args.min_similarity)
        print(f"候选对 {stats['candidates']} 组，新建 {stats['created']} 组")


def cmd_eval_autolabel(args: argparse.Namespace) -> None:
    from .eval import autolabel

    init_db()
    with Session(engine) as session:
        n = autolabel(session, args.overlap)
        print(f"自动预标注 {n} 组（按标题词重叠度，需人工复核）")


def cmd_eval_fixture(args: argparse.Namespace) -> None:
    from .eval import make_fixture

    init_db()
    with Session(engine) as session:
        stats = make_fixture(session, args.count)
        print(f"夹具：新建重复稿 {stats['created']} 篇（status=eval，不进首页）")


def cmd_eval_export(args: argparse.Namespace) -> None:
    from .eval import export_metrics

    init_db()
    with Session(engine) as session:
        text = export_metrics(session)
    Path(args.out).write_text(text, encoding="utf-8")
    print(f"已导出到 {args.out}")


def cmd_purge_demo(_: argparse.Namespace) -> None:
    """清掉演示残留：demo 文章、只含 demo 文章的事件、没有 Feed 的空源。"""
    init_db()
    with Session(engine) as session:
        demo_articles = session.exec(select(Article).where(Article.status == "demo")).all()
        demo_ids = [a.id for a in demo_articles]
        if demo_ids:
            session.exec(delete(ArticleEvent).where(ArticleEvent.article_id.in_(demo_ids)))
            session.exec(delete(Article).where(Article.id.in_(demo_ids)))
            session.commit()

        removed_events = 0
        for event in session.exec(select(Event)).all():
            left = session.exec(
                select(ArticleEvent).where(ArticleEvent.event_id == event.id).limit(1)
            ).first()
            if left is None:
                session.delete(event)
                removed_events += 1
        session.commit()

        removed_sources = 0
        for source in session.exec(select(Source)).all():
            if source.feed_url:
                continue
            used = session.exec(
                select(Article).where(Article.source_id == source.id).limit(1)
            ).first()
            if used is None:
                session.delete(source)
                removed_sources += 1
        session.commit()

        print(
            f"删除 demo 文章 {len(demo_ids)} 篇、空事件 {removed_events} 个、无 Feed 的源 {removed_sources} 个"
        )


def cmd_fetch(args: argparse.Namespace) -> None:
    init_db()
    with Session(engine) as session:
        print("抓取：")
        _run_fetch(session, args.limit)


def cmd_daily(args: argparse.Namespace) -> None:
    """定时任务入口：抓取 → 抽取 → 去重 → 聚类 → 摘要，一次跑完。"""
    from .pipeline import cluster_pending, dedup_pending, extract_pending, summarize_pending

    started = time.time()
    init_db()
    print(f"[{datetime.now(LOCAL_TZ):%Y-%m-%d %H:%M}] 每日运行开始")

    with Session(engine) as session:
        fetch_stats = _run_fetch(session, args.limit)
        extract_stats = extract_pending(session, args.extract_limit)
        dedup_stats = dedup_pending(session)
        cluster_stats = cluster_pending(session)
        summary_stats = summarize_pending(session)

    elapsed = time.time() - started
    print(
        f"抓取 {fetch_stats['sources']} 个源：新增 {fetch_stats['new']}，重复 {fetch_stats['dup']}，"
        f"失败 {fetch_stats['failed']}"
    )
    print(f"抽取 {extract_stats['ok']}/{extract_stats['tried']} 篇")
    print(f"去重：检查 {dedup_stats['checked']}，判重 {dedup_stats['dup']}")
    print(f"聚类：新事件 {cluster_stats['new_events']}，并入 {cluster_stats['joined']}")
    print(
        f"摘要 {int(summary_stats['events'])} 条：模型 {int(summary_stats['llm'])}，"
        f"抽取 {int(summary_stats['extractive'])}，花费 ¥{summary_stats['cost']}"
    )
    print(f"完成，用时 {elapsed:.1f}s")


def cmd_report(args: argparse.Namespace) -> None:
    """看最近几次抓取的情况，排查坏源用。"""
    init_db()
    with Session(engine) as session:
        rows = session.exec(
            select(FetchLog, Source.name)
            .join(Source, Source.id == FetchLog.source_id)
            .order_by(FetchLog.started_at.desc())
            .limit(args.limit)
        ).all()
        if not rows:
            print("还没有抓取记录")
            return
        print(f"{'时间':<17}{'来源':<12}{'新增':>4}{'重复':>4}  状态")
        for log, name in rows:
            status = "OK" if not log.error else f"FAIL {log.error[:40]}"
            print(
                f"{log.started_at.astimezone(LOCAL_TZ):%m-%d %H:%M}    "
                f"{name:<12}{log.new_count:>4}{log.dup_count:>4}  {status}"
            )


def cmd_summarize(args: argparse.Namespace) -> None:
    from .pipeline.summarize import summarize_pending

    init_db()
    with Session(engine) as session:
        stats = summarize_pending(session, force=args.force)
        print(
            f"摘要 {int(stats['events'])} 条：模型 {int(stats['llm'])}，抽取式 {int(stats['extractive'])}；"
            f"tokens 入 {int(stats['tokens_in'])} / 出 {int(stats['tokens_out'])}，"
            f"估算花费 ¥{stats['cost']}"
        )


def cmd_pipeline(args: argparse.Namespace) -> None:
    from .pipeline import cluster_pending, dedup_pending, extract_pending, summarize_pending

    init_db()
    with Session(engine) as session:
        if args.rebuild:
            # 清掉真实数据聚出来的事件，保留种子（demo）事件
            demo_ids = set(
                session.exec(select(ArticleEvent.event_id).join(Article, Article.id == ArticleEvent.article_id)
                             .where(Article.status == "demo")).all()
            )
            for event in session.exec(select(Event)).all():
                if event.id in demo_ids:
                    continue
                session.exec(delete(ArticleEvent).where(ArticleEvent.event_id == event.id))
                session.delete(event)
            session.commit()
            print("已清空自动聚出来的事件")
        if not args.skip_extract:
            print("抽取正文:", extract_pending(session, args.limit))
        print("文章去重:", dedup_pending(session))
        print("事件聚类:", cluster_pending(session))
        print("生成摘要:", summarize_pending(session))


def main() -> None:
    parser = argparse.ArgumentParser(prog="onefold")
    sub = parser.add_subparsers(dest="cmd", required=True)

    sub.add_parser("init", help="建表").set_defaults(func=cmd_init)

    sub.add_parser("bootstrap", help="建主题与数据源（不灌演示数据）").set_defaults(func=cmd_bootstrap)

    seed = sub.add_parser("seed", help="灌示例数据")
    seed.add_argument("--force", action="store_true", help="清空后重灌")
    seed.set_defaults(func=cmd_seed)

    summ = sub.add_parser("summarize", help="给事件生成一句话摘要")
    summ.add_argument("--force", action="store_true", help="重写全部事件的摘要")
    summ.set_defaults(func=cmd_summarize)

    pipe = sub.add_parser("pipeline", help="抽取 → 去重 → 聚类 → 摘要")
    pipe.add_argument("--limit", type=int, default=60, help="每轮最多处理多少篇")
    pipe.add_argument("--skip-extract", action="store_true", help="跳过正文抽取")
    pipe.add_argument("--rebuild", action="store_true", help="先清空自动聚出来的事件再重跑")
    pipe.set_defaults(func=cmd_pipeline)

    sub.add_parser("purge-demo", help="清掉演示数据残留").set_defaults(func=cmd_purge_demo)

    eb = sub.add_parser("eval-build", help="生成待标注的文章对")
    eb.add_argument("--max-pairs", type=int, default=300)
    eb.add_argument("--min-similarity", type=float, default=0.08)
    eb.set_defaults(func=cmd_eval_build)

    ea = sub.add_parser("eval-autolabel", help="按标题重叠做自动预标注（需复核）")
    ea.add_argument("--overlap", type=float, default=0.55)
    ea.set_defaults(func=cmd_eval_autolabel)

    ef = sub.add_parser("eval-fixture", help="生成已知答案的评测夹具（status=eval，不上首页）")
    ef.add_argument("--count", type=int, default=12)
    ef.set_defaults(func=cmd_eval_fixture)

    ee = sub.add_parser("eval-export", help="导出阈值曲线 JSON")
    ee.add_argument("--out", default="docs/eval-metrics.json")
    ee.set_defaults(func=cmd_eval_export)

    fetch = sub.add_parser("fetch", help="抓取所有启用的源")
    fetch.add_argument("--limit", type=int, default=10, help="每个源最多取几条")
    fetch.set_defaults(func=cmd_fetch)

    daily = sub.add_parser("daily", help="每日任务：抓取 → 抽取 → 去重 → 聚类 → 摘要")
    daily.add_argument("--limit", type=int, default=10, help="每个源最多取几条")
    daily.add_argument("--extract-limit", type=int, default=60, help="本轮最多抽取多少篇正文")
    daily.set_defaults(func=cmd_daily)

    report = sub.add_parser("report", help="查看最近的抓取记录")
    report.add_argument("--limit", type=int, default=20)
    report.set_defaults(func=cmd_report)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
