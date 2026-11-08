-- ============================================================
-- سهام‌یار — Database Schema for Backtest Framework
-- PostgreSQL 13+
-- ============================================================

-- Symbols master data
CREATE TABLE IF NOT EXISTS symbols (
    ins_code       VARCHAR(18) PRIMARY KEY,
    ticker         VARCHAR(20) NOT NULL,
    fullname       VARCHAR(100),
    sector_code    INT NOT NULL,
    sector_name    VARCHAR(50),
    flow           INT,                    -- 1=bourse, 2=farabourse, 4=base
    status         VARCHAR(2),             -- A=active, S=suspended, D=delisted
    listed_at      DATE,
    delisted_at    DATE,                   -- NULL if still active
    updated_at     TIMESTAMP DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_symbols_sector ON symbols(sector_code);
CREATE INDEX IF NOT EXISTS idx_symbols_ticker ON symbols(ticker);
CREATE INDEX IF NOT EXISTS idx_symbols_status ON symbols(status);

-- Daily candles (OHLCV + extras)
CREATE TABLE IF NOT EXISTS daily_candles (
    ins_code       VARCHAR(18) REFERENCES symbols(ins_code),
    date_jalali    INT NOT NULL,
    open           DECIMAL(18,2),
    high           DECIMAL(18,2),
    low            DECIMAL(18,2),
    close          DECIMAL(18,2),
    last_price     DECIMAL(18,2),
    yesterday      DECIMAL(18,2),
    volume         BIGINT,
    trade_count    INT,
    value          BIGINT,
    max_allowed    DECIMAL(18,2),
    min_allowed    DECIMAL(18,2),
    PRIMARY KEY (ins_code, date_jalali)
);
CREATE INDEX IF NOT EXISTS idx_candles_date ON daily_candles(date_jalali);
CREATE INDEX IF NOT EXISTS idx_candles_ins_date ON daily_candles(ins_code, date_jalali DESC);

-- Client types (حقوقی/حقیقی)
CREATE TABLE IF NOT EXISTS client_types (
    ins_code          VARCHAR(18) REFERENCES symbols(ins_code),
    date_jalali       INT NOT NULL,
    buy_real_count    INT,
    sell_real_count   INT,
    buy_legal_count   INT,
    sell_legal_count  INT,
    buy_real_volume   BIGINT,
    sell_real_volume  BIGINT,
    buy_legal_volume  BIGINT,
    sell_legal_volume BIGINT,
    buy_real_value    BIGINT,
    sell_real_value   BIGINT,
    buy_legal_value   BIGINT,
    sell_legal_value  BIGINT,
    PRIMARY KEY (ins_code, date_jalali)
);

-- Fundamentals (quarterly)
CREATE TABLE IF NOT EXISTS fundamentals (
    ins_code       VARCHAR(18) REFERENCES symbols(ins_code),
    fiscal_period  VARCHAR(10),         -- e.g. "1404/Q1"
    eps            DECIMAL(18,2),
    estimated_eps  DECIMAL(18,2),
    sector_pe      DECIMAL(8,2),
    nav            DECIMAL(18,2),
    report_date    DATE,                -- when the report was published (CRITICAL for look-ahead bias check)
    PRIMARY KEY (ins_code, fiscal_period)
);
CREATE INDEX IF NOT EXISTS idx_fundamentals_report_date ON fundamentals(report_date);

-- Market index (TEDPIX) daily values for benchmark
CREATE TABLE IF NOT EXISTS market_index (
    date_jalali    INT PRIMARY KEY,
    index_value    DECIMAL(18,2),
    index_change_pct DECIMAL(8,4)
);

-- Benchmark portfolio (equal-weight of all active symbols)
CREATE TABLE IF NOT EXISTS benchmark_returns (
    date_jalali    INT,
    horizon_days   INT,                  -- 7, 14, 30, 60, 90
    avg_return_pct DECIMAL(8,4),
    PRIMARY KEY (date_jalali, horizon_days)
);
