import { useEffect, useRef, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { subDays, formatISO } from "date-fns";
import { dataApi, type KlinesParams } from "@/lib/api/endpoints";

export function useKlines(params: KlinesParams = {}) {
  return useQuery({
    queryKey: ["klines", params],
    queryFn: () => dataApi.getKlines(params),
    staleTime: 5 * 60 * 1000,
  });
}

export function useRecentKlines(days = 7) {
  const end = new Date();
  const start = subDays(end, days);

  return useKlines({
    symbol: "BTCUSDT",
    interval: "1h",
    start: formatISO(start),
    end: formatISO(end),
    limit: days * 24,
  });
}

export function useDailyKlines(days: number) {
  const end = new Date();
  const start = subDays(end, days);

  return useQuery({
    queryKey: ["klines-daily", days],
    queryFn: () =>
      dataApi.getDailyKlines({
        symbol: "BTCUSDT",
        start: formatISO(start),
        end: formatISO(end),
        limit: days,
      }),
    staleTime: 60 * 60 * 1000, // daily data can stay stale for 1h
  });
}

export function useSyncKlines() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: () => dataApi.syncKlines(),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["klines"] });
      queryClient.invalidateQueries({ queryKey: ["klines-daily"] });
      queryClient.invalidateQueries({ queryKey: ["klines-info"] });
    },
  });
}

export function useTicker(symbol = "BTCUSDT") {
  return useQuery({
    queryKey: ["ticker", symbol],
    queryFn: () => dataApi.getTicker(symbol),
    refetchInterval: 5_000,         // live price refresh every 5s
    refetchIntervalInBackground: false,
    staleTime: 4_000,
  });
}

export function useKlinesInfo() {
  return useQuery({
    queryKey: ["klines-info"],
    queryFn: () => dataApi.getKlinesInfo(),
    staleTime: 60 * 1000,
    refetchInterval: 60 * 1000,
  });
}

export function useBackfillKlines() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (params: { start: string; end?: string }) =>
      dataApi.backfillKlines(params),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["klines"] });
      queryClient.invalidateQueries({ queryKey: ["klines-daily"] });
      queryClient.invalidateQueries({ queryKey: ["klines-info"] });
    },
  });
}

export function useEnsureKlines(timeframe: string) {
  const queryClient = useQueryClient();
  const [isIngesting, setIsIngesting] = useState(false);
  const [klineCount, setKlineCount] = useState(0);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  useEffect(() => {
    let cancelled = false;

    function stopPoll() {
      if (pollRef.current) {
        clearInterval(pollRef.current);
        pollRef.current = null;
      }
    }

    async function poll() {
      try {
        const res = await dataApi.checkKlines(timeframe);
        if (cancelled) return;
        setKlineCount(res.count);
        if (res.status === "ok") {
          setIsIngesting(false);
          stopPoll();
          queryClient.invalidateQueries({ queryKey: ["klines"] });
        }
      } catch {
        // silently ignore transient errors
      }
    }

    async function trigger() {
      try {
        const res = await dataApi.ensureKlines(timeframe);
        if (cancelled) return;
        setKlineCount(res.count);
        if (res.status === "ingesting") {
          setIsIngesting(true);
          stopPoll();
          pollRef.current = setInterval(poll, 5_000);
        } else {
          setIsIngesting(false);
          queryClient.invalidateQueries({ queryKey: ["klines"] });
        }
      } catch {
        if (!cancelled) setIsIngesting(false);
      }
    }

    setIsIngesting(false);
    trigger();

    return () => {
      cancelled = true;
      stopPoll();
    };
  }, [timeframe]); // eslint-disable-line react-hooks/exhaustive-deps

  return { isIngesting, klineCount };
}
