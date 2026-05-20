"use client";

import { useEffect, useState } from "react";
import { TrendingUp, TrendingDown } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { InfoTip } from "@/components/ui/tooltip";
import { formatUSD } from "@/lib/format";
import { useKronosLiveCandle } from "@/lib/hooks/use-kronos";
import { useKlines } from "@/lib/hooks/use-klines";

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

function BtcIcon({ size = 28 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 32 32" fill="none" xmlns="http://www.w3.org/2000/svg">
      <circle cx="16" cy="16" r="16" fill="#F7931A" />
      <path
        d="M22.1 13.9c.3-2-1.2-3.1-3.3-3.8l.7-2.7-1.6-.4-.7 2.6c-.4-.1-.8-.2-1.3-.3l.7-2.6-1.6-.4-.7 2.7c-.4-.1-.7-.2-1-.2v0l-2.2-.6-.4 1.7s1.2.3 1.2.3c.7.2.8.7.8 1l-.8 3.3c0 0 .1 0 .2.1l-.2-.1-1.1 4.5c-.1.2-.3.6-.8.4 0 0-1.2-.3-1.2-.3l-.8 1.9 2.1.5c.4.1.8.2 1.2.3l-.7 2.8 1.6.4.7-2.7c.5.1.9.2 1.3.3l-.7 2.7 1.6.4.7-2.8c2.9.5 5.1.3 6-2.3.7-2.1 0-3.3-1.5-4.1 1.1-.3 1.9-1 2.1-2.6zm-3.8 5.3c-.5 2-3.9 1-5 .7l.9-3.6c1.1.3 4.6.8 4.1 2.9zm.5-5.3c-.5 1.8-3.3 1-4.2.7l.8-3.3c.9.2 3.9.7 3.4 2.6z"
        fill="white"
      />
    </svg>
  );
}

function Sparkline({ closes, isUp }: { closes: number[]; isUp: boolean }) {
  if (closes.length < 2) return null;

  const min = Math.min(...closes);
  const max = Math.max(...closes);
  const range = max - min || 1;
  const W = 400;
  const H = 100;

  const pts = closes.map((c, i) => {
    const x = (i / (closes.length - 1)) * W;
    const y = H - ((c - min) / range) * (H * 0.85);
    return `${x.toFixed(1)},${y.toFixed(1)}`;
  });

  const linePath = `M ${pts.join(" L ")}`;
  const fillPath = `M 0,${H} L ${pts.join(" L ")} L ${W},${H} Z`;
  const color    = isUp ? "#10b981" : "#ef4444";
  const gradId   = isUp ? "lcGradUp" : "lcGradDown";

  return (
    <svg
      viewBox={`0 0 ${W} ${H}`}
      preserveAspectRatio="none"
      className="absolute inset-x-0 top-1/2 -translate-y-1/2 w-full h-32 opacity-[0.18] pointer-events-none"
      aria-hidden="true"
    >
      <defs>
        <linearGradient id={gradId} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor={color} stopOpacity="0.5" />
          <stop offset="100%" stopColor={color} stopOpacity="0" />
        </linearGradient>
      </defs>
      <path d={fillPath} fill={`url(#${gradId})`} />
      <path d={linePath} stroke={color} strokeWidth="1.8" fill="none" />
    </svg>
  );
}

export function LiveCandleCard({ timeframe }: Props) {
  const { data: candle, isLoading } = useKronosLiveCandle(timeframe);
  const { data: klinesData } = useKlines({ symbol: "BTCUSDT", interval: "15m", limit: 96 });

  const secs = useCountdownSeconds(candle?.close_time ?? null);

  const totalSecs = candle
    ? Math.round((new Date(candle.close_time).getTime() - new Date(candle.open_time).getTime()) / 1000)
    : 900;
  const elapsed    = Math.max(0, totalSecs - secs);
  const progressPct = totalSecs > 0 ? Math.min(100, Math.round((elapsed / totalSecs) * 100)) : 0;

  const isUp   = (candle?.change_pct ?? 0) >= 0;
  const closes = klinesData?.items.map((k) => k.close) ?? [];

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
    <Card className="relative overflow-hidden bg-bp-surface border-bp-border">

      {/* Real 24h sparkline in background */}
      <Sparkline closes={closes} isUp={isUp} />

      <CardHeader className="pb-1 pt-3 px-4 relative">
        <CardTitle className="text-xs font-semibold text-zinc-400 uppercase tracking-wider flex items-center gap-2">
          <BtcIcon size={22} />
          <span>BTC/USDT · {timeframe}</span>
          <InfoTip text="The currently forming candle on Binance. Updates every 5 seconds. When this candle closes, Kronos starts a new prediction." />
        </CardTitle>
      </CardHeader>

      <CardContent className="px-4 pb-4 space-y-3 relative">

        {/* Live price + change */}
        <div className="flex items-center gap-2">
          {isUp
            ? <TrendingUp className="w-4 h-4 text-emerald-400 shrink-0" />
            : <TrendingDown className="w-4 h-4 text-red-400 shrink-0" />}
          <span className={`text-2xl font-bold font-mono ${isUp ? "text-emerald-400" : "text-red-400"}`}>
            {formatUSD(candle.live_price)}
          </span>
          <span className={`text-sm font-mono ${isUp ? "text-emerald-500" : "text-red-500"}`}>
            {candle.change_pct >= 0 ? "+" : ""}{candle.change_pct.toFixed(2)}%
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
          Vol: <span className="font-mono text-zinc-500">
            {candle.volume.toLocaleString(undefined, { maximumFractionDigits: 2 })} BTC
          </span>
        </div>

        {/* Countdown + progress */}
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
