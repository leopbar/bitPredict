"use client";

import { useCallback } from "react";
import { useRouter, useSearchParams } from "next/navigation";

export const VALID_TIMEFRAMES = ["15m", "1h", "1d"] as const;
export type AppTimeframe = (typeof VALID_TIMEFRAMES)[number];

/**
 * Reads the `?tf=` URL query param and returns [timeframe, setTimeframe].
 * Falls back to "15m" for any unrecognised value.
 * Must be used inside a component wrapped in <Suspense>.
 */
export function useTimeframe(): [AppTimeframe, (tf: AppTimeframe) => void] {
  const searchParams = useSearchParams();
  const router = useRouter();

  const raw = searchParams.get("tf");
  const timeframe: AppTimeframe = VALID_TIMEFRAMES.includes(raw as AppTimeframe)
    ? (raw as AppTimeframe)
    : "15m";

  const setTimeframe = useCallback(
    (tf: AppTimeframe) => {
      const params = new URLSearchParams(searchParams.toString());
      params.set("tf", tf);
      router.push(`?${params.toString()}`, { scroll: false });
    },
    [router, searchParams],
  );

  return [timeframe, setTimeframe];
}
