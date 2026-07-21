"""
main.py
-------
Application entry point — Composition Root.

All dependencies are wired here and nowhere else.
No business logic lives in this file; it only:
  1. Parses CLI args.
  2. Sets up logging.
  3. Loads config (Singleton).
  4. Constructs and injects all collaborators.
  5. Calls the orchestration sequence: read -> FIFO match -> summarize ->
     print -> (optionally) write back.

Design patterns in use across the project
------------------------------------------
| Pattern            | Where                                          |
|--------------------|------------------------------------------------|
| Singleton          | AppConfig.load()                               |
| Factory Method      | SqlConnectionFactory.create()                  |
| Repository          | TransactionReader, AnalyticsWriter              |
| Composition Root    | main.py                                        |
| Decorator           | @traced on all key functions                   |
| Value Object        | SqlConfig, CliArgs                             |
"""

from __future__ import annotations

import logging
import os
import sys
import traceback
import uuid
from datetime import datetime, timezone

import polars as pl

from cli import parse_args
from core import AppConfig, setup_logging
from db import SqlConnectionFactory, TransactionReader, AnalyticsWriter
from etl import match_fifo, summarize

log = logging.getLogger(__name__)


def main() -> None:
    # Windows consoles default to the system codepage (e.g. cp1252), which
    # can't render some characters in Polars' table output — force UTF-8 so
    # printing DataFrames never crashes the run regardless of the terminal.
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")

    # ── 1. CLI args ────────────────────────────
    args = parse_args()

    # ── 2. Logging ─────────────────────────────
    setup_logging(args.log_dir)
    log.info("=" * 60)
    log.info("Sales Analytics ETL (Polars) starting")
    log.info("Python %s | PID %d", sys.version.split()[0], os.getpid())
    log.info("=" * 60)

    try:
        # ── 3. Config (Singleton) ───────────────
        cfg = AppConfig.load()
        log.info("Config loaded from sales_analytics_etl.ini")

        # ── 4. Wire dependencies ────────────────
        factory = SqlConnectionFactory(cfg.sql)
        transaction_reader = TransactionReader(factory, cfg.sql)
        analytics_writer = AnalyticsWriter(factory, cfg.sql)

        log.info(
            "Symbols=%s  trade date range: %s -> %s  period=%s",
            args.symbols or "ALL", args.start, args.end, args.period,
        )

        # ── 5. Extract ───────────────────────────
        transactions = transaction_reader.read(args.symbols, args.start, args.end)
        if transactions.is_empty():
            print("No BUY/SELL transactions found for the given filters.")
            log.info("No transactions found — nothing to do.")
            return

        # ── 6. Transform ─────────────────────────
        realized_gains = match_fifo(transactions)
        summary = summarize(realized_gains, args.period)

        with pl.Config(tbl_rows=50, tbl_cols=-1, fmt_str_lengths=20):
            print("\n=== REALIZED GAINS (FIFO-matched) ===")
            print(realized_gains.sort("Symbol", "SellDate"))

            print(f"\n=== SUMMARY BY {args.period.upper()} ===")
            print(summary)

        unmatched = realized_gains.filter(pl.col("IsUnmatched"))
        if not unmatched.is_empty():
            print(
                f"\nWARNING: {unmatched.height} sale(s) had no matching BUY lot "
                "(see log for details)."
            )

        # ── 7. Load (optional) ───────────────────
        if args.write_back:
            print(f"\nWriting results to SQL Server (mode={args.write_mode}) ...")

            batch_id = str(uuid.uuid4())
            load_date = datetime.now(timezone.utc)

            gains_out = realized_gains.with_columns(
                pl.lit(batch_id).alias("BatchId"),
                pl.lit(load_date).alias("LoadDate"),
            )
            summary_out = summary.with_columns(
                pl.lit(batch_id).alias("BatchId"),
                pl.lit(load_date).alias("LoadDate"),
            )

            g_rows = analytics_writer.write_realized_gains(gains_out, args.write_mode)
            s_rows = analytics_writer.write_summary(summary_out, args.write_mode)
            print(f"RealizedGains: {g_rows} row(s) written. Summary: {s_rows} row(s) written.")
            log.info(
                "Write-back complete. RealizedGains=%d Summary=%d BatchId=%s",
                g_rows, s_rows, batch_id,
            )

        log.info("Run complete.")

    except KeyboardInterrupt:
        log.warning("Interrupted by user")
        print("\nInterrupted.")
        sys.exit(0)

    except Exception as exc:
        log.critical("Unhandled exception: %s\n%s", exc, traceback.format_exc())
        print(f"\nFATAL: {exc}")
        sys.exit(1)


if __name__ == "__main__":
    main()
