"use client";

import { useRouter } from "next/navigation";
import { format, parseISO } from "date-fns";
import { BarChart3, ExternalLink } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { useKronosBacktest } from "@/lib/hooks/use-kronos";

interface Props {
  timeframe: string;
}

function dirColor(v: number | null): string {
  if (v == null) return "text-zinc-400";
  if (v >= 55)   return "text-emerald-400";
  if (v >= 45)   return "text-amber-400";
  return "text-red-400";
}

function dirGlow(v: number | null): string {
  if (v == null) return "none";
  if (v >= 55)   return "0 0 22px rgba(52,211,153,0.35)";
  if (v >= 45)   return "0 0 22px rgba(251,191,36,0.35)";
  return "0 0 22px rgba(248,113,113,0.35)";
}

function pnlColor(v: number | null): string {
  if (v == null) return "text-zinc-400";
  return v >= 0 ? "text-emerald-400" : "text-red-400";
}

function winColor(v: number | null): string {
  if (v == null) return "text-zinc-400";
  return v >= 50 ? "text-emerald-400" : "text-red-400";
}

function ddColor(v: number | null): string {
  if (v == null) return "text-zinc-400";
  if (v <= 5)  return "text-zinc-300";
  if (v <= 15) return "text-amber-400";
  return "text-red-400";
}

function sharpeColor(v: number | null): string {
  if (v == null) return "text-zinc-400";
  if (v >= 1) return "text-emerald-400";
  if (v >= 0) return "text-amber-400";
  return "text-red-400";
}

function KpiCell({
  label,
  primary,
  secondary,
  colorClass,
}: {
  label: string;
  primary: string;
  secondary?: string;
  colorClass: string;
}) {
  return (
    <div className="bg-zinc-900/50 rounded-lg px-2.5 py-2">
      <p className="text-[9px] uppercase tracking-wider text-zinc-600 mb-0.5">{label}</p>
      <p className={`text-sm font-mono font-semibold leading-tight ${colorClass}`}>{primary}</p>
      {secondary && (
        <p className="text-[9px] font-mono text-zinc-600 mt-0.5">{secondary}</p>
      )}
    </div>
  );
}

export function BacktestSummaryCard({ timeframe }: Props) {
  const router = useRouter();
  const { data, isLoading } = useKronosBacktest(timeframe);

  const dirPct  = data?.directional_accuracy ?? null;
  const dirHits =
    dirPct != null && data?.sample_size != null
      ? Math.round((dirPct / 100) * data.sample_size)
      : null;

  return (
    <Card
      className="bg-bp-surface border-bp-border h-full cursor-pointer hover:border-zinc-600 transition-colors overflow-hidden"
      onClick={() => router.push("/backtest")}
    >
      <CardHeader className="pb-1 pt-3 px-4">
        <CardTitle className="text-xs font-semibold text-zinc-400 uppercase tracking-wider flex items-center gap-1.5">
          <BarChart3 className="w-3.5 h-3.5" />
          Backtest · {timeframe}
          <ExternalLink className="w-3 h-3 ml-auto text-zinc-600" />
        </CardTitle>
      </CardHeader>

      <CardContent className="px-4 pb-3 h-full flex flex-col justify-between">
        {isLoading ? (
          <div className="space-y-2">
            <Skeleton className="h-8 w-2/3 mx-auto" />
            <Skeleton className="h-3 w-1/2 mx-auto" />
            <div className="grid grid-cols-2 gap-1.5 mt-2">
              {Array.from({ length: 4 }).map((_, i) => (
                <Skeleton key={i} className="h-12 w-full" />
              ))}
            </div>
          </div>
        ) : !data ? (
          <div className="flex-1 flex flex-col items-center justify-center py-4 space-y-2">
            <BarChart3 className="w-8 h-8 text-zinc-700" />
            <p className="text-xs text-zinc-500">No backtest run yet</p>
            <p className="text-[10px] text-zinc-600">Click to run your first backtest →</p>
          </div>
        ) : (
          <>
            {/* ── Hero: Direction Accuracy ─────────────────────────────── */}
            <div className="text-center">
              <p className="text-[10px] uppercase tracking-wider text-zinc-500 mb-0.5">
                Direction Accuracy
              </p>
              <p
                className={`text-3xl font-bold font-mono leading-none ${dirColor(dirPct)}`}
                style={{ textShadow: dirGlow(dirPct) }}
              >
                {dirPct != null ? `${dirPct.toFixed(1)}%` : "—"}
              </p>
              {dirHits != null && data.sample_size != null && (
                <p className="text-[10px] text-zinc-600 font-mono mt-0.5">
                  {dirHits} / {data.sample_size} hits
                </p>
              )}
            </div>

            <div className="border-t border-bp-border/50" />

            {/* ── 2×2 KPI grid ────────────────────────────────────────── */}
            <div className="grid grid-cols-2 gap-1.5">
              <KpiCell
                label="Net P&L"
                primary={
                  data.net_profit_pct != null
                    ? `${data.net_profit_pct >= 0 ? "+" : ""}${data.net_profit_pct.toFixed(1)}%`
                    : "—"
                }
                secondary={
                  data.net_profit != null
                    ? `${data.net_profit >= 0 ? "+" : ""}$${Math.abs(data.net_profit).toLocaleString("en-US", { maximumFractionDigits: 0 })}`
                    : undefined
                }
                colorClass={pnlColor(data.net_profit_pct)}
              />
              <KpiCell
                label="Win Rate"
                primary={data.win_rate_pct != null ? `${data.win_rate_pct.toFixed(1)}%` : "—"}
                colorClass={winColor(data.win_rate_pct)}
              />
              <KpiCell
                label="Max DD"
                primary={
                  data.max_drawdown_pct != null
                    ? `-${data.max_drawdown_pct.toFixed(1)}%`
                    : "—"
                }
                colorClass={ddColor(data.max_drawdown_pct)}
              />
              <KpiCell
                label="Sharpe"
                primary={data.sharpe_ratio != null ? data.sharpe_ratio.toFixed(2) : "—"}
                colorClass={sharpeColor(data.sharpe_ratio)}
              />
            </div>

            <div className="border-t border-bp-border/50" />

            {/* ── Footer: metadata ────────────────────────────────────── */}
            <div className="flex items-center justify-between text-[10px] text-zinc-600">
              <span>{data.sample_size != null ? `${data.sample_size} trades` : "—"}</span>
              <span>
                {data.executed_at
                  ? format(parseISO(data.executed_at), "MMM d, HH:mm")
                  : "—"}
              </span>
            </div>
          </>
        )}
      </CardContent>
    </Card>
  );
}
