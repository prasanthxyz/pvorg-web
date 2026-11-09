import { useCallback } from "react";

interface TagSelectorProps {
  label: string;
  items: string[];
  selected: Set<string>;
  onChange: (selected: string[]) => void;
  /** Enable right-click context for "select only" / "select all except" */
  enableContextMenu?: boolean;
}

export default function TagSelector({ label, items, selected, onChange, enableContextMenu }: TagSelectorProps) {
  const toggle = useCallback(
    (item: string) => {
      const next = new Set(selected);
      if (next.has(item)) {
        next.delete(item);
      } else {
        next.add(item);
      }
      onChange([...next]);
    },
    [selected, onChange]
  );

  const handleContext = useCallback(
    (e: React.MouseEvent, item: string) => {
      if (!enableContextMenu) return;
      e.preventDefault();

      if (selected.has(item)) {
        // "Select all except this"
        onChange(items.filter((i) => i !== item));
      } else {
        // "Select only this"
        onChange([item]);
      }
    },
    [enableContextMenu, items, selected, onChange]
  );

  return (
    <div style={{ marginBottom: 20 }}>
      <div style={{ fontSize: 15, fontWeight: 600, marginBottom: 8, color: "var(--text-primary)" }}>{label}</div>
      <div style={{ display: "flex", flexWrap: "wrap", gap: 6 }}>
        {items.map((item) => {
          const isSelected = selected.has(item);
          return (
            <button
              key={item}
              onClick={() => toggle(item)}
              onContextMenu={(e) => handleContext(e, item)}
              style={{
                padding: "6px 14px",
                borderRadius: 20,
                fontSize: 13,
                fontWeight: 500,
                background: isSelected ? "var(--tag-selected)" : "var(--tag-bg)",
                color: isSelected ? "#fff" : "var(--text-secondary)",
                transition: "all 0.15s ease",
                border: "1px solid transparent",
              }}
            >
              {item}
            </button>
          );
        })}
      </div>
    </div>
  );
}
