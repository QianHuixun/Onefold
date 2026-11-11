import { useEffect, useRef, useState } from "react";
import { fetchSearch, type SearchHit } from "../api";
import { shortTime } from "../time";

type Props = { open: boolean; onClose: () => void; initialQuery?: string };

export default function SearchPalette({ open, onClose, initialQuery = "" }: Props) {
  const [q, setQ] = useState("");
  const [hits, setHits] = useState<SearchHit[]>([]);
  const [loading, setLoading] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (!open) return;
    setQ(initialQuery);
    setHits([]);
    const t = setTimeout(() => inputRef.current?.focus(), 30);
    return () => clearTimeout(t);
  }, [open, initialQuery]);

  useEffect(() => {
    if (!open) return;
    const term = q.trim();
    if (!term) {
      setHits([]);
      return;
    }
    setLoading(true);
    const t = setTimeout(() => {
      fetchSearch(term)
        .then((d) => setHits(d.hits))
        .catch(() => setHits([]))
        .finally(() => setLoading(false));
    }, 220);
    return () => clearTimeout(t);
  }, [q, open]);

  if (!open) return null;

  return (
    <div className="palette-backdrop" onClick={onClose}>
      <div className="palette" onClick={(e) => e.stopPropagation()}>
        <div className="palette-input">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8">
            <circle cx="11" cy="11" r="7" />
            <path d="M16.5 16.5L21 21" />
          </svg>
          <input
            ref={inputRef}
            value={q}
            onChange={(e) => setQ(e.target.value)}
            placeholder="搜索事件、来源、关键词"
          />
          <span className="kbd">ESC</span>
        </div>

        <div className="palette-body">
          {!q.trim() && <p className="palette-hint">试试：Gemini、OpenAI、量子计算</p>}
          {q.trim() && loading && <p className="palette-hint">检索中…</p>}
          {q.trim() && !loading && hits.length === 0 && (
            <p className="palette-hint">没有找到「{q.trim()}」</p>
          )}
          {hits.map((h) => (
            <div className="palette-hit" key={`${h.kind}-${h.id}`}>
              <span className="ph-kind">{h.kind === "event" ? "事件" : h.source_name}</span>
              <span className="ph-title">{h.title}</span>
              <span className="ph-time">{shortTime(h.published_at)}</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
