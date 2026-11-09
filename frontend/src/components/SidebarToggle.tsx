import { changeCount, mappingSessions } from "../state/mapping";
import { isMac } from "../state/status";
import { SIDEBAR_ID, SIDEBAR_TOGGLE_ID, sidebarHidden, sidebarShortcut, toggleSidebar } from "../state/sidebar";
import { useStore } from "../state/store";
import { Icon } from "./Icon";

/**
 * Hide / Show Sidebar, at the leading edge of every page header (SPEC §4.1). While the sidebar is
 * hidden, a dot stands in for the mapping pages' unsaved-change badges. Wide screens only (CSS).
 */
export function SidebarToggle() {
  const hidden = useStore(sidebarHidden);
  const unsaved =
    changeCount(useStore(mappingSessions.galleries).pending) + changeCount(useStore(mappingSessions.tags).pending);
  const dot = hidden && unsaved > 0;
  const action = hidden ? "Show Sidebar" : "Hide Sidebar";

  return (
    <button
      id={SIDEBAR_TOGGLE_ID}
      type="button"
      className="icon-btn icon-btn--ghost sidebar-toggle"
      aria-label={dot ? `${action}, unsaved mapping changes` : action}
      aria-expanded={!hidden}
      aria-controls={SIDEBAR_ID}
      aria-keyshortcuts={isMac() ? "Control+Meta+S" : "Control+\\"}
      title={`${action} (${sidebarShortcut()})${dot ? "\nUnsaved mapping changes" : ""}`}
      onClick={toggleSidebar}
    >
      <Icon name="sidebarLeft" />
      {dot && <span className="sidebar-toggle__dot" aria-hidden="true" />}
    </button>
  );
}
