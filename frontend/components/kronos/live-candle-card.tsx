"use client";

import { useEffect, useState } from "react";
import { TrendingUp, TrendingDown } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { InfoTip } from "@/components/ui/tooltip";
import { formatUSD } from "@/lib/format";
import { useKronosLiveCandle } from "@/lib/hooks/use-kronos";

interface Props {
  timeframe: string;
}

function useCountdownSeconds(targetIso: string | null | undefined): number {
  const calc = () => {
    if (!targetIso) return 0;
    return Math.max(0, Math.round((new Date(targetIso).getTime() - Date.now()) / 1000));
  };

  const [secs, setSecs] = useState<number>(calc);

  useEffect(() => {
    if (!targetIso) { setSecs(0); return; }
    setSecs(calc());
    const id = setInterval(() => setSecs(calc()), 1000);
    return () => clearInterval(id);
  }, [targetIso]); // eslint-disable-line react-hooks/exhaustive-deps

  return secs;
}

function fmtCountdown(secs: number): string {
  const m = Math.floor(secs / 60);
  const s = secs % 60;
  return `${String(m).padStart(2, "0")}:${String(s).padStart(2, "0")}`;
}

export function LiveCandleCard({ timeframe }: Props) {
  const { data: candle, isLoading } = useKronosLiveCandle(timeframe);
  const secs = useCountdownSeconds(candle?.close_time ?? null);

  // Total candle duration in seconds (from open to close)
  const totalSecs = candle
    ? Math.round((new Date(candle.close_time).getTime() - new Date(candle.open_time).getTime()) / 1000)
    : 900;
  const elapsed = Math.max(0, totalSecs - secs);
  const progressPct = totalSecs > 0 ? Math.min(100, Math.round((elapsed / totalSecs) * 100)) : 0;

  const isUp = (candle?.change_pct ?? 0) >= 0;

  if (isLoading && !candle) {
    return (
      <Card className="bg-bp-surface border-bp-border">
        <CardContent className="px-4 py-4 space-y-2">
          <Skeleton className="h-4 w-32" />
          <Skeleton className="h-8 w-48" />
          <Skeleton className="h-3 w-full" />
        </CardContent>
      </Card>
    );
  }

  if (!candle) {
    return (
      <Card className="bg-bp-surface border-bp-border">
        <CardContent className="px-4 py-4">
          <p className="text-xs text-zinc-500">Live candle unavailable</p>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card className="bg-bp-surface border-bp-border">
      <CardHeader className="pb-1 pt-3 px-4">
        <CardTitle className="text-sm font-semibold text-zinc-200 flex items-center gap-1">
          Live Candle · {timeframe}
          <InfoTip text="The currently forming candle on Binance. The price updates every 5 seconds. When this candle closes, Kronos will start a new prediction." />
        </CardTitle>
      </CardHeader>
      <CardContent className="px-4 pb-4 space-y-3">
        {/* Live price */}
        <div className="flex items-center gap-2">
          {isUp ? (
            <TrendingUp className="w-4 h-4 text-emerald-400 shrink-0" />
          ) : (
            <TrendingDown className="w-4 h-4 text-red-400 shrink-0" />
          )}
          <span className={`text-2xl font-bold font-mono ${isUp ? "text-emerald-400" : "text-red-400"}`}>
            {formatUSD(candle.live_price)}
          </span>
          <span className={`text-sm font-mono ${isUp ? "text-emerald-500" : "text-red-500"}`}>
            {candle.change_pct >= 0 ? "+" : ""}
            {candle.change_pct.toFixed(2)}%
          </span>
        </div>

        {/* OHLC grid */}
        <div className="grid grid-cols-2 gap-x-4 gap-y-1 text-xs">
          {[
            { label: "O", value: candle.open },
            { label: "H", value: candle.high },
            { label: "C", value: candle.close },
            { label: "L", value: candle.low },
          ].map(({ label, value }) => (
            <div key={label} className="flex items-center gap-1.5">
              <span className="text-zinc-600 w-3">{label}</span>
              <span className="font-mono text-zinc-400">{formatUSD(value)}</span>
            </div>
          ))}
        </div>

        {/* Volume */}
        <div className="text-[11px] text-zinc-600">
          Vol: <span className="font-mono text-zinc-500">{candle.volume.toLocaleString(undefined, { maximumFractionDigits: 2 })} BTC</span>
        </div>

        {/* Countdown + progress bar */}
        <div className="space-y-1">
          <div className="flex items-center justify-between text-[11px]">
            <span className="text-zinc-500">Closes in</span>
            <span className="font-mono text-zinc-300 font-medium">{fmtCountdown(secs)}</span>
          </div>
          <div className="w-full h-1.5 bg-bp-surface-2 rounded-full overflow-hidden">
            <div
              className={`h-full rounded-full transition-all duration-1000 ${isUp ? "bg-emerald-600" : "bg-red-600"}`}
              style={{ width: `${progressPct}%` }}
            />
          </div>
        </div>
      </CardContent>
    </Card>
  );
}
