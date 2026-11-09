import { useCallback, useEffect, useRef, useState } from "react";
import { getCombination, shuffle as apiShuffle } from "../api";
import type { CombinationDetail } from "../types";

export function useCombinations() {
  const [combination, setCombination] = useState<CombinationDetail | null>(null);
  const [index, setIndex] = useState(0);
  const [loading, setLoading] = useState(true);
  const fetchRef = useRef(0);

  const fetchCombination = useCallback(async (idx: number) => {
    const id = ++fetchRef.current;
    setLoading(true);
    try {
      const data = await getCombination(idx);
      if (fetchRef.current === id) {
        setCombination(data);
        setIndex(data.index);
      }
    } catch {
      if (fetchRef.current === id) {
        setCombination(null);
      }
    } finally {
      if (fetchRef.current === id) {
        setLoading(false);
      }
    }
  }, []);

  useEffect(() => {
    fetchCombination(0);
  }, [fetchCombination]);

  const next = useCallback(() => {
    if (!combination) return;
    const nextIdx = (index + 1) % combination.total;
    fetchCombination(nextIdx);
  }, [combination, index, fetchCombination]);

  const prev = useCallback(() => {
    if (!combination) return;
    const prevIdx = (index - 1 + combination.total) % combination.total;
    fetchCombination(prevIdx);
  }, [combination, index, fetchCombination]);

  const shuffleAndReload = useCallback(async () => {
    await apiShuffle();
    fetchCombination(0);
  }, [fetchCombination]);

  return { combination, index, loading, next, prev, shuffleAndReload, fetchCombination };
}
