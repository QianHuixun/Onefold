"""数据探针：验证候选 RSS 源能不能抓、正文能不能抽干净。

用法：
    .venv/bin/python scripts/probe_feeds.py [--per-source 8] [--out /tmp/probe.json]

判据（对应 PRD F03）：
    抽取成功率 = 正文长度 ≥ 200 字符的文章数 / 尝试抓取的原文页数
"""

from __future__ import annotations

import argparse
import json
import statistics
import time
from concurrent.futures import ThreadPoolExecutor
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen

import feedparser
import trafilatura

UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
)

SOURCES = [
    {"name": "量子位", "topic": "AI", "lang": "zh", "feed": "https://www.qbitai.com/feed"},
    {"name": "InfoQ 中文", "topic": "AI", "lang": "zh", "feed": "https://www.infoq.cn/feed"},
    {"name": "爱范儿", "topic": "科技", "lang": "zh", "feed": "https://www.ifanr.com/feed"},
    {"name": "Solidot", "topic": "科技", "lang": "zh", "feed": "https://www.solidot.org/index.rss"},
    {"name": "TechCrunch", "topic": "AI", "lang": "en", "feed": "https://techcrunch.com/feed/"},
]

MIN_CHARS = 200


def http_get(url: str, timeout: int = 15) -> tuple[int, bytes]:
    req = Request(
        url,
        headers={
            "User-Agent": UA,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        },
    )
    with urlopen(req, timeout=timeout) as resp:
        return resp.status, resp.read()


def probe_entry(entry) -> dict:
    url = entry.get("link", "")
    result = {
        "title": entry.get("title", "").strip(),
        "url": url,
        "rss_summary_chars": len(entry.get("summary", "") or ""),
        "chars": 0,
        "status": "fail",
        "error": "",
    }
    if not url:
        result["error"] = "no-link"
        return result

    try:
        status, body = http_get(url)
        if status != 200:
            result["error"] = f"http-{status}"
            return result
        html = body.decode("utf-8", errors="replace")
        text = trafilatura.extract(
            html, url=url, include_comments=False, include_tables=False
        )
        if not text:
            result["error"] = "extract-empty"
            return result
        result["chars"] = len(text)
        result["sample"] = text[:160].replace("\n", " ")
        result["status"] = "ok" if result["chars"] >= MIN_CHARS else "short"
    except HTTPError as exc:
        result["error"] = f"http-{exc.code}"
    except URLError as exc:
        result["error"] = f"url-{exc.reason}"[:60]
    except Exception as exc:  # noqa: BLE001 - 探针要记录一切失败
        result["error"] = type(exc).__name__
    return result


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--per-source", type=int, default=8)
    ap.add_argument("--out", default="/tmp/probe.json")
    args = ap.parse_args()

    report = []
    for src in SOURCES:
        started = time.time()
        try:
            _, raw = http_get(src["feed"])
            parsed = feedparser.parse(raw)
            entries = parsed.entries[: args.per_source]
        except Exception as exc:  # noqa: BLE001
            report.append({**src, "feed_status": f"error: {exc}", "items": []})
            print(f"[FAIL] {src['name']} feed: {exc}")
            continue

        with ThreadPoolExecutor(max_workers=4) as pool:
            items = list(pool.map(probe_entry, entries))

        ok = sum(1 for i in items if i["status"] == "ok")
        report.append(
            {
                **src,
                "feed_status": "ok",
                "feed_title": parsed.feed.get("title", ""),
                "elapsed_s": round(time.time() - started, 1),
                "items": items,
                "ok": ok,
            }
        )
        print(f"[{'OK' if parsed.entries else 'EMPTY'}] {src['name']}: "
              f"{len(parsed.entries)} 条，抽取成功 {ok}/{len(items)}，"
              f"{round(time.time() - started, 1)}s")

    with open(args.out, "w", encoding="utf-8") as fh:
        json.dump(report, fh, ensure_ascii=False, indent=2)

    print("\n=== 汇总 ===")
    total_ok = total = 0
    for r in report:
        items = r.get("items", [])
        if not items:
            continue
        ok = sum(1 for i in items if i["status"] == "ok")
        lens = [i["chars"] for i in items if i["chars"]]
        total_ok += ok
        total += len(items)
        errors = {}
        for i in items:
            if i["status"] != "ok":
                errors[i["error"] or i["status"]] = errors.get(i["error"] or i["status"], 0) + 1
        med = int(statistics.median(lens)) if lens else 0
        print(
            f"{r['name']:<12} 成功 {ok}/{len(items)}  "
            f"正文中位数 {med} 字符  "
            f"失败原因 {errors or '-'}"
        )
    if total:
        print(f"\n总体抽取成功率: {total_ok}/{total} = {total_ok / total:.0%}（目标 ≥ 90%）")


if __name__ == "__main__":
    main()
