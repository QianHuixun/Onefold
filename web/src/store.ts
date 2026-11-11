import { useCallback, useEffect, useState } from "react";

const READ_KEY = "onefold_read";
const STAR_KEY = "onefold_starred";

function load(key: string): number[] {
  try {
    const raw = localStorage.getItem(key);
    const parsed: unknown = raw ? JSON.parse(raw) : [];
    return Array.isArray(parsed) ? parsed.filter((x): x is number => typeof x === "number") : [];
  } catch {
    return [];
  }
}

function save(key: string, ids: Set<number>) {
  try {
    localStorage.setItem(key, JSON.stringify([...ids]));
  } catch {
    // 隐私模式下写不进去，静默失败，不影响阅读
  }
}

/**
 * 收藏与已读都存 localStorage（PRD 4.1：无账号，换来零注册）。
 * 代价是换设备不同步、清缓存会丢。
 */
export function useEventFlags() {
  const [read, setRead] = useState<Set<number>>(() => new Set(load(READ_KEY)));
  const [starred, setStarred] = useState<Set<number>>(() => new Set(load(STAR_KEY)));

  useEffect(() => save(READ_KEY, read), [read]);
  useEffect(() => save(STAR_KEY, starred), [starred]);

  const markRead = useCallback((id: number) => {
    setRead((prev) => (prev.has(id) ? prev : new Set(prev).add(id)));
  }, []);

  const toggleStar = useCallback((id: number) => {
    setStarred((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }, []);

  const exportStarred = useCallback(() => {
    const payload = JSON.stringify({ exported_at: new Date().toISOString(), starred: [...starred] }, null, 2);
    const url = URL.createObjectURL(new Blob([payload], { type: "application/json" }));
    const link = document.createElement("a");
    link.href = url;
    link.download = "onefold-starred.json";
    link.click();
    URL.revokeObjectURL(url);
  }, [starred]);

  return { read, starred, markRead, toggleStar, exportStarred };
}
