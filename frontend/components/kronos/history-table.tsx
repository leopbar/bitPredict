"use client";

import { useState } from "react";
import { format, parseISO } from "date-fns";
import { CheckCircle, XCircle, Minus, ChevronDown, ChevronRight } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { InfoTip } from "@/components/ui/tooltip";
import { formatUSD } from "@/lib/format";
import { useKronosHistory } from "@/lib/hooks/use-kronos";
import type { KronosPrediction } from "@/lib/api/schemas";

interface Props {
  timeframe: string;
}

function fmt(d: string) {
  return format(parseISO(d), "MMM d, HH:mm");
}

function OhlcGrid({
  label,
  o, h, l, c,
  accent,
}: {
  label: string;
  o: number | null; h: number | null; l: number | null; c: number | null;
  accent?: string;
}) {
  return (
    <div className="space-y-0.5">
      <p className={`text-[10px] uppercase tracking-wide ${accent ?? "text-zinc-600"}`}>{label}</p>
      <div className="grid grid-cols-2 gap-x-3 gap-y-0.5 text-[11px] font-mono text-zinc-400">
        <span><span className="text-zinc-600">O</span> {o != null ? formatUSD(o) : "—"}</span>
        <span><span className="text-zinc-600">H</span> {h != null ? formatUSD(h) : "—"}</span>
        <span><span className="text-zinc-600">C</span> {c != null ? <span className="text-zinc-200">{formatUSD(c)}</span> : "—"}</span>
        <span><span className="text-zinc-600">L</span> {l != null ? formatUSD(l) : "—"}</span>
      </div>
    </div>
  );
}

function HistoryRow({ row }: { row: KronosPrediction }) {
  const [expanded, setExpanded] = useState(false);
  const hasActuals = row.actual_close != null;

  const errPct = row.close_error_pct;
  const errClass =
    errPct == null
      ? "text-zinc-600"
      : Math.abs(errPct) < 1
        ? "text-emerald-400"
        : Math.abs(errPct) < 3
          ? "text-yellow-400"
          : "text-red-400";

  return (
    <>
      <tr
        className="border-b border-bp-border/50 hover:bg-bp-surface-2/40 transition-colors cursor-pointer"
        onClick={() => setExpanded((v) => !v)}
      >
        {/* Expand toggle */}
        <td className="px-3 py-2.5 text-zinc-600">
          {hasActuals ? (
            expanded ? <ChevronDown className="w-3.5 h-3.5" /> : <ChevronRight className="w-3.5 h-3.5" />
          ) : (
            <span className="w-3.5 h-3.5 inline-block" />
          )}
        </td>

        {/* Date */}
        <td className="px-3 py-2.5 text-zinc-400 text-xs whitespace-nowrap">
          {fmt(row.predicted_at)}
        </td>

        {/* Target */}
        <td className="px-3 py-2.5 text-zinc-500 text-xs whitespace-nowrap">
          {row.target_candle_open_time ? fmt(row.target_candle_open_time) : "—"}
        </td>

        {/* Predicted close + band */}
        <td className="px-3 py-2.5 whitespace-nowrap">
          <p className="text-xs font-mono text-zinc-200">
            {row.predicted_close != null ? formatUSD(row.predicted_close) : "—"}
          </p>
          {row.q10_close != null && row.q90_close != null && (
            <p className="text-[10px] font-mono text-zinc-600">
              {formatUSD(row.q10_close)}–{formatUSD(row.q90_close)}
            </p>
          )}
        </td>

        {/* Actual close */}
        <td className="px-3 py-2.5 text-xs font-mono whitespace-nowrap">
          {row.actual_close != null ? (
            <span className="text-zinc-300">{formatUSD(row.actual_close)}</span>
          ) : (
            <span className="text-zinc-600 italic text-[10px]">pending</span>
          )}
        </td>

        {/* Error % */}
        <td className={`px-3 py-2.5 text-xs font-mono whitespace-nowrap ${errClass}`}>
          {errPct != null
            ? `${errPct >= 0 ? "+" : ""}${errPct.toFixed(2)}%`
            : "—"}
        </td>

        {/* Direction */}
        <td className="px-3 py-2.5">
          {row.direction_correct === null ? (
            <Minus className="w-3.5 h-3.5 text-zinc-600" />
          ) : row.direction_correct ? (
            <CheckCircle className="w-3.5 h-3.5 text-emerald-400" />
          ) : (
            <XCircle className="w-3.5 h-3.5 text-red-400" />
          )}
        </td>
      </tr>

      {/* Expanded OHLC row */}
      {expanded && hasActuals && (
        <tr className="border-b border-bp-border/30 bg-bp-surface-2/30">
          <td />
          <td colSpan={6} className="px-4 py-3">
            <div className="grid grid-cols-2 gap-6 max-w-lg">
              <OhlcGrid
                label="Predicted"
                o={row.predicted_open} h={row.predicted_high}
                l={row.predicted_low} c={row.predicted_close}
                accent="text-cyan-600"
              />
              <OhlcGrid
                label="Actual"
                o={row.actual_open} h={row.actual_high}
                l={row.actual_low} c={row.actual_close}
                accent="text-zinc-400"
              />
            </div>
          </td>
        </tr>
      )}
    </>
  );
}

export function HistoryTable({ timeframe }: Props) {
  const { data, isLoading } = useKronosHistory(timeframe, 50);

  return (
    <Card className="bg-bp-surface border-bp-border">
      <CardHeader className="pb-2 pt-4 px-4">
        <CardTitle className="text-sm font-semibold text-zinc-200 flex items-center gap-1">
          Prediction History
          <InfoTip text="Last 50 predictions for this timeframe. Click any row with actual data to expand the full OHLC comparison." />
        </CardTitle>
      </CardHeader>
      <CardContent className="px-0 pb-2">
        {isLoading ? (
          <div className="space-y-2 px-4">
            {Array.from({ length: 5 }).map((_, i) => (
              <Skeleton key={i} className="h-8 w-full" />
            ))}
          </div>
        ) : !data?.items.length ? (
          <p className="text-sm text-zinc-500 px-4 py-4">No predictions yet for {timeframe}.</p>
        ) : (
          <div className="overflow-x-auto overflow-y-auto max-h-[380px]">
            <table className="w-full text-xs">
              <thead className="sticky top-0 bg-bp-surface z-10">
                <tr className="border-b border-bp-border">
                  <th className="w-8" />
                  <th className="px-3 py-2 text-left text-zinc-500 font-medium whitespace-nowrap">
                    Predicted at
                  </th>
                  <th className="px-3 py-2 text-left text-zinc-500 font-medium whitespace-nowrap">
                    Target candle
                  </th>
                  <th className="px-3 py-2 text-left text-zinc-500 font-medium whitespace-nowrap">
                    <span className="flex items-center gap-1">
                      Pred. close / band
                      <InfoTip text="Median of 30 simulated close prices. The range below (Q10–Q90) is the 80% confidence band — the model expected the actual close to fall here." />
                    </span>
                  </th>
                  <th className="px-3 py-2 text-left text-zinc-500 font-medium whitespace-nowrap">
                    Actual close
                  </th>
                  <th className="px-3 py-2 text-left text-zinc-500 font-medium whitespace-nowrap">
                    <span className="flex items-center gap-1">
                      Error %
                      <InfoTip text="(Predicted − Actual) / Actual × 100. Positive = predicted too high. Negative = predicted too low. Green &lt;1%, yellow &lt;3%, red ≥3%." />
                    </span>
                  </th>
                  <th className="px-3 py-2 text-left text-zinc-500 font-medium whitespace-nowrap">
                    <span className="flex items-center gap-1">
                      Dir
                      <InfoTip text="Did the model predict the correct direction? ✓ means the predicted candle (bullish/bearish) matched what actually happened." />
                    </span>
                  </th>
                </tr>
              </thead>
              <tbody>
                {data.items.map((row) => (
                  <HistoryRow key={`${row.id}-${row.predicted_at}`} row={row} />
                ))}
              </tbody>
            </table>
          </div>
        )}
      </CardContent>
    </Card>
  );
}
