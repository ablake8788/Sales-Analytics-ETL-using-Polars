"""
db/analytics_writer.py
------------------------
Writes computed analytics DataFrames back to SQL Server via pyodbc.

Design pattern: Repository / Unit-of-Work — every public write runs as a
single transaction (optional delete + batch insert), committed once at the
end so a failure never leaves the target table half-updated.

mode="replace" makes reruns idempotent: rows are deleted by the natural key
of the *incoming* batch (SellTransactionId for realized gains, Symbol +
PeriodType + PeriodStart for summary) before the new rows are inserted, so
re-running the ETL for a date range you've already loaded doesn't duplicate
rows. mode="append" skips the delete and just inserts.
"""

from __future__ import annotations

import logging

import polars as pl

from core.config import SqlConfig
from core.logging_setup import TRACE_LEVEL, traced
from db.connection import SqlConnectionFactory

log = logging.getLogger(__name__)

_REALIZED_GAINS_COLUMNS = (
    "SellTransactionId", "BuyTransactionId", "Symbol", "BuyDate", "SellDate",
    "MatchedQuantity", "CostBasis", "Proceeds", "RealizedGainLoss",
    "HoldingPeriodDays", "TermType", "IsUnmatched", "BatchId", "LoadDate",
)

_SUMMARY_COLUMNS = (
    "Symbol", "PeriodType", "PeriodStart", "PeriodEnd", "TradeCount",
    "TotalProceeds", "TotalCostBasis", "TotalRealizedGainLoss",
    "ShortTermGainLoss", "LongTermGainLoss", "BatchId", "LoadDate",
)


class AnalyticsWriter:
    def __init__(self, factory: SqlConnectionFactory, sql_config: SqlConfig) -> None:
        self._factory = factory
        self._cfg = sql_config

    @traced
    def write_realized_gains(self, df: pl.DataFrame, mode: str = "append") -> int:
        if df.is_empty():
            log.info("write_realized_gains: nothing to write")
            return 0

        delete_sql = None
        delete_params: list = []
        if mode == "replace":
            sell_ids = df.get_column("SellTransactionId").unique().to_list()
            placeholders = ", ".join("?" for _ in sell_ids)
            delete_sql = (
                f"DELETE FROM {self._cfg.table_realized_gains} "
                f"WHERE SellTransactionId IN ({placeholders})"
            )
            delete_params = sell_ids

        insert_sql = (
            f"INSERT INTO {self._cfg.table_realized_gains} "
            f"({', '.join(_REALIZED_GAINS_COLUMNS)}) "
            f"VALUES ({', '.join('?' for _ in _REALIZED_GAINS_COLUMNS)})"
        )
        rows = df.select(list(_REALIZED_GAINS_COLUMNS)).rows()
        return self._write(insert_sql, rows, delete_sql, delete_params, self._cfg.table_realized_gains)

    @traced
    def write_summary(self, df: pl.DataFrame, mode: str = "append") -> int:
        if df.is_empty():
            log.info("write_summary: nothing to write")
            return 0

        delete_sql = None
        delete_params: list = []
        if mode == "replace":
            keys = df.select("Symbol", "PeriodType", "PeriodStart").unique().rows()
            clauses = " OR ".join(["(Symbol = ? AND PeriodType = ? AND PeriodStart = ?)"] * len(keys))
            delete_sql = f"DELETE FROM {self._cfg.table_summary} WHERE {clauses}"
            delete_params = [v for key in keys for v in key]

        insert_sql = (
            f"INSERT INTO {self._cfg.table_summary} "
            f"({', '.join(_SUMMARY_COLUMNS)}) "
            f"VALUES ({', '.join('?' for _ in _SUMMARY_COLUMNS)})"
        )
        rows = df.select(list(_SUMMARY_COLUMNS)).rows()
        return self._write(insert_sql, rows, delete_sql, delete_params, self._cfg.table_summary)

    # ── Private helper ─────────────────────────
    def _write(
        self,
        insert_sql: str,
        rows: list[tuple],
        delete_sql: str | None,
        delete_params: list,
        table: str,
    ) -> int:
        with self._factory.connect() as conn:
            cursor = conn.cursor()
            cursor.fast_executemany = True

            if delete_sql is not None:
                log.debug("Deleting existing rows from %s before insert", table)
                cursor.execute(delete_sql, delete_params)

            log.log(TRACE_LEVEL, "Inserting %d row(s) into %s", len(rows), table)
            cursor.executemany(insert_sql, rows)
            conn.commit()

        log.info("Wrote %d row(s) to %s", len(rows), table)
        return len(rows)
