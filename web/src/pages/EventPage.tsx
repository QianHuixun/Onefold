import { useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { detachArticle, fetchEvent, mergeEvent } from "../api";
import { useEventFlags } from "../store";
import type { EventDetail as Detail } from "../types";
import { clock, dayLabel } from "../time";
import MergeDialog from "../components/MergeDialog";

export default function EventPage() {
  const { id } = useParams();
  const navigate = useNavigate();
  const eventId = Number(id);
  const [data, setData] = useState<Detail | null>(null);
  const [error, setError] = useState("");
  const { read, starred, markRead, toggleStar } = useEventFlags();
  const token = localStorage.getItem("onefold_admin_token") ?? "";
  const [correcting, setCorrecting] = useState(
    new URLSearchParams(location.search).get("fix") === "1",
  );
  const [merging, setMerging] = useState(false);
  const [flash, setFlash] = useState("");

  const reload = () => {
    fetchEvent(eventId).then(setData).catch(() => undefined);
  };

  const handleDetach = async (articleId: number) => {
    if (!token) return;
    if (!confirm("把这条报道拆成独立事件？原来的事件会少一家来源。")) return;
    try {
      const res = await detachArticle(token, eventId, articleId);
      setFlash(`已拆成新事件 #${res.event_id}`);
      reload();
    } catch (exc) {
      setFlash(exc instanceof Error ? exc.message : "拆分失败");
    }
  };

  const handleMerge = async (targetId: number) => {
    if (!token) return;
    try {
      await mergeEvent(token, eventId, targetId);
      setMerging(false);
      setFlash("已合并，正在跳转");
      setTimeout(() => navigate(`/e/${targetId}`), 600);
    } catch (exc) {
      setFlash(exc instanceof Error ? exc.message : "合并失败");
    }
  };

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
              {token && (
                <button
                  className={`event-star ${correcting ? "on" : ""}`}
                  onClick={() => setCorrecting(!correcting)}
                >
                  {correcting ? "退出纠错" : "纠错"}
                </button>
              )}
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
              <h2>
                {data.source_count === data.article_count
                  ? `${data.source_count} 家媒体怎么说`
                  : `${data.article_count} 篇报道怎么说`}
              </h2>
              {correcting ? (
                <button className="btn" onClick={() => setMerging(true)}>
                  整个事件合并到…
                </button>
              ) : (
                <span>按与事件中心的相似度排序</span>
              )}
            </div>

            {flash && <p className="admin-ok">{flash}</p>}

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
                <div className="src-actions">
                  <a className="src-open" href={a.url} target="_blank" rel="noopener noreferrer">
                    原文 ↗
                  </a>
                  {correcting && data.articles.length > 1 && (
                    <button className="link danger" onClick={() => handleDetach(a.id)}>
                      拆出
                    </button>
                  )}
                </div>
              </div>
            ))}
          </div>
        </>
      )}

      {merging && data && (
        <MergeDialog
          currentId={data.id}
          onClose={() => setMerging(false)}
          onPick={handleMerge}
        />
      )}
    </section>
  );
}
