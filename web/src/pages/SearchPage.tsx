import { useEffect, useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { fetchSearch, type SearchHit } from "../api";
import { shortTime } from "../time";

export default function SearchPage() {
  const [params] = useSearchParams();
  const navigate = useNavigate();
  const q = params.get("q") ?? "";
  const [hits, setHits] = useState<SearchHit[]>([]);
  const [state, setState] = useState<"loading" | "ok" | "error">("loading");

  useEffect(() => {
    if (!q) {
      setHits([]);
      setState("ok");
      return;
    }
    let alive = true;
    setState("loading");
    fetchSearch(q)
      .then((d) => {
        if (!alive) return;
        setHits(d.hits);
        setState("ok");
      })
      .catch(() => alive && setState("error"));
    return () => {
      alive = false;
    };
  }, [q]);

  return (
    <section className="search-page">
      <div className="search-head">
        <div className="eyebrow">
          <span>搜索</span>
          <span className="sep" />
          <span className="tag">{q || "—"}</span>
        </div>
        <h1>「{q}」</h1>
        <div className="res-meta">
          {state === "loading" ? "检索中…" : `找到 ${hits.length} 条结果`}
          <button className="link" onClick={() => navigate("/")}>
            返回今日
          </button>
        </div>
      </div>

      {state === "error" && <p className="empty-note">接口没响应，检查后端是否在跑。</p>}
      {state === "ok" && q && hits.length === 0 && <p className="empty-note">没有找到「{q}」，换个关键词试试。</p>}

      <div className="hits">
        {hits.map((h) => (
          <div
            className="hit"
            key={`${h.kind}-${h.id}`}
            onClick={() => (h.kind === "event" ? navigate(`/e/${h.id}`) : window.open(h.url, "_blank", "noopener"))}
          >
            <div className="hit-kind">{h.kind === "event" ? "事件" : h.source_name}</div>
            <div>
              <h3>{h.title}</h3>
              {h.snippet && <p>{h.snippet}</p>}
            </div>
            <div className="hit-time">{shortTime(h.published_at)}</div>
          </div>
        ))}
      </div>
    </section>
  );
}
