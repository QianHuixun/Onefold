import type { EventItem } from "../types";
import { clock, dayLabel } from "../time";

type Props = {
  event: EventItem;
  read?: boolean;
  starred?: boolean;
  onOpen: (id: number) => void;
  onStar: (id: number) => void;
};

export default function EventRow({ event, read, starred, onOpen, onStar }: Props) {
  return (
    <article className={`event ${read ? "is-read" : ""}`} onClick={() => onOpen(event.id)}>
      <button
        className={`star ${starred ? "on" : ""}`}
        onClick={(e) => {
          e.stopPropagation();
          onStar(event.id);
        }}
        aria-label={starred ? "取消收藏" : "收藏"}
      >
        {starred ? "★" : "☆"}
      </button>
      <div className="event-top">
        <span className="k">{event.topic_name}</span>
        <span>·</span>
        <time>
          {dayLabel(event.first_seen_at)} {clock(event.first_seen_at)}
        </time>
        {read && <span className="read-tag">已读</span>}
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
