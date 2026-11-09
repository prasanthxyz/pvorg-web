import { Link, useLocation } from "react-router-dom";

const links = [
  { to: "/", label: "Home", hint: "v" },
  { to: "/config", label: "Config", hint: "c" },
  { to: "/deleter", label: "Deleter" },
  { to: "/mapper", label: "Mapper" },
  { to: "/tag-mapper", label: "Tag Mapper" },
] as const;

export default function Navbar() {
  const { pathname } = useLocation();

  return (
    <nav
      style={{
        display: "flex",
        alignItems: "center",
        gap: 4,
        padding: "6px 16px",
        background: "var(--bg-secondary)",
        borderBottom: "1px solid var(--border)",
        flexShrink: 0,
      }}
    >
      <span style={{ fontWeight: 700, fontSize: 14, marginRight: 12, color: "var(--accent)" }}>
        pvorg
      </span>
      {links.map((link) => {
        const active = pathname === link.to;
        return (
          <Link
            key={link.to}
            to={link.to}
            style={{
              padding: "4px 12px",
              borderRadius: 6,
              fontSize: 13,
              fontWeight: 500,
              background: active ? "var(--accent)" : "var(--tag-bg)",
              color: active ? "#fff" : "var(--text-primary)",
              transition: "background 0.15s",
            }}
          >
            {link.label}
            {"hint" in link && (
              <span style={{ marginLeft: 6, opacity: 0.5, fontSize: 11 }}>({link.hint})</span>
            )}
          </Link>
        );
      })}
    </nav>
  );
}
