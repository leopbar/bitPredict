"use client";

import { useQuery } from "@tanstack/react-query";
import { rsi2Api } from "@/lib/api/endpoints";

export function Rsi2EquityCurve() {
  const { data: metrics, isLoading } = useQuery({
    queryKey: ["rsi2-metrics"],
    queryFn: () => rsi2Api.getMetrics(),
    staleTime: 10 * 60_000,
  });

  if (isLoading) {
    return <div className="h-32 animate-pulse rounded-xl bg-zinc-800/50" />;
  }

  // Cast sealed_report to a typed shape (values come back as unknown from the API schema)
  type SealedReport = {
    n_trades?: number;
    win_rate?: number;
    profit_factor?: number;
    calmar_ratio?: number;
    sharpe_ratio?: number;
    total_return_pct?: number;
    max_drawdown_pct?: number;
    mc_max_dd_p95_pct?: number;
    pct_target?: number;
    pct_stop?: number;
    period_start?: string;
    period_end?: string;
  };
  const sealed = metrics?.sealed_report as SealedReport | null | undefined;

  if (!sealed || !metrics?.exists) {
    return (
      <div className="rounded-xl p-4 border border-zinc-800 text-center">
        <p className="text-zinc-500 text-sm">
          Backtesting não disponível ainda.
          <br />
          <span className="text-xs text-zinc-600">
            Use o painel de gerenciamento abaixo para executar as etapas.
          </span>
        </p>
      </div>
    );
  }

  const statRows = [
    { label: "Trades", value: `${sealed.n_trades ?? "—"}` },
    { label: "Win Rate", value: sealed.win_rate != null ? `${(sealed.win_rate * 100).toFixed(1)}%` : "—" },
    { label: "Profit Factor", value: sealed.profit_factor != null ? sealed.profit_factor.toFixed(2) : "—" },
    { label: "Calmar", value: sealed.calmar_ratio != null ? sealed.calmar_ratio.toFixed(3) : "—" },
    { label: "Sharpe", value: sealed.sharpe_ratio != null ? sealed.sharpe_ratio.toFixed(3) : "—" },
    { label: "Retorno Total", value: sealed.total_return_pct != null ? `${sealed.total_return_pct > 0 ? "+" : ""}${sealed.total_return_pct.toFixed(2)}%` : "—" },
    { label: "Max Drawdown", value: sealed.max_drawdown_pct != null ? `${sealed.max_drawdown_pct.toFixed(2)}%` : "—" },
    { label: "DD p95 (MC)", value: sealed.mc_max_dd_p95_pct != null ? `${sealed.mc_max_dd_p95_pct.toFixed(2)}%` : "—" },
    { label: "Alvo RSI", value: sealed.pct_target != null ? `${(sealed.pct_target * 100).toFixed(0)}%` : "—" },
    { label: "Stop", value: sealed.pct_stop != null ? `${(sealed.pct_stop * 100).toFixed(0)}%` : "—" },
  ];

  return (
    <div className="space-y-4">
      {/* Variant badge */}
      <div className="flex items-center gap-2">
        <span className="text-xs text-zinc-500">Variant:</span>
        <span className="text-xs font-semibold text-cyan-400 bg-cyan-500/10 border border-cyan-500/20 px-2 py-0.5 rounded-full">
          {metrics?.winner ?? "—"}
        </span>
        <span className="text-xs text-zinc-600">
          ({sealed.period_start ?? "?"} → {sealed.period_end ?? "?"})
        </span>
      </div>

      {/* Metrics grid */}
      <div className="grid grid-cols-2 gap-2 sm:grid-cols-3">
        {statRows.map(({ label, value }) => (
          <div
            key={label}
            className="rounded-xl p-3"
            style={{ background: "rgba(255,255,255,0.03)", border: "1px solid #27272a" }}
          >
            <p className="text-zinc-500 text-xs mb-1">{label}</p>
            <p className="font-mono font-semibold text-zinc-100 text-sm">{value}</p>
          </div>
        ))}
      </div>

      {/* Validation scores */}
      {metrics.score_a_validation != null && (
        <div className="rounded-xl p-3 border border-zinc-800" style={{ background: "rgba(255,255,255,0.02)" }}>
          <p className="text-zinc-500 text-xs mb-2">Scores de validação (2024)</p>
          <div className="flex gap-4">
            <div>
              <p className="text-xs text-zinc-600">Caminho A</p>
              <p className="font-mono text-sm text-cyan-400 font-semibold">
                {metrics.score_a_validation.toFixed(4)}
              </p>
            </div>
            {metrics.score_b_validation != null && (
              <div>
                <p className="text-xs text-zinc-600">Caminho A+B</p>
                <p className="font-mono text-sm text-emerald-400 font-semibold">
                  {metrics.score_b_validation.toFixed(4)}
                </p>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
