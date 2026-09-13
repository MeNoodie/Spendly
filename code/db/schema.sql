-- ─────────────────────────────────────────────────────────────────
-- Spendly SQLite Schema
-- Designed for Hackathon accuracy & Product extension
-- ─────────────────────────────────────────────────────────────────

-- USERS
CREATE TABLE IF NOT EXISTS users (
  id            TEXT PRIMARY KEY,
  name          TEXT,
  email         TEXT UNIQUE,
  source        TEXT DEFAULT 'hackathon',
  created_at    TEXT DEFAULT (datetime('now'))
);

-- FINANCIAL PROFILES
CREATE TABLE IF NOT EXISTS financial_profiles (
  user_id                                         TEXT PRIMARY KEY REFERENCES users(id),
  home_currency                                   TEXT NOT NULL DEFAULT 'INR',
  current_available_balance                       REAL NOT NULL DEFAULT 0,
  minimum_balance_to_keep                         REAL NOT NULL DEFAULT 0,
  financial_priorities                            TEXT,
  expense_categories_to_protect                   TEXT,
  expense_categories_user_is_willing_to_reduce     TEXT,
  expense_categories_user_is_willing_to_stop       TEXT,
  payment_methods_user_will_consider              TEXT,
  max_installment_months                          REAL,
  updated_at                                      TEXT DEFAULT (datetime('now'))
);

-- FINANCIAL EVENTS (Historical, scheduled, pending, and recurring)
CREATE TABLE IF NOT EXISTS financial_events (
  event_id                TEXT PRIMARY KEY,
  user_id                 TEXT NOT NULL REFERENCES users(id),
  event_type              TEXT NOT NULL,
  description             TEXT,
  category                TEXT,
  direction               TEXT NOT NULL, -- 'debit' | 'credit' | 'non_cash'
  amount                  REAL,          -- NULL = resolve from image
  currency                TEXT,
  event_date              TEXT NOT NULL, -- YYYY-MM-DD
  settlement_date         TEXT,          -- YYYY-MM-DD
  status                  TEXT NOT NULL, -- 'settled'|'cancelled'|'pending'|'scheduled'|'failed'|'unrealized'
  linked_event_id         TEXT,
  flexibility             TEXT,          -- 'fixed'|'stoppable'|'reducible'|'reducible_or_stoppable'
  minimum_allowed_amount  REAL
);
CREATE INDEX IF NOT EXISTS idx_events_user_date ON financial_events(user_id, event_date);
CREATE INDEX IF NOT EXISTS idx_events_user_cat ON financial_events(user_id, category);

-- PAYMENT OPTIONS (installment & payment options per request)
CREATE TABLE IF NOT EXISTS payment_options (
  payment_option_id       TEXT PRIMARY KEY,
  request_id              TEXT NOT NULL,
  payment_method          TEXT NOT NULL,
  payment_amount          REAL NOT NULL,
  number_of_payments      INTEGER NOT NULL DEFAULT 1,
  first_payment_date      TEXT NOT NULL,
  payment_frequency_days  REAL,
  financing_fee           REAL DEFAULT 0,
  total_payable_amount    REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_payment_options_req ON payment_options(request_id);

-- EXCHANGE RATES
CREATE TABLE IF NOT EXISTS exchange_rates (
  id            INTEGER PRIMARY KEY AUTOINCREMENT,
  rate_date     TEXT NOT NULL,
  from_currency TEXT NOT NULL,
  to_currency   TEXT NOT NULL,
  rate          REAL NOT NULL,
  UNIQUE(rate_date, from_currency, to_currency)
);

-- UPLOADED DOCUMENTS / IMAGES
CREATE TABLE IF NOT EXISTS uploaded_documents (
  image_id          TEXT PRIMARY KEY,
  user_id           TEXT REFERENCES users(id),
  request_id        TEXT,
  related_event_id  TEXT,
  file_path         TEXT NOT NULL,
  extracted_amount  REAL,
  extracted_text    TEXT,
  extraction_status TEXT DEFAULT 'pending',
  uploaded_at       TEXT DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_docs_req ON uploaded_documents(request_id);
CREATE INDEX IF NOT EXISTS idx_docs_event ON uploaded_documents(related_event_id);

-- MESSAGES (Contextual overrides / notifications)
CREATE TABLE IF NOT EXISTS event_messages (
  message_id       TEXT PRIMARY KEY,
  user_id          TEXT REFERENCES users(id),
  request_id       TEXT,
  related_event_id TEXT,
  sent_at          TEXT,
  source_type      TEXT,
  message_text     TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_msgs_user ON event_messages(user_id);
CREATE INDEX IF NOT EXISTS idx_msgs_req ON event_messages(request_id);
CREATE INDEX IF NOT EXISTS idx_msgs_event ON event_messages(related_event_id);

-- DECISIONS (Output cache & product history)
CREATE TABLE IF NOT EXISTS decisions (
  request_id              TEXT PRIMARY KEY,
  user_id                 TEXT NOT NULL REFERENCES users(id),
  request_text            TEXT,
  request_type            TEXT,
  requested_amount        REAL NOT NULL,
  request_date            TEXT NOT NULL,
  desired_completion_date TEXT,
  allows_partial          INTEGER DEFAULT 0,
  amount_safe_to_pay      REAL,
  affordability_status    TEXT,
  recommended_method      TEXT,
  payment_plan            TEXT,
  earliest_full_date      TEXT,
  spending_changes        TEXT,
  explanation             TEXT,
  llm_tokens_used         INTEGER DEFAULT 0,
  created_at              TEXT DEFAULT (datetime('now'))
);

-- LLM USAGE LOGS
CREATE TABLE IF NOT EXISTS usage_logs (
  id                 INTEGER PRIMARY KEY AUTOINCREMENT,
  request_id         TEXT,
  model_provider     TEXT,
  model_name         TEXT,
  call_type          TEXT,
  input_tokens       INTEGER,
  output_tokens      INTEGER,
  estimated_cost_usd REAL,
  called_at          TEXT DEFAULT (datetime('now'))
);
