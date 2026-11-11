import type { EventPage, Stats } from "./types";

export type SearchHit = {
  kind: "event" | "article";
  id: number;
  title: string;
  snippet: string;
  source_name: string;
  published_at: string | null;
};

async function getJSON<T>(url: string): Promise<T> {
  const res = await fetch(url);
  if (!res.ok) throw new Error(`${url} → ${res.status}`);
  return res.json() as Promise<T>;
}

export const fetchEvents = () => getJSON<EventPage>("/api/events?limit=40");
export const fetchStats = () => getJSON<Stats>("/api/stats");

export async function fetchSearch(q: string) {
  const data = await getJSON<{ q: string; hits: SearchHit[]; total: number }>(
    `/api/search?q=${encodeURIComponent(q)}`,
  );
  return data;
}
