"""Feature pipeline: orchestrates all feature modules into a single DataFrame."""

from __future__ import annotations

import logging
from pathlib import Path

import polars as pl

from bitpredict.features.calendar import add_calendar
from bitpredict.features.lags import add_all_lags
from bitpredict.features.returns import add_all_returns
from bitpredict.features.target import TARGET_COL, add_target
from bitpredict.features.technical import add_all_technical

logger = logging.getLogger(__name__)

_RAW_PARQUET = Path("/app/data/raw/btcusdt_1h.parquet")
_FEATURES_DIR = Path("/app/data/features")
_FEATURES_PARQUET = _FEATURES_DIR / "btcusdt_1h_features.parquet"

# Columns from raw klines kept as context (not model features)
_CONTEXT_COLS = ["open_time", "open", "high", "low", "close", "volume"]

# Feature categories for describe/display
FEATURE_CATEGORIES: dict[str, str] = {}


def _register_categories(df: pl.DataFrame) -> None:
    """Populate FEATURE_CATEGORIES from DataFrame columns."""
    FEATURE_CATEGORIES.clear()
    for col in df.columns:
        if col in (*_CONTEXT_COLS, TARGET_COL):
            continue
        if col.startswith(("rsi_", "macd", "sma_", "ema_", "bb_", "atr_", "obv")):
            FEATURE_CATEGORIES[col] = "Technical"
        elif col.startswith(("log_return", "realized_vol", "drawdown_")):
            FEATURE_CATEGORIES[col] = "Returns"
        elif col.startswith("lag_"):
            FEATURE_CATEGORIES[col] = "Lags"
        elif col in (
            "hour", "day_of_week", "day_of_month", "month", "is_weekend",
            "hour_sin", "hour_cos", "doy_sin", "doy_cos",
        ):
            FEATURE_CATEGORIES[col] = "Calendar"
        else:
            FEATURE_CATEGORIES[col] = "Other"


def build_feature_set(df: pl.DataFrame) -> pl.DataFrame:
    """Apply all feature modules and return the cleaned DataFrame.

    Steps:
    1. Sort by open_time (ensures lag/rolling windows are correct).
    2. Add technical indicators.
    3. Add return/volatility features.
    4. Add lag features.
    5. Add calendar features.
    6. Add target (close[t+24]).
    7. Drop rows with any null in feature columns (warm-up period).
       Rows with null target (last 24 hours) are also dropped.

    Returns:
        DataFrame with all feature columns + target, no nulls.
    """
    df = df.sort("open_time")
    df = add_all_technical(df)
    df = add_all_returns(df)
    df = add_all_lags(df)
    df = add_calendar(df)
    df = add_target(df)

    rows_before = len(df)
    df = df.drop_nulls()
    rows_after = len(df)

    logger.info(
        "Feature pipeline: %d → %d rows (dropped %d warm-up/tail rows)",
        rows_before,
        rows_after,
        rows_before - rows_after,
    )

    _register_categories(df)
    return df


def load_raw_parquet(path: Path = _RAW_PARQUET) -> pl.DataFrame:
    """Load the Stage 2 raw klines Parquet."""
    if not path.exists():
        raise FileNotFoundError(
            f"Raw klines not found at {path}. Run 'bitpredict download' first."
        )
    return pl.read_parquet(path)


def save_features(df: pl.DataFrame, path: Path = _FEATURES_PARQUET) -> Path:
    """Persist the feature DataFrame to Parquet."""
    path.parent.mkdir(parents=True, exist_ok=True)
    df.write_parquet(path)
    return path


def load_features(path: Path = _FEATURES_PARQUET) -> pl.DataFrame:
    """Load the persisted feature DataFrame."""
    if not path.exists():
        raise FileNotFoundError(
            f"Features not found at {path}. Run 'bitpredict features build' first."
        )
    df = pl.read_parquet(path)
    _register_categories(df)
    return df


def feature_columns(df: pl.DataFrame) -> list[str]:
    """Return only the model feature columns (excludes context and target)."""
    exclude = {*_CONTEXT_COLS, TARGET_COL}
    return [c for c in df.columns if c not in exclude]
