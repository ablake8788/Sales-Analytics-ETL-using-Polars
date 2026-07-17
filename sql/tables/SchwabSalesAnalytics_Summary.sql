-- ============================================
-- Table: dbo.SchwabSalesAnalytics_Summary
-- Purpose: OUTPUT of the Sales Analytics ETL --write-back.
--          Realized P&L rolled up by Symbol x Period (month or year),
--          split into short-term vs long-term gain/loss.
-- ============================================

IF OBJECT_ID('dbo.SchwabSalesAnalytics_Summary', 'U') IS NOT NULL
    DROP TABLE dbo.SchwabSalesAnalytics_Summary;
GO
CREATE TABLE dbo.SchwabSalesAnalytics_Summary (
    SummaryId               int             NOT NULL IDENTITY(1,1),
    Symbol                   nvarchar(20)    NOT NULL,
    PeriodType               nvarchar(10)    NOT NULL,   -- 'MONTH' or 'YEAR'
    PeriodStart              date            NOT NULL,
    PeriodEnd                date            NOT NULL,
    TradeCount               int             NOT NULL,
    TotalProceeds            decimal(18,4)   NOT NULL,
    TotalCostBasis           decimal(18,4)   NOT NULL,
    TotalRealizedGainLoss    decimal(18,4)   NOT NULL,
    ShortTermGainLoss        decimal(18,4)   NOT NULL,
    LongTermGainLoss         decimal(18,4)   NOT NULL,
    BatchId                  nvarchar(50)    NOT NULL,
    LoadDate                 datetime2       NOT NULL,
    CONSTRAINT PK_SchwabSalesAnalytics_Summary PRIMARY KEY (SummaryId),
    CONSTRAINT CK_SchwabSalesAnalytics_Summary_PeriodType
        CHECK (PeriodType IN ('MONTH', 'YEAR')),
    CONSTRAINT UQ_SchwabSalesAnalytics_Summary UNIQUE (Symbol, PeriodType, PeriodStart)
);
GO
