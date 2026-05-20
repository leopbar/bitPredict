"use client";

import { Suspense, useEffect, useRef } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { PipelineProgressCard } from "@/components/kronos/pipeline-progress-card";
import { PriceTargetsCard, ConsensusCard } from "@/components/kronos/prediction-panel";
import { AnalystDistributionChart } from "@/components/kronos/analyst-distribution-chart";
import { HistoryTable } from "@/components/kronos/history-table";
import { ScoreboardCard } from "@/components/kronos/scoreboard-card";
import { LiveCandleCard } from "@/components/kronos/live-candle-card";
import { BacktestSummaryCard } from "@/components/kronos/backtest-summary-card";
import { TimeframeToggle } from "@/components/ui/timeframe-toggle";
import {
  useKronosPrediction,
  useKronosProgress,
  useKronosTrigger,
  useKronosSims,
} from "@/lib/hooks/use-kronos";
import { useEnsureKlines } from "@/lib/hooks/use-klines";
import { useTimeframe } from "@/lib/hooks/use-timeframe";

function KronosDashboard() {
  const queryClient = useQueryClient();
  const [timeframe] = useTimeframe();
  const { data: prediction, isLoading: predLoading } = useKronosPrediction(timeframe);
  const { data: progress } = useKronosProgress(timeframe);
  const { data: sims, isLoading: simsLoading } = useKronosSims(timeframe);
  const trigger = useKronosTrigger();
  const { isIngesting, klineCount } = useEnsureKlines(timeframe);
  const lastTriggeredAt = useRef<number>(0);
  const wasRunning = useRef(false);

  const isRunning = progress?.state === "PROGRESS" || progress?.state === "STARTED";
  const simsAvailable = sims?.available === true;

  useEffect(() => {
    if (wasRunning.current && !isRunning) {
      queryClient.invalidateQueries({ queryKey: ["kronos-prediction", timeframe] });
      queryClient.invalidateQueries({ queryKey: ["kronos-sims", timeframe] });
      queryClient.invalidateQueries({ queryKey: ["kronos-history", timeframe] });
      queryClient.invalidateQueries({ queryKey: ["kronos-scoreboard", timeframe] });
    }
    wasRunning.current = isRunning;
  }, [isRunning, queryClient, timeframe]);

  useEffect(() => {
    const now = Date.now();
    if (
      !isIngesting &&
      !simsLoading &&
      !simsAvailable &&
      !isRunning &&
      !trigger.isPending &&
      now - lastTriggeredAt.current > 60_000
    ) {
      lastTriggeredAt.current = now;
      trigger.mutate(timeframe);
    }
  }, [isIngesting, simsLoading, simsAvailable, isRunning, trigger.isPending, timeframe]); // eslint-disable-line react-hooks/exhaustive-deps

  return (
    <div className="space-y-4">
      <PipelineProgressCard
        timeframe={timeframe}
        isIngesting={isIngesting}
        klineCount={klineCount}
      />

      {/*
        Single grid: [2fr 1fr 1fr 280px]
        Row 1 — 4 cards share the same height via CSS grid stretch (default).
        Row 2 — left content spans 3 cols; BacktestSummary stays in col 4 (280px).
      */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-[2fr_1fr_1fr_280px] gap-4">

        {/* Row 1 — top cards */}
        <PriceTargetsCard
          timeframe={timeframe}
          prediction={prediction}
          isLoading={predLoading}
        />
        <ConsensusCard
          timeframe={timeframe}
          prediction={prediction}
          isLoading={predLoading}
        />
        <LiveCandleCard timeframe={timeframe} />
        <ScoreboardCard timeframe={timeframe} />

        {/* Row 2 — AnalystDistribution (col-span-3) + BacktestSummary (col 4) same height */}
        <div className="lg:col-span-3">
          <AnalystDistributionChart
            timeframe={timeframe}
            prediction={prediction}
          />
        </div>
        <BacktestSummaryCard timeframe={timeframe} />

        {/* Row 3 — HistoryTable spans all 4 cols */}
        <div className="lg:col-span-4">
          <HistoryTable timeframe={timeframe} />
        </div>

      </div>
    </div>
  );
}

export default function Home() {
  return (
    <div className="p-6 space-y-5 max-w-[1400px] mx-auto">
      <div className="flex items-start justify-between gap-4">
        <div>
          <h1 className="text-base font-semibold text-zinc-100">BTC Forecast</h1>
          <p className="text-xs text-zinc-500 mt-0.5">Powered by Kronos · NeoQuasar · 30 stochastic simulations per candle</p>
        </div>
        <Suspense>
          <TimeframeToggle />
        </Suspense>
      </div>

      <Suspense>
        <KronosDashboard />
      </Suspense>
    </div>
  );
}
