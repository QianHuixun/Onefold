import { Link } from "react-router-dom";
import { STATIC_MODE } from "../api";
import EvalPanel from "../components/EvalPanel";

export default function EvalPage() {
  if (STATIC_MODE) {
    return (
      <div className="state">
        静态部署下没有后端，「阈值实验台」需要连本地服务才能用。
        <br />
        在仓库根目录跑 <code>.venv/bin/uvicorn app.main:app --port 8000</code>，再用 <code>npm run dev</code> 打开。
      </div>
    );
  }

  return (
    <>
      <div className="crumb">
        <Link to="/">今日</Link>
        <span>/</span>
        <Link to="/admin">管理</Link>
        <span>/</span>
        <span className="now">实验台</span>
      </div>
      <EvalPanel />
    </>
  );
}
