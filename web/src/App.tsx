import { useCallback, useEffect, useState } from "react";
import { Route, Routes, useNavigate } from "react-router-dom";
import Footer from "./components/Footer";
import SearchPalette from "./components/SearchPalette";
import TopBar from "./components/TopBar";
import { fetchTopics } from "./api";
import AdminPage from "./pages/AdminPage";
import EvalPage from "./pages/EvalPage";
import EventPage from "./pages/EventPage";
import Home from "./pages/Home";
import SearchPage from "./pages/SearchPage";
import type { SearchHit } from "./api";

export default function App() {
  const navigate = useNavigate();
  const [topics, setTopics] = useState<{ slug: string; name: string }[]>([]);
  const [activeTopic, setActiveTopic] = useState("");
  const [searchOpen, setSearchOpen] = useState(false);

  useEffect(() => {
    fetchTopics().then(setTopics).catch(() => undefined);
  }, []);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        setSearchOpen(true);
      }
      if (e.key === "Escape") setSearchOpen(false);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  useEffect(() => {
    document.body.style.overflow = searchOpen ? "hidden" : "";
    return () => {
      document.body.style.overflow = "";
    };
  }, [searchOpen]);

  const goTopic = useCallback(
    (slug: string) => {
      setActiveTopic(slug);
      navigate(slug ? `/topic/${slug}` : "/");
    },
    [navigate],
  );

  const openHit = (hit: SearchHit) => {
    setSearchOpen(false);
    if (hit.kind === "event") navigate(`/e/${hit.id}`);
    else if (hit.url) window.open(hit.url, "_blank", "noopener");
  };

  return (
    <>
      <div className="scene" aria-hidden="true">
        <span className="glow g1" />
        <span className="glow g2" />
        <span className="glow g3" />
        <div className="grain" />
      </div>

      <TopBar
        topics={topics}
        active={activeTopic}
        onTopic={goTopic}
        onOpenSearch={() => setSearchOpen(true)}
      />

      <main className="plate">
        <Routes>
          <Route path="/" element={<Home onTopicChange={setActiveTopic} />} />
          <Route path="/topic/:slug" element={<Home onTopicChange={setActiveTopic} />} />
          <Route path="/e/:id" element={<EventPage />} />
          <Route path="/search" element={<SearchPage />} />
          <Route path="/admin" element={<AdminPage />} />
          <Route path="/admin/eval" element={<EvalPage />} />
          <Route path="*" element={<div className="state">这一页还没有做。</div>} />
        </Routes>
      </main>

      <Footer onAdmin={() => navigate("/admin")} />

      <SearchPalette
        open={searchOpen}
        onClose={() => setSearchOpen(false)}
        initialQuery=""
        onSelect={openHit}
      />
    </>
  );
}
