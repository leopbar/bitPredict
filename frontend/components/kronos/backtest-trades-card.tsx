"use client";

import { format, parseISO } from "date-fns";
import { CheckCircle, XCircle, Minus, TrendingUp, TrendingDown, List } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { InfoTip } from "@/components/ui/tooltip";
import { formatUSD } from "@/lib/format";
import { useKronosBacktestTrades } from "@/lib/hooks/use-kronos";
import type { KronosBacktestTrade } from "@/lib/api/schemas";

interface Props {
  timeframe: string;
  backtestId?: number;
}

function fmtDate(iso: string) {
  return format(parseISO(iso), "MMM d, yyyy HH:mm");
}

function signed(v: number, decimals = 2): string {
  return `${v >= 0 ? "+" : ""}${v.toFixed(decimals)}%`;
}

function pnlColor(v: number | null): string {
  if (v == null) return "text-zinc-500";
  return v > 0 ? "text-emerald-400" : v < 0 ? "text-red-400" : "text-zinc-400";
}

function TradeRow({ t }: { t: KronosBacktestTrade }) {
  const isLong    = (t.prob_bullish ?? 0.5) >= 0.5;
  const probPct   = Math.round(Math.abs((t.prob_bullish ?? 0.5) - (isLong ? 0 : 1)) * 100);
  const errAbs    = t.close_error_pct != null ? Math.abs(t.close_error_pct) : null;
  const errClass  =
    errAbs == null ? "text-zinc-600"
    : errAbs < 1   ? "text-emerald-400"
    : errAbs < 3   ? "text-yellow-400"
    : "text-red-400";

  const retClass  = pnlColor(t.trade_return_pct);
  const pnlClass  = pnlColor(t.trade_pnl_usd);
  const hasBand   = t.q10_close != null && t.q90_close != null;

  return (
    <tr className="border-b border-bp-border/40 hover:bg-bp-surface-2/30 transition-colors">
      {/* Date */}
      <td className="px-3 py-2 text-xs text-zinc-400 whitespace-nowrap">
        {fmtDate(t.target_open_time)}
      </td>

      {/* Signal */}
      <td className="px-3 py-2 whitespace-nowrap">
        <span className={`inline-flex items-center gap-1 text-xs font-semibold ${isLong ? "text-emerald-400" : "text-red-400"}`}>
          {isLong
            ? <TrendingUp className="w-3 h-3" />
            : <TrendingDown className="w-3 h-3" />}
          {isLong ? "LONG" : "SHORT"}
          <span className="font-normal text-[10px] opacity-70">{probPct}%</span>
        </span>
      </td>

      {/* Predicted close */}
      <td className="px-3 py-2 text-xs font-mono text-zinc-300 whitespace-nowrap">
        {t.predicted_close != null ? formatUSD(t.predicted_close) : "—"}
      </td>

      {/* Actual close */}
      <td className="px-3 py-2 text-xs font-mono text-zinc-200 whitespace-nowrap">
        {t.actual_close != null ? formatUSD(t.actual_close) : "—"}
      </td>

      {/* Error % */}
      <td className={`px-3 py-2 text-xs font-mono whitespace-nowrap ${errClass}`}>
        {t.close_error_pct != null
          ? `${t.close_error_pct >= 0 ? "+" : ""}${t.close_error_pct.toFixed(2)}%`
          : "—"}
      </td>

      {/* Direction */}
      <td className="px-3 py-2">
        {t.direction_correct === null ? (
          <Minus className="w-3.5 h-3.5 text-zinc-600" />
        ) : t.direction_correct ? (
          <CheckCircle className="w-3.5 h-3.5 text-emerald-400" />
        ) : (
          <XCircle className="w-3.5 h-3.5 text-red-400" />
        )}
      </td>

      {/* Band Q10–Q90 + hit */}
      <td className="px-3 py-2 whitespace-nowrap">
        {hasBand ? (
          <div className="flex items-center gap-1.5">
            <span className="text-[10px] font-mono text-zinc-600">
              {formatUSD(t.q10_close!)}–{formatUSD(t.q90_close!)}
            </span>
            {t.band_covers_actual != null && (
              t.band_covers_actual
                ? <CheckCircle className="w-3 h-3 text-emerald-500/70 shrink-0" />
                : <XCircle className="w-3 h-3 text-red-500/70 shrink-0" />
            )}
          </div>
        ) : (
          <span className="text-zinc-600">—</span>
        )}
      </td>

      {/* Ganho % */}
      <td className={`px-3 py-2 text-xs font-mono font-semibold whitespace-nowrap ${retClass}`}>
        {t.trade_return_pct != null ? signed(t.trade_return_pct) : "—"}
      </td>

      {/* Result. $ */}
      <td className={`px-3 py-2 text-xs font-mono font-semibold whitespace-nowrap ${pnlClass}`}>
        {t.trade_pnl_usd != null
          ? `${t.trade_pnl_usd >= 0 ? "+" : ""}${formatUSD(t.trade_pnl_usd)}`
          : "—"}
      </td>
    </tr>
  );
}

export function BacktestTradesCard({ timeframe, backtestId }: Props) {
  const { data: trades, isLoading } = useKronosBacktestTrades(timeframe, backtestId);

  const wins   = trades?.filter((t) => (t.trade_return_pct ?? 0) > 0).length ?? 0;
  const total  = trades?.length ?? 0;
  const hasPnl = trades?.some((t) => t.trade_pnl_usd != null) ?? false;

  return (
    <Card className="bg-bp-surface border-bp-border">
      <CardHeader className="pb-2 pt-4 px-4">
        <CardTitle className="text-sm font-semibold text-zinc-200 flex items-center gap-1.5 flex-wrap">
          <List className="w-4 h-4 text-zinc-400" />
          Trade Operations
          <InfoTip text="Individual trade results from the latest backtest run. Each row is one historical candle evaluated by the model. LONG when prob ≥ 50%, SHORT otherwise — entry at candle open, exit at candle close." />
          {total > 0 && (
            <div className="ml-2 flex items-center gap-4 text-[11px] font-normal text-zinc-500 normal-case tracking-normal">
              <span>
                <span className="font-mono text-zinc-300">{total}</span> trades
              </span>
              <span>
                <span className={`font-mono font-semibold ${wins / total >= 0.5 ? "text-emerald-400" : "text-red-400"}`}>
                  {Math.round((wins / total) * 100)}%
                </span> win rate
              </span>
            </div>
          )}
        </CardTitle>
      </CardHeader>

      <CardContent className="px-0 pb-2">
        {isLoading ? (
          <div className="space-y-2 px-4">
            {Array.from({ length: 8 }).map((_, i) => (
              <Skeleton key={i} className="h-8 w-full" />
            ))}
          </div>
        ) : !trades || trades.length === 0 ? (
          <p className="text-sm text-zinc-500 px-4 py-4">
            No trade data yet. Run a backtest to populate this table.
          </p>
        ) : (
          <div className="overflow-x-auto max-h-[520px] overflow-y-auto">
            <table className="w-full text-xs">
              <thead className="sticky top-0 bg-bp-surface z-10">
                <tr className="border-b border-bp-border">
                  <th className="px-3 py-2 text-left text-zinc-500 font-medium whitespace-nowrap">Date</th>
                  <th className="px-3 py-2 text-left text-zinc-500 font-medium whitespace-nowrap">
                    <span className="flex items-center gap-1">
                      Signal
                      <InfoTip text="Model direction call and conviction percentage." />
                    </span>
                  </th>
                  <th className="px-3 py-2 text-left text-zinc-500 font-medium whitespace-nowrap">Pred. Close</th>
                  <th className="px-3 py-2 text-left text-zinc-500 font-medium whitespace-nowrap">Actual Close</th>
                  <th className="px-3 py-2 text-left text-zinc-500 font-medium whitespace-nowrap">
                    <span className="flex items-center gap-1">
                      Error %
                      <InfoTip text="(Predicted − Actual) / Actual × 100. Green &lt;1%, yellow &lt;3%, red ≥3%." />
                    </span>
                  </th>
                  <th className="px-3 py-2 text-left text-zinc-500 font-medium whitespace-nowrap">
                    <span className="flex items-center gap-1">
                      Dir.
                      <InfoTip text="Correct direction prediction (✓) or wrong (✗)." />
                    </span>
                  </th>
                  <th className="px-3 py-2 text-left text-zinc-500 font-medium whitespace-nowrap">
                    <span className="flex items-center gap-1">
                      Band 80%
                      <InfoTip text="Q10–Q90 confidence interval. ✓ = actual close fell inside the band." />
                    </span>
                  </th>
                  <th className="px-3 py-2 text-left text-zinc-500 font-medium whitespace-nowrap">
                    <span className="flex items-center gap-1">
                      Ganho %
                      <InfoTip text="Trade return as % of position. Positive on a winning trade regardless of direction (LONG profits from rising prices, SHORT from falling)." />
                    </span>
                  </th>
                  {hasPnl && (
                    <th className="px-3 py-2 text-left text-zinc-500 font-medium whitespace-nowrap">
                      <span className="flex items-center gap-1">
                        Result. $
                        <InfoTip text="Dollar P&L based on initial capital × position size. Shown only when portfolio parameters were set." />
                      </span>
                    </th>
                  )}
                </tr>
              </thead>
              <tbody>
                {trades.map((t) => (
                  <TradeRow key={`${t.id}-${t.target_open_time}`} t={t} />
                ))}
              </tbody>
            </table>
          </div>
        )}
      </CardContent>
    </Card>
  );
}
