import { useEffect, useRef, useState } from "react";
import { fetchSearch, type SearchHit } from "../api";
import { shortTime } from "../time";

type Props = {
  open: boolean;
  onClose: () => void;
  onSelect: (hit: SearchHit) => void;
  initialQuery?: string;
};

export default function SearchPalette({ open, onClose, onSelect, initialQuery = "" }: Props) {
  const [q, setQ] = useState("");
  const [hits, setHits] = useState<SearchHit[]>([]);
  const [loading, setLoading] = useState(false);
  const [active, setActive] = useState(-1);
  const inputRef = useRef<HTMLInputElement>(null);
  const activeRef = useRef<HTMLDivElement>(null);

  // 打开时重置
  useEffect(() => {
    if (!open) return;
    setQ(initialQuery);
    setHits([]);
    setActive(-1);
    const t = setTimeout(() => inputRef.current?.focus(), 30);
    return () => clearTimeout(t);
  }, [open, initialQuery]);

  // 检索（防抖）
  useEffect(() => {
    if (!open) return;
    const term = q.trim();
    if (!term) {
      setHits([]);
      setActive(-1);
      return;
    }
    setLoading(true);
    const t = setTimeout(() => {
      fetchSearch(term)
        .then((d) => {
          setHits(d.hits);
          setActive(d.hits.length ? 0 : -1);
        })
        .catch(() => {
          setHits([]);
          setActive(-1);
        })
        .finally(() => setLoading(false));
    }, 200);
    return () => clearTimeout(t);
  }, [q, open]);

  // 选中项滚进可视区
  useEffect(() => {
    activeRef.current?.scrollIntoView({ block: "nearest" });
  }, [active]);

  if (!open) return null;

  const move = (step: number) => {
    if (!hits.length) return;
    setActive((i) => (i < 0 ? 0 : (i + step + hits.length) % hits.length));
  };

  const onKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "ArrowDown") {
      e.preventDefault();
      move(1);
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      move(-1);
    } else if (e.key === "Enter") {
      e.preventDefault();
      const hit = hits[active] ?? hits[0];
      if (hit) onSelect(hit);
    }
  };

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
            onKeyDown={onKeyDown}
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
          {hits.map((h, i) => (
            <div
              key={`${h.kind}-${h.id}`}
              ref={i === active ? activeRef : undefined}
              className={`palette-hit ${i === active ? "active" : ""}`}
              onMouseEnter={() => setActive(i)}
              onClick={() => onSelect(h)}
            >
              <span className="ph-kind">{h.kind === "event" ? "事件" : h.source_name}</span>
              <span className="ph-title">{h.title}</span>
              <span className="ph-time">{shortTime(h.published_at)}</span>
            </div>
          ))}
        </div>

        <div className="palette-foot">
          <span>
            <b>↑</b>
            <b>↓</b> 选择
          </span>
          <span>
            <b>↵</b> 打开
          </span>
          <span>
            <b>ESC</b> 关闭
          </span>
        </div>
      </div>
    </div>
  );
}
