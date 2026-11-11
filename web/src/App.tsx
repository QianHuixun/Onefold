import { useEffect, useMemo, useState } from "react";
import Footer from "./components/Footer";
import Hero from "./components/Hero";
import EventRow from "./components/EventRow";
import Rail from "./components/Rail";
import SearchResults from "./components/SearchResults";
import TopBar from "./components/TopBar";
import { fetchEvents, fetchStats } from "./api";
import type { EventItem, Stats } from "./types";
import { clock, dayKey, dayLabel, todayLabel } from "./time";

export default function App() {
  const [events, setEvents] = useState<EventItem[]>([]);
  const [stats, setStats] = useState<Stats | null>(null);
  const [state, setState] = useState<"loading" | "ok" | "error">("loading");
  const [topic, setTopic] = useState("");
  const [query, setQuery] = useState("");

  useEffect(() => {
    let alive = true;
    Promise.all([fetchEvents(), fetchStats()])
      .then(([page, s]) => {
        if (!alive) return;
        setEvents(page.items);
        setStats(s);
        setState("ok");
      })
      .catch(() => alive && setState("error"));
    return () => {
      alive = false;
    };
  }, []);

  const topics = useMemo(() => {
    const map = new Map<string, string>();
    for (const e of events) map.set(e.topic_slug, e.topic_name);
    return [...map.entries()].map(([slug, name]) => ({ slug, name }));
  }, [events]);

  const visible = useMemo(
    () => (topic ? events.filter((e) => e.topic_slug === topic) : events),
    [events, topic],
  );

  const hero = useMemo(
    () => visible.reduce<EventItem | null>((best, e) => (!best || e.article_count > best.article_count ? e : best), null),
    [visible],
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

  return (
    <>
      <div className="scene" aria-hidden="true">
        <span className="glow g1" />
        <span className="glow g2" />
        <span className="glow g3" />
        <div className="grain" />
      </div>

      <TopBar
        topics={topics}
        active={topic}
        onTopic={(t) => {
          setTopic(t);
          setQuery("");
        }}
        onSearch={(q) => setQuery(q)}
      />

      <main className="plate">
        {query ? (
          <SearchResults q={query} onClear={() => setQuery("")} />
        ) : state === "loading" ? (
          <div className="state">正在取今日事件…</div>
        ) : state === "error" ? (
          <div className="state">
            接口没响应。先在仓库根目录跑 <code>.venv/bin/uvicorn app.main:app --port 8000</code>
          </div>
        ) : (
          <>
            {hero && <Hero event={hero} />}
            <div className="grid">
              <div className="feed">
                <div className="feed-head">
                  <div>
                    <div className="day-title">今天 · {todayLabel()}</div>
                    <div className="day-sub">
                      {visible.length} 个事件 · 更新于 {stats?.updated_at ? clock(stats.updated_at) : "—"}
                    </div>
                  </div>
                  <div className="chips">
                    <button className={`chip ${topic === "" ? "on" : ""}`} onClick={() => setTopic("")}>
                      全部
                    </button>
                    {topics.map((t) => (
                      <button
                        key={t.slug}
                        className={`chip ${topic === t.slug ? "on" : ""}`}
                        onClick={() => setTopic(t.slug)}
                      >
                        {t.name}
                      </button>
                    ))}
                  </div>
                </div>

                {groups.map((g, gi) => (
                  <div key={g.key}>
                    {gi > 0 && <div className="day-break">{g.label}</div>}
                    {g.items.map((e) => (
                      <EventRow key={e.id} event={e} />
                    ))}
                  </div>
                ))}

                {rest.length === 0 && <p className="empty-note">这个主题今天还没有事件。</p>}
              </div>

              <Rail stats={stats} events={visible} />
            </div>
          </>
        )}
      </main>

      <Footer />
    </>
  );
}
