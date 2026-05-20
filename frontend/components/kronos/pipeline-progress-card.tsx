"use client";

import { Square } from "lucide-react";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { useKronosProgress, useKronosStop } from "@/lib/hooks/use-kronos";

interface Props {
  timeframe: string;
  isIngesting?: boolean;
  klineCount?: number;
}

export function PipelineProgressCard({ timeframe, isIngesting, klineCount }: Props) {
  const { data: progress } = useKronosProgress(timeframe);
  const stop = useKronosStop();

  const isPredicting = progress?.state === "PROGRESS" || progress?.state === "STARTED";

  // Show card when downloading klines OR running inference
  if (!isIngesting && !isPredicting) return null;

  // ── Klines download state ─────────────────────────────────────────────────
  if (isIngesting) {
    return (
      <Card className="bg-amber-950/20 border border-amber-500/25">
        <CardContent className="px-4 py-3 flex items-center gap-4">
          <div className="flex-1 space-y-1.5">
            <div className="flex items-center justify-between">
              <span className="text-xs text-amber-300 font-medium">
                Downloading {timeframe} historical data…
              </span>
              {klineCount !== undefined && klineCount > 0 && (
                <span className="text-xs text-zinc-500">{klineCount.toLocaleString()} candles so far</span>
              )}
            </div>
            <div className="w-full h-1.5 bg-bp-surface-2 rounded-full overflow-hidden">
              <div className="h-full bg-amber-500 rounded-full animate-pulse w-full" />
            </div>
          </div>
        </CardContent>
      </Card>
    );
  }

  // ── Prediction inference state ────────────────────────────────────────────
  const current = progress?.current ?? 0;
  const total = progress?.total ?? 30;
  const pct = total > 0 ? Math.round((current / total) * 100) : 0;
  const eta = progress?.eta_seconds;
  const step = progress?.step ?? "running";

  return (
    <Card className="bg-cyan-950/20 border border-cyan-500/25">
      <CardContent className="px-4 py-3 flex items-center gap-4">
        <div className="flex-1 space-y-1.5">
          <div className="flex items-center justify-between">
            <span className="text-xs text-cyan-300 font-medium capitalize">
              {step} — {current}/{total} samples
            </span>
            {eta !== null && eta !== undefined && (
              <span className="text-xs text-zinc-500">ETA {eta}s</span>
            )}
          </div>
          <div className="w-full h-1.5 bg-bp-surface-2 rounded-full overflow-hidden">
            <div
              className="h-full bg-cyan-500 rounded-full transition-all duration-300"
              style={{ width: `${pct}%` }}
            />
          </div>
        </div>
        <Button
          variant="ghost"
          size="sm"
          className="text-red-400 hover:text-red-300 hover:bg-red-950/30 h-7 px-2 shrink-0"
          onClick={() => stop.mutate(timeframe)}
          disabled={stop.isPending}
          title="Stop after the current sample completes"
        >
          <Square className="w-3 h-3 mr-1 fill-current" />
          Stop
        </Button>
      </CardContent>
    </Card>
  );
}
