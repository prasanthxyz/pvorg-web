import { useEffect, useRef } from "react";
import { isMenuOpen } from "../components/Menu";
import { redo, undo } from "../state/feedback";
import { isMac } from "../state/status";

/**
 * Keyboard rules (SPEC §7.1):
 * - typing always wins: no single-key shortcut acts while a text field has focus;
 * - nothing app-level acts while a dialog or menu is open;
 * - page keys are scoped to their page (pages register a handler while mounted).
 */
export type PageHandler = (event: KeyboardEvent, info: { mod: boolean; editing: boolean }) => boolean;

let pageHandler: PageHandler | null = null;

export function isEditable(element: Element | null): boolean {
  if (!(element instanceof HTMLElement)) return false;
  if (element.isContentEditable) return true;
  if (element instanceof HTMLTextAreaElement || element instanceof HTMLSelectElement) return true;
  if (element instanceof HTMLInputElement) {
    return !["button", "checkbox", "radio", "range", "submit", "reset", "color", "file"].includes(element.type);
  }
  return false;
}

/** Register the current page's shortcuts. The handler returns true when it handled the key. */
export function usePageShortcuts(handler: PageHandler): void {
  const ref = useRef(handler);
  ref.current = handler;
  useEffect(() => {
    const wrapped: PageHandler = (e, info) => ref.current(e, info);
    pageHandler = wrapped;
    return () => {
      if (pageHandler === wrapped) pageHandler = null;
    };
  }, []);
}

export function installShortcuts(navigate: (path: string) => void, canNavigate: () => boolean): () => void {
  const onKeyDown = (e: KeyboardEvent) => {
    if (e.defaultPrevented || e.isComposing) return;
    if (document.querySelector("dialog[open]") || isMenuOpen()) return;
    const editing = isEditable(document.activeElement);
    const mod = isMac() ? e.metaKey && !e.ctrlKey : e.ctrlKey && !e.metaKey;
    const key = e.key.toLowerCase();

    if (mod && !e.altKey) {
      if (!editing && key === "z") {
        e.preventDefault();
        void (e.shiftKey ? redo() : undo());
        return;
      }
      if (!editing && !isMac() && key === "y") {
        e.preventDefault();
        void redo();
        return;
      }
      if (pageHandler?.(e, { mod, editing })) e.preventDefault();
      return;
    }

    if (editing || e.metaKey || e.ctrlKey || e.altKey) return;
    if (pageHandler?.(e, { mod: false, editing })) {
      e.preventDefault();
      return;
    }
    if (!canNavigate()) return;
    if (key === "v") {
      e.preventDefault();
      navigate("/");
    } else if (key === "c") {
      e.preventDefault();
      navigate("/filters");
    }
  };
  window.addEventListener("keydown", onKeyDown);
  return () => window.removeEventListener("keydown", onKeyDown);
}
