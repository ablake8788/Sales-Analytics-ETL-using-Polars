from datetime import date

import polars as pl
import pytest

from etl.fifo_matching import match_fifo
from etl.summary import summarize

_SCHEMA = {
    "TransactionId": pl.Int64,
    "Symbol": pl.Utf8,
    "TradeDate": pl.Date,
    "Instruction": pl.Utf8,
    "Quantity": pl.Float64,
    "Price": pl.Float64,
    "Commission": pl.Float64,
    "Fees": pl.Float64,
}


def _txns(rows: list[tuple]) -> pl.DataFrame:
    return pl.DataFrame(rows, schema=_SCHEMA, orient="row")


def test_single_full_match_short_term():
    txns = _txns([
        (1, "AAPL", date(2026, 1, 1), "BUY", 10, 100.0, 0.0, 0.0),
        (2, "AAPL", date(2026, 6, 1), "SELL", 10, 120.0, 0.0, 0.0),
    ])
    result = match_fifo(txns)

    assert result.height == 1
    row = result.row(0, named=True)
    assert row["SellTransactionId"] == 2
    assert row["BuyTransactionId"] == 1
    assert row["MatchedQuantity"] == 10
    assert row["CostBasis"] == pytest.approx(1000.0)
    assert row["Proceeds"] == pytest.approx(1200.0)
    assert row["RealizedGainLoss"] == pytest.approx(200.0)
    assert row["TermType"] == "SHORT"
    assert row["IsUnmatched"] is False


def test_long_term_classification():
    txns = _txns([
        (1, "AAPL", date(2024, 1, 1), "BUY", 5, 50.0, 0.0, 0.0),
        (2, "AAPL", date(2026, 6, 1), "SELL", 5, 80.0, 0.0, 0.0),
    ])
    result = match_fifo(txns)

    assert result.height == 1
    assert result.row(0, named=True)["TermType"] == "LONG"


def test_sell_splits_across_two_buy_lots_fifo_order():
    txns = _txns([
        (1, "AAPL", date(2026, 1, 1), "BUY", 5, 100.0, 0.0, 0.0),
        (2, "AAPL", date(2026, 2, 1), "BUY", 5, 110.0, 0.0, 0.0),
        (3, "AAPL", date(2026, 3, 1), "SELL", 8, 120.0, 0.0, 0.0),
    ])
    result = match_fifo(txns).sort("BuyTransactionId")

    assert result.height == 2
    first, second = result.row(0, named=True), result.row(1, named=True)
    # Oldest lot (BuyTransactionId=1) consumed first, fully (5 shares)
    assert first["BuyTransactionId"] == 1
    assert first["MatchedQuantity"] == 5
    # Remaining 3 shares come from the second lot
    assert second["BuyTransactionId"] == 2
    assert second["MatchedQuantity"] == 3


def test_sell_with_no_prior_buy_is_flagged_unmatched():
    txns = _txns([
        (1, "AAPL", date(2026, 3, 1), "SELL", 10, 120.0, 0.0, 0.0),
    ])
    result = match_fifo(txns)

    assert result.height == 1
    row = result.row(0, named=True)
    assert row["IsUnmatched"] is True
    assert row["BuyTransactionId"] is None
    assert row["CostBasis"] is None
    assert row["MatchedQuantity"] == 10


def test_fees_allocated_proportionally():
    txns = _txns([
        (1, "AAPL", date(2026, 1, 1), "BUY", 10, 100.0, 10.0, 0.0),  # $1/share buy fee
        (2, "AAPL", date(2026, 6, 1), "SELL", 10, 120.0, 5.0, 0.0),  # $0.50/share sell fee
    ])
    result = match_fifo(txns)

    row = result.row(0, named=True)
    # CostBasis = qty * (price + fee_per_share) = 10 * (100 + 1) = 1010
    assert row["CostBasis"] == pytest.approx(1010.0)
    # Proceeds = qty * price - total_sell_fee = 10*120 - 5 = 1195
    assert row["Proceeds"] == pytest.approx(1195.0)
    assert row["RealizedGainLoss"] == pytest.approx(185.0)


def test_summarize_rolls_up_by_symbol_and_month():
    txns = _txns([
        (1, "AAPL", date(2026, 1, 1), "BUY", 10, 100.0, 0.0, 0.0),
        (2, "AAPL", date(2026, 1, 15), "SELL", 4, 120.0, 0.0, 0.0),
        (3, "AAPL", date(2026, 1, 20), "SELL", 6, 90.0, 0.0, 0.0),
    ])
    gains = match_fifo(txns)
    summary = summarize(gains, period="month")

    assert summary.height == 1
    row = summary.row(0, named=True)
    assert row["Symbol"] == "AAPL"
    assert row["PeriodType"] == "MONTH"
    assert row["PeriodStart"] == date(2026, 1, 1)
    assert row["TradeCount"] == 2
    # Gains: sell1 = 4*120 - 4*100 = 80; sell2 = 6*90 - 6*100 = -60
    assert row["TotalRealizedGainLoss"] == pytest.approx(20.0)
    assert row["ShortTermGainLoss"] == pytest.approx(20.0)
    assert row["LongTermGainLoss"] == pytest.approx(0.0)


def test_summarize_excludes_unmatched_rows():
    txns = _txns([
        (1, "AAPL", date(2026, 3, 1), "SELL", 10, 120.0, 0.0, 0.0),
    ])
    gains = match_fifo(txns)
    summary = summarize(gains, period="month")

    assert summary.is_empty()
