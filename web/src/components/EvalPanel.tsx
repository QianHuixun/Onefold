import { useEffect, useMemo, useState } from "react";
import {
  evalLabel,
  evalMetrics,
  evalPairs,
  evalSummary,
  type EvalMetrics,
  type EvalPair,
  type EvalSummary,
} from "../api";

const TOKEN_KEY = "onefold_admin_token";

export default function EvalPanel() {
  const token = localStorage.getItem(TOKEN_KEY) ?? "";
  const [summary, setSummary] = useState<EvalSummary | null>(null);
  const [metrics, setMetrics] = useState<EvalMetrics | null>(null);
  const [pairs, setPairs] = useState<EvalPair[]>([]);
  const [cursor, setCursor] = useState(0);
  const [tab, setTab] = useState<"label" | "curve">("label");
  const [threshold, setThreshold] = useState(0.35);
  const [error, setError] = useState("");

  const refresh = async () => {
    try {
      const [s, m] = await Promise.all([evalSummary(token), evalMetrics(token)]);
      setSummary(s);
      setMetrics(m);
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : "加载失败");
    }
  };

  const loadPairs = async () => {
    try {
      const list = await evalPairs(token, 20);
      setPairs(list);
      setCursor(0);
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : "加载失败");
    }
  };

  useEffect(() => {
    if (!token) {
      setError("先到管理页输入 Admin-Token");
      return;
    }
    refresh();
    loadPairs();
  }, [token]);

  const current = pairs[cursor];

  const judge = async (label: number) => {
    if (!current) return;
    await evalLabel(token, current.id, label);
    if (cursor + 1 < pairs.length) setCursor(cursor + 1);
    else await loadPairs();
    refresh();
  };

  const point = useMemo(() => {
    if (!metrics) return null;
    return (
      metrics.points.find((p) => Math.abs(p.threshold - threshold) < 0.001) ??
      metrics.points[0]
    );
  }, [metrics, threshold]);

  if (!token) {
    return (
      <section className="admin">
        <header className="admin-head">
          <div>
            <div className="eyebrow">实验台</div>
            <h1>需要 Token</h1>
          </div>
        </header>
        <p className="admin-hint">先到页脚「管理入口」输入 Admin-Token，再回来。</p>
      </section>
    );
  }

  return (
    <section className="admin">
      <header className="admin-head">
        <div>
          <div className="eyebrow">实验台</div>
          <h1>阈值与合并质量</h1>
          <div className="admin-sub">
            {summary
              ? `${summary.total} 组候选 · ${summary.labeled} 组已标注（${summary.positives} 正 / ${summary.negatives} 负）· 其中 ${summary.auto_labeled} 组为自动预标注`
              : "加载中"}
          </div>
        </div>
        <div className="admin-actions">
          <button className={`btn ${tab === "label" ? "solid" : ""}`} onClick={() => setTab("label")}>
            标注
          </button>
          <button className={`btn ${tab === "curve" ? "solid" : ""}`} onClick={() => setTab("curve")}>
            曲线
          </button>
        </div>
      </header>

      {error && <p className="admin-alert">{error}</p>}

      {tab === "label" && (
        <div className="eval-label">
          {!current && <p className="admin-hint">待标注的组已经清空。跑 `eval-build` 生成新的候选对。</p>}
          {current && (
            <>
              <div className="eval-progress">
                <span>
                  第 {cursor + 1} / {pairs.length} 组
                </span>
                <span className="mono dim">相似度 {current.similarity.toFixed(3)}</span>
                <span className="dim">判断下面两篇是不是同一件事</span>
              </div>

              <div className="eval-cards">
                {[current.a_title, current.b_title].map((title, i) => (
                  <article className="eval-card" key={i}>
                    <div className="eval-src">
                      {i === 0 ? current.a_source : current.b_source} ·{" "}
                      {(i === 0 ? current.a_time : current.b_time)
                        ? new Date((i === 0 ? current.a_time : current.b_time)!).toLocaleString("zh-CN", {
                            month: "2-digit",
                            day: "2-digit",
                            hour: "2-digit",
                            minute: "2-digit",
                          })
                        : "—"}
                    </div>
                    <h3>{title}</h3>
                    <p>{i === 0 ? current.a_excerpt : current.b_excerpt}</p>
                  </article>
                ))}
              </div>

              <div className="eval-actions">
                <button className="btn solid" onClick={() => judge(1)}>
                  同一件事
                </button>
                <button className="btn" onClick={() => judge(0)}>
                  不是同一件
                </button>
                <button className="link" onClick={() => setCursor(cursor + 1)}>
                  跳过
                </button>
              </div>
            </>
          )}
        </div>
      )}

      {tab === "curve" && metrics && (
        <div className="eval-curve">
          <div className="curve-head">
            <div>
              <div className="rail-title">当前阈值 {threshold.toFixed(2)}</div>
              <div className="curve-vals">
                <span>
                  精确率 <b>{point ? point.precision.toFixed(2) : "—"}</b>
                </span>
                <span>
                  召回率 <b>{point ? point.recall.toFixed(2) : "—"}</b>
                </span>
                <span>
                  F1 <b>{point ? point.f1.toFixed(2) : "—"}</b>
                </span>
              </div>
            </div>
            <div className="curve-best">
              最佳 F1 <b>{metrics.best_f1.toFixed(2)}</b>
              <span className="dim"> @ {metrics.best_threshold?.toFixed(2)}</span>
            </div>
          </div>

          <Chart metrics={metrics} threshold={threshold} />

          <input
            className="curve-slider"
            type="range"
            min={0.05}
            max={0.95}
            step={0.05}
            value={threshold}
            onChange={(e) => setThreshold(Number(e.target.value))}
          />

          <table className="admin-table">
            <thead>
              <tr>
                <th>阈值</th>
                <th className="num">精确率</th>
                <th className="num">召回率</th>
                <th className="num">F1</th>
                <th className="num">TP</th>
                <th className="num">FP</th>
                <th className="num">FN</th>
              </tr>
            </thead>
            <tbody>
              {metrics.points.map((p) => (
                <tr key={p.threshold} className={p.threshold === point?.threshold ? "row-active" : ""}>
                  <td className="mono">{p.threshold.toFixed(2)}</td>
                  <td className="num mono">{p.precision.toFixed(2)}</td>
                  <td className="num mono">{p.recall.toFixed(2)}</td>
                  <td className="num mono">{p.f1.toFixed(2)}</td>
                  <td className="num mono dim">{p.tp}</td>
                  <td className="num mono dim">{p.fp}</td>
                  <td className="num mono dim">{p.fn}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}

function Chart({ metrics, threshold }: { metrics: EvalMetrics; threshold: number }) {
  const W = 760;
  const H = 240;
  const PAD = { l: 36, r: 12, t: 12, b: 26 };
  const x = (t: number) => PAD.l + ((t - 0.05) / 0.9) * (W - PAD.l - PAD.r);
  const y = (v: number) => PAD.t + (1 - v) * (H - PAD.t - PAD.b);

  const line = (key: "precision" | "recall" | "f1") =>
    metrics.points.map((p, i) => `${i === 0 ? "M" : "L"}${x(p.threshold)},${y(p[key])}`).join(" ");

  return (
    <svg className="curve-svg" viewBox={`0 0 ${W} ${H}`} role="img" aria-label="阈值曲线">
      {[0, 0.25, 0.5, 0.75, 1].map((v) => (
        <g key={v}>
          <line x1={PAD.l} x2={W - PAD.r} y1={y(v)} y2={y(v)} stroke="rgba(255,255,255,.08)" />
          <text x={PAD.l - 8} y={y(v) + 3} textAnchor="end" className="axis">
            {v}
          </text>
        </g>
      ))}
      {[0.2, 0.4, 0.6, 0.8].map((t) => (
        <text key={t} x={x(t)} y={H - 8} textAnchor="middle" className="axis">
          {t.toFixed(1)}
        </text>
      ))}

      <line
        x1={x(threshold)}
        x2={x(threshold)}
        y1={PAD.t}
        y2={H - PAD.b}
        stroke="rgba(203,169,110,.55)"
        strokeDasharray="3 3"
      />

      <path d={line("precision")} fill="none" stroke="#cba96e" strokeWidth="1.6" />
      <path d={line("recall")} fill="none" stroke="#8fa6c0" strokeWidth="1.6" />
      <path d={line("f1")} fill="none" stroke="#e8e4db" strokeWidth="1.6" strokeDasharray="4 3" />
    </svg>
  );
}
