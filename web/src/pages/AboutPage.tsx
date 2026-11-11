import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { fetchSources, fetchStats } from "../api";
import { clock } from "../time";

type Source = { name: string; topic: string; articles: number };

const SECTIONS = [
  ["what", "这是什么"],
  ["how", "怎么工作"],
  ["sources", "数据来源"],
  ["update", "更新与时效"],
  ["disclaimer", "摘要与免责"],
  ["tech", "技术说明"],
  ["contact", "联系"],
] as const;

export default function AboutPage() {
  const [sources, setSources] = useState<Source[]>([]);
  const [stats, setStats] = useState<{ events: number; sources: number; articles: number; updated_at: string | null } | null>(null);
  const [active, setActive] = useState("what");

  useEffect(() => {
    fetchSources().then(setSources).catch(() => undefined);
    fetchStats().then(setStats).catch(() => undefined);
  }, []);

  useEffect(() => {
    const onScroll = () => {
      let current: string = SECTIONS[0][0];
      for (const [id] of SECTIONS) {
        const el = document.getElementById(id);
        if (el && el.getBoundingClientRect().top < 140) current = id;
      }
      setActive(current);
    };
    window.addEventListener("scroll", onScroll, { passive: true });
    onScroll();
    return () => window.removeEventListener("scroll", onScroll);
  }, []);

  return (
    <section className="about">
      <header className="about-head">
        <div className="eyebrow">
          <span>关于</span>
          <span className="sep" />
          <span className="tag">Onefold</span>
        </div>
        <h1>一件事，只读一遍</h1>
        <p>
          归一（Onefold）把多个来源里同一件事的报道合并成一个事件，每个事件配一句话摘要。不做推荐，不做社交，不加登录墙——打开就能看。
        </p>
        <div className="about-ver">
          最后更新 2026-11-11 · v0.1
          {stats ? ` · 当前收录 ${stats.events} 个事件、${stats.articles} 篇文章` : ""}
          {stats?.updated_at ? ` · 数据更新于 ${clock(stats.updated_at)}` : ""}
        </div>
      </header>

      <div className="about-grid">
        <div className="prose">
          <h2 id="what">这是什么</h2>
          <p>
            现在的资讯工具不缺「汇聚」，缺「归并」。同一件事会在几小时内被六家媒体重复报道，标题不同、角度不同、正文大面积重叠。读第二遍的时候，你已经在浪费生命了。
          </p>
          <p>
            归一以事件为单位组织信息，而不是以文章为单位。首页每一条是一个事件，点进去能看到六家媒体分别怎么说，以及它们出现的先后顺序。
          </p>

          <h2 id="how">怎么工作</h2>
          <div className="flow">
            <div>
              <div className="n">01</div>
              <h3>抓取</h3>
              <p>每天 00:00 拉一次 RSS，单源失败不影响其他源。</p>
            </div>
            <div>
              <div className="n">02</div>
              <h3>去重</h3>
              <p>SimHash 指纹比对，先把同一篇的转载剔掉。</p>
            </div>
            <div>
              <div className="n">03</div>
              <h3>聚类</h3>
              <p>标题与首段向量加时间窗，判为同一件事的归到一起。</p>
            </div>
            <div>
              <div className="n">04</div>
              <h3>摘要</h3>
              <p>合并后的多篇正文交给模型，生成一句话。</p>
            </div>
          </div>
          <p>合并错了可以手动拆分或修正，这些修正会留下来作为后续调参的样本。</p>

          <h2 id="sources">数据来源</h2>
          <p>
            目前覆盖 {sources.length || stats?.sources || 0} 个来源。只抓取公开发布的 RSS，正文保留原文链接。
          </p>
          <table className="about-table">
            <thead>
              <tr>
                <th>来源</th>
                <th>主题</th>
                <th className="num">文章</th>
              </tr>
            </thead>
            <tbody>
              {sources.map((s) => (
                <tr key={s.name}>
                  <td>{s.name}</td>
                  <td className="dim">{s.topic}</td>
                  <td className="num mono dim">{s.articles}</td>
                </tr>
              ))}
            </tbody>
          </table>
          <p>机器之心、36氪目前没有可用的公开 RSS，暂未接入。失效的源会被标记。</p>

          <h2 id="update">更新与时效</h2>
          <ul>
            <li>每天 00:00 抓取一次，单次约 1 分钟</li>
            <li>单源失败自动重试一次，连续失败计入失败次数，可在管理页停用</li>
            <li>事件摘要异步生成，先出标题、稍后补摘要</li>
            <li>数据库快照降级尚未实现，数据库挂了首页会直接报错</li>
          </ul>

          <h2 id="disclaimer">摘要与免责</h2>
          <ul>
            <li>摘要由 DeepSeek 生成，提示词限定「只陈述材料里出现过的事实」</li>
            <li>没有配置模型密钥时会降级为抽取式摘要，页面会标明是哪种</li>
            <li>摘要只用于判断要不要读，事实以原文为准，每条事件都能点回原文</li>
            <li>不做翻译，英文源保持原文</li>
          </ul>

          <h2 id="tech">技术说明</h2>
          <ul>
            <li>后端 FastAPI，数据库 SQLite 单文件，备份就是复制文件</li>
            <li>中文检索用 jieba 预分词写入 FTS5 索引列</li>
            <li>聚类用 TF-IDF 向量加时间窗，阈值在实验台上调</li>
            <li>前端 React + Vite，只支持桌面浏览器（≥1280px）</li>
          </ul>

          <h2 id="contact">联系</h2>
          <p>这是一个个人项目，不做商业化。问题、建议、发现合并错误的例子，都欢迎发邮件。</p>
          <ul>
            <li>邮箱 junxundhd@gmail.com</li>
            <li>
              代码 <a href="https://github.com/QianHuixun/Onefold">github.com/QianHuixun/Onefold</a>
            </li>
            <li>
              <Link to="/">回到今日事件</Link>
            </li>
          </ul>
        </div>

        <aside className="toc">
          <div className="rail-title">本页目录</div>
          {SECTIONS.map(([id, label]) => (
            <a key={id} href={`#${id}`} className={active === id ? "on" : ""}>
              {label}
            </a>
          ))}
        </aside>
      </div>
    </section>
  );
}
