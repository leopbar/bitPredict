"use client";

import { useState, useCallback, useRef, useEffect } from "react";
import { rsi2Api } from "@/lib/api/endpoints";
import type { Rsi2JobStatus } from "@/lib/api/endpoints";

// ---------------------------------------------------------------------------
// Trials table (all Optuna trials, sortable)
// ---------------------------------------------------------------------------

type TrialRow = {
  trial: number; score: number;
  body_min_pct: number; close_pos_min: number;
  stop_type: string; stop_lookback: number | null; atr_k: number;
  timeout_bars: number | null; target_r_multiple: number;
  n_trades: number | null; win_rate: number | null;
  profit_factor: number | null; calmar: number | null; max_dd_pct: number | null;
};

type SortKey = keyof TrialRow;

function TrialsTable() {
  const [trials, setTrials] = useState<TrialRow[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [sortKey, setSortKey] = useState<SortKey>("score");
  const [sortAsc, setSortAsc] = useState(false);
  const [showAll, setShowAll] = useState(false);

  useEffect(() => {
    setLoading(true);
    rsi2Api.getTrials()
      .then((d) => { setTrials(d.trials); setTotal(d.total); })
      .catch((e) => setError(String(e)))
      .finally(() => setLoading(false));
  }, []);

  if (loading) return <p className="text-xs text-zinc-500 mt-3">Carregando trials...</p>;
  if (error) return <p className="text-xs text-red-400 mt-3">{error}</p>;
  if (!trials.length) return null;

  const sorted = [...trials].sort((a, b) => {
    const av = a[sortKey] ?? -Infinity;
    const bv = b[sortKey] ?? -Infinity;
    return sortAsc ? (av > bv ? 1 : -1) : (av < bv ? 1 : -1);
  });
  const displayed = showAll ? sorted : sorted.slice(0, 50);

  const hasMetrics = trials.some((t) => t.n_trades !== null);

  function Th({ k, label }: { k: SortKey; label: string }) {
    const active = sortKey === k;
    return (
      <th
        className="px-2 py-1.5 text-left cursor-pointer select-none whitespace-nowrap hover:text-zinc-200 transition-colors"
        onClick={() => { if (active) setSortAsc((p) => !p); else { setSortKey(k); setSortAsc(false); } }}
      >
        <span className={active ? "text-cyan-400" : "text-zinc-500"}>
          {label} {active ? (sortAsc ? "▲" : "▼") : ""}
        </span>
      </th>
    );
  }

  return (
    <div className="mt-4">
      <div className="flex items-center justify-between mb-2">
        <p className="text-[10px] font-semibold uppercase tracking-wider text-zinc-400">
          Todos os Trials — {total} tentativas
          {!hasMetrics && <span className="text-amber-500 ml-2">(win rate / DD disponíveis na próxima otimização)</span>}
        </p>
        {total > 50 && (
          <button onClick={() => setShowAll((p) => !p)} className="text-[10px] text-zinc-500 hover:text-zinc-300 underline">
            {showAll ? "Mostrar top 50" : `Ver todos (${total})`}
          </button>
        )}
      </div>
      <div className="overflow-x-auto rounded-lg border border-zinc-800">
        <table className="w-full text-[11px]">
          <thead className="bg-zinc-900 border-b border-zinc-800">
            <tr>
              <Th k="trial" label="#" />
              <Th k="score" label="Score" />
              <Th k="body_min_pct" label="Body %" />
              <Th k="stop_type" label="Stop" />
              <Th k="atr_k" label="ATR k" />
              <Th k="stop_lookback" label="Lookback" />
              <Th k="target_r_multiple" label="Alvo R" />
              <Th k="timeout_bars" label="Timeout" />
              <Th k="close_pos_min" label="ClosePos" />
              {hasMetrics && <><Th k="n_trades" label="Trades" /><Th k="win_rate" label="Win%" /><Th k="profit_factor" label="PF" /><Th k="calmar" label="Calmar" /><Th k="max_dd_pct" label="Max DD%" /></>}
            </tr>
          </thead>
          <tbody>
            {displayed.map((t, i) => (
              <tr key={t.trial} className={i % 2 === 0 ? "bg-zinc-950" : "bg-zinc-900/40"}>
                <td className="px-2 py-1 text-zinc-600 font-mono">{t.trial}</td>
                <td className="px-2 py-1 font-mono text-cyan-300 font-bold">{t.score.toFixed(4)}</td>
                <td className="px-2 py-1 font-mono text-zinc-300">{t.body_min_pct.toFixed(2)}%</td>
                <td className="px-2 py-1 font-mono text-zinc-300 uppercase">{t.stop_type}</td>
                <td className="px-2 py-1 font-mono text-zinc-300">{t.atr_k.toFixed(2)}</td>
                <td className="px-2 py-1 font-mono text-zinc-300">{t.stop_lookback ?? "—"}</td>
                <td className="px-2 py-1 font-mono text-zinc-300">{t.target_r_multiple.toFixed(2)}×</td>
                <td className="px-2 py-1 font-mono text-zinc-300">{t.timeout_bars != null ? `${t.timeout_bars}b` : "—"}</td>
                <td className="px-2 py-1 font-mono text-zinc-300">{t.close_pos_min.toFixed(2)}</td>
                {hasMetrics && (
                  <>
                    <td className="px-2 py-1 font-mono text-zinc-300">{t.n_trades ?? "—"}</td>
                    <td className={`px-2 py-1 font-mono ${(t.win_rate ?? 0) >= 0.4 ? "text-emerald-400" : "text-amber-400"}`}>{t.win_rate != null ? `${(t.win_rate * 100).toFixed(1)}%` : "—"}</td>
                    <td className="px-2 py-1 font-mono text-zinc-300">{t.profit_factor?.toFixed(2) ?? "—"}</td>
                    <td className="px-2 py-1 font-mono text-zinc-300">{t.calmar?.toFixed(2) ?? "—"}</td>
                    <td className={`px-2 py-1 font-mono ${(t.max_dd_pct ?? 0) > 20 ? "text-red-400" : "text-amber-400"}`}>{t.max_dd_pct != null ? `${t.max_dd_pct.toFixed(1)}%` : "—"}</td>
                  </>
                )}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

type JobType = "ingest" | "optimize" | "train-meta" | "select" | "sealed-test";

interface JobState {
  jobId: string | null;
  status: Rsi2JobStatus["status"] | "idle";
  progress: number;
  message: string;
  error: string | null;
  result: Record<string, unknown> | null;
}

const INITIAL_JOB: JobState = {
  jobId: null,
  status: "idle",
  progress: 0,
  message: "",
  error: null,
  result: null,
};

// ---------------------------------------------------------------------------
// Hook: single job poller with refresh-safe restore
// ---------------------------------------------------------------------------

function useJob(jobType: JobType) {
  const [job, setJob] = useState<JobState>(INITIAL_JOB);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const stopPolling = useCallback(() => {
    if (pollRef.current) {
      clearInterval(pollRef.current);
      pollRef.current = null;
    }
  }, []);

  const pollStatus = useCallback(
    async (jobId: string) => {
      try {
        const data = await rsi2Api.getJobStatus(jobId);
        setJob((prev) => ({
          ...prev,
          status: data.status,
          progress: data.progress,
          message: data.message,
        }));

        if (data.status === "done" || data.status === "failed") {
          stopPolling();
          try {
            const res = await rsi2Api.getJobResults(jobId);
            setJob((prev) => ({ ...prev, result: res.result ?? null, error: res.error ?? null }));
          } catch {}
        }
      } catch (e) {
        console.error("polling error", e);
      }
    },
    [stopPolling],
  );

  const attachPolling = useCallback(
    (jobId: string) => {
      stopPolling();
      pollRef.current = setInterval(() => pollStatus(jobId), 2000);
    },
    [stopPolling, pollStatus],
  );

  // On mount: restore state from backend for this job type
  useEffect(() => {
    let cancelled = false;
    async function restore() {
      try {
        const recent = await rsi2Api.getRecentJobs();
        if (cancelled) return;
        const entry = recent[jobType];
        if (!entry) return;

        // If result is already embedded in the recent-jobs response (disk fallback or in-memory),
        // use it directly — no need to call getJobResults.
        const entryRecord = entry as unknown as Record<string, unknown>;
        const embeddedResult = entryRecord.result as Record<string, unknown> | null | undefined;

        const restored: JobState = {
          jobId: entry.job_id,
          status: entry.status as JobState["status"],
          progress: entry.progress ?? 0,
          message: entry.message ?? "",
          error: (entryRecord.error as string | null) ?? null,
          result: embeddedResult ?? null,
        };
        setJob(restored);

        if (entry.status === "queued" || entry.status === "running") {
          attachPolling(entry.job_id);
        } else if (entry.status === "done" && !embeddedResult) {
          // Only fetch separately if the result wasn't embedded (old in-memory jobs)
          try {
            const res = await rsi2Api.getJobResults(entry.job_id);
            if (!cancelled) setJob((prev) => ({ ...prev, result: res.result ?? null }));
          } catch {}
        }
      } catch {}
    }
    restore();
    return () => { cancelled = true; };
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [jobType]);

  const start = useCallback(
    async (starter: () => Promise<{ job_id: string; status: string; message: string }>) => {
      stopPolling();
      setJob({ jobId: null, status: "queued", progress: 0, message: "Enviando job...", error: null, result: null });
      try {
        const res = await starter();
        setJob((prev) => ({ ...prev, jobId: res.job_id, message: res.message }));
        attachPolling(res.job_id);
      } catch (e: unknown) {
        const msg = e instanceof Error ? e.message : String(e);
        setJob((prev) => ({ ...prev, status: "failed", error: msg }));
      }
    },
    [stopPolling, attachPolling],
  );

  return { job, start };
}

// ---------------------------------------------------------------------------
// Sub-component: single operation card
// ---------------------------------------------------------------------------

interface OperationCardProps {
  jobType: JobType;
  title: string;
  description: string;
  buttonLabel: string;
  job: JobState;
  onStart: () => void;
  disabled?: boolean;
  destructive?: boolean;
  extraContent?: React.ReactNode;
}

function OperationCard({
  jobType,
  title,
  description,
  buttonLabel,
  job,
  onStart,
  disabled,
  destructive,
  extraContent,
}: OperationCardProps) {
  const isRunning = job.status === "queued" || job.status === "running";

  const statusColor =
    job.status === "done"
      ? "text-emerald-400"
      : job.status === "failed"
        ? "text-red-400"
        : job.status === "running" || job.status === "queued"
          ? "text-cyan-400"
          : "text-zinc-500";

  return (
    <div className="rounded-xl border border-zinc-800 p-4" style={{ background: "#111114" }}>
      <div className="flex items-start justify-between gap-4">
        <div className="flex-1 min-w-0">
          <h3 className="text-sm font-semibold text-zinc-200">{title}</h3>
          <p className="text-xs text-zinc-500 mt-0.5">{description}</p>
        </div>
        <button
          onClick={onStart}
          disabled={isRunning || disabled}
          className={[
            "shrink-0 px-3 py-1.5 rounded-lg text-xs font-semibold transition-colors",
            "disabled:opacity-40 disabled:cursor-not-allowed",
            destructive
              ? "bg-red-900/60 text-red-300 border border-red-700/50 hover:bg-red-800/60"
              : "bg-cyan-900/60 text-cyan-300 border border-cyan-700/50 hover:bg-cyan-800/60",
          ].join(" ")}
        >
          {isRunning ? "Em execução..." : buttonLabel}
        </button>
      </div>

      {/* Progress bar */}
      {(isRunning || job.status === "done" || job.status === "failed") && (
        <div className="mt-3 space-y-1.5">
          <div className="flex items-center gap-2">
            <div className="flex-1 h-2 rounded-full bg-zinc-800 overflow-hidden">
              <div
                className={[
                  "h-full rounded-full transition-all duration-300",
                  job.status === "failed" ? "bg-red-500" : job.status === "done" ? "bg-emerald-500" : "bg-cyan-500",
                ].join(" ")}
                style={{ width: `${Math.round(job.progress * 100)}%` }}
              />
            </div>
            <span className={`text-xs font-mono shrink-0 ${statusColor}`}>
              {Math.round(job.progress * 100)}%
            </span>
          </div>
          <p className={`text-xs ${statusColor}`}>{job.message}</p>
          {job.error && (
            <p className="text-xs text-red-400 bg-red-950/30 rounded px-2 py-1 mt-1 break-words">
              {job.error}
            </p>
          )}
        </div>
      )}

      {extraContent}

      {/* Result display after completion */}
      {job.status === "done" && job.result && (
        <ResultDisplay jobType={jobType} result={job.result} />
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Result renderer per job type
// ---------------------------------------------------------------------------

function ResultDisplay({ jobType, result }: { jobType: JobType; result: Record<string, unknown> }) {
  const [showTrials, setShowTrials] = useState(false);

  if (jobType === "optimize") {
    return (
      <div className="mt-3 space-y-3">
        {/* Best params summary */}
        <div className="rounded-lg bg-zinc-900/60 border border-zinc-700/50 p-3 text-xs space-y-1.5">
          <p className="text-zinc-400 font-semibold uppercase tracking-wider text-[10px] mb-2">Melhores Parâmetros (validação 2024)</p>
          <div className="grid grid-cols-2 gap-x-4 gap-y-1">
            <span className="text-zinc-500">Body mínimo do candle</span>
            <span className="text-zinc-200 font-mono">{((result.body_min_pct as number) ?? 0).toFixed(3)}%</span>
            <span className="text-zinc-500">Tipo de stop</span>
            <span className="text-zinc-200 font-mono">{String(result.stop_type ?? "—").toUpperCase()}</span>
            <span className="text-zinc-500">Multiplicador ATR</span>
            <span className="text-zinc-200 font-mono">{((result.atr_k as number) ?? 0).toFixed(2)}×</span>
            <span className="text-zinc-500">Lookback do stop (barras)</span>
            <span className="text-zinc-200 font-mono">{String(result.stop_lookback ?? "—")} barras</span>
            <span className="text-zinc-500">Alvo em R (risco/retorno)</span>
            <span className="text-zinc-200 font-mono">{((result.target_r_multiple as number) ?? 0).toFixed(2)}×</span>
            <span className="text-zinc-500">Timeout máximo</span>
            <span className="text-zinc-200 font-mono">{String(result.timeout_bars ?? "—")} barras = {((result.timeout_bars as number) ?? 0) * 15}min</span>
            <span className="text-zinc-500">Posição do fechamento mín</span>
            <span className="text-zinc-200 font-mono">{((result.close_pos_min as number) ?? 0).toFixed(3)}</span>
          </div>
        </div>
        {/* Trials table toggle */}
        <button
          onClick={() => setShowTrials((p) => !p)}
          className="text-xs text-cyan-600 hover:text-cyan-400 underline"
        >
          {showTrials ? "▲ Ocultar tabela de trials" : "▼ Ver todos os trials testados (ordenável)"}
        </button>
        {showTrials && <TrialsTable />}
      </div>
    );
  }

  if (jobType === "train-meta") {
    const r = result as Record<string, number>;
    return (
      <div className="mt-3 rounded-lg bg-zinc-900/60 border border-zinc-700/50 p-3 text-xs space-y-2">
        <p className="text-zinc-400 font-semibold uppercase tracking-wider text-[10px] mb-2">Resultado do Modelo XGBoost (Caminho B)</p>
        {r.roc_auc != null && (
          <div>
            <div className="flex justify-between">
              <span className="text-zinc-400 font-medium">Precisão do modelo (AUC)</span>
              <span className={`font-mono font-bold ${r.roc_auc >= 0.55 ? "text-emerald-400" : "text-amber-400"}`}>{r.roc_auc.toFixed(4)}</span>
            </div>
            <p className="text-zinc-600 text-[10px] mt-0.5">
              Mede o quanto o modelo consegue separar trades lucrativos de perdedores.
              0.5 = chute aleatório · 0.55+ = útil · 0.65+ = bom.
              {r.roc_auc < 0.55 ? " ⚠ Abaixo do mínimo — Caminho A provavelmente vence." : " ✓ Acima do mínimo."}
            </p>
          </div>
        )}
        {r.val_score_b != null && (
          <div>
            <div className="flex justify-between">
              <span className="text-zinc-400 font-medium">Score composto A+B (validação 2024)</span>
              <span className="text-zinc-200 font-mono">{r.val_score_b.toFixed(4)}</span>
            </div>
            <p className="text-zinc-600 text-[10px] mt-0.5">
              O mesmo score do Caminho A, mas calculado com o filtro XGBoost ativo.
              Se maior que o score A, o modelo agrega valor.
            </p>
          </div>
        )}
        {r.threshold != null && (
          <div>
            <div className="flex justify-between">
              <span className="text-zinc-400 font-medium">Threshold de confiança</span>
              <span className="text-zinc-200 font-mono">{r.threshold.toFixed(3)}</span>
            </div>
            <p className="text-zinc-600 text-[10px] mt-0.5">
              Probabilidade mínima que o modelo precisa dar para o sinal ser executado.
              Ex: 0.55 = só opera se o modelo estiver ≥55% confiante que vai lucrar.
            </p>
          </div>
        )}
      </div>
    );
  }

  if (jobType === "select") {
    const winner = result.winner as string | undefined;
    return (
      <div className="mt-3 rounded-lg bg-zinc-900/60 border border-zinc-700/50 p-3 text-xs">
        <p className="text-zinc-400 font-semibold uppercase tracking-wider text-[10px] mb-2">Winner Selecionado</p>
        <div className="flex items-center gap-2">
          <span className={`px-2 py-0.5 rounded font-mono font-bold ${winner === "A" ? "bg-cyan-900/60 text-cyan-300" : "bg-purple-900/60 text-purple-300"}`}>
            Caminho {winner ?? "—"}
          </span>
          {result.val_score_a !== undefined && (
            <span className="text-zinc-500">A: {(result.val_score_a as number).toFixed(4)}</span>
          )}
          {result.val_score_b !== undefined && (
            <span className="text-zinc-500">A+B: {(result.val_score_b as number).toFixed(4)}</span>
          )}
        </div>
      </div>
    );
  }

  if (jobType === "sealed-test") {
    const r = result as Record<string, number | string>;
    return (
      <div className="mt-3 rounded-lg bg-zinc-900/60 border border-red-800/30 p-3 text-xs space-y-1">
        <p className="text-red-400 font-semibold uppercase tracking-wider text-[10px] mb-2">Teste Lacrado (2025 → hoje)</p>
        <div className="grid grid-cols-2 gap-x-4 gap-y-1">
          {r.n_trades !== undefined && <><span className="text-zinc-500">Trades</span><span className="text-zinc-200 font-mono">{r.n_trades}</span></>}
          {r.win_rate !== undefined && <><span className="text-zinc-500">Win rate</span><span className={`font-mono ${(r.win_rate as number) >= 0.4 ? "text-emerald-400" : "text-amber-400"}`}>{((r.win_rate as number) * 100).toFixed(1)}%</span></>}
          {r.equity_final !== undefined && <><span className="text-zinc-500">Equity final</span><span className={`font-mono ${(r.equity_final as number) >= 1 ? "text-emerald-400" : "text-red-400"}`}>{(r.equity_final as number).toFixed(4)}×</span></>}
          {r.calmar !== undefined && <><span className="text-zinc-500">Calmar</span><span className={`font-mono ${(r.calmar as number) >= 0 ? "text-emerald-400" : "text-red-400"}`}>{(r.calmar as number).toFixed(3)}</span></>}
          {r.max_drawdown !== undefined && <><span className="text-zinc-500">Max DD</span><span className="text-amber-400 font-mono">{((r.max_drawdown as number) * 100).toFixed(2)}%</span></>}
          {r.profit_factor !== undefined && <><span className="text-zinc-500">Profit factor</span><span className="text-zinc-200 font-mono">{(r.profit_factor as number).toFixed(3)}</span></>}
        </div>
      </div>
    );
  }

  return null;
}

// ---------------------------------------------------------------------------
// Main management panel
// ---------------------------------------------------------------------------

export function Rsi2ManagementPanel() {
  const ingest = useJob("ingest");
  const optimize = useJob("optimize");
  const [nTrials, setNTrials] = useState(500);
  const trainMeta = useJob("train-meta");
  const select = useJob("select");
  const sealedTest = useJob("sealed-test");
  const [confirmSealed, setConfirmSealed] = useState(false);

  const anyRunning =
    ["queued", "running"].includes(ingest.job.status) ||
    ["queued", "running"].includes(optimize.job.status) ||
    ["queued", "running"].includes(trainMeta.job.status) ||
    ["queued", "running"].includes(select.job.status) ||
    ["queued", "running"].includes(sealedTest.job.status);

  return (
    <div className="space-y-3">
      {/* Step 1 — Ingest */}
      <OperationCard
        jobType="ingest"
        title="1. Ingestão de Dados"
        description="Baixa/atualiza klines 15min (desde 2018) e funding rates da Binance. Retoma de onde parou."
        buttonLabel="Iniciar Ingestão"
        job={ingest.job}
        disabled={anyRunning && ingest.job.status === "idle"}
        onStart={() =>
          ingest.start(() => rsi2Api.startIngest())
        }
      />

      {/* Step 2 — Optimize */}
      <OperationCard
        jobType="optimize"
        title="2. Otimização (Caminho A)"
        description="Roda Optuna TPE no período de treino (2018–2023) e seleciona os melhores parâmetros na validação (2024)."
        buttonLabel="Otimizar"
        job={optimize.job}
        disabled={anyRunning && optimize.job.status === "idle"}
        onStart={() =>
          optimize.start(() => rsi2Api.startOptimize(nTrials))
        }
        extraContent={
          <div className="mt-2 flex items-center gap-2">
            <label className="text-xs text-zinc-500">Trials:</label>
            <input
              type="number"
              min={10}
              max={2000}
              step={10}
              value={nTrials}
              onChange={(e) => setNTrials(Number(e.target.value))}
              className="w-20 rounded bg-zinc-800 border border-zinc-700 text-xs text-zinc-200 px-2 py-0.5 focus:outline-none focus:border-cyan-600"
            />
          </div>
        }
      />

      {/* Step 3 — Train meta */}
      <OperationCard
        jobType="train-meta"
        title="3. Treinar Modelo ML (Caminho B)"
        description="Treina XGBoost meta-labeling com Purged K-Fold + embargo. Requer parâmetros otimizados (passo 2)."
        buttonLabel="Treinar ML"
        job={trainMeta.job}
        disabled={anyRunning && trainMeta.job.status === "idle"}
        onStart={() =>
          trainMeta.start(() => rsi2Api.startTrainMeta())
        }
      />

      {/* Step 4 — Select winner */}
      <OperationCard
        jobType="select"
        title="4. Selecionar Winner"
        description="Compara Caminho A vs A+B na validação. Empate → A vence (parsimônia). Salva winner.json."
        buttonLabel="Selecionar"
        job={select.job}
        disabled={anyRunning && select.job.status === "idle"}
        onStart={() =>
          select.start(() => rsi2Api.startSelect())
        }
      />

      {/* Step 5 — Sealed test */}
      <div className="rounded-xl border border-red-900/40 p-4" style={{ background: "#111114" }}>
        <div className="flex items-start justify-between gap-4">
          <div className="flex-1 min-w-0">
            <h3 className="text-sm font-semibold text-red-300">5. Teste Lacrado</h3>
            <p className="text-xs text-zinc-500 mt-0.5">
              Avalia o winner no período 2025-01-01 → hoje. Irreversível por convenção científica.
              Só execute quando os passos 1–4 estiverem concluídos.
            </p>
          </div>
          <button
            onClick={() => {
              if (!confirmSealed) {
                setConfirmSealed(true);
                setTimeout(() => setConfirmSealed(false), 5000);
              } else {
                setConfirmSealed(false);
                sealedTest.start(() => rsi2Api.startSealedTest(false));
              }
            }}
            disabled={
              (["queued", "running"].includes(sealedTest.job.status)) ||
              (anyRunning && sealedTest.job.status === "idle")
            }
            className={[
              "shrink-0 px-3 py-1.5 rounded-lg text-xs font-semibold transition-colors",
              "disabled:opacity-40 disabled:cursor-not-allowed",
              confirmSealed
                ? "bg-red-700 text-white border border-red-500 animate-pulse"
                : "bg-red-900/60 text-red-300 border border-red-700/50 hover:bg-red-800/60",
            ].join(" ")}
          >
            {["queued", "running"].includes(sealedTest.job.status)
              ? "Em execução..."
              : confirmSealed
                ? "⚠ Confirmar?"
                : "Executar Teste"}
          </button>
        </div>

        {(["queued", "running", "done", "failed"].includes(sealedTest.job.status)) && (
          <div className="mt-3 space-y-1.5">
            <div className="h-1.5 w-full rounded-full bg-zinc-800 overflow-hidden">
              <div
                className={[
                  "h-full rounded-full transition-all duration-500",
                  sealedTest.job.status === "failed" ? "bg-red-500" : "bg-red-400",
                  ["queued", "running"].includes(sealedTest.job.status) ? "animate-pulse" : "",
                ].join(" ")}
                style={{ width: `${Math.round(sealedTest.job.progress * 100)}%` }}
              />
            </div>
            <p
              className={`text-xs ${sealedTest.job.status === "failed" ? "text-red-400" : "text-emerald-400"} truncate`}
            >
              {sealedTest.job.message}
            </p>
            {sealedTest.job.error && (
              <p className="text-xs text-red-400 bg-red-950/30 rounded px-2 py-1 break-words">
                {sealedTest.job.error}
              </p>
            )}
          </div>
        )}

        {/* Result metrics */}
        {sealedTest.job.status === "done" && sealedTest.job.result && (
          <ResultDisplay jobType="sealed-test" result={sealedTest.job.result} />
        )}

        {/* Re-run with force */}
        {sealedTest.job.status === "done" && (
          <button
            onClick={() => sealedTest.start(() => rsi2Api.startSealedTest(true))}
            className="mt-2 text-xs text-zinc-600 hover:text-zinc-400 underline"
          >
            Re-executar (force)
          </button>
        )}
      </div>
    </div>
  );
}
