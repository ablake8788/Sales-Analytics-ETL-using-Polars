"""
db/transaction_reader.py
-------------------------
Reads raw BUY/SELL trade rows from dbo.SchwabTransactions (see
sql/tables/SchwabTransactions.sql for the expected contract) as a Polars
DataFrame.

Design pattern: Repository — callers ask for rows in domain terms
(symbols + trade-date range) and never see SQL. Date-range filtering is
pushed down into the query so SQL Server does the row elimination instead
of shipping the whole table to the client.
"""

from __future__ import annotations

import logging

import polars as pl

from core.config import SqlConfig
from core.logging_setup import traced
from db._validation import validate_date, validate_symbols
from db.connection import SqlConnectionFactory

log = logging.getLogger(__name__)

_COLUMNS = (
    "TransactionId, Symbol, TradeDate, Instruction, Quantity, "
    "Price, Commission, Fees"
)


class TransactionReader:
    def __init__(self, factory: SqlConnectionFactory, sql_config: SqlConfig) -> None:
        self._factory = factory
        self._cfg = sql_config

    @traced
    def read(self, symbols: list[str] | None, start: str, end: str) -> pl.DataFrame:
        """
        Read BUY/SELL rows with TradeDate in [start, end], ordered so FIFO
        matching can consume them directly (per symbol, oldest first).

        Parameters
        ----------
        symbols : list[str] | None
            Tickers to include; None or [] means "all symbols in range".
        start, end : str
            Inclusive trade-date bounds, "YYYY-MM-DD".
        """
        # start/end/symbols are validated against strict whitelists before
        # interpolation — this is the injection guard, same idiom as
        # db/_jdbc.py::validate_symbols in the sibling PySpark project.
        start = validate_date("start", start)
        end = validate_date("end", end)

        where = [
            "Instruction IN ('BUY', 'SELL')",
            f"TradeDate BETWEEN '{start}' AND '{end}'",
        ]

        if symbols:
            clean_symbols = validate_symbols(symbols)
            symbol_list = ", ".join(f"'{s}'" for s in clean_symbols)
            where.append(f"Symbol IN ({symbol_list})")

        query = (
            f"SELECT {_COLUMNS} FROM {self._cfg.table_transactions} "
            f"WHERE {' AND '.join(where)} "
            f"ORDER BY Symbol, TradeDate, TransactionId"
        )

        with self._factory.connect() as conn:
            df = pl.read_database(query=query, connection=conn)

        log.info(
            "Loaded %d transaction row(s) symbols=%s [%s, %s]",
            df.height, symbols or "ALL", start, end,
        )
        return df
