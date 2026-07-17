"""
etl/fifo_matching.py
---------------------
FIFO (first-in, first-out) cost-basis matching of SELL transactions against
prior BUY transactions, per symbol, to compute realized gain/loss.

This is an inherently sequential/stateful algorithm — a running per-symbol
lot queue — so it's implemented as a Python loop over rows grouped by
symbol rather than as vectorised Polars expressions. Input volumes for a
personal trading account are small (thousands of rows, not millions), so
the loop is not a performance concern; Polars is still used for the
group-by/sort and for the final DataFrame construction.
"""

from __future__ import annotations

import logging
from collections import deque
from dataclasses import dataclass
from datetime import date

import polars as pl

from core.logging_setup import traced

log = logging.getLogger(__name__)

_LONG_TERM_DAYS = 365  # holding period > 365 days => long-term capital gain

_OUTPUT_SCHEMA = {
    "SellTransactionId": pl.Int64,
    "BuyTransactionId": pl.Int64,
    "Symbol": pl.Utf8,
    "BuyDate": pl.Date,
    "SellDate": pl.Date,
    "MatchedQuantity": pl.Float64,
    "CostBasis": pl.Float64,
    "Proceeds": pl.Float64,
    "RealizedGainLoss": pl.Float64,
    "HoldingPeriodDays": pl.Int64,
    "TermType": pl.Utf8,
    "IsUnmatched": pl.Boolean,
}


@dataclass
class _Lot:
    transaction_id: int
    trade_date: date
    qty_remaining: float
    price: float
    fee_per_share: float  # buy-side (Commission + Fees) / original Quantity


@traced
def match_fifo(transactions: pl.DataFrame) -> pl.DataFrame:
    """
    Match each SELL row against prior BUY rows for the same symbol using
    FIFO, allocating commission/fees proportionally to matched quantity.

    Parameters
    ----------
    transactions : pl.DataFrame
        Columns: TransactionId, Symbol, TradeDate, Instruction ('BUY'/'SELL'),
        Quantity, Price, Commission, Fees — sorted by Symbol, TradeDate,
        TransactionId (TransactionReader.read() guarantees this ordering).

    Returns
    -------
    pl.DataFrame
        One row per (sell, matched-buy-lot) pair. A sell with insufficient
        prior BUY quantity produces a trailing row with IsUnmatched=True and
        CostBasis/Proceeds/RealizedGainLoss/TermType left null, so shortfalls
        (e.g. missing purchase history) are visible instead of silently
        dropped or crashing the run.
    """
    output_rows: list[dict] = []

    for symbol, group in transactions.group_by("Symbol", maintain_order=True):
        symbol = symbol[0] if isinstance(symbol, tuple) else symbol
        lots: deque[_Lot] = deque()

        for row in group.iter_rows(named=True):
            if row["Instruction"] == "BUY":
                qty = float(row["Quantity"])
                buy_fees = float(row["Commission"] or 0) + float(row["Fees"] or 0)
                lots.append(
                    _Lot(
                        transaction_id=row["TransactionId"],
                        trade_date=row["TradeDate"],
                        qty_remaining=qty,
                        price=float(row["Price"]),
                        fee_per_share=(buy_fees / qty) if qty else 0.0,
                    )
                )
                continue

            output_rows.extend(_match_sell(symbol, row, lots))

    if not output_rows:
        return pl.DataFrame(schema=_OUTPUT_SCHEMA)
    return pl.DataFrame(output_rows, schema=_OUTPUT_SCHEMA)


def _match_sell(symbol: str, sell_row: dict, lots: "deque[_Lot]") -> list[dict]:
    sell_id = sell_row["TransactionId"]
    sell_date = sell_row["TradeDate"]
    sell_price = float(sell_row["Price"])
    sell_fees_total = float(sell_row["Commission"] or 0) + float(sell_row["Fees"] or 0)
    total_sell_qty = float(sell_row["Quantity"])
    qty_to_sell = total_sell_qty

    rows: list[dict] = []
    while qty_to_sell > 1e-9 and lots:
        lot = lots[0]
        matched_qty = min(lot.qty_remaining, qty_to_sell)

        cost_basis = matched_qty * (lot.price + lot.fee_per_share)
        sell_fee_share = sell_fees_total * (matched_qty / total_sell_qty)
        proceeds = matched_qty * sell_price - sell_fee_share
        gain_loss = proceeds - cost_basis
        holding_days = (sell_date - lot.trade_date).days
        term_type = "LONG" if holding_days > _LONG_TERM_DAYS else "SHORT"

        rows.append({
            "SellTransactionId": sell_id,
            "BuyTransactionId": lot.transaction_id,
            "Symbol": symbol,
            "BuyDate": lot.trade_date,
            "SellDate": sell_date,
            "MatchedQuantity": matched_qty,
            "CostBasis": cost_basis,
            "Proceeds": proceeds,
            "RealizedGainLoss": gain_loss,
            "HoldingPeriodDays": holding_days,
            "TermType": term_type,
            "IsUnmatched": False,
        })

        lot.qty_remaining -= matched_qty
        qty_to_sell -= matched_qty
        if lot.qty_remaining <= 1e-9:
            lots.popleft()

    if qty_to_sell > 1e-9:
        log.warning(
            "Symbol=%s SellTransactionId=%s: %.6f share(s) have no matching "
            "BUY lot (missing purchase history?) — emitting unmatched row",
            symbol, sell_id, qty_to_sell,
        )
        rows.append({
            "SellTransactionId": sell_id,
            "BuyTransactionId": None,
            "Symbol": symbol,
            "BuyDate": None,
            "SellDate": sell_date,
            "MatchedQuantity": qty_to_sell,
            "CostBasis": None,
            "Proceeds": None,
            "RealizedGainLoss": None,
            "HoldingPeriodDays": None,
            "TermType": None,
            "IsUnmatched": True,
        })

    return rows
