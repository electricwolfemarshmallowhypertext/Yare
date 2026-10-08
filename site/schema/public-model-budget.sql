-- Create tables only. No budget is seeded or enabled by this migration.
CREATE TABLE IF NOT EXISTS yare_public_model_budgets (
    budget_id TEXT PRIMARY KEY,
    limit_usd_micros INT8 NOT NULL CHECK (limit_usd_micros > 0),
    max_calls INT8 NOT NULL CHECK (max_calls > 0),
    max_tokens INT8 NOT NULL CHECK (max_tokens > 0),
    charged_usd_micros INT8 NOT NULL DEFAULT 0 CHECK (charged_usd_micros >= 0),
    calls_used INT8 NOT NULL DEFAULT 0 CHECK (calls_used >= 0),
    tokens_charged INT8 NOT NULL DEFAULT 0 CHECK (tokens_charged >= 0),
    blocked BOOL NOT NULL DEFAULT true,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS yare_public_model_calls (
    request_id UUID PRIMARY KEY,
    budget_id TEXT NOT NULL REFERENCES yare_public_model_budgets (budget_id),
    model_id TEXT NOT NULL,
    reserved_usd_micros INT8 NOT NULL,
    input_bound INT8 NOT NULL,
    output_bound INT8 NOT NULL,
    input_rate_micros INT8 NOT NULL,
    output_rate_micros INT8 NOT NULL,
    status TEXT NOT NULL,
    prompt_tokens INT8,
    completion_tokens INT8,
    observed_usd_micros INT8,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
