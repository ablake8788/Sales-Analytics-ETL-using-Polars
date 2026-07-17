-- ============================================
-- Table: dbo.SchwabSalesAnalytics_RealizedGains
-- Purpose: OUTPUT of the Sales Analytics ETL --write-back.
--          One row per (sell, matched-BUY-lot) pair produced by FIFO
--          matching. A sell with insufficient prior BUY quantity produces
--          a trailing row with IsUnmatched = 1 and the nullable financial
--          columns left NULL.
-- ============================================

IF OBJECT_ID('dbo.SchwabSalesAnalytics_RealizedGains', 'U') IS NOT NULL
    DROP TABLE dbo.SchwabSalesAnalytics_RealizedGains;
GO
CREATE TABLE dbo.SchwabSalesAnalytics_RealizedGains (
    RealizedGainId      int             NOT NULL IDENTITY(1,1),
    SellTransactionId   bigint          NOT NULL,
    BuyTransactionId    bigint          NULL,       -- NULL when IsUnmatched = 1
    Symbol               nvarchar(20)    NOT NULL,
    BuyDate              date            NULL,
    SellDate             date            NOT NULL,
    MatchedQuantity      decimal(18,6)   NOT NULL,
    CostBasis            decimal(18,4)   NULL,
    Proceeds             decimal(18,4)   NULL,
    RealizedGainLoss     decimal(18,4)   NULL,
    HoldingPeriodDays    int             NULL,
    TermType             nvarchar(10)    NULL,       -- 'SHORT' or 'LONG'
    IsUnmatched          bit             NOT NULL DEFAULT 0,
    BatchId              nvarchar(50)    NOT NULL,
    LoadDate             datetime2       NOT NULL,
    CONSTRAINT PK_SchwabSalesAnalytics_RealizedGains PRIMARY KEY (RealizedGainId),
    CONSTRAINT CK_SchwabSalesAnalytics_RealizedGains_TermType
        CHECK (TermType IN ('SHORT', 'LONG') OR TermType IS NULL)
);
GO
CREATE INDEX IX_SchwabSalesAnalytics_RealizedGains_Symbol_SellDate
    ON dbo.SchwabSalesAnalytics_RealizedGains (Symbol, SellDate);
GO
CREATE INDEX IX_SchwabSalesAnalytics_RealizedGains_SellTransactionId
    ON dbo.SchwabSalesAnalytics_RealizedGains (SellTransactionId);
GO
