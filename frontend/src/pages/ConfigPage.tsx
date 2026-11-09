import { useCallback, useEffect, useState } from "react";
import { getConfig, updateConfig } from "../api";
import type { ConfigData } from "../types";
import TagSelector from "../components/TagSelector";

export default function ConfigPage() {
  const [config, setConfig] = useState<ConfigData | null>(null);

  const fetchConfig = useCallback(async () => {
    const data = await getConfig();
    setConfig(data);
  }, []);

  useEffect(() => {
    fetchConfig();
  }, [fetchConfig]);

  const handleGalleriesChange = useCallback(
    async (selected: string[]) => {
      const data = await updateConfig({ selected_galleries: selected });
      setConfig(data);
    },
    []
  );

  const handleStudiosChange = useCallback(
    async (selected: string[]) => {
      const data = await updateConfig({ selected_studios: selected });
      setConfig(data);
    },
    []
  );

  const handleTagsChange = useCallback(
    async (selected: string[]) => {
      const data = await updateConfig({ selected_tags: selected });
      setConfig(data);
    },
    []
  );

  const handleCastChange = useCallback(
    async (selected: string[]) => {
      const data = await updateConfig({ selected_cast: selected });
      setConfig(data);
    },
    []
  );

  if (!config) {
    return (
      <div style={{ display: "flex", alignItems: "center", justifyContent: "center", height: "100%", fontSize: 18 }}>
        Loading config...
      </div>
    );
  }

  return (
    <div style={{ display: "flex", height: "100%", overflow: "hidden" }}>
      {/* Selectors panel */}
      <div style={{ flex: 1, overflow: "auto", padding: 24 }}>
        <TagSelector
          label="Galleries"
          items={config.galleries}
          selected={new Set(config.selected_galleries)}
          onChange={handleGalleriesChange}
          enableContextMenu
        />
        <TagSelector
          label="Tags"
          items={config.tags}
          selected={new Set(config.selected_tags)}
          onChange={handleTagsChange}
        />
        <TagSelector
          label="Studios"
          items={config.studios}
          selected={new Set(config.selected_studios)}
          onChange={handleStudiosChange}
        />
        <TagSelector
          label="Cast"
          items={config.cast}
          selected={new Set(config.selected_cast)}
          onChange={handleCastChange}
        />
      </div>

      {/* Sample combinations panel */}
      <div
        style={{
          width: 340,
          borderLeft: "1px solid var(--border)",
          overflow: "auto",
          padding: 20,
          flexShrink: 0,
        }}
      >
        <div style={{ fontSize: 15, fontWeight: 600, marginBottom: 12 }}>
          Sample Combinations ({config.combination_count} total)
        </div>
        {config.sample_combinations.length === 0 ? (
          <div style={{ color: "var(--text-secondary)", fontSize: 14 }}>No combinations</div>
        ) : (
          <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
            {config.sample_combinations.map((c, i) => (
              <div
                key={i}
                style={{
                  display: "flex",
                  justifyContent: "space-between",
                  padding: "10px 12px",
                  background: "var(--tag-bg)",
                  borderRadius: 8,
                  fontSize: 13,
                  gap: 8,
                }}
              >
                <span style={{ overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap", flex: 1 }}>
                  {c.video}
                </span>
                <span style={{ color: "var(--text-secondary)", flexShrink: 0 }}>{c.gallery}</span>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
