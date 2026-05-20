"""Prediction target: close price 24 hours in the future."""

from __future__ import annotations

import polars as pl

TARGET_COL = "target_close_24h"
HORIZON_HOURS = 24


def add_target(df: pl.DataFrame, horizon_hours: int = HORIZON_HOURS) -> pl.DataFrame:
    """Add the forecast target: close[t + horizon_hours].

    The last `horizon_hours` rows will have a null target because the future
    is not yet available. The pipeline drops these before training.
    """
    return df.with_columns(
        pl.col("close").shift(-horizon_hours).alias(TARGET_COL)
    )
