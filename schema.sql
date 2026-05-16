-- Create trades table
CREATE TABLE IF NOT EXISTS trades (
    id         SERIAL PRIMARY KEY,
    symbol     VARCHAR(10)    NOT NULL,
    side       VARCHAR(4)     NOT NULL CHECK (side IN ('BUY', 'SELL')),
    quantity   NUMERIC(18, 6) NOT NULL CHECK (quantity > 0),
    price      NUMERIC(18, 6) NOT NULL CHECK (price > 0),
    timestamp  TIMESTAMPTZ    NOT NULL DEFAULT NOW()
);

-- Index for common query patterns
CREATE INDEX IF NOT EXISTS idx_trades_symbol    ON trades (symbol);
CREATE INDEX IF NOT EXISTS idx_trades_timestamp ON trades (timestamp DESC);

-- Seed some sample data
INSERT INTO trades (symbol, side, quantity, price, timestamp) VALUES
    ('AAPL',  'BUY',  10,  195.50, NOW() - INTERVAL '3 days'),
    ('TSLA',  'SELL',  5,  245.00, NOW() - INTERVAL '2 days'),
    ('NVDA',  'BUY',   8,  875.00, NOW() - INTERVAL '1 day'),
    ('MSFT',  'BUY',  15,  415.00, NOW() - INTERVAL '6 hours'),
    ('AAPL',  'SELL',  3,  198.00, NOW());
