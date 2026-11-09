import { isMac } from "./status";
import { createStore } from "./store";

/** Whether the wide-screen sidebar is hidden (SPEC §4.1). Shown is the first-run default. */
const KEY = "pvorg.sidebar";

export const SIDEBAR_ID = "sidebar";
export const SIDEBAR_TOGGLE_ID = "sidebar-toggle";

export const sidebarHidden = createStore(localStorage.getItem(KEY) === "hidden");

/** The sidebar is persistent (and can be hidden) only on wide screens; below this it's a drawer. */
const wide = window.matchMedia("(min-width: 900px)");

export function sidebarApplies(): boolean {
  return wide.matches;
}

export function setSidebarHidden(hidden: boolean): void {
  if (hidden === sidebarHidden.get()) return;
  // Hiding takes the sidebar's controls away, so focus that was in it moves to the toggle (SPEC §4.1).
  const moveFocus = hidden && !!document.activeElement?.closest(`#${SIDEBAR_ID}`);
  localStorage.setItem(KEY, hidden ? "hidden" : "shown");
  sidebarHidden.set(hidden);
  if (moveFocus) document.getElementById(SIDEBAR_TOGGLE_ID)?.focus({ preventScroll: true });
}

export function toggleSidebar(): void {
  setSidebarHidden(!sidebarHidden.get());
}

/** ⌃⌘S on macOS, Ctrl+\ elsewhere (SPEC §7.1). */
export function isSidebarShortcut(e: KeyboardEvent): boolean {
  if (e.altKey || e.shiftKey) return false;
  if (isMac()) return e.ctrlKey && e.metaKey && (e.key.toLowerCase() === "s" || e.code === "KeyS");
  return e.ctrlKey && !e.metaKey && (e.key === "\\" || e.code === "Backslash");
}

export function sidebarShortcut(): string {
  return isMac() ? "⌃⌘S" : "Ctrl+\\";
}

// Keep other tabs of the app in step.
window.addEventListener("storage", (e) => {
  if (e.key === KEY) sidebarHidden.set(e.newValue === "hidden");
});
