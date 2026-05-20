"use client";

import { useQuery } from "@tanstack/react-query";
import { rsi2Api } from "@/lib/api/endpoints";

function fmt(dt: string | null) {
  if (!dt) return "—";
  return new Date(dt).toLocaleDateString("pt-BR", {
    year: "numeric",
    month: "short",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    timeZone: "UTC",
  }) + " UTC";
}

function fmtNumber(n: number) {
  return n.toLocaleString("pt-BR");
}

export function Rsi2DataInfo() {
  const { data: info, isLoading, error, refetch } = useQuery({
    queryKey: ["rsi2-data-info"],
    queryFn: () => rsi2Api.getDataInfo(),
    staleTime: 60_000,
    retry: 1,
  });

  if (isLoading) {
    return <div className="h-20 animate-pulse rounded-xl bg-zinc-800/40" />;
  }

  if (error || !info) {
    return (
      <div className="rounded-xl border border-zinc-800 p-3 text-xs text-zinc-500">
        Erro ao carregar informações dos dados.{" "}
        <button onClick={() => refetch()} className="underline hover:text-zinc-300">
          Tentar novamente
        </button>
      </div>
    );
  }

  if (!info.parquet_exists || info.total_rows === 0) {
    return (
      <div className="rounded-xl border border-amber-800/40 bg-amber-950/20 p-3 text-xs text-amber-400">
        Parquet 15min não encontrado. Execute a <strong>Ingestão de Dados</strong> abaixo.
      </div>
    );
  }

  const hasGaps = info.gap_count > 0;

  return (
    <div className="rounded-xl border border-zinc-800 p-4" style={{ background: "#111114" }}>
      <div className="flex items-center justify-between mb-3">
        <h3 className="text-xs font-semibold text-zinc-400 uppercase tracking-widest">
          Dataset 15min (BTCUSDT)
        </h3>
        <span
          className={`text-xs font-semibold px-2 py-0.5 rounded-full ${
            hasGaps
              ? "bg-amber-500/10 text-amber-400 border border-amber-500/20"
              : "bg-emerald-500/10 text-emerald-400 border border-emerald-500/20"
          }`}
        >
          {hasGaps ? `⚠ ${info.gap_count} gaps` : "✓ Sem gaps"}
        </span>
      </div>

      <div className="grid grid-cols-2 gap-x-6 gap-y-2 sm:grid-cols-4">
        <div>
          <p className="text-xs text-zinc-600">Total de candles</p>
          <p className="text-sm font-mono font-semibold text-zinc-200">
            {fmtNumber(info.total_rows)}
          </p>
        </div>
        <div>
          <p className="text-xs text-zinc-600">Primeiro candle</p>
          <p className="text-xs font-mono text-zinc-300">{fmt(info.first_open_time)}</p>
        </div>
        <div>
          <p className="text-xs text-zinc-600">Último candle</p>
          <p className="text-xs font-mono text-zinc-300">{fmt(info.last_open_time)}</p>
        </div>
        <div>
          <p className="text-xs text-zinc-600">Candles faltando</p>
          <p className={`text-sm font-mono font-semibold ${hasGaps ? "text-amber-400" : "text-zinc-500"}`}>
            {hasGaps ? fmtNumber(info.missing_candles) : "0"}
          </p>
        </div>
      </div>
    </div>
  );
}
