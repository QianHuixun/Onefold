import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { fetchEvent } from "../api";
import { useEventFlags } from "../store";
import type { EventDetail as Detail } from "../types";
import { clock, dayLabel } from "../time";

export default function EventPage() {
  const { id } = useParams();
  const eventId = Number(id);
  const [data, setData] = useState<Detail | null>(null);
  const [error, setError] = useState("");
  const { read, starred, markRead, toggleStar } = useEventFlags();

  useEffect(() => {
    let alive = true;
    setData(null);
    setError("");
    if (!Number.isFinite(eventId)) {
      setError("事件编号不对");
      return;
    }
    fetchEvent(eventId)
      .then((d) => {
        if (!alive) return;
        setData(d);
        markRead(eventId);
      })
      .catch(() => alive && setError("这条事件没取到，可能已经被删除"));
    return () => {
      alive = false;
    };
  }, [eventId, markRead]);

  const sims = data?.articles.map((a) => a.similarity) ?? [];

  return (
    <section className="event-page">
      <div className="crumb">
        <Link to="/">今日</Link>
        <span>/</span>
        <span className="now">{data ? data.topic_name : "事件"}</span>
      </div>

      {error && <p className="empty-note">{error}</p>}
      {!data && !error && <p className="empty-note">读取中…</p>}

      {data && (
        <>
          <header className="event-head">
            <div className="eyebrow">
              <span>{data.topic_name}</span>
              <span className="sep" />
              <span className="tag">
                {dayLabel(data.first_seen_at)} {clock(data.first_seen_at)}
              </span>
              {read.has(data.id) && <span className="tag">已读</span>}
            </div>
            <h1>{data.title}</h1>
            <div className="event-meta">
              <span>
                <b>{data.article_count}</b> 篇报道
              </span>
              <span className="dot" />
              <span>
                <b>{data.source_count}</b> 家来源
              </span>
              {sims.length > 1 && (
                <>
                  <span className="dot" />
                  <span>
                    相似度 {Math.min(...sims).toFixed(2)}–{Math.max(...sims).toFixed(2)}
                  </span>
                </>
              )}
              <button
                className={`event-star ${starred.has(data.id) ? "on" : ""}`}
                onClick={() => toggleStar(data.id)}
              >
                {starred.has(data.id) ? "★ 已收藏" : "☆ 收藏"}
              </button>
            </div>
          </header>

          <div className="event-body">
            <div className="sum-label">
              {data.summary_source && data.summary_source !== "extractive"
                ? `AI 摘要 · ${data.summary_source}`
                : "抽取式摘要 · 取最接近事件中心那篇的首句"}
            </div>
            <blockquote className="sum-text">{data.summary}</blockquote>

            <div className="sec-head">
              <h2>{data.source_count} 家媒体怎么说</h2>
              <span>按与事件中心的相似度排序</span>
            </div>

            {data.articles.map((a) => (
              <div className="src-row" key={a.id}>
                <div className="src-name">{a.source_name}</div>
                <div>
                  <a className="src-title" href={a.url} target="_blank" rel="noopener noreferrer">
                    {a.title}
                  </a>
                  <div className="src-meta">
                    {a.published_at ? `${dayLabel(a.published_at)} ${clock(a.published_at)}` : ""}
                    {a.content_length ? ` · 约 ${Math.round(a.content_length / 3)} 字` : ""}
                  </div>
                </div>
                <div className="src-sim">{a.similarity.toFixed(2)}</div>
                <a className="src-open" href={a.url} target="_blank" rel="noopener noreferrer">
                  原文 ↗
                </a>
              </div>
            ))}
          </div>
        </>
      )}
    </section>
  );
}
