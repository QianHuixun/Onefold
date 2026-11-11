export type Topic = { slug: string; name: string };

export type EventItem = {
  id: number;
  title: string;
  summary: string;
  topic_slug: string;
  topic_name: string;
  first_seen_at: string;
  last_seen_at: string;
  article_count: number;
  source_count: number;
  sources: string[];
};

export type EventPage = {
  items: EventItem[];
  total: number;
  offset: number;
  limit: number;
};

export type Stats = {
  events: number;
  sources: number;
  articles: number;
  updated_at: string | null;
};

export type ArticleItem = {
  id: number;
  title: string;
  url: string;
  source_name: string;
  published_at: string | null;
  content_length: number;
  similarity: number;
};

export type EventDetail = EventItem & { articles: ArticleItem[] };
