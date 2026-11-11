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

async function getJSON<T>(url: string): Promise<T> {
  const res = await fetch(url);
  if (!res.ok) throw new Error(`${url} → ${res.status}`);
  return res.json() as Promise<T>;
}

export const fetchEvents = () => getJSON<EventPage>("/api/events?limit=100");
export const fetchStats = () => getJSON<Stats>("/api/stats");
export const fetchTopics = () => getJSON<{ slug: string; name: string }[]>("/api/topics");
export const fetchEvent = (id: number) => getJSON<EventDetail>(`/api/events/${id}`);

export async function fetchSearch(q: string) {
  const data = await getJSON<{ q: string; hits: SearchHit[]; total: number }>(
    `/api/search?q=${encodeURIComponent(q)}`,
  );
  return data;
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
