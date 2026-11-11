import { useCallback, useEffect, useState } from "react";
import {
  createSource,
  deleteSource,
  fetchLogs,
  listSources,
  triggerFetch,
  updateSource,
  type AdminSource,
  type FetchLogItem,
} from "../api";
import { shortTime } from "../time";

const TOKEN_KEY = "onefold_admin_token";

import { Link } from "react-router-dom";
import { fetchTopics } from "../api";

export default function AdminPanel() {
  const [token, setToken] = useState(() => localStorage.getItem(TOKEN_KEY) ?? "");
  const [draft, setDraft] = useState(token);
  const [sources, setSources] = useState<AdminSource[]>([]);
  const [logs, setLogs] = useState<FetchLogItem[]>([]);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [busy, setBusy] = useState(false);

  const [name, setName] = useState("");
  const [feedUrl, setFeedUrl] = useState("");
  const [topicSlug, setTopicSlug] = useState("ai");
  const [topics, setTopics] = useState<{ slug: string; name: string }[]>([]);

  const load = useCallback(
    async (t: string) => {
      if (!t) return;
      setError("");
      try {
        const [list, history] = await Promise.all([listSources(t), fetchLogs(t)]);
        setSources(list);
        setLogs(history);
      } catch (exc) {
        setError(exc instanceof Error ? exc.message : "加载失败");
      }
    },
    [],
  );

  useEffect(() => {
    fetchTopics().then((list) => {
      setTopics(list);
      if (list[0]) setTopicSlug(list[0].slug);
    }).catch(() => undefined);
  }, []);

  useEffect(() => {
    if (token) load(token);
  }, [token, load]);

  const saveToken = () => {
    localStorage.setItem(TOKEN_KEY, draft.trim());
    setToken(draft.trim());
    setNotice("");
  };

  const act = async (fn: () => Promise<unknown>, message: string) => {
    setBusy(true);
    setError("");
    setNotice("");
    try {
      await fn();
      setNotice(message);
      await load(token);
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : "操作失败");
    } finally {
      setBusy(false);
    }
  };

  if (!token) {
    return (
      <section className="admin">
        <header className="admin-head">
          <div>
            <div className="eyebrow">管理</div>
            <h1>需要 Token</h1>
          </div>
        </header>
        <p className="admin-hint">
          写操作凭 Admin-Token。默认值是 <code>dev-token</code>，生产环境请在 <code>.env</code> 里改掉。
        </p>
        <div className="admin-token">
          <input
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            placeholder="粘贴 Admin-Token"
            onKeyDown={(e) => e.key === "Enter" && saveToken()}
          />
          <button className="btn solid" onClick={saveToken}>
            保存并进入
          </button>
        </div>
      </section>
    );
  }

  return (
    <section className="admin">
      <header className="admin-head">
        <div>
          <div className="eyebrow">管理</div>
          <h1>数据源</h1>
          <div className="admin-sub">
            {sources.length} 个源 · {sources.filter((s) => s.enabled).length} 个启用
          </div>
        </div>
        <div className="admin-actions">
          <button className="btn" onClick={() => load(token)} disabled={busy}>
            刷新
          </button>
          <button
            className="btn"
            onClick={() => act(() => triggerFetch(token), "已触发抓取，一两分钟后看日志")}
            disabled={busy}
          >
            立即抓取
          </button>
          <Link className="btn" to="/admin/eval">
            实验台
          </Link>
          <button className="btn solid" onClick={() => setToken("")}>
            退出
          </button>
        </div>
      </header>

      {error && <p className="admin-alert">{error}</p>}
      {notice && <p className="admin-ok">{notice}</p>}

      <table className="admin-table">
        <thead>
          <tr>
            <th>名称</th>
            <th>主题</th>
            <th>Feed</th>
            <th className="num">文章</th>
            <th>最近抓取</th>
            <th className="num">失败</th>
            <th>状态</th>
            <th />
          </tr>
        </thead>
        <tbody>
          {sources.map((s) => (
            <tr key={s.id}>
              <td>{s.name}</td>
              <td className="dim">{s.topic_name}</td>
              <td className={`dim mono ellipsis${s.feed_url ? "" : " warn"}`}>
                {s.feed_url || "无 Feed"}
              </td>
              <td className="num mono">{s.article_count}</td>
              <td className="dim">{s.last_fetch_at ? shortTime(s.last_fetch_at) : "—"}</td>
              <td className={`num mono ${s.fail_count > 0 ? "warn" : "dim"}`}>{s.fail_count}</td>
              <td>
                <button
                  className={`toggle ${s.enabled ? "on" : ""}`}
                  onClick={() =>
                    act(
                      () => updateSource(token, s.id, { enabled: !s.enabled }),
                      `${s.name} 已${s.enabled ? "停用" : "启用"}`,
                    )
                  }
                  disabled={busy}
                >
                  {s.enabled ? "启用" : "停用"}
                </button>
              </td>
              <td className="right">
                <button
                  className="link danger"
                  onClick={() => {
                    if (!confirm(`删除「${s.name}」？这个源下的文章有 ${s.article_count} 篇，删不掉的话请改用停用。`)) return;
                    act(() => deleteSource(token, s.id), `${s.name} 已删除`);
                  }}
                  disabled={busy}
                >
                  删除
                </button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>

      <div className="admin-add">
        <div className="rail-title">添加源</div>
        <div className="admin-form">
          <input value={name} onChange={(e) => setName(e.target.value)} placeholder="名称，如 少数派" />
          <input
            value={feedUrl}
            onChange={(e) => setFeedUrl(e.target.value)}
            placeholder="Feed 地址，https://…"
          />
          <select value={topicSlug} onChange={(e) => setTopicSlug(e.target.value)}>
            {topics.map((t) => (
              <option key={t.slug} value={t.slug}>
                {t.name}
              </option>
            ))}
          </select>
          <button
            className="btn solid"
            disabled={busy || !name.trim() || !feedUrl.trim()}
            onClick={() =>
              act(async () => {
                await createSource(token, { name: name.trim(), feed_url: feedUrl.trim(), topic_slug: topicSlug });
                setName("");
                setFeedUrl("");
              }, "已添加，下次抓取生效")
            }
          >
            添加
          </button>
        </div>
      </div>

      <div className="admin-logs">
        <div className="rail-title">最近抓取</div>
        {logs.length === 0 && <p className="admin-hint">还没有记录。</p>}
        {logs.map((log, i) => (
          <div className="log-row" key={`${log.started_at}-${i}`}>
            <span className="mono dim">{shortTime(log.started_at)}</span>
            <span>{log.source_name}</span>
            <span className="mono dim">+{log.new_count}</span>
            <span className="mono dim">重 {log.dup_count}</span>
            <span className={log.error ? "warn ellipsis" : "dim ellipsis"}>
              {log.error || "OK"}
            </span>
          </div>
        ))}
      </div>
    </section>
  );
}
