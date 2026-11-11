import type { EventItem } from "../types";
import { clock, dayLabel } from "../time";

export default function EventRow({ event }: { event: EventItem }) {
  return (
    <article className="event">
      <span className="star">☆</span>
      <div className="event-top">
        <span className="k">{event.topic_name}</span>
        <span>·</span>
        <time>
          {dayLabel(event.first_seen_at)} {clock(event.first_seen_at)}
        </time>
      </div>
      <h2>{event.title}</h2>
      <p>{event.summary}</p>
      <div className="event-foot">
        <span>{event.source_count} 家媒体</span>
        <span className="dot" />
        <span>{clock(event.first_seen_at)}</span>
        <span className="srcs">{event.sources.join(" · ")}</span>
      </div>
    </article>
  );
}
