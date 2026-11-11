import type { EventItem } from "../types";
import { clock, dayLabel } from "../time";

export default function Hero({ event }: { event: EventItem }) {
  return (
    <section className="hero">
      <div className="eyebrow">
        <span>今日头条</span>
        <span className="sep" />
        <span className="tag">
          {dayLabel(event.first_seen_at)} {clock(event.first_seen_at)}
        </span>
        <span className="sep" />
        <span className="tag">{event.topic_name}</span>
      </div>
      <h1>{event.title}</h1>
      <p>{event.summary}</p>
      <div className="hero-meta">
        <span>
          <b>{event.source_count}</b> 家媒体报道
        </span>
        <span className="dot" />
        <span className="hero-srcs">{event.sources.join(" · ")}</span>
        <a className="hero-go" href="#">
          阅读事件 <span>→</span>
        </a>
      </div>
    </section>
  );
}
