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
import { kronosApi } from "@/lib/api/endpoints";

// All supported timeframes — used for the startup bootstrap below.
const ALL_TIMEFRAMES = ["15m", "1h", "1d"] as const;

// Minimum cooldown between UI-triggered cycles per timeframe.
// Matches the candle duration so the UI never fires more than once per candle,
// even if simsAvailable keeps returning false between polling cycles.
const TRIGGER_COOLDOWN_MS: Record<string, number> = {
  "15m": 15 * 60 * 1000,
  "1h":  60 * 60 * 1000,
  "1d":  24 * 60 * 60 * 1000,
};

function KronosDashboard() {
  const queryClient = useQueryClient();
  const [timeframe] = useTimeframe();
  const { data: prediction, isLoading: predLoading } = useKronosPrediction(timeframe);
  const { data: progress } = useKronosProgress(timeframe);
  const { data: sims, isLoading: simsLoading } = useKronosSims(timeframe);
  const trigger = useKronosTrigger();
  const { isIngesting, klineCount } = useEnsureKlines(timeframe);
  // Per-timeframe timestamps of the last trigger (bootstrap or active-tab).
  // Keyed by timeframe string so the 60s guard covers ALL timeframes, not just
  // the one currently visible.
  const lastTriggeredAt = useRef<Record<string, number>>({});
  const wasRunning = useRef(false);
  const bootstrapped = useRef(false);

  // ── Startup bootstrap ──────────────────────────────────────────────────────
  // Runs once on mount. For EVERY timeframe (not just the active tab), check
  // whether predictions already exist. If a timeframe has no sims, fire the
  // trigger immediately so the backend queues a cycle regardless of which tab
  // the user is looking at. Celery Beat owns ongoing scheduling; this only
  // covers the "fresh deploy / first boot" gap.
  //
  // Critically: we stamp lastTriggeredAt BEFORE awaiting triggerPrediction so
  // the active-tab effect sees "triggered recently" even during the gap between
  // the dispatch and the Celery worker writing status="running" to the DB.
  useEffect(() => {
    if (bootstrapped.current) return;
    bootstrapped.current = true;

    const bootstrap = async () => {
      for (const tf of ALL_TIMEFRAMES) {
        try {
          const simsResp = await kronosApi.getSims(tf);
          if (!simsResp.available) {
            lastTriggeredAt.current[tf] = Date.now();
            await kronosApi.triggerPrediction(tf);
          }
        } catch {
          // Ignore per-timeframe errors — the active-tab effect is the fallback.
          delete lastTriggeredAt.current[tf];
        }
      }
    };

    void bootstrap();
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

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
    const cooldown = TRIGGER_COOLDOWN_MS[timeframe] ?? 60_000;
    if (
      !isIngesting &&
      !simsLoading &&
      !simsAvailable &&
      !isRunning &&
      !trigger.isPending &&
      now - (lastTriggeredAt.current[timeframe] ?? 0) > cooldown
    ) {
      lastTriggeredAt.current[timeframe] = now;
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
