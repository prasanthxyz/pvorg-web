import type {
  AppStatus,
  CombinationDetail,
  ConfigData,
  GalleryMappingResponse,
  TagMappingResponse,
  VideoListResponse,
} from "./types";

const BASE = "";

async function fetchJSON<T>(url: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${url}`, init);
  if (!res.ok) throw new Error(`API error: ${res.status}`);
  return res.json();
}

export function getStatus(): Promise<AppStatus> {
  return fetchJSON("/api/status");
}

export function getCombination(index: number): Promise<CombinationDetail> {
  return fetchJSON(`/api/combinations/${index}`);
}

export function getConfig(): Promise<ConfigData> {
  return fetchJSON("/api/config");
}

export function updateConfig(
  selections: Partial<{
    selected_galleries: string[];
    selected_studios: string[];
    selected_tags: string[];
    selected_cast: string[];
  }>
): Promise<ConfigData> {
  return fetchJSON("/api/config", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(selections),
  });
}

export function shuffle(): Promise<{ total: number }> {
  return fetchJSON("/api/shuffle", { method: "POST" });
}

export function reload(): Promise<{ status: string }> {
  return fetchJSON("/api/reload", { method: "POST" });
}

export function getVideos(page: number, pageSize: number): Promise<VideoListResponse> {
  return fetchJSON(`/api/videos?page=${page}&page_size=${pageSize}`);
}

export function deleteVideos(filenames: string[]): Promise<{ deleted: number; errors?: string[] }> {
  return fetchJSON("/api/videos", {
    method: "DELETE",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ filenames }),
  });
}

export function getGalleryMapping(
  page: number,
  pageSize: number,
  hideDecided: boolean,
): Promise<GalleryMappingResponse> {
  return fetchJSON(
    `/api/gallery-mapping?page=${page}&page_size=${pageSize}&hide_decided=${hideDecided}`,
  );
}

export function saveGalleryMapping(
  mappings: Record<string, Record<string, string>>,
): Promise<{ updated: number }> {
  return fetchJSON("/api/gallery-mapping", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ mappings }),
  });
}

export function getTagMapping(
  page: number,
  pageSize: number,
  hideDecided: boolean,
): Promise<TagMappingResponse> {
  return fetchJSON(
    `/api/tag-mapping?page=${page}&page_size=${pageSize}&hide_decided=${hideDecided}`,
  );
}

export function saveTagMapping(
  mappings: Record<string, Record<string, string>>,
): Promise<{ updated: number }> {
  return fetchJSON("/api/tag-mapping", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ mappings }),
  });
}
