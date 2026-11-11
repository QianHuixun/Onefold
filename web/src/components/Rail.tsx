import type { EventItem, Stats } from "../types";
import { clock } from "../time";

type Props = {
  stats: Stats | null;
  events: EventItem[];
};

export default function Rail({ stats, events }: Props) {
  const top = [...events].sort((a, b) => b.article_count - a.article_count).slice(0, 5);

  const counts = new Map<string, number>();
  for (const e of events) {
    for (const name of e.sources) counts.set(name, (counts.get(name) ?? 0) + 1);
  }
  const sources = [...counts.entries()].sort((a, b) => b[1] - a[1]).slice(0, 8);

  return (
    <aside className="rail">
      <section className="rail-card">
        <div className="rail-title">今日概览</div>
        <div className="stats">
          <div>
            <div className="stat-num">{stats?.events ?? "—"}</div>
            <div className="stat-label">个事件</div>
          </div>
          <div>
            <div className="stat-num">{stats?.sources ?? "—"}</div>
            <div className="stat-label">个来源</div>
          </div>
          <div>
            <div className="stat-num">{stats?.updated_at ? clock(stats.updated_at) : "—"}</div>
            <div className="stat-label">最后更新</div>
          </div>
        </div>
      </section>

      <section className="rail-card">
        <div className="rail-title">报道最多的事件</div>
        <ol className="rank">
          {top.map((e, i) => (
            <li key={e.id}>
              <span className="n">{String(i + 1).padStart(2, "0")}</span>
              <span>{e.title}</span>
            </li>
          ))}
        </ol>
      </section>

      <section className="rail-card">
        <div className="rail-title">来源</div>
        <ul className="src-list">
          {sources.map(([name, n]) => (
            <li key={name}>
              <span>{name}</span>
              <span className="c">{n}</span>
            </li>
          ))}
        </ul>
      </section>

      <section className="rail-card about-card">
        <div className="rail-title">关于</div>
        <p>
          把多个来源里同一件事的报道合并成一个事件，每个事件配一句话摘要。只抓取公开发布的 RSS，正文保留原文链接。
        </p>
        <a href="#">数据来源与更新频率 →</a>
      </section>
    </aside>
  );
}
