import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { kronosApi } from "@/lib/api/endpoints";

const PREDICTION_STALE = 60_000;        // refetch prediction every 60s when idle
const PROGRESS_INTERVAL = 5_000;        // poll progress every 5s when running
const HISTORY_STALE = 30_000;

export function useKronosPrediction(timeframe: string) {
  return useQuery({
    queryKey: ["kronos-prediction", timeframe],
    queryFn: () => kronosApi.getPrediction(timeframe),
    staleTime: PREDICTION_STALE,
    refetchInterval: PREDICTION_STALE,
    refetchIntervalInBackground: false,
    retry: 1,
  });
}

export function useKronosProgress(timeframe: string) {
  return useQuery({
    queryKey: ["kronos-progress", timeframe],
    queryFn: () => kronosApi.getProgress(timeframe),
    refetchInterval: PROGRESS_INTERVAL,
    refetchIntervalInBackground: false,
    staleTime: 0,
    retry: false,
  });
}

export function useKronosHistory(timeframe: string, limit = 50) {
  const { data: progress } = useKronosProgress(timeframe);
  const isRunning = progress?.state === "PROGRESS" || progress?.state === "STARTED";

  return useQuery({
    queryKey: ["kronos-history", timeframe, limit],
    queryFn: () => kronosApi.getHistory(timeframe, limit),
    staleTime: 0,
    // Poll fast while inference is running so the new row appears as soon as it's done;
    // poll every 30s at rest to pick up actuals filled by the fill_actuals task.
    refetchInterval: isRunning ? 5_000 : 30_000,
    refetchIntervalInBackground: false,
    retry: 1,
  });
}

export function useKronosHealth() {
  return useQuery({
    queryKey: ["kronos-health"],
    queryFn: () => kronosApi.getHealth(),
    staleTime: 60_000,
    refetchInterval: 60_000,
    refetchIntervalInBackground: false,
  });
}

export function useKronosTrigger() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (timeframe: string) => kronosApi.triggerPrediction(timeframe),
    onSuccess: (_, timeframe) => {
      queryClient.invalidateQueries({ queryKey: ["kronos-progress", timeframe] });
      queryClient.invalidateQueries({ queryKey: ["kronos-prediction", timeframe] });
      queryClient.invalidateQueries({ queryKey: ["kronos-history", timeframe] });
    },
  });
}

export function useKronosStop() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (timeframe: string) => kronosApi.stopPrediction(timeframe),
    onSuccess: (_, timeframe) => {
      queryClient.invalidateQueries({ queryKey: ["kronos-progress", timeframe] });
    },
  });
}

export function useKronosTriggerBacktest() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ timeframe, sampleSize, sampleCount, initialCapital, positionPct, compound }: { timeframe: string; sampleSize?: number; sampleCount?: number; initialCapital?: number; positionPct?: number; compound?: boolean }) =>
      kronosApi.triggerBacktest(timeframe, sampleSize, sampleCount, initialCapital, positionPct, compound),
    onSuccess: (_, { timeframe }) => {
      queryClient.invalidateQueries({ queryKey: ["kronos-backtest-progress", timeframe] });
    },
  });
}

export function useKronosBacktest(timeframe: string) {
  return useQuery({
    queryKey: ["kronos-backtest", timeframe],
    queryFn: () => kronosApi.getBacktest(timeframe),
    staleTime: 120_000,
    retry: false,
  });
}

export function useKronosBacktestDataInfo() {
  return useQuery({
    queryKey: ["kronos-backtest-data-info"],
    queryFn: () => kronosApi.getBacktestDataInfo(),
    staleTime: 60_000,
    retry: 1,
  });
}

export function useKronosBacktestProgress(timeframe: string) {
  return useQuery({
    queryKey: ["kronos-backtest-progress", timeframe],
    queryFn: () => kronosApi.getBacktestProgress(timeframe),
    refetchInterval: 2_000,
    refetchIntervalInBackground: false,
    staleTime: 0,
    retry: false,
  });
}

export function useKronosStopBacktest() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (timeframe: string) => kronosApi.stopBacktest(timeframe),
    onSuccess: (_, timeframe) => {
      queryClient.invalidateQueries({ queryKey: ["kronos-backtest-progress", timeframe] });
    },
  });
}

export function useKronosScoreboard(timeframe: string) {
  return useQuery({
    queryKey: ["kronos-scoreboard", timeframe],
    queryFn: () => kronosApi.getScoreboard(timeframe),
    staleTime: 0,
    refetchInterval: 60_000,
    refetchIntervalInBackground: false,
    retry: 1,
  });
}

export function useKronosSims(timeframe: string) {
  const { data: progress } = useKronosProgress(timeframe);
  const isRunning = progress?.state === "PROGRESS" || progress?.state === "STARTED";

  return useQuery({
    queryKey: ["kronos-sims", timeframe],
    queryFn: () => kronosApi.getSims(timeframe),
    // Poll fast when inference is running (new samples appearing), slower when idle
    refetchInterval: isRunning ? 2_000 : 30_000,
    refetchIntervalInBackground: false,
    staleTime: 0,
    retry: 1,
  });
}

export function useKronosBacktestTrades(timeframe: string, backtestId?: number) {
  return useQuery({
    queryKey: ["kronos-backtest-trades", timeframe, backtestId],
    queryFn: () => kronosApi.getBacktestTrades(timeframe, 1000, backtestId),
    staleTime: 120_000,
    retry: false,
  });
}

export function useKronosLiveCandle(timeframe: string) {
  return useQuery({
    queryKey: ["kronos-live-candle", timeframe],
    queryFn: () => kronosApi.getLiveCandle(timeframe),
    refetchInterval: 5_000,
    refetchIntervalInBackground: false,
    staleTime: 0,
    retry: 1,
  });
}
