import { useCallback } from "react";
import { getGalleryMapping, saveGalleryMapping } from "../api";
import MappingTable from "../components/MappingTable";
import type { FetchResult } from "../components/MappingTable";

export default function MapperPage() {
  const fetchFn = useCallback(
    async (page: number, pageSize: number, hideDecided: boolean): Promise<FetchResult> => {
      const data = await getGalleryMapping(page, pageSize, hideDecided);
      return {
        total: data.total,
        page: data.page,
        columns: data.galleries,
        videos: data.videos.map((v) => ({
          filename: v.filename,
          title: v.title,
          studio: v.studio,
          tgp_url: v.tgp_url,
          map: v.gallery_map,
        })),
      };
    },
    [],
  );

  return (
    <MappingTable
      fetchFn={fetchFn}
      saveFn={saveGalleryMapping}
    />
  );
}
