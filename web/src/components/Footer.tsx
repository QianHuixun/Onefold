export default function Footer({ onAdmin }: { onAdmin?: () => void }) {
  return (
    <footer className="site-foot">
      <div className="foot-grid">
        <div>
          <div className="foot-brand">归一 Onefold</div>
          <p className="foot-tag">
            多源报道，一个事件。
            <br />
            Manifold reports, onefold story.
          </p>
        </div>

        <div className="foot-col">
          <div className="foot-h">浏览</div>
          <ul>
            <li>今日事件</li>
            <li>AI</li>
            <li>综合科技</li>
            <li>按日期浏览</li>
          </ul>
        </div>

        <div className="foot-col">
          <div className="foot-h">资源</div>
          <ul>
            <li>RSS 订阅</li>
            <li>GitHub</li>
            <li><a href="/about">关于本站</a></li>
            <li onClick={onAdmin}>管理入口</li>
          </ul>
        </div>

        <div className="foot-col">
          <div className="foot-h">说明</div>
          <p className="foot-note">
            每天 00:00 抓取一次。只收录公开发布的 RSS 内容，摘要由模型生成，事实以原文为准。
          </p>
        </div>
      </div>

      <div className="foot-bottom">
        <span>© 2026 Onefold · 归一</span>
        <span>个人项目 · 非商业用途</span>
      </div>
    </footer>
  );
}
