import { useCallback } from "react";
import { getTagMapping, saveTagMapping } from "../api";
import MappingTable from "../components/MappingTable";
import type { FetchResult } from "../components/MappingTable";

export default function TagMapperPage() {
  const fetchFn = useCallback(
    async (page: number, pageSize: number, hideDecided: boolean): Promise<FetchResult> => {
      const data = await getTagMapping(page, pageSize, hideDecided);
      return {
        total: data.total,
        page: data.page,
        columns: data.tags,
        videos: data.videos.map((v) => ({
          filename: v.filename,
          title: v.title,
          studio: v.studio,
          tgp_url: v.tgp_url,
          map: v.tag_map,
        })),
      };
    },
    [],
  );

  return (
    <MappingTable
      fetchFn={fetchFn}
      saveFn={saveTagMapping}
    />
  );
}
