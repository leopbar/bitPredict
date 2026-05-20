"use client";

import { format, parseISO } from "date-fns";
import { TrendingUp, TrendingDown, ShieldCheck, ShieldAlert, Shield, Brain } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { InfoTip } from "@/components/ui/tooltip";
import { formatUSD } from "@/lib/format";
import type { KronosPrediction } from "@/lib/api/schemas";

interface Props {
  timeframe: string;
  prediction: KronosPrediction | undefined;
  isLoading: boolean;
}


function ConfidenceBadge({ bandWidthPct }: { bandWidthPct: number }) {
  const level =
    bandWidthPct < 0.3 ? "High"
    : bandWidthPct < 0.8 ? "Medium"
    : "Low";

  const styles = {
    High:   { color: "text-emerald-400", bg: "bg-emerald-950/40 border-emerald-500/30", Icon: ShieldCheck },
    Medium: { color: "text-yellow-400",  bg: "bg-yellow-950/40 border-yellow-500/30",  Icon: Shield },
    Low:    { color: "text-red-400",     bg: "bg-red-950/40 border-red-500/30",         Icon: ShieldAlert },
  }[level];

  const { Icon } = styles;

  return (
    <div className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full border text-xs font-semibold ${styles.bg} ${styles.color}`}>
      <Icon className="w-3.5 h-3.5" />
      {level} Confidence
      <span className="font-mono font-normal opacity-70">±{bandWidthPct.toFixed(2)}%</span>
    </div>
  );
}

// ── Price Targets Card ────────────────────────────────────────────────────────

export function PriceTargetsCard({ timeframe, prediction, isLoading }: Props) {
  if (isLoading) {
    return (
      <Card className="bg-bp-surface border-bp-border">
        <CardContent className="px-4 py-4 space-y-2">
          <Skeleton className="h-4 w-32" />
          <Skeleton className="h-8 w-40" />
          <Skeleton className="h-3 w-full" />
        </CardContent>
      </Card>
    );
  }

  if (!prediction) {
    return (
      <Card className="bg-bp-surface border-bp-border">
        <CardContent className="px-4 py-6 text-center">
          <p className="text-xs text-zinc-500">No prediction yet</p>
        </CardContent>
      </Card>
    );
  }

  const close = prediction.predicted_close;
  const q10   = prediction.q10_close;
  const q90   = prediction.q90_close;
  const high  = prediction.predicted_high;
  const low   = prediction.predicted_low;
  const open  = prediction.predicted_open;

  const bandWidthPct =
    q90 != null && q10 != null && close != null && close > 0
      ? ((q90 - q10) / close) * 100
      : null;

  const rangePct =
    high != null && low != null && close != null && close > 0
      ? (((high - low) / close) * 100).toFixed(2)
      : null;

  return (
    <Card className="relative overflow-hidden bg-bp-surface border-bp-border">

      {/* Decorative blue chart line in background */}
      <svg
        viewBox="0 0 400 120"
        preserveAspectRatio="none"
        fill="none"
        xmlns="http://www.w3.org/2000/svg"
        className="absolute inset-0 w-full h-full opacity-[0.15] pointer-events-none"
        aria-hidden="true"
      >
        <defs>
          <linearGradient id="ptcGrad" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="#3B82F6" stopOpacity="0.6" />
            <stop offset="100%" stopColor="#3B82F6" stopOpacity="0" />
          </linearGradient>
        </defs>
        <path
          d="M0 100 C40 95, 70 88, 100 75 C130 62, 150 70, 180 54 C210 38, 240 45, 270 28 C300 11, 330 18, 400 8"
          stroke="#3B82F6"
          strokeWidth="2"
        />
        <path
          d="M0 100 C40 95, 70 88, 100 75 C130 62, 150 70, 180 54 C210 38, 240 45, 270 28 C300 11, 330 18, 400 8 L400 120 L0 120 Z"
          fill="url(#ptcGrad)"
        />
      </svg>

      {/* Header — title only, no icon */}
      <CardHeader className="pb-1 pt-3 px-4 relative">
        <CardTitle className="text-xs font-semibold text-zinc-400 uppercase tracking-wider flex items-center gap-1">
          Price Targets · {timeframe}
          <InfoTip text="Median predicted candle and confidence band across all 30 simulations." />
        </CardTitle>
      </CardHeader>

      {/* Body — two columns: content left, brain + badge right */}
      <CardContent className="px-4 pb-4 relative">
        <div className="flex items-stretch justify-between gap-4">

          {/* Left: expected close → price → range */}
          <div className="flex flex-col gap-1.5 min-w-0">
            <div className="flex items-center gap-1">
              <span className="text-[10px] uppercase tracking-wide text-zinc-500">Expected close</span>
              <InfoTip text="Median of the 30 simulated close prices — the consensus target." />
            </div>

            <p
              className="text-4xl font-bold font-mono text-blue-400 leading-none tracking-tight"
              style={{ textShadow: "0 0 24px rgba(59,130,246,0.35)" }}
            >
              {close != null ? formatUSD(close) : "—"}
            </p>

            {q10 != null && q90 != null && (
              <div className="mt-0.5">
                <div className="flex items-center gap-1 mb-0.5">
                  <span className="text-[10px] uppercase tracking-wide text-zinc-500">80% range</span>
                  <InfoTip text="80% of simulations predicted a close between these two values." />
                </div>
                <p className="text-base font-mono whitespace-nowrap">
                  <span className="text-amber-400">{formatUSD(q10)}</span>
                  <span className="text-zinc-600 mx-1.5">—</span>
                  <span className="text-violet-400">{formatUSD(q90)}</span>
                </p>
                {bandWidthPct != null && (
                  <p className="text-[11px] text-zinc-600 font-mono mt-0.5">±{bandWidthPct.toFixed(2)}%</p>
                )}
                <p className="text-xs text-zinc-600 font-mono mt-0.5">
                  Last run: {format(parseISO(prediction.predicted_at), "HH:mm:ss")}
                </p>
              </div>
            )}
          </div>

          {/* Right: brain icon top, confidence badge bottom */}
          <div className="flex flex-col items-end justify-between shrink-0">
            <span
              className="h-12 w-12 rounded-xl bg-blue-500/10 border border-blue-500/25 flex items-center justify-center"
              style={{ boxShadow: "0 0 18px rgba(59,130,246,0.25)" }}
            >
              <Brain className="w-6 h-6 text-blue-400" />
            </span>

            {bandWidthPct != null && (
              <ConfidenceBadge bandWidthPct={bandWidthPct} />
            )}
          </div>

        </div>
      </CardContent>
    </Card>
  );
}

// ── Consensus Card ────────────────────────────────────────────────────────────

export function ConsensusCard({ timeframe, prediction, isLoading }: Props) {
  if (isLoading) {
    return (
      <Card className="bg-bp-surface border-bp-border">
        <CardContent className="px-4 py-4 space-y-2">
          <Skeleton className="h-4 w-32" />
          <Skeleton className="h-8 w-40" />
          <Skeleton className="h-3 w-full" />
        </CardContent>
      </Card>
    );
  }

  if (!prediction) {
    return (
      <Card className="bg-bp-surface border-bp-border">
        <CardContent className="px-4 py-6 text-center">
          <p className="text-xs text-zinc-500">No prediction yet</p>
        </CardContent>
      </Card>
    );
  }

  const prob         = prediction.prob_bullish ?? 0;
  const bullishPct   = Math.round(prob * 100);
  const bearishPct   = 100 - bullishPct;
  const total        = prediction.sample_count ?? 30;
  const bullishCount = Math.round(prob * total);
  const isBullish    = prob >= 0.5;
  const displayPct   = isBullish ? bullishPct : bearishPct;

  const cardAccent = isBullish
    ? "border-emerald-500/20 bg-emerald-950/10"
    : "border-red-500/20 bg-red-950/10";

  const directionBg = isBullish
    ? "bg-emerald-500/10 border border-emerald-500/25"
    : "bg-red-500/10 border border-red-500/25";

  const directionColor = isBullish ? "text-emerald-400" : "text-red-400";

  return (
    <Card className={`border ${cardAccent}`}>
      <CardHeader className="pb-1 pt-3 px-4">
        <CardTitle className="text-xs font-semibold text-zinc-400 uppercase tracking-wider flex items-center gap-1">
          Consensus · {timeframe}
          <InfoTip text="How many of the 30 stochastic simulations predicted a higher close price." />
        </CardTitle>
      </CardHeader>
      <CardContent className="px-4 pb-4 space-y-3">

        {/* Direction block with translucent background */}
        <div className={`flex items-center gap-2.5 px-3 py-2.5 rounded-xl ${directionBg}`}>
          {isBullish
            ? <TrendingUp className={`w-5 h-5 shrink-0 ${directionColor}`} />
            : <TrendingDown className={`w-5 h-5 shrink-0 ${directionColor}`} />}
          <div className="leading-tight">
            <span className={`text-xl font-bold ${directionColor}`}>{displayPct}%</span>
            <span className={`text-xl font-bold ml-1.5 ${directionColor}`}>
              {isBullish ? "Bullish" : "Bearish"}
            </span>
          </div>
        </div>

        {/* Analyst counts */}
        <div className="flex items-center gap-3 text-xs">
          <span>
            <span className="text-emerald-400 font-semibold">▲ {bullishCount}</span>
            <span className="text-zinc-600 mx-1">/</span>
            <span className="text-red-400 font-semibold">▼ {total - bullishCount}</span>
            <span className="text-zinc-500 ml-1">analysts</span>
          </span>
          <InfoTip text="Number of simulated analysts predicting a bullish vs bearish close." />
        </div>

        {/* Analyst consensus bar */}
        <div>
          <div className="w-full h-2 bg-zinc-800 rounded-full overflow-hidden flex">
            <div
              className="h-full bg-emerald-500 transition-all rounded-l-full"
              style={{ width: `${bullishPct}%` }}
            />
            <div
              className="h-full bg-red-500 transition-all rounded-r-full"
              style={{ width: `${bearishPct}%` }}
            />
          </div>
          <div className="flex justify-between mt-0.5 text-[9px] font-mono">
            <span className="text-emerald-600">{bullishPct}% bull</span>
            <span className="text-red-600">{bearishPct}% bear</span>
          </div>
        </div>

      </CardContent>
    </Card>
  );
}

