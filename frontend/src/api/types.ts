export type Phase = "loading" | "ready" | "error";

export interface Status {
  phase: Phase;
  step: string;
  detail: string | null;
  fraction: number | null;
  error: string | null;
  configPath: string;
  configExists: boolean;
  revision: number;
  library: { videos: number; galleries: number };
}

export interface Settings {
  configPath: string;
  videosPath: string | null;
  galleriesPath: string | null;
}

export type EmptyReason = "noVideos" | "noGalleries" | "filters" | "mappings";

export interface ViewerCombination {
  video: {
    filename: string;
    title: string;
    credits: string;
    extension: string;
    sheetUrl: string | null;
    videoUrl: string;
    spriteUrl: string | null;
    vttUrl: string | null;
  };
  gallery: { name: string; images: string[] };
}

export interface ViewerState {
  position: number;
  total: number;
  revision: number;
  current: ViewerCombination | null;
  nextSheetUrl: string | null;
  empty: { reason: EmptyReason; videosPath: string; galleriesPath: string; tagsRequired: boolean } | null;
}

export type FilterKey = "galleries" | "studios" | "tags" | "cast";

export interface FilterItem {
  value: string;
  label: string;
}

export interface FiltersState {
  sections: Record<FilterKey, { items: FilterItem[]; selected: string[] }>;
  isDefault: boolean;
  count: number;
  videoCount: number;
  galleryCount: number;
  upNext: { index: number; title: string; gallery: string; thumbUrl: string | null }[];
  revision: number;
}

export interface VideoSummary {
  filename: string;
  title: string;
  credits: string;
  studio: string;
  actors: string[];
  thumbUrl: string | null;
  previewUrl: string | null;
}

export interface SkippedFile {
  filename: string;
  reasons: string[];
}

export interface LibraryState {
  videos: VideoSummary[];
  skipped: SkippedFile[];
  videosPath: string;
  revision: number;
}

export type MappingKind = "galleries" | "tags";
export type TriState = "yes" | "no" | "undecided";

export interface MappingRow extends VideoSummary {
  /** One character per column: y, n or u. */
  states: string;
}

export interface MappingState {
  kind: MappingKind;
  columns: string[];
  rows: MappingRow[];
  galleriesPath: string;
  revision: number;
}

export interface CleanupPreview {
  videosPath: string;
  videoFileCount: number;
  relationCount: number;
  staleEntries: string[];
  highRisk: boolean;
}
