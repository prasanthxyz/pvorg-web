import { useCallback, useEffect, useState } from "react";

export interface MappingRow {
  filename: string;
  title: string;
  studio: string;
  tgp_url: string;
  map: Record<string, "yes" | "no" | "undecided">;
}

export interface FetchResult {
  total: number;
  page: number;
  columns: string[];
  videos: MappingRow[];
}

export interface MappingTableProps {
  fetchFn: (page: number, pageSize: number, hideDecided: boolean) => Promise<FetchResult>;
  saveFn: (mappings: Record<string, Record<string, string>>) => Promise<{ updated: number }>;
}

const PAGE_SIZE = 20;

type TriState = "yes" | "no" | "undecided";

function cycleState(current: TriState): TriState {
  if (current === "undecided") return "yes";
  if (current === "yes") return "no";
  return "undecided";
}

export default function MappingTable({ fetchFn, saveFn }: MappingTableProps) {
  const [videos, setVideos] = useState<MappingRow[]>([]);
  const [columns, setColumns] = useState<string[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [hideDecided, setHideDecided] = useState(true);
  const [loading, setLoading] = useState(true);
  const [localChanges, setLocalChanges] = useState<
    Record<string, Record<string, TriState>>
  >({});
  const [saving, setSaving] = useState(false);
  const [hoveredUrl, setHoveredUrl] = useState<string | null>(null);
  const [hoverPos, setHoverPos] = useState({ x: 0, y: 0 });

  const hasChanges = Object.keys(localChanges).length > 0;

  const fetchPage = useCallback(
    async (p: number, hide: boolean) => {
      setLoading(true);
      try {
        const data = await fetchFn(p, PAGE_SIZE, hide);
        setVideos(data.videos);
        setColumns(data.columns);
        setTotal(data.total);
        setPage(data.page);
      } finally {
        setLoading(false);
      }
    },
    [fetchFn],
  );

  useEffect(() => {
    fetchPage(1, hideDecided);
  }, [fetchPage, hideDecided]);

  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE));

  const getState = (filename: string, col: string): TriState => {
    return localChanges[filename]?.[col] ?? (
      videos.find((v) => v.filename === filename)?.map[col] ?? "undecided"
    );
  };

  const toggleState = (filename: string, col: string) => {
    const current = getState(filename, col);
    const next = cycleState(current);
    setLocalChanges((prev) => {
      const videoMap = { ...(prev[filename] ?? {}) };
      const original = videos.find((v) => v.filename === filename)?.map[col];
      if (next === original) {
        delete videoMap[col];
        if (Object.keys(videoMap).length === 0) {
          const { [filename]: _, ...rest } = prev;
          return rest;
        }
      } else {
        videoMap[col] = next;
      }
      return { ...prev, [filename]: videoMap };
    });
  };

  const handleSave = async () => {
    if (!hasChanges) return;
    setSaving(true);
    try {
      const mappings: Record<string, Record<string, string>> = {};
      for (const [filename, changes] of Object.entries(localChanges)) {
        mappings[filename] = { ...changes };
      }
      await saveFn(mappings);
      setLocalChanges({});
      fetchPage(page, hideDecided);
    } finally {
      setSaving(false);
    }
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
        <label style={{ display: "flex", alignItems: "center", gap: 6, fontSize: 13, cursor: "pointer" }}>
          <input
            type="checkbox"
            checked={hideDecided}
            onChange={() => {
              setHideDecided((h) => !h);
              setPage(1);
            }}
          />
          Hide fully decided
        </label>
        <div style={{ flex: 1 }} />
        {hasChanges && (
          <span style={{ fontSize: 12, color: "#f6ad55" }}>
            {Object.keys(localChanges).length} unsaved change(s)
          </span>
        )}
        <button
          onClick={handleSave}
          disabled={!hasChanges || saving}
          style={{
            ...toolBtnStyle,
            background: hasChanges ? "var(--accent)" : "var(--tag-bg)",
            color: hasChanges ? "#fff" : "var(--text-secondary)",
          }}
        >
          {saving ? "Saving..." : "Save"}
        </button>
        <span style={{ fontSize: 13, color: "var(--text-secondary)" }}>
          {total} videos
        </span>
      </div>

      {/* Table */}
      <div style={{ flex: 1, overflow: "auto" }}>
        {loading ? (
          <div style={{ textAlign: "center", padding: 48, fontSize: 18 }}>Loading...</div>
        ) : videos.length === 0 ? (
          <div style={{ textAlign: "center", padding: 48, fontSize: 18 }}>
            {hideDecided
              ? `All videos are fully decided. Uncheck the filter to see all.`
              : "No videos found."}
          </div>
        ) : (
          <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 13 }}>
            <thead>
              <tr style={{ borderBottom: "2px solid var(--border)", background: "var(--bg-secondary)" }}>
                <th style={thStyle}>TGP</th>
                <th style={{ ...thStyle, textAlign: "left" }}>Video</th>
                {columns.map((c) => (
                  <th key={c} style={{ ...thStyle, minWidth: 70 }}>{c}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {videos.map((v) => (
                <tr key={v.filename} style={{ borderBottom: "1px solid var(--border)" }}>
                  <td style={{ ...tdStyle, width: 80, padding: 4 }}>
                    <img
                      src={v.tgp_url}
                      alt={v.title}
                      style={{ width: 72, height: 40, objectFit: "cover", borderRadius: 4, cursor: "pointer", display: "block" }}
                      onMouseEnter={(e) => handleMouseEnter(v.tgp_url, e)}
                      onMouseMove={handleMouseMove}
                      onMouseLeave={() => setHoveredUrl(null)}
                    />
                  </td>
                  <td style={{ ...tdStyle, textAlign: "left", maxWidth: 200, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }} title={v.filename}>
                    {v.title || v.filename}
                  </td>
                  {columns.map((c) => {
                    const state = getState(v.filename, c);
                    const isChanged = localChanges[v.filename]?.[c] !== undefined;
                    return (
                      <td key={c} style={tdStyle}>
                        <button
                          onClick={() => toggleState(v.filename, c)}
                          style={{
                            width: 32,
                            height: 24,
                            borderRadius: 4,
                            border: isChanged ? "2px solid #f6ad55" : "1px solid var(--border)",
                            background: state === "yes"
                              ? "#38a169"
                              : state === "no"
                                ? "#e53e3e"
                                : "var(--tag-bg)",
                            color: state === "undecided" ? "var(--text-secondary)" : "#fff",
                            fontSize: 14,
                            fontWeight: 700,
                            cursor: "pointer",
                            lineHeight: 1,
                          }}
                          title={`${state} (click to cycle)`}
                        >
                          {state === "yes" ? "\u2713" : state === "no" ? "\u2717" : "\u2014"}
                        </button>
                      </td>
                    );
                  })}
                </tr>
              ))}
            </tbody>
          </table>
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
          <button onClick={() => fetchPage(page - 1, hideDecided)} disabled={page <= 1} style={toolBtnStyle}>
            Prev
          </button>
          <span style={{ fontSize: 13 }}>Page {page} / {totalPages}</span>
          <button onClick={() => fetchPage(page + 1, hideDecided)} disabled={page >= totalPages} style={toolBtnStyle}>
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
          <img src={hoveredUrl} alt="Preview" style={{ width: "100%", display: "block" }} />
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

const thStyle: React.CSSProperties = {
  padding: "8px 6px",
  textAlign: "center",
  fontWeight: 600,
  fontSize: 12,
  position: "sticky",
  top: 0,
  background: "var(--bg-secondary)",
  zIndex: 1,
};

const tdStyle: React.CSSProperties = {
  padding: "6px",
  textAlign: "center",
  verticalAlign: "middle",
};
