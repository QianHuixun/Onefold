import { useEffect, useState } from "react";
import { fetchEvent } from "../api";
import type { EventDetail as Detail } from "../types";
import { clock, dayLabel } from "../time";

export default function EventDetail({ id, onClose }: { id: number; onClose: () => void }) {
  const [data, setData] = useState<Detail | null>(null);
  const [error, setError] = useState(false);

  useEffect(() => {
    let alive = true;
    setData(null);
    setError(false);
    fetchEvent(id)
      .then((d) => alive && setData(d))
      .catch(() => alive && setError(true));
    return () => {
      alive = false;
    };
  }, [id]);

  const sims = data?.articles.map((a) => a.similarity) ?? [];

  return (
    <div className="detail-backdrop" onClick={onClose}>
      <article className="detail" onClick={(e) => e.stopPropagation()}>
        <div className="detail-top">
          <div className="eyebrow">
            <span>{data?.topic_name ?? "事件"}</span>
            <span className="sep" />
            <span className="tag">
              {data ? `${dayLabel(data.first_seen_at)} ${clock(data.first_seen_at)}` : ""}
            </span>
          </div>
          <button className="detail-close" onClick={onClose}>
            ESC 关闭
          </button>
        </div>

        {error && <p className="empty-note">这条事件没取到，可能是接口没起。</p>}
        {!data && !error && <p className="empty-note">读取中…</p>}

        {data && (
          <>
            <h1>{data.title}</h1>

            <div className="detail-meta">
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
            </div>

            <div className="detail-sum-label">
              {data.summary_source && data.summary_source !== "extractive"
                ? `AI 摘要 · ${data.summary_source}`
                : "抽取式摘要 · 取最接近事件中心那篇的首句"}
            </div>
            <blockquote className="detail-sum">{data.summary}</blockquote>

            <div className="detail-src-head">
              <span>{data.article_count} 家媒体怎么说</span>
              <span>按与事件中心的相似度排序</span>
            </div>

            {data.articles.map((a) => (
              <div className="detail-row" key={a.id}>
                <div className="detail-src">{a.source_name}</div>
                <div className="detail-title">
                  <a href={a.url} target="_blank" rel="noopener noreferrer">
                    {a.title}
                  </a>
                  <div className="detail-sub">
                    {a.published_at ? `${dayLabel(a.published_at)} ${clock(a.published_at)}` : ""}
                    {a.content_length ? ` · 约 ${Math.round(a.content_length / 3)} 字` : ""}
                  </div>
                </div>
                <div className="detail-sim">{a.similarity.toFixed(2)}</div>
                <a className="detail-open" href={a.url} target="_blank" rel="noopener noreferrer">
                  原文 ↗
                </a>
              </div>
            ))}
          </>
        )}
      </article>
    </div>
  );
}
