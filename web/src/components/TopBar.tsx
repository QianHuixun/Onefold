import { useState } from "react";
import { fullDate } from "../time";

type Props = {
  topics: { slug: string; name: string }[];
  active: string;
  onTopic: (slug: string) => void;
  onSearch: (q: string) => void;
};

export default function TopBar({ topics, active, onTopic, onSearch }: Props) {
  const [q, setQ] = useState("");

  return (
    <header className="topbar">
      <div className="topbar-in">
        <a className="brand" href="/">
          <span className="brand-cn">归一</span>
          <span className="brand-en">Onefold</span>
        </a>

        <nav className="nav">
          <a
            className={active === "" ? "on" : ""}
            onClick={() => onTopic("")}
            role="button"
          >
            今日
          </a>
          {topics.map((t) => (
            <a
              key={t.slug}
              className={active === t.slug ? "on" : ""}
              onClick={() => onTopic(t.slug)}
              role="button"
            >
              {t.name}
            </a>
          ))}
        </nav>

        <div className="top-right">
          <label className="search">
            <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8">
              <circle cx="11" cy="11" r="7" />
              <path d="M16.5 16.5L21 21" />
            </svg>
            <input
              value={q}
              onChange={(e) => setQ(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter" && q.trim()) onSearch(q.trim());
              }}
              placeholder="搜索事件、来源"
            />
          </label>
          <span className="topbar-date">{fullDate()}</span>
        </div>
      </div>
    </header>
  );
}
