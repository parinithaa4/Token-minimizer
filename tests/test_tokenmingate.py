"""Comprehensive test suite for TokenMinGate multi-layer pipeline and SupaDB."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from llm_gateway.app import create_app
from llm_gateway.config import default_config
from llm_gateway.prompt_pruner import syntax_safe_prune
from llm_gateway.complexity_router import ComplexityRouter


@pytest.fixture
def tmg_client():
    app = create_app(default_config())
    return TestClient(app)


def test_employee_demo_users_and_auth(tmg_client):
    # 1. Fetch demo users
    r = tmg_client.get("/auth/demo-users")
    assert r.status_code == 200
    users = r.json()
    assert len(users) >= 4
    alice = next(u for u in users if u["email"] == "alice@company.internal")
    assert alice["name"] == "Alice Johnson"
    assert alice["team_id"] == "support"
    assert alice["api_key"].startswith("sk-gw-")

    # 2. Login as Alice with correct password
    login_res = tmg_client.post(
        "/auth/login",
        json={"email": "alice@company.internal", "password": "demo"},
    )
    assert login_res.status_code == 200
    user_data = login_res.json()
    assert user_data["email"] == "alice@company.internal"
    assert user_data["api_key"] == alice["api_key"]

    # 3. Login with invalid password
    bad_login = tmg_client.post(
        "/auth/login",
        json={"email": "alice@company.internal", "password": "wrongpassword999"},
    )
    assert bad_login.status_code == 401

    # 4. Register a new employee
    reg_res = tmg_client.post(
        "/auth/register",
        json={
            "name": "Eve Developer",
            "email": "eve@company.internal",
            "password": "eve_secure_pass",
            "team_id": "engineering",
        },
    )
    assert reg_res.status_code == 200
    eve = reg_res.json()
    assert eve["email"] == "eve@company.internal"
    assert eve["team_id"] == "engineering"


def test_syntax_safe_pruning():
    pruner = ComplexityRouter()
    
    # Polite prompt with filler
    polite_prompt = (
        "Hello dear assistant, could you please tell me how to reset the VPN password? "
        "Thank you very much in advance!"
    )
    result = syntax_safe_prune(polite_prompt)
    assert "could you please" not in result.pruned_text.lower()
    assert "thank you" not in result.pruned_text.lower()
    assert "vpn password" in result.pruned_text.lower()
    assert result.tokens_saved > 0
    assert result.reduction_pct > 0

    # Prompt with code block - code must remain untouched
    code_prompt = "Please debug this:\n```python\ndef add(a, b):\n    return a + b\n```\nThanks!"
    c_res = syntax_safe_prune(code_prompt)
    assert "def add(a, b):" in c_res.pruned_text
    assert "```python" in c_res.pruned_text


def test_complexity_router_scoring():
    router = ComplexityRouter()

    # Simple formatting request -> Economy tier
    s_easy = router.score("Fix the formatting on this JSON payload.")
    assert s_easy.tier in ("economy", "balanced")

    # Coding task -> skips Economy tier per Paper Section VII-B
    s_code = router.score("Write a Python function to parse CSV files and return dict.")
    assert s_code.tier in ("balanced", "frontier")

    # Multi-instruction + reasoning + code context -> Frontier tier
    hard_prompt = (
        "class DistributedOptimizer:\n    def __init__(self):\n        pass\n"
        "Derive, prove, analyze, compare and evaluate the trade-offs step-by-step. "
        "Write, build, create, implement, and debug the complete distributed architecture. "
        "Explain implications and justify time complexity sql api json.\n"
        + "Here is the architectural context: " + ("system architecture details and invariants. " * 30)
    )
    s_hard = router.score(hard_prompt)
    assert s_hard.tier == "frontier"


def test_tokenmingate_pipeline_l1_and_l2_cache(tmg_client):
    headers = {"Authorization": "Bearer sk-gw-dev"}

    # Request 1: Fresh prompt
    q1 = "How do I reset my VPN password?"
    r1 = tmg_client.post(
        "/api/chat/pipeline",
        json={"model": "mock-echo", "messages": [{"role": "user", "content": q1}]},
        headers=headers,
    )
    assert r1.status_code == 200
    p1 = r1.json()["pipeline"]
    assert p1["l1_cache"]["hit"] is False
    assert p1["l2_cache"]["hit"] is False
    assert r1.json()["cache_hit"] is False

    # Request 2: Exact same prompt -> triggers L1 Exact Cache
    r2 = tmg_client.post(
        "/api/chat/pipeline",
        json={"model": "mock-echo", "messages": [{"role": "user", "content": q1}]},
        headers=headers,
    )
    assert r2.status_code == 200
    p2 = r2.json()["pipeline"]
    assert p2["l1_cache"]["hit"] is True
    assert r2.json()["cache_hit"] is True
    assert p2["savings"]["cost_usd"] == 0.0

    # Request 3: Paraphrase -> triggers L2 Semantic Cache
    q_para = "can you please tell me: how do i reset my vpn password? thanks!"
    r3 = tmg_client.post(
        "/api/chat/pipeline",
        json={"model": "mock-echo", "messages": [{"role": "user", "content": q_para}]},
        headers=headers,
    )
    assert r3.status_code == 200
    p3 = r3.json()["pipeline"]
    assert p3["l1_cache"]["hit"] is False
    assert p3["l2_cache"]["hit"] is True
    assert r3.json()["cache_hit"] is True
    assert p3["l2_cache"]["similarity"] >= 0.84


def test_l2_human_feedback_updates_research_metrics(tmg_client):
    headers = {"Authorization": "Bearer sk-gw-dev"}

    # Seed an L2 hit
    tmg_client.post(
        "/api/chat/pipeline",
        json={"model": "mock-echo", "messages": [{"role": "user", "content": "Company refund policy for customers"}]},
        headers=headers,
    )
    r_para = tmg_client.post(
        "/api/chat/pipeline",
        json={"model": "mock-echo", "messages": [{"role": "user", "content": "can you tell me: company refund policy for customers?"}]},
        headers=headers,
    )
    log_id = r_para.json()["pipeline"]["log_id"]

    # Submit feedback: mark answer as accurate
    f1 = tmg_client.post("/api/cache/feedback", json={"log_id": log_id, "is_wrong_answer": False})
    assert f1.status_code == 200
    assert f1.json()["success"] is True

    # Check metrics
    m1 = tmg_client.get("/api/metrics/research-summary").json()
    assert "trr_pct" in m1
    assert "trr_net_pct" in m1
    assert "table_1" in m1
    assert "table_2" in m1
    assert "table_3" in m1
    assert len(m1["table_1"]) == 6
    assert len(m1["table_2"]) == 6
    assert len(m1["table_3"]) == 4

    # Mark as inaccurate answer
    f2 = tmg_client.post("/api/cache/feedback", json={"log_id": log_id, "is_wrong_answer": True})
    assert f2.status_code == 200


def test_supadb_and_cache_management_endpoints(tmg_client):
    # 1. SupaDB status
    db_stat = tmg_client.get("/api/db/status").json()
    assert "mode" in db_stat
    assert "records_count" in db_stat

    # 2. Schema SQL
    sql_res = tmg_client.get("/api/db/schema.sql")
    assert sql_res.status_code == 200
    assert "CREATE TABLE IF NOT EXISTS teams" in sql_res.text

    # 3. Cache entries inspection
    entries_res = tmg_client.get("/api/cache/entries")
    assert entries_res.status_code == 200

    # 4. Ledger pagination
    ledger_res = tmg_client.get("/api/ledger?limit=10&offset=0")
    assert ledger_res.status_code == 200
    assert "rows" in ledger_res.json()
    assert "total" in ledger_res.json()
