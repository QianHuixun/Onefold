import type { EventDetail, EventPage, Stats } from "./types";

export type SearchHit = {
  kind: "event" | "article";
  id: number;
  title: string;
  snippet: string;
  source_name: string;
  url: string;
  published_at: string | null;
};

/** GitHub Pages 这类纯静态托管：读预导出的 JSON，不走后端。 */
export const STATIC_MODE = import.meta.env.VITE_STATIC === "1";

const DATA = (name: string) => `${import.meta.env.BASE_URL}data/${name}`;

async function getJSON<T>(url: string): Promise<T> {
  const res = await fetch(url);
  if (!res.ok) throw new Error(`${url} → ${res.status}`);
  return res.json() as Promise<T>;
}

export const fetchEvents = () =>
  STATIC_MODE ? getJSON<EventPage>(DATA("events.json")) : getJSON<EventPage>("/api/events?limit=100");

export const fetchStats = () =>
  STATIC_MODE ? getJSON<Stats>(DATA("stats.json")) : getJSON<Stats>("/api/stats");

export const fetchSources = () =>
  STATIC_MODE
    ? getJSON<{ name: string; topic: string; articles: number }[]>(DATA("sources.json"))
    : getJSON<{ name: string; topic: string; articles: number }[]>("/api/sources");

export const fetchTopics = () =>
  STATIC_MODE
    ? getJSON<{ slug: string; name: string }[]>(DATA("topics.json"))
    : getJSON<{ slug: string; name: string }[]>("/api/topics");

export const fetchEvent = (id: number) =>
  STATIC_MODE
    ? getJSON<EventDetail>(DATA(`events/${id}.json`))
    : getJSON<EventDetail>(`/api/events/${id}`);

let searchIndex: SearchHit[] | null = null;

export async function fetchSearch(q: string) {
  if (!STATIC_MODE) {
    return getJSON<{ q: string; hits: SearchHit[]; total: number }>(
      `/api/search?q=${encodeURIComponent(q)}`,
    );
  }

  // 静态模式：全量索引在前端过滤。没有分词，只能做子串匹配。
  searchIndex ??= await getJSON<SearchHit[]>(DATA("search.json"));
  const needle = q.trim().toLowerCase();
  if (!needle) return { q, hits: [], total: 0 };

  const matched = searchIndex.filter((h) =>
    `${h.title} ${h.snippet}`.toLowerCase().includes(needle),
  );

  // 事件已经覆盖的文章不再重复列出
  const eventTitles = new Set(matched.filter((h) => h.kind === "event").map((h) => h.title));
  const hits = matched
    .filter((h) => h.kind === "event" || !eventTitles.has(h.title))
    .sort((a, b) => {
      if (a.kind !== b.kind) return a.kind === "event" ? -1 : 1;
      return Number(b.title.toLowerCase().includes(needle)) - Number(a.title.toLowerCase().includes(needle));
    })
    .slice(0, 20);

  return { q, hits, total: hits.length };
}

/* ── 管理接口 ───────────────────────────────────────── */

export type AdminSource = {
  id: number;
  name: string;
  feed_url: string;
  topic_slug: string;
  topic_name: string;
  enabled: boolean;
  last_fetch_at: string | null;
  fail_count: number;
  article_count: number;
};

export type FetchLogItem = {
  source_name: string;
  started_at: string;
  finished_at: string | null;
  new_count: number;
  dup_count: number;
  error: string;
};


async function adminRequest<T>(
  url: string,
  token: string,
  init?: { method?: string; body?: unknown },
): Promise<T> {
  const res = await fetch(url, {
    method: init?.method ?? "GET",
    headers: { "Content-Type": "application/json", "X-Admin-Token": token },
    body: init?.body === undefined ? undefined : JSON.stringify(init.body),
  });
  if (res.status === 204) return undefined as T;
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error((data as { detail?: string }).detail ?? `请求失败 ${res.status}`);
  return data as T;
}

export const listSources = (token: string) =>
  adminRequest<AdminSource[]>("/api/admin/sources", token);

export const createSource = (token: string, body: { name: string; feed_url: string; topic_slug: string }) =>
  adminRequest<AdminSource>("/api/admin/sources", token, { method: "POST", body });

export const updateSource = (token: string, id: number, body: Record<string, unknown>) =>
  adminRequest<AdminSource>(`/api/admin/sources/${id}`, token, { method: "PATCH", body });

export const deleteSource = (token: string, id: number) =>
  adminRequest<void>(`/api/admin/sources/${id}`, token, { method: "DELETE" });

export const triggerFetch = (token: string, limit = 10) =>
  adminRequest<{ started: boolean }>(`/api/admin/fetch?limit=${limit}`, token, { method: "POST" });

export const fetchLogs = (token: string) =>
  adminRequest<FetchLogItem[]>("/api/admin/fetch-log?limit=12", token);

/* ── 阈值实验台 ─────────────────────────────────────── */

export type EvalPair = {
  id: number;
  similarity: number;
  label: number | null;
  auto: boolean;
  a_title: string;
  a_source: string;
  a_time: string | null;
  a_excerpt: string;
  b_title: string;
  b_source: string;
  b_time: string | null;
  b_excerpt: string;
};

export type EvalSummary = {
  total: number;
  labeled: number;
  auto_labeled: number;
  positives: number;
  negatives: number;
  topics: string[];
};

export type MetricPoint = {
  threshold: number;
  precision: number;
  recall: number;
  f1: number;
  tp: number;
  fp: number;
  fn: number;
};

export type EvalMetrics = {
  points: MetricPoint[];
  best_threshold: number | null;
  best_f1: number;
  labeled: number;
  positives: number;
};

export const evalSummary = (token: string) =>
  adminRequest<EvalSummary>("/api/admin/eval/summary", token);

export const evalPairs = (token: string, limit = 10) =>
  adminRequest<EvalPair[]>(`/api/admin/eval/pairs?limit=${limit}`, token);

export const evalLabel = (token: string, id: number, label: number) =>
  adminRequest<unknown>(`/api/admin/eval/pairs/${id}`, token, { method: "POST", body: { label } });

export const evalMetrics = (token: string) =>
  adminRequest<EvalMetrics>("/api/admin/eval/metrics", token);
