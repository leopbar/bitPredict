"use client";

import { TrendingUp, TrendingDown } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { formatUSD, formatPercent } from "@/lib/format";
import { useKronosScoreboard } from "@/lib/hooks/use-kronos";
import type { KronosPrediction } from "@/lib/api/schemas";

interface CardProps {
  prediction: KronosPrediction | undefined;
  isLoading: boolean;
}

interface DirectionCardProps extends CardProps {
  timeframe: string;
}

function KpiShell({
  title,
  tooltip,
  children,
}: {
  title: string;
  tooltip: string;
  children: React.ReactNode;
}) {
  return (
    <Card className="bg-bp-surface border-bp-border" title={tooltip}>
      <CardHeader className="pb-1 pt-3 px-4">
        <CardTitle className="text-xs font-medium text-zinc-400 uppercase tracking-wide">
          {title}
        </CardTitle>
      </CardHeader>
      <CardContent className="px-4 pb-3">{children}</CardContent>
    </Card>
  );
}

export function KpiDirectionCard({ prediction, isLoading, timeframe }: DirectionCardProps) {
  const { data: scoreboard } = useKronosScoreboard(timeframe);
  const accuracy = scoreboard?.directional_accuracy ?? null;
  const evaluated = scoreboard?.total_evaluated ?? 0;

  if (isLoading) {
    return (
      <KpiShell title="Direction" tooltip="Predicted market direction for the next candle">
        <Skeleton className="h-8 w-24 mt-1" />
      </KpiShell>
    );
  }

  const bullish = (prediction?.prob_bullish ?? 0) >= 0.5;
  const prob = prediction?.prob_bullish ?? null;

  return (
    <KpiShell
      title="Direction"
      tooltip="Predicted market direction — based on how many of the 30 simulations closed higher than the last candle"
    >
      {prob === null ? (
        <p className="text-sm text-zinc-500 mt-1">No data</p>
      ) : (
        <div className="mt-1">
          <div className="flex items-center gap-2">
            {bullish ? (
              <TrendingUp className="w-5 h-5 text-emerald-400" />
            ) : (
              <TrendingDown className="w-5 h-5 text-red-400" />
            )}
            <span
              className={`text-lg font-bold ${bullish ? "text-emerald-400" : "text-red-400"}`}
            >
              {bullish ? "Bullish" : "Bearish"}
            </span>
          </div>
          {accuracy !== null && evaluated >= 5 && (
            <p
              className={`text-[10px] mt-1 ${
                accuracy >= 0.55
                  ? "text-emerald-500"
                  : accuracy >= 0.45
                    ? "text-yellow-500"
                    : "text-red-500"
              }`}
              title={`Based on ${evaluated} evaluated predictions`}
            >
              {(accuracy * 100).toFixed(0)}% hist. accuracy
            </p>
          )}
        </div>
      )}
    </KpiShell>
  );
}

export function KpiBullishCard({ prediction, isLoading }: CardProps) {
  if (isLoading) {
    return (
      <KpiShell title="% Bullish" tooltip="Probability of a bullish close">
        <Skeleton className="h-8 w-20 mt-1" />
      </KpiShell>
    );
  }

  const prob = prediction?.prob_bullish ?? null;
  const pct = prob !== null ? prob * 100 : null;

  return (
    <KpiShell
      title="% Bullish"
      tooltip="Out of 30 simulated futures, this fraction predicted a higher close than the last actual candle"
    >
      {pct === null ? (
        <p className="text-sm text-zinc-500 mt-1">No data</p>
      ) : (
        <div className="mt-1 space-y-1">
          <p
            className={`text-lg font-bold ${pct >= 50 ? "text-emerald-400" : "text-red-400"}`}
          >
            {pct.toFixed(0)}%
          </p>
          <div className="w-full h-1.5 bg-bp-surface-2 rounded-full overflow-hidden">
            <div
              className={`h-full rounded-full transition-all ${pct >= 50 ? "bg-emerald-500" : "bg-red-500"}`}
              style={{ width: `${pct}%` }}
            />
          </div>
        </div>
      )}
    </KpiShell>
  );
}

export function KpiPriceCard({ prediction, isLoading }: CardProps) {
  if (isLoading) {
    return (
      <KpiShell title="Price Target" tooltip="Predicted close price">
        <Skeleton className="h-8 w-32 mt-1" />
      </KpiShell>
    );
  }

  const close = prediction?.predicted_close ?? null;
  const q10 = prediction?.q10_close ?? null;
  const q90 = prediction?.q90_close ?? null;

  return (
    <KpiShell
      title="Price Target"
      tooltip="Median predicted close price across 30 simulations, with the 10th–90th percentile band showing uncertainty"
    >
      {close === null ? (
        <p className="text-sm text-zinc-500 mt-1">No data</p>
      ) : (
        <div className="mt-1">
          <p className="text-lg font-bold text-zinc-100">{formatUSD(close)}</p>
          {q10 !== null && q90 !== null && (
            <p className="text-xs text-zinc-500 mt-0.5">
              {formatUSD(q10)} – {formatUSD(q90)}
            </p>
          )}
        </div>
      )}
    </KpiShell>
  );
}

export function KpiRangeCard({ prediction, isLoading }: CardProps) {
  if (isLoading) {
    return (
      <KpiShell title="Candle Range" tooltip="Predicted high-low spread">
        <Skeleton className="h-8 w-20 mt-1" />
      </KpiShell>
    );
  }

  const high = prediction?.predicted_high ?? null;
  const low = prediction?.predicted_low ?? null;
  const close = prediction?.predicted_close ?? null;
  const rangePct =
    high !== null && low !== null && close !== null && close > 0
      ? ((high - low) / close) * 100
      : null;

  return (
    <KpiShell
      title="Candle Range"
      tooltip="Expected high minus low as a percentage of the predicted close — wider means more volatile candle"
    >
      {rangePct === null ? (
        <p className="text-sm text-zinc-500 mt-1">No data</p>
      ) : (
        <div className="mt-1">
          <p className="text-lg font-bold text-amber-400">{rangePct.toFixed(2)}%</p>
          {high !== null && low !== null && (
            <p className="text-xs text-zinc-500 mt-0.5">
              H {formatUSD(high)} · L {formatUSD(low)}
            </p>
          )}
        </div>
      )}
    </KpiShell>
  );
}
