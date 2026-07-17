"""
etl/summary.py
----------------
Aggregates matched realized-gain rows (etl.fifo_matching.match_fifo output)
into per-symbol, per-period totals — proceeds, cost basis, realized P&L,
split into short-term vs long-term gain/loss.
"""

from __future__ import annotations

import logging

import polars as pl

from core.logging_setup import traced

log = logging.getLogger(__name__)

_PERIOD_TRUNC = {"month": "1mo", "year": "1y"}

_SUMMARY_SCHEMA = {
    "Symbol": pl.Utf8,
    "PeriodType": pl.Utf8,
    "PeriodStart": pl.Date,
    "PeriodEnd": pl.Date,
    "TradeCount": pl.Int64,
    "TotalProceeds": pl.Float64,
    "TotalCostBasis": pl.Float64,
    "TotalRealizedGainLoss": pl.Float64,
    "ShortTermGainLoss": pl.Float64,
    "LongTermGainLoss": pl.Float64,
}


@traced
def summarize(realized_gains: pl.DataFrame, period: str = "month") -> pl.DataFrame:
    """
    Roll matched realized-gain rows up to Symbol x Period totals.

    Parameters
    ----------
    realized_gains : pl.DataFrame
        Output of etl.fifo_matching.match_fifo(). Rows with IsUnmatched=True
        are excluded — there's no realized gain/loss to summarize for them.
    period : {"month", "year"}
        Aggregation granularity.
    """
    if period not in _PERIOD_TRUNC:
        raise ValueError(f"period must be 'month' or 'year', got {period!r}")

    matched = realized_gains.filter(~pl.col("IsUnmatched"))
    if matched.is_empty():
        return pl.DataFrame(schema=_SUMMARY_SCHEMA)

    trunc = _PERIOD_TRUNC[period]
    period_type = period.upper()

    with_period = matched.with_columns(
        pl.col("SellDate").dt.truncate(trunc).alias("PeriodStart")
    )

    grouped = with_period.group_by("Symbol", "PeriodStart").agg(
        pl.len().cast(pl.Int64).alias("TradeCount"),
        pl.col("Proceeds").sum().alias("TotalProceeds"),
        pl.col("CostBasis").sum().alias("TotalCostBasis"),
        pl.col("RealizedGainLoss").sum().alias("TotalRealizedGainLoss"),
        pl.col("RealizedGainLoss")
        .filter(pl.col("TermType") == "SHORT")
        .sum()
        .alias("ShortTermGainLoss"),
        pl.col("RealizedGainLoss")
        .filter(pl.col("TermType") == "LONG")
        .sum()
        .alias("LongTermGainLoss"),
    )

    result = (
        grouped.with_columns(
            pl.lit(period_type).alias("PeriodType"),
            pl.col("PeriodStart").dt.offset_by(trunc).dt.offset_by("-1d").alias("PeriodEnd"),
            pl.col("ShortTermGainLoss").fill_null(0.0),
            pl.col("LongTermGainLoss").fill_null(0.0),
        )
        .select(list(_SUMMARY_SCHEMA.keys()))
        .sort("Symbol", "PeriodStart")
    )

    log.info("Summarized %d realized-gain row(s) into %d %s period row(s)", matched.height, result.height, period)
    return result
