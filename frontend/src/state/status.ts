import { api } from "../api/client";
import type { Status } from "../api/types";
import { bumpData } from "./feedback";
import { createStore } from "./store";

export const status = createStore<Status | null>(null);
export const connectionError = createStore(false);

let polling = false;

/** Poll while the library loads; stop once ready or failed. */
export async function pollStatus(): Promise<void> {
  if (polling) return;
  polling = true;
  try {
    for (;;) {
      try {
        const next = await api.status();
        connectionError.set(false);
        status.set(next);
        if (next.phase !== "loading") break;
      } catch {
        connectionError.set(true);
      }
      await new Promise((resolve) => setTimeout(resolve, 400));
    }
  } finally {
    polling = false;
  }
}

export async function refreshStatus(): Promise<void> {
  try {
    status.set(await api.status());
  } catch {
    connectionError.set(true);
  }
}

export async function reloadLibrary(): Promise<void> {
  await api.reload();
  status.set((s) => (s ? { ...s, phase: "loading", step: "Starting Up", detail: null, fraction: null } : s));
  await pollStatus();
  bumpData();
}

export function isMac(): boolean {
  const platform = (navigator as Navigator & { userAgentData?: { platform?: string } }).userAgentData?.platform
    ?? navigator.platform;
  return /mac/i.test(platform);
}

/** "⌘" on macOS, "Ctrl+" elsewhere. */
export function commandKey(): string {
  return isMac() ? "⌘" : "Ctrl+";
}
