type Props = {
  topics: { slug: string; name: string }[];
  active: string;
  counts: Record<string, number>;
  total: number;
  sources: number;
  onTopic: (slug: string) => void;
};

export default function IndexNav({ topics, active, counts, total, sources, onTopic }: Props) {
  return (
    <nav className="index">
      <a className={active === "" ? "on" : ""} onClick={() => onTopic("")}>
        全部 <span className="n">{total}</span>
      </a>
      {topics.map((t) => (
        <a key={t.slug} className={active === t.slug ? "on" : ""} onClick={() => onTopic(t.slug)}>
          {t.name} <span className="n">{counts[t.slug] ?? 0}</span>
        </a>
      ))}
      <div className="index-meta">{sources} 个来源</div>
    </nav>
  );
}
