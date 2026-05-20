"use client";

import { useQuery } from "@tanstack/react-query";
import { rsi2Api } from "@/lib/api/endpoints";

function PnlBadge({ value }: { value: number }) {
  const pct = (value * 100).toFixed(3);
  const positive = value >= 0;
  return (
    <span
      className={`font-mono text-xs font-semibold ${positive ? "text-emerald-400" : "text-rose-400"}`}
    >
      {positive ? "+" : ""}
      {pct}%
    </span>
  );
}

const EXIT_LABELS: Record<string, string> = {
  target: "Alvo RSI",
  stop: "Stop",
  timeout: "Timeout",
};

export function Rsi2TradesTable() {
  const { data, isLoading, error } = useQuery({
    queryKey: ["rsi2-trades"],
    queryFn: () => rsi2Api.getTrades(100),
    staleTime: 60_000,
    refetchInterval: 5 * 60_000,
  });

  if (isLoading) {
    return (
      <div className="space-y-2">
        {[...Array(5)].map((_, i) => (
          <div key={i} className="h-10 animate-pulse rounded-lg bg-zinc-800/50" />
        ))}
      </div>
    );
  }

  if (error) return <p className="text-rose-400 text-sm">Erro ao carregar trades.</p>;
  if (!data?.length) return <p className="text-zinc-500 text-sm">Nenhum trade registrado ainda.</p>;

  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-zinc-800 text-left">
            <th className="pb-2 text-zinc-500 font-medium text-xs">Direção</th>
            <th className="pb-2 text-zinc-500 font-medium text-xs">Entrada</th>
            <th className="pb-2 text-zinc-500 font-medium text-xs">Saída</th>
            <th className="pb-2 text-zinc-500 font-medium text-xs">P&L Líq.</th>
            <th className="pb-2 text-zinc-500 font-medium text-xs">Motivo</th>
            <th className="pb-2 text-zinc-500 font-medium text-xs">Barras</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-zinc-800/50">
          {data.map((trade, i) => (
            <tr key={i} className="hover:bg-white/[0.02] transition-colors">
              <td className="py-2 pr-3">
                <span
                  className={`text-xs font-bold uppercase ${
                    trade.side === "long" ? "text-emerald-400" : "text-rose-400"
                  }`}
                >
                  {trade.side === "long" ? "▲ Long" : "▼ Short"}
                </span>
              </td>
              <td className="py-2 pr-3 font-mono text-zinc-300 text-xs">
                ${trade.entry_price.toLocaleString("pt-BR", { minimumFractionDigits: 0 })}
                <br />
                <span className="text-zinc-600">
                  {new Date(trade.entry_time).toLocaleString("pt-BR", {
                    timeZone: "America/Sao_Paulo",
                    month: "2-digit",
                    day: "2-digit",
                    hour: "2-digit",
                    minute: "2-digit",
                  })}
                </span>
              </td>
              <td className="py-2 pr-3 font-mono text-zinc-300 text-xs">
                ${trade.exit_price.toLocaleString("pt-BR", { minimumFractionDigits: 0 })}
              </td>
              <td className="py-2 pr-3">
                <PnlBadge value={trade.net_pnl_pct} />
              </td>
              <td className="py-2 pr-3">
                <span
                  className={`text-xs ${
                    trade.exit_reason === "target"
                      ? "text-emerald-400"
                      : trade.exit_reason === "stop"
                      ? "text-rose-400"
                      : "text-zinc-400"
                  }`}
                >
                  {EXIT_LABELS[trade.exit_reason] ?? trade.exit_reason}
                </span>
              </td>
              <td className="py-2 text-zinc-500 text-xs">{trade.bars_held}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
