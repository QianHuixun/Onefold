import { useEffect, useMemo, useState } from "react";
import Footer from "./components/Footer";
import Hero from "./components/Hero";
import EventRow from "./components/EventRow";
import IndexNav from "./components/IndexNav";
import Rail from "./components/Rail";
import SearchPalette from "./components/SearchPalette";
import AdminPanel from "./components/AdminPanel";
import EventDetail from "./components/EventDetail";
import TopBar from "./components/TopBar";
import { fetchEvents, fetchStats } from "./api";
import type { EventItem, Stats } from "./types";
import { clock, dayKey, dayLabel, todayLabel } from "./time";

export default function App() {
  const [events, setEvents] = useState<EventItem[]>([]);
  const [stats, setStats] = useState<Stats | null>(null);
  const [state, setState] = useState<"loading" | "ok" | "error">("loading");
  const [topic, setTopic] = useState("");
  const [searchOpen, setSearchOpen] = useState(false);
  const [initialQuery, setInitialQuery] = useState("");
  const [detailId, setDetailId] = useState<number | null>(null);
  const [view, setView] = useState<"home" | "admin">("home");

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

  useEffect(() => {
    const params = new URLSearchParams(location.search);
    if (params.get("admin") === "1") setView("admin");
    const q = params.get("q");
    if (q) {
      setInitialQuery(q);
      setSearchOpen(true);
    }
    const ev = params.get("event");
    if (ev) setDetailId(Number(ev));
  }, []);

  // 浮层打开时锁住页面滚动
  useEffect(() => {
    document.body.style.overflow = searchOpen || detailId ? "hidden" : "";
    return () => {
      document.body.style.overflow = "";
    };
  }, [searchOpen, detailId]);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        setSearchOpen(true);
      }
      if (e.key === "Escape") {
        setSearchOpen(false);
        setDetailId(null);
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  const topics = useMemo(() => {
    const map = new Map<string, string>();
    for (const e of events) map.set(e.topic_slug, e.topic_name);
    return [...map.entries()].map(([slug, name]) => ({ slug, name }));
  }, [events]);

  const counts = useMemo(() => {
    const m: Record<string, number> = {};
    for (const e of events) m[e.topic_slug] = (m[e.topic_slug] ?? 0) + 1;
    return m;
  }, [events]);

  const visible = useMemo(
    () => (topic ? events.filter((e) => e.topic_slug === topic) : events),
    [events, topic],
  );

  const hero = useMemo(
    () =>
      visible.reduce<EventItem | null>(
        (best, e) => (!best || e.article_count > best.article_count ? e : best),
        null,
      ),
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

      <TopBar topics={topics} active={topic} onTopic={setTopic} onOpenSearch={() => setSearchOpen(true)} />

      <main className="plate">
        {view === "admin" ? (
          <AdminPanel topics={topics} />
        ) : state === "loading" ? (
          <div className="state">正在取今日事件…</div>
        ) : state === "error" ? (
          <div className="state">
            接口没响应。先在仓库根目录跑 <code>.venv/bin/uvicorn app.main:app --port 8000</code>
          </div>
        ) : (
          <>
            {hero && <Hero event={hero} onOpen={setDetailId} />}
            <div className="grid">
              <IndexNav
                topics={topics}
                active={topic}
                counts={counts}
                total={stats?.events ?? events.length}
                sources={stats?.sources ?? 0}
                onTopic={setTopic}
              />

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
                      <EventRow key={e.id} event={e} onOpen={setDetailId} />
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

      <Footer onAdmin={() => setView(view === "admin" ? "home" : "admin")} />

      <SearchPalette
        open={searchOpen}
        onClose={() => setSearchOpen(false)}
        initialQuery={initialQuery}
        onSelect={(hit) => {
          setSearchOpen(false);
          if (hit.kind === "event") setDetailId(hit.id);
          else if (hit.url) window.open(hit.url, "_blank", "noopener");
        }}
      />

      {detailId !== null && <EventDetail id={detailId} onClose={() => setDetailId(null)} />}
    </>
  );
}
