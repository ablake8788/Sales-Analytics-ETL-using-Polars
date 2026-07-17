-- ============================================
-- Table: dbo.SchwabTransactions
-- Purpose: INPUT contract for the Sales Analytics ETL.
--          Raw BUY/SELL trade executions. This project only READS this
--          table — it is populated by the sibling schwab_market_data
--          project's transactions_main.py (Schwab Trader API loader).
--          Keep this DDL in sync with that project's copy under
--          sql/tables/SchwabTransactions.sql; only one of the two needs
--          to actually be run against the database.
-- ============================================

IF OBJECT_ID('dbo.SchwabTransactions', 'U') IS NOT NULL
    DROP TABLE dbo.SchwabTransactions;
GO
CREATE TABLE dbo.SchwabTransactions (
    TransactionId   bigint          NOT NULL,   -- source system's unique trade/activity id
    AccountNumber   nvarchar(20)    NULL,
    Symbol          nvarchar(20)    NOT NULL,
    TradeDate       date            NOT NULL,
    SettlementDate  date            NULL,
    Instruction     nvarchar(10)    NOT NULL,   -- 'BUY' or 'SELL'
    Quantity        decimal(18,6)   NOT NULL,
    Price           decimal(18,4)   NOT NULL,
    Commission      decimal(18,4)   NOT NULL DEFAULT 0,
    Fees            decimal(18,4)   NOT NULL DEFAULT 0,
    NetAmount       decimal(18,4)   NULL,
    InsertedAt      datetime2       NOT NULL DEFAULT SYSUTCDATETIME(),
    CONSTRAINT PK_SchwabTransactions PRIMARY KEY (TransactionId),
    CONSTRAINT CK_SchwabTransactions_Instruction CHECK (Instruction IN ('BUY', 'SELL'))
);
GO
CREATE INDEX IX_SchwabTransactions_Symbol_TradeDate
    ON dbo.SchwabTransactions (Symbol, TradeDate, TransactionId);
GO
