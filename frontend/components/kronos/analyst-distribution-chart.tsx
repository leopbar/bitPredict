"use client";

import { useMemo } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { InfoTip } from "@/components/ui/tooltip";
import { formatUSD } from "@/lib/format";
import { useKronosSims } from "@/lib/hooks/use-kronos";
import type { KronosPrediction } from "@/lib/api/schemas";

const N_BUCKETS = 10;
const VB_W = 600;
const VB_H = 190;
const PAD = { top: 30, right: 20, bottom: 48, left: 20 };

interface Props {
  timeframe: string;
  prediction: KronosPrediction | undefined;
}

function bucketColor(i: number, n: number): string {
  // Smooth gradient: red (0°) → orange (30°) → yellow (55°) → lime (90°) → emerald (145°)
  const hue = Math.round((i / Math.max(n - 1, 1)) * 145);
  return `hsl(${hue}, 85%, 55%)`;
}

export function AnalystDistributionChart({ timeframe, prediction }: Props) {
  const { data: sims, isLoading } = useKronosSims(timeframe);

  const closes = useMemo(() => sims?.samples?.map((s) => s.close) ?? [], [sims]);
  const refClose = sims?.ref_close ?? null;
  const q10 = prediction?.q10_close ?? null;
  const q90 = prediction?.q90_close ?? null;
  const median = prediction?.predicted_close ?? null;

  const chart = useMemo(() => {
    if (closes.length === 0 || median == null) return null;

    const min = Math.min(...closes);
    const max = Math.max(...closes);
    const span = max - min || 1;
    const step = span / N_BUCKETS;
    const plotW = VB_W - PAD.left - PAD.right;
    const plotH = VB_H - PAD.top - PAD.bottom;
    const barW = plotW / N_BUCKETS;

    const buckets = Array.from({ length: N_BUCKETS }, (_, i) => {
      const lo = min + i * step;
      const hi = min + (i + 1) * step;
      const count = closes.filter((c) =>
        i === N_BUCKETS - 1 ? c >= lo && c <= hi : c >= lo && c < hi,
      ).length;
      const pct = Math.round((count / closes.length) * 100);
      return { lo, hi, count, pct };
    });

    const maxCount = Math.max(...buckets.map((b) => b.count), 1);
    const xScale = (v: number) =>
      PAD.left + ((Math.max(min, Math.min(max, v)) - min) / span) * plotW;
    const yScale = (count: number) =>
      PAD.top + plotH - (count / maxCount) * plotH;

    // Smooth bezier curve through bar-top midpoints
    const pts = buckets.map((b, i) => ({
      x: PAD.left + (i + 0.5) * barW,
      y: yScale(b.count),
    }));

    const curvePath = pts.reduce((d, p, i) => {
      if (i === 0) return `M ${p.x.toFixed(1)} ${p.y.toFixed(1)}`;
      const prev = pts[i - 1];
      const cpx = ((prev.x + p.x) / 2).toFixed(1);
      return `${d} C ${cpx} ${prev.y.toFixed(1)} ${cpx} ${p.y.toFixed(1)} ${p.x.toFixed(1)} ${p.y.toFixed(1)}`;
    }, "");

    const areaPath = `${curvePath} L ${pts[pts.length - 1].x.toFixed(1)} ${(PAD.top + plotH).toFixed(1)} L ${pts[0].x.toFixed(1)} ${(PAD.top + plotH).toFixed(1)} Z`;

    const medianX = xScale(median);
    const q10X = q10 != null ? xScale(q10) : null;
    const q90X = q90 != null ? xScale(q90) : null;
    const refX = refClose != null ? xScale(refClose) : null;

    return { buckets, maxCount, barW, plotW, plotH, curvePath, areaPath, medianX, q10X, q90X, refX, min, max };
  }, [closes, median, q10, q90, refClose]);

  if (isLoading) {
    return (
      <Card className="bg-bp-surface border-bp-border">
        <CardContent className="px-4 py-4">
          <Skeleton className="h-[200px] w-full" />
        </CardContent>
      </Card>
    );
  }

  if (!chart || closes.length === 0) {
    return (
      <Card className="bg-bp-surface border-bp-border">
        <CardContent className="px-4 py-8 text-center">
          <p className="text-xs text-zinc-500">
            No simulation data yet. Run a prediction to see the analyst distribution.
          </p>
        </CardContent>
      </Card>
    );
  }

  const { buckets, maxCount, barW, plotW, plotH, curvePath, areaPath, medianX, q10X, q90X, refX, min, max } = chart;

  return (
    <Card className="bg-bp-surface border-bp-border">
      <CardHeader className="pb-1 pt-3 px-4">
        <CardTitle className="text-sm font-semibold text-zinc-200 flex items-center gap-1">
          Analyst Distribution · {timeframe}
          <InfoTip text="Distribution of all 30 simulated close prices. Each bar shows how many stochastic simulations converged on that price zone. Taller = stronger consensus." />
          {/* Legend */}
          <div className="ml-auto flex items-center gap-4 text-[10px] font-normal text-zinc-500">
            {q10X != null && (
              <span className="flex items-center gap-1">
                <span className="block w-3 h-0.5 bg-amber-400 rounded" />Q10
              </span>
            )}
            <span className="flex items-center gap-1">
              <span className="block w-3 h-0.5 bg-cyan-400 rounded" />Median
            </span>
            {q90X != null && (
              <span className="flex items-center gap-1">
                <span className="block w-3 h-0.5 bg-violet-400 rounded" />Q90
              </span>
            )}
            {refX != null && (
              <span className="flex items-center gap-1">
                <span className="block w-3 h-px bg-white/30" />Last close
              </span>
            )}
          </div>
        </CardTitle>
      </CardHeader>
      <CardContent className="px-4 pb-3">
        <svg viewBox={`0 0 ${VB_W} ${VB_H}`} className="w-full" style={{ height: 190 }}>
          <defs>
            <linearGradient id="adAreaGrad" x1="0%" y1="0%" x2="100%" y2="0%">
              <stop offset="0%"   stopColor="#ef4444" stopOpacity="0.14" />
              <stop offset="35%"  stopColor="#f97316" stopOpacity="0.14" />
              <stop offset="50%"  stopColor="#eab308" stopOpacity="0.14" />
              <stop offset="65%"  stopColor="#84cc16" stopOpacity="0.14" />
              <stop offset="100%" stopColor="#10b981" stopOpacity="0.14" />
            </linearGradient>
            <linearGradient id="adCurveGrad" x1="0%" y1="0%" x2="100%" y2="0%">
              <stop offset="0%"   stopColor="#ef4444" />
              <stop offset="35%"  stopColor="#f97316" />
              <stop offset="50%"  stopColor="#eab308" />
              <stop offset="65%"  stopColor="#84cc16" />
              <stop offset="100%" stopColor="#10b981" />
            </linearGradient>
          </defs>

          {/* Q10–Q90 band highlight */}
          {q10X != null && q90X != null && (
            <rect
              x={q10X} y={PAD.top}
              width={q90X - q10X} height={plotH}
              fill="white" fillOpacity={0.025} rx={2}
            />
          )}

          {/* Histogram bars */}
          {buckets.map((b, i) => {
            const x = PAD.left + i * barW;
            const barH = (b.count / maxCount) * plotH;
            const y = PAD.top + plotH - barH;
            return (
              <g key={i}>
                {b.count > 0 && (
                  <rect
                    x={x + 1.5} y={y}
                    width={barW - 3} height={barH}
                    fill={bucketColor(i, N_BUCKETS)}
                    fillOpacity={0.65} rx={3}
                  />
                )}
                {b.pct >= 5 && (
                  <text
                    x={x + barW / 2} y={y - 5}
                    textAnchor="middle" fill="#a1a1aa"
                    fontSize={9} fontFamily="monospace"
                  >
                    {b.pct}%
                  </text>
                )}
              </g>
            );
          })}

          {/* Smooth area fill */}
          <path d={areaPath} fill="url(#adAreaGrad)" />

          {/* Smooth curve stroke */}
          <path
            d={curvePath} fill="none"
            stroke="url(#adCurveGrad)" strokeWidth={2}
            strokeLinecap="round" strokeLinejoin="round"
          />

          {/* Last close line */}
          {refX != null && (
            <line
              x1={refX} y1={PAD.top} x2={refX} y2={PAD.top + plotH}
              stroke="rgba(255,255,255,0.2)" strokeWidth={1} strokeDasharray="4,3"
            />
          )}

          {/* Q10 marker */}
          {q10X != null && (
            <g>
              <line
                x1={q10X} y1={PAD.top} x2={q10X} y2={PAD.top + plotH}
                stroke="#f59e0b" strokeWidth={1.5} strokeDasharray="4,3"
              />
              <text x={q10X} y={PAD.top + plotH + 12} textAnchor="middle" fill="#f59e0b" fontSize={9} fontFamily="monospace">Q10</text>
              <text x={q10X} y={PAD.top + plotH + 23} textAnchor="middle" fill="#78716c" fontSize={8} fontFamily="monospace">
                {q10 != null ? formatUSD(q10) : ""}
              </text>
            </g>
          )}

          {/* Q90 marker */}
          {q90X != null && (
            <g>
              <line
                x1={q90X} y1={PAD.top} x2={q90X} y2={PAD.top + plotH}
                stroke="#a855f7" strokeWidth={1.5} strokeDasharray="4,3"
              />
              <text x={q90X} y={PAD.top + plotH + 12} textAnchor="middle" fill="#a855f7" fontSize={9} fontFamily="monospace">Q90</text>
              <text x={q90X} y={PAD.top + plotH + 23} textAnchor="middle" fill="#78716c" fontSize={8} fontFamily="monospace">
                {q90 != null ? formatUSD(q90) : ""}
              </text>
            </g>
          )}

          {/* Median marker */}
          <line
            x1={medianX} y1={PAD.top - 6} x2={medianX} y2={PAD.top + plotH}
            stroke="#22d3ee" strokeWidth={2}
          />
          <text x={medianX} y={PAD.top - 10} textAnchor="middle" fill="#22d3ee" fontSize={9} fontWeight="600" fontFamily="monospace">
            {median != null ? formatUSD(median) : ""}
          </text>
          <text x={medianX} y={PAD.top + plotH + 12} textAnchor="middle" fill="#22d3ee" fontSize={9} fontFamily="monospace">
            Median
          </text>

          {/* Min / Max price labels */}
          <text x={PAD.left} y={PAD.top + plotH + 36} textAnchor="start" fill="#52525b" fontSize={8} fontFamily="monospace">
            {formatUSD(min)}
          </text>
          <text x={PAD.left + plotW} y={PAD.top + plotH + 36} textAnchor="end" fill="#52525b" fontSize={8} fontFamily="monospace">
            {formatUSD(max)}
          </text>
        </svg>

        {/* Summary row */}
        <div className="flex items-center gap-6 mt-0.5 text-[11px]">
          <span className="text-zinc-500">
            <span className="font-mono text-amber-400">{q10 != null ? formatUSD(q10) : "—"}</span>
            <span className="text-zinc-700 mx-1.5">──</span>
            <span className="font-mono text-violet-400">{q90 != null ? formatUSD(q90) : "—"}</span>
            <span className="text-zinc-600 ml-1.5">80% band</span>
          </span>
          <span className="text-zinc-600">{closes.length} simulations</span>
          {refClose != null && (
            <span className="text-zinc-500">
              last close{" "}
              <span className="font-mono text-zinc-400">{formatUSD(refClose)}</span>
            </span>
          )}
        </div>
      </CardContent>
    </Card>
  );
}
