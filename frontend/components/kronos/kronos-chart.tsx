"use client";

import { useEffect, useRef, useState } from "react";
import {
  createChart,
  type IChartApi,
  type ISeriesApi,
  type CandlestickData,
  type UTCTimestamp,
} from "lightweight-charts";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { useKlines } from "@/lib/hooks/use-klines";
import type { KronosPrediction } from "@/lib/api/schemas";

interface Props {
  timeframe: string;
  prediction: KronosPrediction | undefined;
  isIngesting?: boolean;
  klineCount?: number;
}

function toTs(isoStr: string): UTCTimestamp {
  return Math.floor(new Date(isoStr).getTime() / 1000) as UTCTimestamp;
}

function useCountdown(targetIso: string | null | undefined): string | null {
  const calc = () => {
    if (!targetIso) return null;
    const ms = new Date(targetIso).getTime() - Date.now();
    if (ms <= 0) return "00:00:00";
    const s = Math.floor(ms / 1000);
    const h = Math.floor(s / 3600);
    const m = Math.floor((s % 3600) / 60);
    const sec = s % 60;
    return [h, m, sec].map((x) => String(x).padStart(2, "0")).join(":");
  };

  const [remaining, setRemaining] = useState<string | null>(calc);

  useEffect(() => {
    if (!targetIso) { setRemaining(null); return; }
    setRemaining(calc());
    const interval = setInterval(() => setRemaining(calc()), 1000);
    return () => clearInterval(interval);
  }, [targetIso]); // eslint-disable-line react-hooks/exhaustive-deps

  return remaining;
}

export function KronosChart({ timeframe, prediction, isIngesting = false, klineCount = 0 }: Props) {
  const containerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const realSeriesRef = useRef<ISeriesApi<"Candlestick"> | null>(null);
  const predSeriesRef = useRef<ISeriesApi<"Candlestick"> | null>(null);

  const { data: klines, isLoading: klinesLoading } = useKlines({
    symbol: "BTCUSDT",
    interval: timeframe,
    limit: 120,
  });

  const countdown = useCountdown(prediction?.target_candle_close_time);

  // Init chart once on mount
  useEffect(() => {
    if (!containerRef.current) return;

    const chart = createChart(containerRef.current, {
      autoSize: true,
      height: 320,
      layout: {
        background: { color: "#131316" },
        textColor: "#71717a",
        fontSize: 11,
      },
      grid: {
        vertLines: { color: "#27272a" },
        horzLines: { color: "#27272a" },
      },
      rightPriceScale: { borderColor: "#27272a" },
      timeScale: {
        borderColor: "#27272a",
        timeVisible: true,
        secondsVisible: false,
      },
      crosshair: {
        vertLine: { color: "#52525b" },
        horzLine: { color: "#52525b" },
      },
    });

    realSeriesRef.current = chart.addCandlestickSeries({
      upColor: "#10b981",
      downColor: "#ef4444",
      borderUpColor: "#10b981",
      borderDownColor: "#ef4444",
      wickUpColor: "#10b981",
      wickDownColor: "#ef4444",
    });

    predSeriesRef.current = chart.addCandlestickSeries({
      upColor: "rgba(34, 211, 238, 0.5)",
      downColor: "rgba(34, 211, 238, 0.5)",
      borderUpColor: "#22d3ee",
      borderDownColor: "#22d3ee",
      wickUpColor: "#22d3ee",
      wickDownColor: "#22d3ee",
    });

    chartRef.current = chart;

    return () => {
      chart.remove();
      chartRef.current = null;
      realSeriesRef.current = null;
      predSeriesRef.current = null;
    };
  }, []);

  // Clear chart when timeframe changes (before new klines arrive)
  useEffect(() => {
    realSeriesRef.current?.setData([]);
    predSeriesRef.current?.setData([]);
  }, [timeframe]);

  // Update real candles when klines data arrives
  useEffect(() => {
    if (!realSeriesRef.current || !klines?.items?.length) return;
    const data: CandlestickData[] = klines.items.map((k) => ({
      time: toTs(k.open_time),
      open: k.open,
      high: k.high,
      low: k.low,
      close: k.close,
    }));
    realSeriesRef.current.setData(data);
    chartRef.current?.timeScale().fitContent();
  }, [klines]);

  // Update predicted candle
  useEffect(() => {
    if (!predSeriesRef.current) return;
    if (!prediction?.predicted_close || !prediction.target_candle_open_time) {
      predSeriesRef.current.setData([]);
      return;
    }
    const c = prediction.predicted_close;
    predSeriesRef.current.setData([
      {
        time: toTs(prediction.target_candle_open_time),
        open: prediction.predicted_open ?? c,
        high: prediction.q90_close ?? prediction.predicted_high ?? c,
        low: prediction.q10_close ?? prediction.predicted_low ?? c,
        close: c,
      },
    ]);
    chartRef.current?.timeScale().fitContent();
  }, [prediction]);

  return (
    <Card className="bg-bp-surface border-bp-border">
      <CardHeader className="pb-2 pt-3 px-4 flex flex-row items-center justify-between">
        <CardTitle className="text-sm font-semibold text-zinc-200">
          BTC/USDT · {timeframe.toUpperCase()}
        </CardTitle>
        <div className="flex items-center gap-4 text-xs text-zinc-500">
          <span className="flex items-center gap-1.5">
            <span className="inline-block w-2 h-2 rounded-sm bg-cyan-400" />
            Predicted (wicks = Q10/Q90)
          </span>
          {countdown && (
            <span className="text-zinc-400">
              Closes in{" "}
              <span className="font-mono text-cyan-400">{countdown}</span>
            </span>
          )}
        </div>
      </CardHeader>
      <CardContent className="px-0 pb-0">
        <div className="relative">
          <div ref={containerRef} className="w-full" style={{ height: 320 }} />
          {(klinesLoading || isIngesting) && (
            <div className="absolute inset-0 flex flex-col items-center justify-center gap-2 bg-[#131316]">
              <div className="h-1.5 w-48 rounded-full bg-zinc-800 overflow-hidden">
                <div className="h-full bg-cyan-500/60 rounded-full animate-pulse w-full" />
              </div>
              <p className="text-xs text-zinc-500">
                {isIngesting
                  ? `Downloading ${timeframe} history… ${klineCount > 0 ? `${klineCount} candles` : ""}`
                  : "Loading…"}
              </p>
            </div>
          )}
          {!klinesLoading && !isIngesting && !klines?.items?.length && (
            <div className="absolute inset-0 flex items-center justify-center bg-[#131316]">
              <p className="text-sm text-zinc-500">No data for {timeframe}.</p>
            </div>
          )}
        </div>
      </CardContent>
    </Card>
  );
}
