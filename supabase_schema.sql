-- ============================================================================
-- TokenMinGate: Supabase Database Schema
-- Run this in the Supabase SQL Editor to initialize all tables, indexes, & views
-- ============================================================================

-- 1. Teams Table
CREATE TABLE IF NOT EXISTS teams (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    budget_usd NUMERIC(10, 4) NOT NULL DEFAULT 100.0,
    budget_tokens BIGINT NOT NULL DEFAULT 1000000,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::text, now()) NOT NULL
);

-- 2. Employees / Users Table
CREATE TABLE IF NOT EXISTS employees (
    id TEXT PRIMARY KEY,
    email TEXT UNIQUE NOT NULL,
    name TEXT NOT NULL,
    role TEXT NOT NULL DEFAULT 'employee', -- 'admin', 'team_lead', 'employee'
    team_id TEXT NOT NULL REFERENCES teams(id) ON DELETE CASCADE,
    app_id TEXT NOT NULL DEFAULT 'web',
    api_key TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::text, now()) NOT NULL
);

-- 3. Virtual API Keys Table
CREATE TABLE IF NOT EXISTS api_keys (
    key TEXT PRIMARY KEY,
    name TEXT NOT NULL DEFAULT 'default',
    user_id TEXT,
    team_id TEXT,
    allowed_models JSONB NOT NULL DEFAULT '[]'::jsonb,
    max_usd NUMERIC(10, 4),
    max_tokens BIGINT,
    cache_enabled BOOLEAN NOT NULL DEFAULT true,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::text, now()) NOT NULL
);

-- 4. Key Usage Table (Atomic Accounting)
CREATE TABLE IF NOT EXISTS usage (
    key TEXT PRIMARY KEY REFERENCES api_keys(key) ON DELETE CASCADE,
    requests BIGINT NOT NULL DEFAULT 0,
    cache_hits BIGINT NOT NULL DEFAULT 0,
    prompt_tokens BIGINT NOT NULL DEFAULT 0,
    completion_tokens BIGINT NOT NULL DEFAULT 0,
    total_tokens BIGINT NOT NULL DEFAULT 0,
    cost_usd NUMERIC(14, 6) NOT NULL DEFAULT 0.0,
    jtf_saved BIGINT NOT NULL DEFAULT 0
);

-- 5. Request Log / Cost Ledger (TokenMinGate Audit Trail)
CREATE TABLE IF NOT EXISTS request_log (
    id BIGSERIAL PRIMARY KEY,
    ts NUMERIC NOT NULL,
    key TEXT NOT NULL,
    user_id TEXT,
    team_id TEXT,
    app_id TEXT,
    prompt TEXT NOT NULL,
    pruned_prompt TEXT,
    model TEXT NOT NULL,
    provider TEXT NOT NULL,
    tier TEXT NOT NULL, -- 'l1', 'l2', 'economy', 'balanced', 'frontier'
    prompt_tokens INTEGER NOT NULL DEFAULT 0,
    pruned_tokens INTEGER NOT NULL DEFAULT 0,
    completion_tokens INTEGER NOT NULL DEFAULT 0,
    total_tokens INTEGER NOT NULL DEFAULT 0,
    tokens_saved INTEGER NOT NULL DEFAULT 0,
    cost_usd NUMERIC(14, 6) NOT NULL DEFAULT 0.0,
    baseline_cost_usd NUMERIC(14, 6) NOT NULL DEFAULT 0.0,
    cache_hit BOOLEAN NOT NULL DEFAULT false,
    cache_tier TEXT, -- 'l1', 'l2', NULL
    similarity NUMERIC(6, 4),
    threshold NUMERIC(6, 4),
    latency_ms NUMERIC(10, 2) NOT NULL DEFAULT 0.0,
    is_wrong_answer BOOLEAN NOT NULL DEFAULT false,
    feedback_notes TEXT,
    status INTEGER NOT NULL DEFAULT 200,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::text, now()) NOT NULL
);

-- 6. Cache Entries Store
CREATE TABLE IF NOT EXISTS cache_store (
    id TEXT PRIMARY KEY,
    namespace TEXT NOT NULL,
    prompt_norm TEXT NOT NULL,
    response JSONB NOT NULL,
    tier TEXT NOT NULL, -- 'l1', 'l2'
    created_at NUMERIC NOT NULL,
    last_used_at NUMERIC NOT NULL,
    ttl_seconds NUMERIC NOT NULL,
    tokens_saved INTEGER NOT NULL DEFAULT 0
);

-- Indexes for high-throughput query performance
CREATE INDEX IF NOT EXISTS idx_request_log_team ON request_log(team_id);
CREATE INDEX IF NOT EXISTS idx_request_log_user ON request_log(user_id);
CREATE INDEX IF NOT EXISTS idx_request_log_tier ON request_log(tier);
CREATE INDEX IF NOT EXISTS idx_request_log_cache_hit ON request_log(cache_hit);
CREATE INDEX IF NOT EXISTS idx_cache_store_ns ON cache_store(namespace);

-- Row Level Security (RLS) policies
ALTER TABLE teams ENABLE ROW LEVEL SECURITY;
ALTER TABLE employees ENABLE ROW LEVEL SECURITY;
ALTER TABLE api_keys ENABLE ROW LEVEL SECURITY;
ALTER TABLE usage ENABLE ROW LEVEL SECURITY;
ALTER TABLE request_log ENABLE ROW LEVEL SECURITY;
ALTER TABLE cache_store ENABLE ROW LEVEL SECURITY;

-- Allow anon read/write for gateway operations with API Key
CREATE POLICY "Public read teams" ON teams FOR SELECT USING (true);
CREATE POLICY "Public read employees" ON employees FOR SELECT USING (true);
CREATE POLICY "Gateway operations request_log" ON request_log FOR ALL USING (true);
CREATE POLICY "Gateway operations usage" ON usage FOR ALL USING (true);
CREATE POLICY "Gateway operations cache" ON cache_store FOR ALL USING (true);

-- Seed Initial Teams
INSERT INTO teams (id, name, budget_usd, budget_tokens)
VALUES 
    ('support', 'Customer Support', 50.00, 500000),
    ('engineering', 'Core Engineering', 150.00, 2000000),
    ('finance', 'Finance & Ops', 75.00, 750000),
    ('platform', 'Platform & AI Gateway', 500.00, 10000000)
ON CONFLICT (id) DO NOTHING;

-- Seed Demo Employees (passwords: 'alice123', 'bob123', 'carol123', 'admin123')
INSERT INTO employees (id, email, name, role, team_id, app_id, api_key, password_hash)
VALUES
    ('emp-alice', 'alice@company.internal', 'Alice Johnson', 'employee', 'support', 'support-agent', 'sk-gw-alice', '888a75e3a0bf64391e44fcba0fb2b757f5c71db1f3ebcc9a8d29ff705b451fc3'),
    ('emp-bob', 'bob@company.internal', 'Bob Smith', 'employee', 'engineering', 'code-assistant', 'sk-gw-bob', 'e46358c5f0f353ee395d98aeefc0cb687f87a8b3017caef2713f01b1b11e2f3a'),
    ('emp-carol', 'carol@company.internal', 'Carol Davis', 'team_lead', 'finance', 'finance-copilot', 'sk-gw-carol', '3917454f762dd76d3f2347209930fcaae736ecdc3c4ec5f48ec3a0a38217bb41'),
    ('emp-david', 'admin@company.internal', 'David Lee', 'admin', 'platform', 'admin-console', 'sk-gw-admin', 'c7ad44cbad762a5da0a452f9e854fdc1e0e7a52a38015f23f3eab1d80b931dd4')
ON CONFLICT (id) DO NOTHING;
