import { z } from "zod";

// ---------------------------------------------------------------------------
// Health
// ---------------------------------------------------------------------------

export const HealthStatusSchema = z.object({
  status: z.string(),
  version: z.string().default("2.0.0"),
});

export const ReadinessStatusSchema = z.object({
  ready: z.boolean(),
  checks: z.record(z.string()),
});

export type HealthStatus = z.infer<typeof HealthStatusSchema>;
export type ReadinessStatus = z.infer<typeof ReadinessStatusSchema>;

// ---------------------------------------------------------------------------
// Parameters
// ---------------------------------------------------------------------------

export const ParameterResponseSchema = z.object({
  key: z.string(),
  value: z.unknown(),
  updated_at: z.string(),
  updated_by: z.string(),
});

export type ParameterResponse = z.infer<typeof ParameterResponseSchema>;

// ---------------------------------------------------------------------------
// Klines
// ---------------------------------------------------------------------------

export const KlineResponseSchema = z.object({
  open_time: z.string(),
  open: z.number(),
  high: z.number(),
  low: z.number(),
  close: z.number(),
  volume: z.number(),
  trades: z.number(),
});

export const KlineRangeResponseSchema = z.object({
  symbol: z.string(),
  interval: z.string(),
  count: z.number(),
  items: z.array(KlineResponseSchema),
});

export type KlineResponse = z.infer<typeof KlineResponseSchema>;
export type KlineRangeResponse = z.infer<typeof KlineRangeResponseSchema>;

export const EnsureKlinesResponseSchema = z.object({
  status: z.enum(["ok", "ingesting"]),
  count: z.number(),
  is_fresh: z.boolean(),
});
export type EnsureKlinesResponse = z.infer<typeof EnsureKlinesResponseSchema>;

// ---------------------------------------------------------------------------
// Kronos
// ---------------------------------------------------------------------------

export const KronosPredictionSchema = z.object({
  id: z.number(),
  timeframe: z.string(),
  predicted_at: z.string(),
  target_candle_open_time: z.string().nullable(),
  target_candle_close_time: z.string().nullable(),
  predicted_open: z.number().nullable(),
  predicted_high: z.number().nullable(),
  predicted_low: z.number().nullable(),
  predicted_close: z.number().nullable(),
  predicted_volume: z.number().nullable(),
  q10_close: z.number().nullable(),
  q90_close: z.number().nullable(),
  prob_bullish: z.number().nullable(),
  actual_open: z.number().nullable(),
  actual_high: z.number().nullable(),
  actual_low: z.number().nullable(),
  actual_close: z.number().nullable(),
  actual_volume: z.number().nullable(),
  direction_correct: z.boolean().nullable(),
  close_error_pct: z.number().nullable(),
  model_variant: z.string().nullable(),
  sample_count: z.number().nullable(),
  temperature: z.number().nullable(),
  context_length: z.number().nullable(),
  task_id: z.string().nullable(),
  status: z.string(),
});
export type KronosPrediction = z.infer<typeof KronosPredictionSchema>;

export const KronosHistorySchema = z.object({
  items: z.array(KronosPredictionSchema),
  total: z.number(),
  limit: z.number(),
  offset: z.number(),
});
export type KronosHistory = z.infer<typeof KronosHistorySchema>;

export const KronosProgressSchema = z.object({
  timeframe: z.string(),
  task_id: z.string().nullable(),
  state: z.string(),
  step: z.string().nullable(),
  current: z.number().nullable(),
  total: z.number().nullable(),
  eta_seconds: z.number().nullable(),
});
export type KronosProgress = z.infer<typeof KronosProgressSchema>;

export const KronosTfHealthSchema = z.object({
  last_predicted_at: z.string().nullable(),
  last_status: z.string().nullable(),
  last_ingest_at: z.string().nullable(),
});
export const KronosHealthSchema = z.object({
  status: z.string(),
  timeframes: z.record(KronosTfHealthSchema),
});
export type KronosHealth = z.infer<typeof KronosHealthSchema>;

export const TriggerResponseSchema = z.object({
  task_id: z.string(),
  timeframe: z.string(),
  message: z.string(),
});
export type TriggerResponse = z.infer<typeof TriggerResponseSchema>;

export const StopResponseSchema = z.object({
  timeframe: z.string(),
  task_id: z.string().nullable(),
  message: z.string(),
});
export type StopResponse = z.infer<typeof StopResponseSchema>;

export const KronosScoreboardSchema = z.object({
  timeframe: z.string(),
  total_evaluated: z.number(),
  total_predictions: z.number(),
  directional_accuracy: z.number().nullable(),
  avg_abs_error_pct: z.number().nullable(),
  best_error_pct: z.number().nullable(),
  worst_error_pct: z.number().nullable(),
  bullish_count: z.number().nullable(),
  correct_bullish: z.number().nullable(),
  correct_bearish: z.number().nullable(),
});
export type KronosScoreboard = z.infer<typeof KronosScoreboardSchema>;

export const KronosSimSampleSchema = z.object({
  open: z.number(),
  high: z.number(),
  low: z.number(),
  close: z.number(),
  volume: z.number(),
});
export type KronosSimSample = z.infer<typeof KronosSimSampleSchema>;

export const KronosSimsResponseSchema = z.object({
  timeframe: z.string(),
  samples: z.array(KronosSimSampleSchema),
  ref_close: z.number().nullable(),
  total: z.number(),
  model_variant: z.string().nullable(),
  temperature: z.number().nullable(),
  available: z.boolean(),
});
export type KronosSimsResponse = z.infer<typeof KronosSimsResponseSchema>;

export const KronosLiveCandleSchema = z.object({
  timeframe: z.string(),
  open_time: z.string(),
  close_time: z.string(),
  open: z.number(),
  high: z.number(),
  low: z.number(),
  close: z.number(),
  volume: z.number(),
  live_price: z.number(),
  change_pct: z.number(),
  seconds_until_close: z.number(),
});
export type KronosLiveCandle = z.infer<typeof KronosLiveCandleSchema>;

export const KronosBacktestSchema = z.object({
  id: z.number(),
  timeframe: z.string(),
  executed_at: z.string(),
  sample_size: z.number().nullable(),
  model_variant: z.string().nullable(),
  sample_count: z.number().nullable(),
  context_length: z.number().nullable(),
  directional_accuracy: z.number().nullable(),
  mape_close: z.number().nullable(),
  mape_high: z.number().nullable(),
  mape_low: z.number().nullable(),
  mape_volume: z.number().nullable(),
  band_width_pct_avg: z.number().nullable(),
  band_calibration_pct: z.number().nullable(),
  high_conf_accuracy: z.number().nullable().optional(),
  high_conf_count: z.number().nullable().optional(),
  duration_seconds: z.number().nullable(),
  status: z.string(),
  task_id: z.string().nullable(),
  sample_from: z.string().nullable(),
  sample_to: z.string().nullable(),
  // portfolio params
  initial_capital: z.number().nullable(),
  position_pct: z.number().nullable(),
  compound: z.boolean().nullable(),
  // portfolio results
  final_equity: z.number().nullable(),
  net_profit: z.number().nullable(),
  net_profit_pct: z.number().nullable(),
  profit_factor: z.number().nullable(),
  win_rate_pct: z.number().nullable(),
  payoff_ratio: z.number().nullable(),
  max_drawdown_pct: z.number().nullable(),
  max_consecutive_losses: z.number().nullable(),
  recovery_factor: z.number().nullable(),
  sharpe_ratio: z.number().nullable(),
  avg_trade_pct: z.number().nullable(),
  best_trade_pct: z.number().nullable(),
  worst_trade_pct: z.number().nullable(),
  total_trades: z.number().nullable(),
});
export type KronosBacktest = z.infer<typeof KronosBacktestSchema>;

export const KronosBacktestDataInfoItemSchema = z.object({
  timeframe: z.string(),
  binance_interval: z.string(),
  total_klines: z.number(),
  first_open_time: z.string().nullable(),
  last_open_time: z.string().nullable(),
  eligible_samples: z.number(),
  expected_sample_size: z.number().nullable(),
  actual_sample_size: z.number(),
});
export type KronosBacktestDataInfoItem = z.infer<typeof KronosBacktestDataInfoItemSchema>;

export const KronosBacktestDataInfoSchema = z.object({
  timeframes: z.record(KronosBacktestDataInfoItemSchema),
});
export type KronosBacktestDataInfo = z.infer<typeof KronosBacktestDataInfoSchema>;

export const KronosBacktestTradeSchema = z.object({
  id: z.number(),
  target_open_time: z.string(),
  backtest_id: z.number(),
  timeframe: z.string(),
  predicted_close: z.number().nullable(),
  predicted_high: z.number().nullable(),
  predicted_low: z.number().nullable(),
  q10_close: z.number().nullable(),
  q90_close: z.number().nullable(),
  actual_open: z.number().nullable(),
  actual_close: z.number().nullable(),
  actual_high: z.number().nullable(),
  actual_low: z.number().nullable(),
  prob_bullish: z.number().nullable(),
  direction_correct: z.boolean().nullable(),
  close_error_pct: z.number().nullable(),
  band_covers_actual: z.boolean().nullable(),
  trade_return_pct: z.number().nullable(),
  trade_pnl_usd: z.number().nullable(),
});
export type KronosBacktestTrade = z.infer<typeof KronosBacktestTradeSchema>;

export const KronosBacktestProgressSchema = z.object({
  timeframe: z.string(),
  task_id: z.string().nullable(),
  state: z.string(),
  step: z.string().nullable(),
  current: z.number().nullable(),
  total: z.number().nullable(),
  eta_seconds: z.number().nullable(),
  sim_current: z.number().nullable().optional(),
  sim_total: z.number().nullable().optional(),
});
export type KronosBacktestProgress = z.infer<typeof KronosBacktestProgressSchema>;
