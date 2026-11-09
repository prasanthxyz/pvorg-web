import { useCallback, useEffect, useState } from "react";
import { Route, Routes, useNavigate } from "react-router-dom";
import { getStatus } from "./api";
import type { AppStatus } from "./types";
import ViewerPage from "./pages/ViewerPage";
import ConfigPage from "./pages/ConfigPage";
import DeleterPage from "./pages/DeleterPage";
import MapperPage from "./pages/MapperPage";
import TagMapperPage from "./pages/TagMapperPage";
import Navbar from "./components/Navbar";

export default function App() {
  const [status, setStatus] = useState<AppStatus | null>(null);
  const navigate = useNavigate();

  useEffect(() => {
    let cancelled = false;
    const poll = async () => {
      while (!cancelled) {
        try {
          const s = await getStatus();
          setStatus(s);
          if (s.ready) break;
        } catch {
          /* server not up yet */
        }
        await new Promise((r) => setTimeout(r, 1000));
      }
    };
    poll();
    return () => {
      cancelled = true;
    };
  }, []);

  const handleKeyDown = useCallback(
    (e: KeyboardEvent) => {
      if (e.target instanceof HTMLInputElement || e.target instanceof HTMLTextAreaElement) return;
      if (e.key === "v") {
        e.preventDefault();
        navigate("/");
      } else if (e.key === "c") {
        e.preventDefault();
        navigate("/config");
      }
    },
    [navigate]
  );

  useEffect(() => {
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [handleKeyDown]);

  if (!status || !status.ready) {
    return (
      <div
        style={{
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
          justifyContent: "center",
          height: "100%",
          gap: 16,
        }}
      >
        <div style={{ fontSize: 24, fontWeight: 600 }}>
          {status?.progress || "Connecting to server..."}
        </div>
        <div
          style={{
            width: 48,
            height: 48,
            border: "4px solid var(--border)",
            borderTopColor: "var(--accent)",
            borderRadius: "50%",
            animation: "spin 1s linear infinite",
          }}
        />
        <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>
        {status && (
          <div style={{ color: "var(--text-secondary)", fontSize: 14 }}>
            {status.video_count} videos, {status.gallery_count} galleries
          </div>
        )}
      </div>
    );
  }

  return (
    <div style={{ display: "flex", flexDirection: "column", height: "100%" }}>
      <Navbar />
      <div style={{ flex: 1, overflow: "hidden" }}>
        <Routes>
          <Route path="/" element={<ViewerPage />} />
          <Route path="/config" element={<ConfigPage />} />
          <Route path="/deleter" element={<DeleterPage />} />
          <Route path="/mapper" element={<MapperPage />} />
          <Route path="/tag-mapper" element={<TagMapperPage />} />
        </Routes>
      </div>
    </div>
  );
}
