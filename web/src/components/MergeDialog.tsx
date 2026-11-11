import { useEffect, useMemo, useState } from "react";
import { fetchEvents } from "../api";
import type { EventItem } from "../types";

type Props = {
  currentId: number;
  onClose: () => void;
  onPick: (targetId: number) => void;
};

export default function MergeDialog({ currentId, onClose, onPick }: Props) {
  const [events, setEvents] = useState<EventItem[]>([]);
  const [q, setQ] = useState("");

  useEffect(() => {
    fetchEvents()
      .then((page) => setEvents(page.items.filter((e) => e.id !== currentId)))
      .catch(() => undefined);
  }, [currentId]);

  const list = useMemo(() => {
    const needle = q.trim().toLowerCase();
    const base = needle
      ? events.filter((e) => `${e.title} ${e.summary}`.toLowerCase().includes(needle))
      : events;
    return base.slice(0, 12);
  }, [events, q]);

  return (
    <div className="merge-backdrop" onClick={onClose}>
      <div className="merge-panel" onClick={(e) => e.stopPropagation()}>
        <div className="merge-head">
          <span>合并到哪个事件</span>
          <button className="link" onClick={onClose}>
            取消
          </button>
        </div>
        <input
          className="merge-search"
          value={q}
          onChange={(e) => setQ(e.target.value)}
          placeholder="按标题过滤"
          autoFocus
        />
        <div className="merge-list">
          {list.map((e) => (
            <button key={e.id} className="merge-item" onClick={() => onPick(e.id)}>
              <span className="merge-title">{e.title}</span>
              <span className="merge-meta">
                {e.source_count} 家 · {new Date(e.first_seen_at).toLocaleDateString("zh-CN")}
              </span>
            </button>
          ))}
          {list.length === 0 && <p className="admin-hint">没有匹配的事件。</p>}
        </div>
      </div>
    </div>
  );
}
