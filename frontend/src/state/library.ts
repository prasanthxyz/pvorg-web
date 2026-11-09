import { createStore } from "./store";

/** Library search and selection; the selection only ever contains shown videos (SPEC §3.8). */
export const librarySearch = createStore("");
export const librarySelection = createStore<ReadonlySet<string>>(new Set());

export function toggleSelection(filename: string): void {
  librarySelection.set((selected) => {
    const next = new Set(selected);
    if (next.has(filename)) next.delete(filename);
    else next.add(filename);
    return next;
  });
}

export function keepOnly(visible: Set<string>): void {
  librarySelection.set((selected) => {
    const kept = [...selected].filter((f) => visible.has(f));
    return kept.length === selected.size ? selected : new Set(kept);
  });
}
