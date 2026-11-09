export interface VideoInfo {
  filename: string;
  studio: string;
  actors: string[];
  title: string;
  url: string;
  tgp_url: string;
  sprite_url: string;
  sprite_vtt_url: string;
}

export interface GalleryInfo {
  name: string;
  images: string[];
}

export interface CombinationDetail {
  index: number;
  total: number;
  video: VideoInfo;
  gallery: GalleryInfo;
}

export interface CombinationSummary {
  index: number;
  video: { filename: string; studio: string; actors: string[]; title: string };
  gallery: { name: string };
  tgp_url: string;
}

export interface ConfigData {
  galleries: string[];
  studios: string[];
  tags: string[];
  cast: string[];
  selected_galleries: string[];
  selected_studios: string[];
  selected_tags: string[];
  selected_cast: string[];
  combination_count: number;
  sample_combinations: { video: string; gallery: string }[];
}

export interface AppStatus {
  ready: boolean;
  progress: string;
  video_count: number;
  gallery_count: number;
  combination_count: number;
  startup_report?: {
    invalid_filenames_skipped: number;
    entries_normalized: number;
    orphan_assets_removed: number;
    stale_config_entries_removed: number;
  };
}

export interface VideoListItem {
  filename: string;
  studio: string;
  title: string;
  actors: string[];
  tgp_url: string;
}

export interface VideoListResponse {
  total: number;
  page: number;
  page_size: number;
  videos: VideoListItem[];
}

export interface GalleryMappingVideo {
  filename: string;
  title: string;
  studio: string;
  tgp_url: string;
  gallery_map: Record<string, "yes" | "no" | "undecided">;
}

export interface GalleryMappingResponse {
  total: number;
  page: number;
  page_size: number;
  galleries: string[];
  videos: GalleryMappingVideo[];
}

export interface TagMappingVideo {
  filename: string;
  title: string;
  studio: string;
  tgp_url: string;
  tag_map: Record<string, "yes" | "no" | "undecided">;
}

export interface TagMappingResponse {
  total: number;
  page: number;
  page_size: number;
  tags: string[];
  videos: TagMappingVideo[];
}
