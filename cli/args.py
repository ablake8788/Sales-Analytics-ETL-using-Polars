"""
cli/args.py
-----------
Command-line argument definition and parsing.

Kept separate from main() so it can be imported and tested in isolation,
and so the argument schema lives in one obvious place.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path


@dataclass
class CliArgs:
    """Typed result of CLI argument parsing."""
    symbols: list[str] | None
    start: str
    end: str
    period: str
    write_back: bool
    write_mode: str
    log_dir: Path | None


def parse_args(argv=None) -> CliArgs:
    """
    Parse and return typed CLI arguments.

    Parameters
    ----------
    argv : list[str] | None
        Argument list (defaults to sys.argv when None).
    """
    parser = argparse.ArgumentParser(
        description="Sales Analytics ETL — FIFO realized gain/loss over "
                     "SchwabTransactions, computed with Polars",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples
--------
  # Show realized gains/summary without writing back:
  python main.py --start 2026-01-01 --end 2026-07-01

  # Restrict to specific symbols, summarize by year, and persist to SQL Server:
  python main.py --symbols AAPL,MSFT --start 2026-01-01 --end 2026-07-01 \\
      --period year --write-back
""",
    )

    parser.add_argument(
        "--symbols",
        default=None,
        metavar="SYM,SYM,...",
        help="Comma-separated list of ticker symbols (default: all symbols in range)",
    )
    parser.add_argument(
        "--start",
        required=True,
        metavar="YYYY-MM-DD",
        help="Start of the trade-date range to analyze",
    )
    parser.add_argument(
        "--end",
        required=True,
        metavar="YYYY-MM-DD",
        help="End of the trade-date range to analyze",
    )
    parser.add_argument(
        "--period",
        choices=["month", "year"],
        default="month",
        help="Summary aggregation granularity (default: month)",
    )
    parser.add_argument(
        "--write-back",
        action="store_true",
        help="Persist results to SQL Server instead of just printing them",
    )
    parser.add_argument(
        "--write-mode",
        choices=["append", "replace"],
        default="append",
        help="Write mode when --write-back is set: 'replace' deletes rows "
             "matching the incoming batch's keys first, for idempotent "
             "reruns (default: append)",
    )
    parser.add_argument(
        "--log-dir",
        metavar="DIR",
        type=Path,
        help="Directory for rotating log files (default: ./logs)",
    )

    ns = parser.parse_args(argv)
    symbols = (
        [s.strip() for s in ns.symbols.split(",") if s.strip()]
        if ns.symbols
        else None
    )
    return CliArgs(
        symbols=symbols,
        start=ns.start,
        end=ns.end,
        period=ns.period,
        write_back=ns.write_back,
        write_mode=ns.write_mode,
        log_dir=ns.log_dir,
    )
