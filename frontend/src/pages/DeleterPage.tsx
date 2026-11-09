import { useCallback, useEffect, useState } from "react";
import { deleteVideos, getVideos } from "../api";
import type { VideoListItem } from "../types";

const PAGE_SIZE = 24;

export default function DeleterPage() {
  const [videos, setVideos] = useState<VideoListItem[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [hoveredUrl, setHoveredUrl] = useState<string | null>(null);
  const [hoverPos, setHoverPos] = useState({ x: 0, y: 0 });
  const [loading, setLoading] = useState(true);
  const [feedback, setFeedback] = useState<string | null>(null);

  const fetchPage = useCallback(async (p: number) => {
    setLoading(true);
    try {
      const data = await getVideos(p, PAGE_SIZE);
      setVideos(data.videos);
      setTotal(data.total);
      setPage(data.page);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchPage(1);
  }, [fetchPage]);

  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE));

  const toggleSelect = (filename: string) => {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(filename)) next.delete(filename);
      else next.add(filename);
      return next;
    });
  };

  const selectAll = () => {
    setSelected(new Set(videos.map((v) => v.filename)));
  };

  const deselectAll = () => {
    setSelected(new Set());
  };

  const handleDelete = async () => {
    if (selected.size === 0) return;
    const confirmed = window.confirm(`Delete ${selected.size} video(s)? This cannot be undone.`);
    if (!confirmed) return;

    setFeedback(null);
    try {
      const result = await deleteVideos(Array.from(selected));
      const parts: string[] = [`Deleted ${result.deleted} video(s).`];
      if (result.errors && result.errors.length > 0) {
        parts.push(`${result.errors.length} failed.`);
      }
      setFeedback(parts.join(" "));
    } catch {
      setFeedback("Deletion request failed.");
    }
    setSelected(new Set());
    fetchPage(1);
  };

  const handleMouseEnter = (url: string, e: React.MouseEvent) => {
    setHoveredUrl(url);
    setHoverPos({ x: e.clientX, y: e.clientY });
  };

  const handleMouseMove = (e: React.MouseEvent) => {
    setHoverPos({ x: e.clientX, y: e.clientY });
  };

  return (
    <div style={{ display: "flex", flexDirection: "column", height: "100%", overflow: "hidden" }}>
      {/* Toolbar */}
      <div
        style={{
          display: "flex",
          alignItems: "center",
          gap: 12,
          padding: "8px 16px",
          borderBottom: "1px solid var(--border)",
          background: "var(--bg-secondary)",
          flexShrink: 0,
        }}
      >
        <button onClick={selectAll} style={toolBtnStyle}>Select All</button>
        <button onClick={deselectAll} style={toolBtnStyle}>Deselect All</button>
        <div style={{ flex: 1 }} />
        {selected.size > 0 && (
          <button
            onClick={handleDelete}
            style={{ ...toolBtnStyle, background: "#e53e3e", color: "#fff" }}
          >
            Delete Selected ({selected.size})
          </button>
        )}
        {feedback && (
          <span style={{ fontSize: 13, color: feedback.includes("failed") ? "#e53e3e" : "#38a169" }}>
            {feedback}
          </span>
        )}
        <span style={{ fontSize: 13, color: "var(--text-secondary)" }}>
          {total} videos
        </span>
      </div>

      {/* Grid */}
      <div style={{ flex: 1, overflow: "auto", padding: 16 }}>
        {loading ? (
          <div style={{ textAlign: "center", padding: 48, fontSize: 18 }}>Loading...</div>
        ) : videos.length === 0 ? (
          <div style={{ textAlign: "center", padding: 48, fontSize: 18 }}>No videos found.</div>
        ) : (
          <div
            style={{
              display: "grid",
              gridTemplateColumns: "repeat(auto-fill, minmax(200px, 1fr))",
              gap: 12,
            }}
          >
            {videos.map((v) => {
              const isSelected = selected.has(v.filename);
              return (
                <div
                  key={v.filename}
                  onClick={() => toggleSelect(v.filename)}
                  style={{
                    borderRadius: 8,
                    overflow: "hidden",
                    border: isSelected ? "2px solid #e53e3e" : "2px solid var(--border)",
                    background: "var(--bg-card)",
                    cursor: "pointer",
                    transition: "border-color 0.15s",
                  }}
                >
                  <div
                    style={{ position: "relative", width: "100%", aspectRatio: "16/9", overflow: "hidden" }}
                    onMouseEnter={(e) => handleMouseEnter(v.tgp_url, e)}
                    onMouseMove={handleMouseMove}
                    onMouseLeave={() => setHoveredUrl(null)}
                  >
                    <img
                      src={v.tgp_url}
                      alt={v.title}
                      style={{ width: "100%", height: "100%", objectFit: "cover", display: "block" }}
                    />
                    <input
                      type="checkbox"
                      checked={isSelected}
                      readOnly
                      style={{
                        position: "absolute",
                        top: 6,
                        left: 6,
                        width: 18,
                        height: 18,
                        accentColor: "#e53e3e",
                        pointerEvents: "none",
                      }}
                    />
                  </div>
                  <div
                    style={{
                      padding: "6px 8px",
                      fontSize: 12,
                      overflow: "hidden",
                      textOverflow: "ellipsis",
                      whiteSpace: "nowrap",
                      color: "var(--text-primary)",
                    }}
                    title={v.filename}
                  >
                    {v.title || v.filename}
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>

      {/* Pagination */}
      {totalPages > 1 && (
        <div
          style={{
            display: "flex",
            justifyContent: "center",
            alignItems: "center",
            gap: 12,
            padding: "8px 16px",
            borderTop: "1px solid var(--border)",
            background: "var(--bg-secondary)",
            flexShrink: 0,
          }}
        >
          <button
            onClick={() => fetchPage(page - 1)}
            disabled={page <= 1}
            style={toolBtnStyle}
          >
            Prev
          </button>
          <span style={{ fontSize: 13 }}>
            Page {page} / {totalPages}
          </span>
          <button
            onClick={() => fetchPage(page + 1)}
            disabled={page >= totalPages}
            style={toolBtnStyle}
          >
            Next
          </button>
        </div>
      )}

      {/* Hover zoom overlay */}
      {hoveredUrl && (
        <div
          style={{
            position: "fixed",
            left: Math.min(hoverPos.x + 16, window.innerWidth - 520),
            top: Math.min(hoverPos.y - 150, window.innerHeight - 320),
            width: 500,
            zIndex: 1000,
            pointerEvents: "none",
            borderRadius: 8,
            overflow: "hidden",
            boxShadow: "0 4px 24px rgba(0,0,0,0.8)",
            border: "2px solid var(--border)",
          }}
        >
          <img
            src={hoveredUrl}
            alt="Preview"
            style={{ width: "100%", display: "block" }}
          />
        </div>
      )}
    </div>
  );
}

const toolBtnStyle: React.CSSProperties = {
  padding: "4px 12px",
  borderRadius: 6,
  background: "var(--tag-bg)",
  color: "var(--text-primary)",
  fontSize: 13,
  fontWeight: 500,
  border: "none",
};
