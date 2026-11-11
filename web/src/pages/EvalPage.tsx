import { Link } from "react-router-dom";
import EvalPanel from "../components/EvalPanel";

export default function EvalPage() {
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
