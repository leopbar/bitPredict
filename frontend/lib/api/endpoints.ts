import { apiClient } from "./client";
import type {
  HealthStatus,
  ReadinessStatus,
  ParameterResponse,
  KlineRangeResponse,
  EnsureKlinesResponse,
  KronosPrediction,
  KronosHistory,
  KronosProgress,
  KronosHealth,
  TriggerResponse,
  StopResponse,
  KronosScoreboard,
  KronosSimsResponse,
  KronosLiveCandle,
  KronosBacktest,
  KronosBacktestDataInfo,
  KronosBacktestProgress,
  KronosBacktestTrade,
} from "./schemas";

// ---------------------------------------------------------------------------
// Health
// ---------------------------------------------------------------------------

export const healthApi = {
  getHealth: () => apiClient.get<HealthStatus>("/health", false),
  getReady: () => apiClient.get<ReadinessStatus>("/ready", false),
};

// ---------------------------------------------------------------------------
// Parameters
// ---------------------------------------------------------------------------

export const parametersApi = {
  getAll: () => apiClient.get<ParameterResponse[]>("/parameters"),
  getByKey: (key: string) => apiClient.get<ParameterResponse>(`/parameters/${key}`),
  update: (key: string, value: unknown, updatedBy = "dashboard") =>
    apiClient.put<ParameterResponse>(`/parameters/${key}`, { value, updated_by: updatedBy }),
  bulkUpdate: (parameters: Record<string, unknown>, updatedBy = "dashboard") =>
    apiClient.put<ParameterResponse[]>("/parameters", { parameters, updated_by: updatedBy }),
};

// ---------------------------------------------------------------------------
// Klines
// ---------------------------------------------------------------------------

export interface KlinesParams {
  symbol?: string;
  interval?: string;
  start?: string;
  end?: string;
  limit?: number;
}

export const dataApi = {
  getKlines: (params: KlinesParams = {}) => {
    const qs = new URLSearchParams();
    if (params.symbol) qs.set("symbol", params.symbol);
    if (params.interval) qs.set("interval", params.interval);
    if (params.start) qs.set("start", params.start);
    if (params.end) qs.set("end", params.end);
    if (params.limit) qs.set("limit", String(params.limit));
    const query = qs.toString();
    return apiClient.get<KlineRangeResponse>(`/klines${query ? `?${query}` : ""}`);
  },

  getDailyKlines: (params: Omit<KlinesParams, "interval"> = {}) => {
    const qs = new URLSearchParams();
    if (params.symbol) qs.set("symbol", params.symbol);
    if (params.start) qs.set("start", params.start);
    if (params.end) qs.set("end", params.end);
    if (params.limit) qs.set("limit", String(params.limit));
    const query = qs.toString();
    return apiClient.get<KlineRangeResponse>(`/klines/daily${query ? `?${query}` : ""}`);
  },

  ensureKlines: (timeframe: string) =>
    apiClient.post<EnsureKlinesResponse>(`/klines/ensure/${timeframe}`, {}),

  checkKlines: (timeframe: string) =>
    apiClient.get<EnsureKlinesResponse>(`/klines/ensure/${timeframe}`),

  syncKlines: (symbol = "BTCUSDT", interval = "1h") =>
    apiClient.post<{ status: string; task_id: string }>(
      `/klines/sync?symbol=${symbol}&interval=${interval}`,
      {},
    ),

  getKlinesInfo: (symbol = "BTCUSDT", interval = "1h") =>
    apiClient.get<{
      symbol: string;
      interval: string;
      total_rows: number;
      first_open_time: string | null;
      last_open_time: string | null;
      expected_rows: number;
      missing_rows: number;
    }>(`/klines/info?symbol=${symbol}&interval=${interval}`),

  getTicker: (symbol = "BTCUSDT") =>
    apiClient.get<{
      symbol: string;
      price: number;
      price_change_24h: number;
      price_change_pct_24h: number;
      high_24h: number;
      low_24h: number;
      volume_24h: number;
      quote_volume_24h: number;
      trades_24h: number;
      timestamp: number;
    }>(`/klines/ticker?symbol=${symbol}`),

  backfillKlines: (params: {
    symbol?: string;
    interval?: string;
    start: string;
    end?: string;
  }) => {
    const qs = new URLSearchParams();
    qs.set("symbol", params.symbol ?? "BTCUSDT");
    qs.set("interval", params.interval ?? "1h");
    qs.set("start", params.start);
    if (params.end) qs.set("end", params.end);
    return apiClient.post<{ status: string; start: string; end: string }>(
      `/klines/backfill?${qs.toString()}`,
      {},
    );
  },
};

// ---------------------------------------------------------------------------
// RSI-2 Strategy
// ---------------------------------------------------------------------------

export interface Rsi2SignalResponse {
  side: "long" | "short" | "none";
  entry_price: number | null;
  stop_price: number | null;
  rsi2_value: number | null;
  meta_proba: number | null;
  signal_time: string;
  params_version: string;
  reason: string;
}

export interface Rsi2TradeItem {
  entry_time: string;
  exit_time: string;
  side: "long" | "short";
  entry_price: number;
  exit_price: number;
  stop_price: number;
  gross_pnl_pct: number;
  net_pnl_pct: number;
  exit_reason: "target" | "stop" | "timeout";
  bars_held: number;
}

export interface Rsi2MetricsResponse {
  exists: boolean;
  winner: string | null;
  score_a_validation: number | null;
  score_b_validation: number | null;
  sealed_report: Record<string, unknown> | null;
}

export interface Rsi2JobResponse {
  job_id: string;
  job_type: string;
  status: string;
  message: string;
}

export interface Rsi2JobStatus {
  job_id: string;
  job_type: string;
  status: "queued" | "running" | "done" | "failed";
  progress: number;
  message: string;
}

export interface Rsi2JobResult {
  job_id: string;
  job_type: string;
  status: string;
  result: Record<string, unknown> | null;
  error: string | null;
}

export interface Kline15mItem {
  open_time: string;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
}

export interface Kline15mInfo {
  total_rows: number;
  first_open_time: string | null;
  last_open_time: string | null;
  symbol: string;
  interval: string;
  parquet_exists: boolean;
  gap_count: number;
  missing_candles: number;
}

// ---------------------------------------------------------------------------
// Kronos
// ---------------------------------------------------------------------------

export const kronosApi = {
  getPrediction: (timeframe: string) =>
    apiClient.get<KronosPrediction>(`/kronos/prediction/${timeframe}`),

  getHistory: (timeframe: string, limit = 50, offset = 0) =>
    apiClient.get<KronosHistory>(
      `/kronos/history/${timeframe}?limit=${limit}&offset=${offset}`,
    ),

  getProgress: (timeframe: string) =>
    apiClient.get<KronosProgress>(`/kronos/progress/${timeframe}`),

  getHealth: () => apiClient.get<KronosHealth>("/kronos/health"),

  triggerPrediction: (timeframe: string) =>
    apiClient.post<TriggerResponse>(`/kronos/prediction/${timeframe}/trigger`, {}),

  stopPrediction: (timeframe: string) =>
    apiClient.post<StopResponse>(`/kronos/prediction/${timeframe}/stop`, {}),

  triggerBacktest: (
    timeframe: string,
    sampleSize?: number,
    sampleCount?: number,
    initialCapital?: number,
    positionPct?: number,
    compound?: boolean,
  ) =>
    apiClient.post<TriggerResponse>(`/kronos/backtest/${timeframe}/trigger`, {
      ...(sampleSize != null && { sample_size: sampleSize }),
      ...(sampleCount != null && { sample_count: sampleCount }),
      ...(initialCapital != null && { initial_capital: initialCapital }),
      ...(positionPct != null && { position_pct: positionPct }),
      ...(compound != null && { compound }),
    }),

  getScoreboard: (timeframe: string) =>
    apiClient.get<KronosScoreboard>(`/kronos/scoreboard/${timeframe}`),

  getSims: (timeframe: string) =>
    apiClient.get<KronosSimsResponse>(`/kronos/prediction/${timeframe}/sims`),

  getLiveCandle: (timeframe: string) =>
    apiClient.get<KronosLiveCandle>(`/kronos/live-candle/${timeframe}`),

  getBacktest: (timeframe: string) =>
    apiClient.get<KronosBacktest>(`/kronos/backtest/${timeframe}`),

  getBacktestDataInfo: () =>
    apiClient.get<KronosBacktestDataInfo>("/kronos/backtest/data-info"),

  getBacktestProgress: (timeframe: string) =>
    apiClient.get<KronosBacktestProgress>(`/kronos/backtest/${timeframe}/progress`),

  stopBacktest: (timeframe: string) =>
    apiClient.post<StopResponse>(`/kronos/backtest/${timeframe}/stop`, {}),

  getBacktestTrades: (timeframe: string, limit = 1000, backtestId?: number) => {
    const qs = new URLSearchParams({ limit: String(limit) });
    if (backtestId != null) qs.set("backtest_id", String(backtestId));
    return apiClient.get<KronosBacktestTrade[]>(
      `/kronos/backtest/${timeframe}/trades?${qs.toString()}`,
    );
  },
};

// ---------------------------------------------------------------------------
// RSI-2 Strategy
// ---------------------------------------------------------------------------

export const rsi2Api = {
  getSignal: () => apiClient.get<Rsi2SignalResponse>("/rsi2/signal"),
  getHistory: (limit = 50) => apiClient.get<Rsi2SignalResponse[]>(`/rsi2/history?limit=${limit}`),
  getTrades: (limit = 100) => apiClient.get<Rsi2TradeItem[]>(`/rsi2/trades?limit=${limit}`),
  getParams: () => apiClient.get<Record<string, unknown>>("/rsi2/params"),
  getMetrics: () => apiClient.get<Rsi2MetricsResponse>("/rsi2/metrics"),

  getDataInfo: (symbol = "BTCUSDT") => apiClient.get<Kline15mInfo>(`/rsi2/data/info?symbol=${symbol}`),
  getKlines15m: (params?: { symbol?: string; start?: string; end?: string; limit?: number }) => {
    const qs = new URLSearchParams();
    if (params?.symbol) qs.set("symbol", params.symbol);
    if (params?.start) qs.set("start", params.start);
    if (params?.end) qs.set("end", params.end);
    if (params?.limit) qs.set("limit", String(params.limit));
    const q = qs.toString();
    return apiClient.get<Kline15mItem[]>(`/rsi2/data/klines${q ? `?${q}` : ""}`);
  },

  startIngest: () => apiClient.post<Rsi2JobResponse>("/rsi2/jobs/ingest", {}),
  startOptimize: (n_trials = 500) => apiClient.post<Rsi2JobResponse>("/rsi2/jobs/optimize", { n_trials }),
  startTrainMeta: () => apiClient.post<Rsi2JobResponse>("/rsi2/jobs/train-meta", {}),
  startSelect: () => apiClient.post<Rsi2JobResponse>("/rsi2/jobs/select", {}),
  startSealedTest: (force = false) => apiClient.post<Rsi2JobResponse>("/rsi2/jobs/sealed-test", { force }),
  getJobStatus: (jobId: string) => apiClient.get<Rsi2JobStatus>(`/rsi2/jobs/${jobId}/status`),
  getJobResults: (jobId: string) => apiClient.get<Rsi2JobResult>(`/rsi2/jobs/${jobId}/results`),
  getActiveJobs: () => apiClient.get<{ running: boolean; jobs: Rsi2JobStatus[] }>("/rsi2/jobs/active"),
  getRecentJobs: () => apiClient.get<Record<string, Rsi2JobStatus & { job_id: string; error?: string | null; result?: Record<string, unknown> | null }>>("/rsi2/jobs/recent"),
  getTrials: () => apiClient.get<{
    total: number;
    trials: {
      trial: number;
      score: number;
      body_min_pct: number;
      close_pos_min: number;
      stop_type: string;
      stop_lookback: number | null;
      atr_k: number;
      timeout_bars: number | null;
      target_r_multiple: number;
      n_trades: number | null;
      win_rate: number | null;
      profit_factor: number | null;
      calmar: number | null;
      max_dd_pct: number | null;
    }[];
  }>("/rsi2/trials"),
};
