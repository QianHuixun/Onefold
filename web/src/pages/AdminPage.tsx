import { Link } from "react-router-dom";
import AdminPanel from "../components/AdminPanel";

export default function AdminPage() {
  return (
    <>
      <div className="crumb">
        <Link to="/">今日</Link>
        <span>/</span>
        <span className="now">管理</span>
      </div>
      <AdminPanel />
    </>
  );
}
