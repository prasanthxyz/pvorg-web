import type {
  CleanupPreview,
  FilterKey,
  FiltersState,
  LibraryState,
  MappingKind,
  MappingState,
  Settings,
  Status,
  TriState,
  ViewerState,
} from "./types";

export class ApiError extends Error {
  constructor(
    message: string,
    readonly status: number,
  ) {
    super(message);
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(path, {
    ...init,
    headers: init?.body ? { "Content-Type": "application/json", ...init.headers } : init?.headers,
  });
  if (!response.ok) {
    let message = `The server returned an error (${response.status}).`;
    try {
      const body = await response.json();
      if (typeof body?.detail === "string") message = body.detail;
    } catch {
      /* not JSON */
    }
    throw new ApiError(message, response.status);
  }
  return response.json() as Promise<T>;
}

const post = <T>(path: string, body?: unknown) =>
  request<T>(path, { method: "POST", body: body === undefined ? undefined : JSON.stringify(body) });

export const api = {
  status: () => request<Status>("/api/status"),
  reload: () => post<{ started: boolean }>("/api/reload"),
  settings: () => request<Settings>("/api/settings"),

  viewer: () => request<ViewerState>("/api/viewer"),
  move: (delta: number) => post<ViewerState>("/api/viewer/move", { delta }),
  goto: (index: number) => post<ViewerState>("/api/viewer/move", { index }),
  exclude: (filename: string, gallery: string) =>
    post<{ exclusionId: string; viewer: ViewerState }>("/api/pairings/exclude", { filename, gallery }),
  restore: (exclusionId: string) =>
    post<{ viewer: ViewerState }>(`/api/pairings/restore/${encodeURIComponent(exclusionId)}`),

  filters: () => request<FiltersState>("/api/filters"),
  setFilters: (update: Partial<Record<FilterKey, string[]>>) =>
    request<FiltersState>("/api/filters", { method: "PUT", body: JSON.stringify(update) }),
  resetFilters: () => post<FiltersState>("/api/filters/reset"),

  library: () => request<LibraryState>("/api/library"),
  deleteVideos: (filenames: string[]) =>
    post<{ deleted: number; errors: string[] }>("/api/library/delete", { filenames }),

  mapping: (kind: MappingKind) => request<MappingState>(`/api/mapping/${kind}`),
  saveMapping: (kind: MappingKind, changes: Record<string, Record<string, TriState>>) =>
    post<{ saved: number }>(`/api/mapping/${kind}`, { changes }),

  cleanupPreview: () => request<CleanupPreview>("/api/cleanup"),
  removeStale: (entries: string[]) => post<{ removed: number }>("/api/cleanup", { entries }),
};
