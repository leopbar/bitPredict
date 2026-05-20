"use client";

import { useQuery } from "@tanstack/react-query";
import { TrendingUp, TrendingDown, Minus, RefreshCw } from "lucide-react";
import { rsi2Api } from "@/lib/api/endpoints";

export function Rsi2SignalCard() {
  const { data, isLoading, error, refetch, isFetching } = useQuery({
    queryKey: ["rsi2-signal"],
    queryFn: () => rsi2Api.getSignal(),
    refetchInterval: 60_000, // refresh every minute
    staleTime: 30_000,
  });

  const side = data?.side ?? "none";

  const config = {
    long: {
      label: "LONG",
      color: "text-emerald-400",
      borderColor: "border-emerald-500/30",
      bg: "rgba(16,185,129,0.08)",
      Icon: TrendingUp,
      glow: "0 0 20px rgba(16,185,129,0.2)",
    },
    short: {
      label: "SHORT",
      color: "text-rose-400",
      borderColor: "border-rose-500/30",
      bg: "rgba(239,68,68,0.08)",
      Icon: TrendingDown,
      glow: "0 0 20px rgba(239,68,68,0.2)",
    },
    none: {
      label: "AGUARDANDO",
      color: "text-zinc-400",
      borderColor: "border-zinc-700",
      bg: "rgba(255,255,255,0.02)",
      Icon: Minus,
      glow: "none",
    },
  }[side] ?? {
    label: "—",
    color: "text-zinc-500",
    borderColor: "border-zinc-800",
    bg: "transparent",
    Icon: Minus,
    glow: "none",
  };

  const { Icon } = config;

  return (
    <div
      className={`rounded-2xl p-5 border ${config.borderColor} flex flex-col gap-4`}
      style={{ background: config.bg, boxShadow: config.glow }}
    >
      <div className="flex items-center justify-between">
        <span className="text-xs text-zinc-500 uppercase tracking-widest font-medium">
          Sinal Atual — RSI-2
        </span>
        <button
          onClick={() => refetch()}
          disabled={isFetching}
          className="text-zinc-500 hover:text-zinc-300 transition-colors disabled:opacity-40"
        >
          <RefreshCw className={`h-4 w-4 ${isFetching ? "animate-spin" : ""}`} />
        </button>
      </div>

      {isLoading ? (
        <div className="h-16 animate-pulse bg-zinc-800 rounded-xl" />
      ) : error ? (
        <p className="text-rose-400 text-sm">Erro ao carregar sinal.</p>
      ) : (
        <>
          <div className="flex items-center gap-3">
            <Icon className={`h-8 w-8 ${config.color}`} />
            <span className={`text-4xl font-bold tracking-tight ${config.color}`}>
              {config.label}
            </span>
          </div>

          {side !== "none" && (
            <div className="grid grid-cols-2 gap-3 text-sm">
              <div className="rounded-xl p-3" style={{ background: "rgba(255,255,255,0.04)" }}>
                <p className="text-zinc-500 text-xs mb-1">Entrada</p>
                <p className="font-mono font-semibold text-zinc-100">
                  ${data?.entry_price?.toLocaleString("pt-BR", { minimumFractionDigits: 2 }) ?? "—"}
                </p>
              </div>
              <div className="rounded-xl p-3" style={{ background: "rgba(255,255,255,0.04)" }}>
                <p className="text-zinc-500 text-xs mb-1">Stop</p>
                <p className="font-mono font-semibold text-rose-400">
                  ${data?.stop_price?.toLocaleString("pt-BR", { minimumFractionDigits: 2 }) ?? "—"}
                </p>
              </div>
              <div className="rounded-xl p-3" style={{ background: "rgba(255,255,255,0.04)" }}>
                <p className="text-zinc-500 text-xs mb-1">RSI(2) prev</p>
                <p className="font-mono font-semibold text-zinc-100">
                  {data?.rsi2_value?.toFixed(2) ?? "—"}
                </p>
              </div>
              {data?.meta_proba != null && (
                <div className="rounded-xl p-3" style={{ background: "rgba(255,255,255,0.04)" }}>
                  <p className="text-zinc-500 text-xs mb-1">Prob. ML</p>
                  <p className="font-mono font-semibold text-cyan-400">
                    {(data.meta_proba * 100).toFixed(1)}%
                  </p>
                </div>
              )}
            </div>
          )}

          <div className="text-xs text-zinc-500 border-t border-zinc-800 pt-3">
            <p className="truncate">{data?.reason ?? "Sem dados"}</p>
            <p className="mt-1">
              {data?.signal_time
                ? new Date(data.signal_time).toLocaleString("pt-BR", { timeZone: "America/Sao_Paulo" })
                : "—"}
              {" · "}
              <span className="text-cyan-500">{data?.params_version ?? "—"}</span>
            </p>
          </div>
        </>
      )}
    </div>
  );
}
