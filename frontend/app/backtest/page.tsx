"use client";

import { Suspense, useState, useEffect, useRef } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { Play, Square, Database, BarChart3, Clock, CheckCircle2, XCircle, AlertCircle, TrendingUp, TrendingDown } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { InfoTip } from "@/components/ui/tooltip";
import { TimeframeToggle } from "@/components/ui/timeframe-toggle";
import { useTimeframe, type AppTimeframe } from "@/lib/hooks/use-timeframe";
import {
  useKronosBacktest,
  useKronosBacktestDataInfo,
  useKronosBacktestProgress,
  useKronosTriggerBacktest,
  useKronosStopBacktest,
} from "@/lib/hooks/use-kronos";
import { BacktestTradesCard } from "@/components/kronos/backtest-trades-card";
import type { KronosBacktest, KronosBacktestDataInfoItem } from "@/lib/api/schemas";

// ── helpers ───────────────────────────────────────────────────────────────────

function fmtDate(iso: string | null | undefined) {
  if (!iso) return "—";
  return new Date(iso).toLocaleDateString("en-US", { year: "numeric", month: "short", day: "numeric" });
}

function fmtDuration(secs: number | null | undefined) {
  if (secs == null) return "—";
  if (secs < 60) return `${secs}s`;
  const m = Math.floor(secs / 60);
  const s = secs % 60;
  return s > 0 ? `${m}m ${s}s` : `${m}m`;
}

function fmtEta(secs: number | null | undefined) {
  if (secs == null) return null;
  if (secs < 60) return `~${secs}s`;
  return `~${Math.ceil(secs / 60)}m`;
}

function pct(v: number | null | undefined, decimals = 1) {
  if (v == null) return "—";
  return `${v.toFixed(decimals)}%`;
}

function fmtUSD(v: number | null | undefined) {
  if (v == null) return "—";
  return new Intl.NumberFormat("en-US", { style: "currency", currency: "USD", maximumFractionDigits: 2 }).format(v);
}

function fmtSigned(v: number | null | undefined, decimals = 2, suffix = "%") {
  if (v == null) return "—";
  const sign = v > 0 ? "+" : "";
  return `${sign}${v.toFixed(decimals)}${suffix}`;
}

// ── Sub-components ────────────────────────────────────────────────────────────

function DataInfoRow({ item }: { item: KronosBacktestDataInfoItem }) {
  const coverage =
    item.first_open_time && item.last_open_time
      ? `${fmtDate(item.first_open_time)} → ${fmtDate(item.last_open_time)}`
      : "No data";

  return (
    <div className="grid grid-cols-[60px_1fr_80px_80px] gap-2 items-center py-2 border-b border-zinc-800/60 last:border-0">
      <span className="text-xs font-mono font-semibold text-cyan-400">{item.timeframe.toUpperCase()}</span>
      <span className="text-xs text-zinc-400 truncate">{coverage}</span>
      <span className="text-xs font-mono text-zinc-300 text-right">
        {item.total_klines.toLocaleString()}
      </span>
      <span className="text-xs font-mono text-zinc-300 text-right">
        {item.actual_sample_size.toLocaleString()}
        {item.expected_sample_size != null && item.actual_sample_size < item.expected_sample_size && (
          <span className="text-yellow-500 ml-1">↓</span>
        )}
      </span>
    </div>
  );
}

function DataInfoCard({ timeframe }: { timeframe: AppTimeframe }) {
  const { data, isLoading } = useKronosBacktestDataInfo();
  const item = data?.timeframes[timeframe];

  return (
    <Card className="bg-bp-surface border-bp-border">
      <CardHeader className="pb-1 pt-3 px-4">
        <CardTitle className="text-sm font-semibold text-zinc-200 flex items-center gap-1.5">
          <Database className="w-4 h-4 text-zinc-400" />
          Available Data · {timeframe.toUpperCase()}
          <InfoTip text="Candles available in the database and how many are eligible as backtest targets (each requires 512 prior candles for context)." />
        </CardTitle>
      </CardHeader>
      <CardContent className="px-4 pb-3">
        {isLoading ? (
          <div className="space-y-2">
            <Skeleton className="h-6 w-full" />
            <Skeleton className="h-6 w-3/4" />
          </div>
        ) : item ? (
          <div className="space-y-2 text-xs">
            <div className="flex justify-between items-center py-1.5 border-b border-zinc-800/60">
              <span className="text-zinc-500">Coverage</span>
              <span className="text-zinc-300 font-mono">
                {item.first_open_time ? fmtDate(item.first_open_time) : "—"}
                {" → "}
                {item.last_open_time ? fmtDate(item.last_open_time) : "—"}
              </span>
            </div>
            <div className="flex justify-between items-center py-1.5 border-b border-zinc-800/60">
              <span className="text-zinc-500">Total candles</span>
              <span className="text-zinc-300 font-mono">{item.total_klines.toLocaleString()}</span>
            </div>
            <div className="flex justify-between items-center py-1.5 border-b border-zinc-800/60">
              <span className="text-zinc-500 flex items-center gap-1">
                Eligible targets
                <InfoTip text="Candles that have at least 512 prior candles available as context for the model." />
              </span>
              <span className="text-zinc-300 font-mono">{item.eligible_samples.toLocaleString()}</span>
            </div>
            <div className="flex justify-between items-center py-1.5">
              <span className="text-zinc-500 flex items-center gap-1">
                Samples to test
                <InfoTip text="Random sample drawn from eligible targets. Each run uses a different random selection." />
              </span>
              <span className="text-cyan-400 font-mono font-semibold">{item.actual_sample_size.toLocaleString()}</span>
            </div>
          </div>
        ) : (
          <p className="text-xs text-zinc-500">No {timeframe.toUpperCase()} data available yet.</p>
        )}
      </CardContent>
    </Card>
  );
}

function StatusBadge({ status }: { status: string }) {
  if (status === "done") return (
    <span className="flex items-center gap-1 text-emerald-400 text-xs font-semibold">
      <CheckCircle2 className="w-3.5 h-3.5" /> Done
    </span>
  );
  if (status === "error") return (
    <span className="flex items-center gap-1 text-red-400 text-xs font-semibold">
      <XCircle className="w-3.5 h-3.5" /> Error
    </span>
  );
  if (status === "stopped_by_user") return (
    <span className="flex items-center gap-1 text-yellow-400 text-xs font-semibold">
      <AlertCircle className="w-3.5 h-3.5" /> Stopped
    </span>
  );
  return <span className="text-xs text-zinc-500 font-semibold capitalize">{status}</span>;
}

function MetricRow({ label, value, tip }: { label: string; value: string; tip?: string }) {
  return (
    <div className="flex items-center justify-between py-1.5 border-b border-zinc-800/60 last:border-0">
      <span className="text-xs text-zinc-500 flex items-center gap-1">
        {label}
        {tip && <InfoTip text={tip} />}
      </span>
      <span className="text-xs font-mono text-zinc-200">{value}</span>
    </div>
  );
}

function ResultsCard({ timeframe }: { timeframe: AppTimeframe }) {
  const { data, isLoading } = useKronosBacktest(timeframe);
  const queryClient = useQueryClient();
  const { data: progress } = useKronosBacktestProgress(timeframe);

  // Refresh results when backtest transitions from running → done
  const wasRunning = useRef(false);
  const isRunning = progress?.state === "PROGRESS" || progress?.state === "STARTED";
  useEffect(() => {
    if (wasRunning.current && !isRunning) {
      queryClient.invalidateQueries({ queryKey: ["kronos-backtest", timeframe] });
      queryClient.invalidateQueries({ queryKey: ["kronos-backtest-trades", timeframe] });
    }
    wasRunning.current = isRunning;
  }, [isRunning, timeframe, queryClient]);

  if (isLoading) {
    return (
      <Card className="bg-bp-surface border-bp-border">
        <CardContent className="px-4 py-4 space-y-2">
          {Array.from({ length: 6 }).map((_, i) => <Skeleton key={i} className="h-6 w-full" />)}
        </CardContent>
      </Card>
    );
  }

  if (!data) {
    return (
      <Card className="bg-bp-surface border-bp-border">
        <CardContent className="px-4 py-6 text-center">
          <BarChart3 className="w-8 h-8 text-zinc-700 mx-auto mb-2" />
          <p className="text-xs text-zinc-500">No backtest results yet for {timeframe.toUpperCase()}.</p>
          <p className="text-xs text-zinc-600 mt-1">Run a backtest to see results here.</p>
        </CardContent>
      </Card>
    );
  }

  const b: KronosBacktest = data;

  return (
    <Card className="bg-bp-surface border-bp-border">
      <CardHeader className="pb-1 pt-3 px-4">
        <CardTitle className="text-sm font-semibold text-zinc-200 flex items-center justify-between">
          <span className="flex items-center gap-1.5">
            <BarChart3 className="w-4 h-4 text-zinc-400" />
            Results · {timeframe.toUpperCase()}
          </span>
          <StatusBadge status={b.status} />
        </CardTitle>
      </CardHeader>
      <CardContent className="px-4 pb-3">
        <div className="mb-3 flex flex-wrap gap-x-4 gap-y-1">
          <span className="text-xs text-zinc-500">
            Run: <span className="text-zinc-300">{fmtDate(b.executed_at)}</span>
          </span>
          <span className="text-xs text-zinc-500">
            Duration: <span className="text-zinc-300">{fmtDuration(b.duration_seconds)}</span>
          </span>
          <span className="text-xs text-zinc-500">
            Model: <span className="text-zinc-300 font-mono">{b.model_variant ?? "—"}</span>
          </span>
          <span className="text-xs text-zinc-500">
            Sims/sample: <span className="text-zinc-300">{b.sample_count ?? "—"}</span>
          </span>
        </div>

        {b.sample_from && b.sample_to && (
          <div className="mb-3 text-xs text-zinc-500">
            Sampled period:{" "}
            <span className="text-zinc-300">{fmtDate(b.sample_from)} → {fmtDate(b.sample_to)}</span>
            {b.sample_size != null && (
              <span className="text-zinc-600 ml-2">({b.sample_size} candles tested)</span>
            )}
          </div>
        )}

        {/* Accuracy metrics */}
        <div>
          <p className="text-[10px] uppercase tracking-wider text-zinc-600 mb-2">Model Accuracy</p>

          {/* Plain-language directional summary */}
          {b.directional_accuracy != null && (
            <div className="mb-3 p-2.5 rounded-lg bg-zinc-900/60 space-y-1.5">
              <p className="text-xs text-zinc-300 leading-relaxed">
                Called{" "}
                <span className="font-semibold text-zinc-100">
                  {pct(b.directional_accuracy)} of directions
                </span>{" "}
                correctly.
              </p>
              {b.high_conf_accuracy != null && b.high_conf_count != null && b.sample_size != null && (
                <p className="text-xs text-zinc-300 leading-relaxed">
                  When ≥70% confident, hit{" "}
                  <span className="font-semibold text-zinc-100">
                    {pct(b.high_conf_accuracy)}
                  </span>{" "}
                  — across{" "}
                  <span className="font-semibold text-zinc-100">
                    {b.high_conf_count} of {b.sample_size}
                  </span>{" "}
                  samples.
                </p>
              )}
              {b.high_conf_count === 0 && (
                <p className="text-xs text-zinc-500 italic">
                  No samples with ≥70% confidence in this run.
                </p>
              )}
            </div>
          )}

          <MetricRow
            label="MAPE Close"
            value={pct(b.mape_close, 2)}
            tip="Mean Absolute Percentage Error on the closing price. Lower = more accurate price targets."
          />
          <MetricRow
            label="MAPE High"
            value={pct(b.mape_high, 2)}
            tip="Mean Absolute Percentage Error on the candle high."
          />
          <MetricRow
            label="MAPE Low"
            value={pct(b.mape_low, 2)}
            tip="Mean Absolute Percentage Error on the candle low."
          />
          <MetricRow
            label="Band Width Avg"
            value={pct(b.band_width_pct_avg, 2)}
            tip="Average width of the Q10–Q90 confidence band as % of close. Narrower = model is more certain."
          />
          <MetricRow
            label="Band Calibration"
            value={pct(b.band_calibration_pct)}
            tip="% of actual closes that fell inside the Q10–Q90 band. A well-calibrated model should hit ~80%."
          />
        </div>

        {/* Portfolio simulation results */}
        {b.initial_capital != null && (
          <div className="mt-3 pt-3 border-t border-zinc-800">
            <p className="text-[10px] uppercase tracking-wider text-zinc-600 mb-1">
              Portfolio Simulation
              {b.compound != null && (
                <span className="ml-2 normal-case text-zinc-600">
                  · {b.compound ? "compound" : "fixed"} sizing
                  · {pct((b.position_pct ?? 0) * 100, 0)} per trade
                  · starting {fmtUSD(b.initial_capital)}
                </span>
              )}
            </p>

            {/* P&L highlight */}
            <div className="flex items-center gap-3 mb-2 p-2 rounded-lg bg-zinc-900/60">
              <div className="flex-1 text-center">
                <div className="text-[10px] text-zinc-600 mb-0.5">Final Equity</div>
                <div className="text-sm font-mono font-bold text-zinc-100">{fmtUSD(b.final_equity)}</div>
              </div>
              <div className="flex-1 text-center border-l border-zinc-800">
                <div className="text-[10px] text-zinc-600 mb-0.5">Net Profit</div>
                <div className={`text-sm font-mono font-bold flex items-center justify-center gap-0.5 ${(b.net_profit ?? 0) >= 0 ? "text-emerald-400" : "text-red-400"}`}>
                  {(b.net_profit ?? 0) >= 0 ? <TrendingUp className="w-3 h-3" /> : <TrendingDown className="w-3 h-3" />}
                  {fmtSigned(b.net_profit_pct, 1)}
                </div>
                <div className="text-[10px] text-zinc-500 font-mono">
                  {b.net_profit != null ? `${b.net_profit >= 0 ? "+" : ""}${fmtUSD(b.net_profit)}` : "—"}
                </div>
              </div>
            </div>

            <MetricRow
              label="Profit Factor"
              value={b.profit_factor != null ? b.profit_factor.toFixed(2) : "—"}
              tip="Total gross profit ÷ total gross loss. Above 1.0 = profitable overall. Above 2.0 = strong."
            />
            <MetricRow
              label="Win Rate"
              value={pct(b.win_rate_pct)}
              tip="% of trades that closed in profit."
            />
            <MetricRow
              label="Payoff Ratio"
              value={b.payoff_ratio != null ? b.payoff_ratio.toFixed(2) : "—"}
              tip="Average winning trade ÷ average losing trade. Shows if wins are bigger than losses."
            />
            <MetricRow
              label="Max Drawdown"
              value={pct(b.max_drawdown_pct)}
              tip="Largest peak-to-trough equity drop during the test. Lower is safer."
            />
            <MetricRow
              label="Max Consec. Losses"
              value={b.max_consecutive_losses != null ? String(b.max_consecutive_losses) : "—"}
              tip="Longest losing streak. Tests emotional and capital resilience."
            />
            <MetricRow
              label="Recovery Factor"
              value={b.recovery_factor != null ? b.recovery_factor.toFixed(2) : "—"}
              tip="Net profit ÷ max drawdown in dollars. How many times does the strategy recover its worst loss?"
            />
            <MetricRow
              label="Sharpe Ratio"
              value={b.sharpe_ratio != null ? b.sharpe_ratio.toFixed(2) : "—"}
              tip="Risk-adjusted return. Average trade return ÷ standard deviation × √n. Above 1.0 is good."
            />
            <MetricRow
              label="Total Trades"
              value={b.total_trades != null ? String(b.total_trades) : "—"}
              tip="Number of trades executed in the simulation."
            />
            <MetricRow
              label="Avg Trade"
              value={pct(b.avg_trade_pct, 2)}
              tip="Average return per trade as % of position size."
            />
            <MetricRow
              label="Best Trade"
              value={pct(b.best_trade_pct, 2)}
              tip="Best single trade return."
            />
            <MetricRow
              label="Worst Trade"
              value={pct(b.worst_trade_pct, 2)}
              tip="Worst single trade return."
            />
          </div>
        )}
      </CardContent>
    </Card>
  );
}

function RunCard({ timeframe }: { timeframe: AppTimeframe }) {
  const { data: progress } = useKronosBacktestProgress(timeframe);
  const trigger = useKronosTriggerBacktest();
  const stop = useKronosStopBacktest();
  const { data: dataInfo } = useKronosBacktestDataInfo();
  const tfInfo = dataInfo?.timeframes[timeframe];

  const maxSamples = tfInfo?.actual_sample_size ?? 500;
  const [sampleSize, setSampleSize] = useState(Math.min(50, maxSamples));
  const [sampleCount, setSampleCount] = useState(10);
  const [initialCapital, setInitialCapital] = useState(10000);
  const [positionPct, setPositionPct] = useState(10);
  const [compound, setCompound] = useState(false);

  // Any non-idle state with a task_id means the task is queued or running
  const IDLE_STATES = ["idle", "SUCCESS", "FAILURE", "REVOKED"];
  const isRunning = !!progress?.task_id && !IDLE_STATES.includes(progress?.state ?? "idle");
  const isPending = isRunning && progress?.state === "PENDING";

  const current = progress?.current ?? 0;
  const total = progress?.total ?? sampleSize;
  const progressPct = total > 0 ? Math.round((current / total) * 100) : 0;
  const eta = fmtEta(progress?.eta_seconds);

  const simCurrent = progress?.sim_current ?? 0;
  const simTotal = progress?.sim_total ?? 0;
  const simPct = simTotal > 0 ? Math.round((simCurrent / simTotal) * 100) : 0;

  const isLoading = isRunning && (progress?.step === "loading model" || progress?.step === "loading samples" || isPending);
  const isBacktesting = isRunning && progress?.step === "backtest";

  return (
    <Card className="bg-bp-surface border-bp-border">
      <CardHeader className="pb-1 pt-3 px-4">
        <CardTitle className="text-sm font-semibold text-zinc-200 flex items-center gap-1.5">
          <Clock className="w-4 h-4 text-zinc-400" />
          Run Backtest · {timeframe.toUpperCase()}
        </CardTitle>
      </CardHeader>
      <CardContent className="px-4 pb-4 space-y-4">
        {/* Editable parameters */}
        <div className="space-y-3">
          <div>
            <label className="flex items-center gap-1 text-xs text-zinc-500 mb-1">
              Samples to test
              <InfoTip text="How many historical candles to evaluate. More samples = more reliable metrics, but takes longer." />
            </label>
            <div className="flex items-center gap-2">
              <input
                type="number"
                min={10}
                max={maxSamples}
                value={sampleSize}
                onChange={(e) => setSampleSize(Math.min(maxSamples, Math.max(10, Number(e.target.value))))}
                disabled={isRunning}
                className="w-full bg-zinc-900 border border-zinc-700 rounded-lg px-3 py-1.5 text-sm font-mono text-zinc-100 focus:outline-none focus:border-cyan-500/60 disabled:opacity-50"
              />
              <span className="text-xs text-zinc-600 whitespace-nowrap">max {maxSamples.toLocaleString()}</span>
            </div>
          </div>

          <div>
            <label className="flex items-center gap-1 text-xs text-zinc-500 mb-1">
              Simulations per sample
              <InfoTip text="How many stochastic runs per candle. More simulations = better confidence bands, but slower." />
            </label>
            <div className="flex items-center gap-2">
              <input
                type="number"
                min={1}
                max={100}
                value={sampleCount}
                onChange={(e) => setSampleCount(Math.min(100, Math.max(1, Number(e.target.value))))}
                disabled={isRunning}
                className="w-full bg-zinc-900 border border-zinc-700 rounded-lg px-3 py-1.5 text-sm font-mono text-zinc-100 focus:outline-none focus:border-cyan-500/60 disabled:opacity-50"
              />
            </div>
          </div>

          <div className="flex items-center justify-between text-xs text-zinc-600 pt-1 border-t border-zinc-800">
            <span>Context per sample</span>
            <span className="font-mono">512 candles (fixed)</span>
          </div>
        </div>

        {/* Portfolio parameters */}
        <div className="space-y-3 pt-2 border-t border-zinc-800">
          <p className="text-[10px] uppercase tracking-wider text-zinc-600">Portfolio Simulation</p>

          <div>
            <label className="flex items-center gap-1 text-xs text-zinc-500 mb-1">
              Initial capital (USD)
              <InfoTip text="Starting capital for the simulated portfolio." />
            </label>
            <input
              type="number"
              min={100}
              step={1000}
              value={initialCapital}
              onChange={(e) => setInitialCapital(Math.max(100, Number(e.target.value)))}
              disabled={isRunning}
              className="w-full bg-zinc-900 border border-zinc-700 rounded-lg px-3 py-1.5 text-sm font-mono text-zinc-100 focus:outline-none focus:border-cyan-500/60 disabled:opacity-50"
            />
          </div>

          <div>
            <label className="flex items-center gap-1 text-xs text-zinc-500 mb-1">
              Position size (% of capital)
              <InfoTip text="How much of the capital to risk on each trade. 10% means each trade uses $1,000 of a $10,000 portfolio." />
            </label>
            <div className="flex items-center gap-2">
              <input
                type="number"
                min={1}
                max={100}
                value={positionPct}
                onChange={(e) => setPositionPct(Math.min(100, Math.max(1, Number(e.target.value))))}
                disabled={isRunning}
                className="w-full bg-zinc-900 border border-zinc-700 rounded-lg px-3 py-1.5 text-sm font-mono text-zinc-100 focus:outline-none focus:border-cyan-500/60 disabled:opacity-50"
              />
              <span className="text-xs text-zinc-600">%</span>
            </div>
          </div>

          <div className="flex items-center justify-between">
            <label className="flex items-center gap-1 text-xs text-zinc-500">
              Compound returns
              <InfoTip text="On: each trade uses % of current equity (profits reinvested). Off: each trade always uses % of the starting capital." />
            </label>
            <button
              type="button"
              role="switch"
              aria-checked={compound}
              disabled={isRunning}
              onClick={() => setCompound((v) => !v)}
              className={`relative inline-flex h-5 w-9 items-center rounded-full transition-colors focus:outline-none disabled:opacity-50 ${compound ? "bg-cyan-600" : "bg-zinc-700"}`}
            >
              <span
                className={`inline-block h-3.5 w-3.5 transform rounded-full bg-white transition-transform ${compound ? "translate-x-4" : "translate-x-1"}`}
              />
            </button>
          </div>
          <p className="text-[10px] text-zinc-600">
            {compound
              ? "Compound: position size grows as equity grows."
              : "Fixed: always trade a fixed % of starting capital."}
          </p>
        </div>

        {isRunning ? (
          <div className="space-y-3">
            {/* Sample progress bar (cyan) */}
            <div className="space-y-1">
              <div className="flex items-center justify-between text-xs">
                <span className="text-zinc-400">
                  {isLoading ? (progress?.step ?? "loading…") : "samples"}
                  {isBacktesting && (
                    <>
                      {" — "}
                      <span className="font-mono text-zinc-300">{current}</span>
                      <span className="text-zinc-600"> / </span>
                      <span className="font-mono text-zinc-300">{total}</span>
                    </>
                  )}
                </span>
                <span className="text-zinc-500 text-[10px]">
                  {isBacktesting && eta && `${eta} remaining`}
                </span>
              </div>
              <div className="relative w-full h-2 bg-zinc-800 rounded-full overflow-hidden">
                {isLoading ? (
                  <div className="absolute inset-y-0 w-2/5 rounded-full bg-cyan-600 animate-indeterminate" />
                ) : (
                  <div
                    className="h-full rounded-full bg-cyan-500 transition-all duration-500"
                    style={{ width: `${progressPct}%` }}
                  />
                )}
              </div>
              <p className="text-[10px] text-zinc-600 text-center">
                {isLoading
                  ? "loading model into memory…"
                  : `${progressPct}% of samples done`}
              </p>
            </div>

            {/* Per-sample simulations bar (green) */}
            {isBacktesting && (
              <div className="space-y-1">
                <div className="flex items-center justify-between text-xs">
                  <span className="text-zinc-400">
                    simulations
                    {simTotal > 0 && (
                      <>
                        {" — "}
                        <span className="font-mono text-zinc-300">{simCurrent}</span>
                        <span className="text-zinc-600"> / </span>
                        <span className="font-mono text-zinc-300">{simTotal}</span>
                      </>
                    )}
                  </span>
                  <span className="text-[10px] text-zinc-500">
                    {simTotal > 0 ? `${simPct}% · this sample` : "waiting…"}
                  </span>
                </div>
                <div className="w-full h-1.5 bg-zinc-800 rounded-full overflow-hidden">
                  <div
                    className={`h-full rounded-full bg-emerald-500 ${simPct > 0 ? "transition-all duration-200" : ""}`}
                    style={{ width: `${simPct}%` }}
                  />
                </div>
              </div>
            )}

            <Button
              size="sm"
              variant="danger"
              className="w-full"
              onClick={() => stop.mutate(timeframe)}
              disabled={stop.isPending}
            >
              <Square className="w-3.5 h-3.5 mr-2" />
              Stop
            </Button>
          </div>
        ) : (
          <Button
            size="sm"
            className="w-full bg-cyan-600 hover:bg-cyan-500 text-black font-semibold"
            onClick={() => trigger.mutate({ timeframe, sampleSize, sampleCount, initialCapital, positionPct: positionPct / 100, compound })}
            disabled={trigger.isPending || isRunning}
          >
            <Play className="w-3.5 h-3.5 mr-2" />
            Run Backtest
          </Button>
        )}

        <p className="text-[10px] text-zinc-600 leading-relaxed">
          Each sample uses 512 prior candles as context. The model generates stochastic simulations per target and we compare the median to the actual outcome. Portfolio simulation runs long when bullish (prob ≥ 50%) and short otherwise.
        </p>
      </CardContent>
    </Card>
  );
}

// ── Inner content (uses useTimeframe → needs Suspense) ────────────────────────

function BacktestContent() {
  const [timeframe] = useTimeframe();

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-1 lg:grid-cols-[1fr_320px] gap-4">
        {/* Left: data info + results */}
        <div className="space-y-4">
          <DataInfoCard timeframe={timeframe} />
          <ResultsCard timeframe={timeframe} />
        </div>

        {/* Right: run card — key forces remount (resets inputs) on TF change */}
        <RunCard key={timeframe} timeframe={timeframe} />
      </div>

      <BacktestTradesCard timeframe={timeframe} />
    </div>
  );
}

// ── Page ──────────────────────────────────────────────────────────────────────

export default function BacktestPage() {
  return (
    <div className="p-6 space-y-5 max-w-[1400px] mx-auto">
      <div className="flex items-start justify-between gap-4">
        <div>
          <h1 className="text-base font-semibold text-zinc-100">Kronos Backtest</h1>
          <p className="text-xs text-zinc-500 mt-0.5">
            Historical accuracy evaluation · random sampling · 512 candles context per sample
          </p>
        </div>
        <Suspense>
          <TimeframeToggle />
        </Suspense>
      </div>

      <Suspense>
        <BacktestContent />
      </Suspense>
    </div>
  );
}
