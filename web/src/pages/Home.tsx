import { useEffect, useMemo, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import Hero from "../components/Hero";
import EventRow from "../components/EventRow";
import IndexNav from "../components/IndexNav";
import Rail from "../components/Rail";
import { fetchEvents, fetchStats } from "../api";
import { useEventFlags } from "../store";
import type { EventItem, Stats } from "../types";
import { clock, dayKey, dayLabel, todayLabel } from "../time";

type Props = { onTopicChange?: (slug: string) => void };

export default function Home({ onTopicChange }: Props) {
  const { slug } = useParams();
  const navigate = useNavigate();
  const [events, setEvents] = useState<EventItem[]>([]);
  const [stats, setStats] = useState<Stats | null>(null);
  const [state, setState] = useState<"loading" | "ok" | "error">("loading");
  const [feedFilter, setFeedFilter] = useState<"all" | "unread" | "starred">("all");
  const { read, starred, markRead, toggleStar, exportStarred } = useEventFlags();

  useEffect(() => {
    let alive = true;
    fetchEvents()
      .then((page) => {
        if (!alive) return;
        setEvents(page.items);
        setState("ok");
      })
      .catch(() => alive && setState("error"));
    fetchStats().then((s) => alive && setStats(s)).catch(() => undefined);
    return () => {
      alive = false;
    };
  }, []);

  useEffect(() => {
    onTopicChange?.(slug ?? "");
  }, [slug, onTopicChange]);

  const topics = useMemo(() => {
    const map = new Map<string, string>();
    for (const e of events) map.set(e.topic_slug, e.topic_name);
    return [...map.entries()].map(([s, name]) => ({ slug: s, name }));
  }, [events]);

  const counts = useMemo(() => {
    const m: Record<string, number> = {};
    for (const e of events) m[e.topic_slug] = (m[e.topic_slug] ?? 0) + 1;
    return m;
  }, [events]);

  const scoped = useMemo(
    () => (slug ? events.filter((e) => e.topic_slug === slug) : events),
    [events, slug],
  );

  const visible = useMemo(() => {
    if (feedFilter === "unread") return scoped.filter((e) => !read.has(e.id));
    if (feedFilter === "starred") return scoped.filter((e) => starred.has(e.id));
    return scoped;
  }, [scoped, feedFilter, read, starred]);

  const hero = useMemo(
    () =>
      feedFilter !== "all"
        ? null
        : visible.reduce<EventItem | null>(
            (best, e) => (!best || e.article_count > best.article_count ? e : best),
            null,
          ),
    [visible, feedFilter],
  );

  const rest = useMemo(() => visible.filter((e) => e.id !== hero?.id), [visible, hero]);

  const groups = useMemo(() => {
    const out: { key: string; label: string; items: EventItem[] }[] = [];
    for (const e of rest) {
      const k = dayKey(e.first_seen_at);
      const last = out[out.length - 1];
      if (last && last.key === k) last.items.push(e);
      else out.push({ key: k, label: dayLabel(e.first_seen_at), items: [e] });
    }
    return out;
  }, [rest]);

  if (state === "loading") return <div className="state">正在取今日事件…</div>;
  if (state === "error")
    return (
      <div className="state">
        接口没响应。先在仓库根目录跑 <code>.venv/bin/uvicorn app.main:app --port 8000</code>
      </div>
    );

  return (
    <>
      {hero && (
        <Hero
          event={hero}
          onOpen={(id) => {
            markRead(id);
            navigate(`/e/${id}`);
          }}
        />
      )}

      <div className="grid">
        <IndexNav
          topics={topics}
          active={slug ?? ""}
          counts={counts}
          total={events.length}
          sources={stats?.sources ?? 0}
          onTopic={(s) => navigate(s ? `/topic/${s}` : "/")}
        />

        <div className="feed">
          <div className="feed-head">
            <div>
              <div className="day-title">今天 · {todayLabel()}</div>
              <div className="day-sub">
                {visible.length} 个事件 · 更新于 {stats?.updated_at ? clock(stats.updated_at) : "—"}
              </div>
              <div className="feed-filters">
                <button className={`ff ${feedFilter === "all" ? "on" : ""}`} onClick={() => setFeedFilter("all")}>
                  全部
                </button>
                <button className={`ff ${feedFilter === "unread" ? "on" : ""}`} onClick={() => setFeedFilter("unread")}>
                  未读 <span className="n">{scoped.filter((e) => !read.has(e.id)).length}</span>
                </button>
                <button className={`ff ${feedFilter === "starred" ? "on" : ""}`} onClick={() => setFeedFilter("starred")}>
                  收藏 <span className="n">{starred.size}</span>
                </button>
                {starred.size > 0 && (
                  <button className="ff export" onClick={exportStarred}>
                    导出
                  </button>
                )}
              </div>
            </div>
          </div>

          {groups.map((g, gi) => (
            <div key={g.key}>
              {gi > 0 && <div className="day-break">{g.label}</div>}
              {g.items.map((e) => (
                <EventRow
                  key={e.id}
                  event={e}
                  read={read.has(e.id)}
                  starred={starred.has(e.id)}
                  onOpen={(id) => {
                    markRead(id);
                    navigate(`/e/${id}`);
                  }}
                  onStar={toggleStar}
                />
              ))}
            </div>
          ))}

          {rest.length === 0 && (
            <p className="empty-note">
              {feedFilter === "unread"
                ? "都读完了。"
                : feedFilter === "starred"
                  ? "还没有收藏。点事件右上角的星标试试。"
                  : "这个主题今天还没有事件。"}
            </p>
          )}
        </div>

        <Rail stats={stats} events={visible} />
      </div>
    </>
  );
}
