"""Unit and integration tests for Phase 8: NL2SQL Router & Full ACL Enforcement.

Tests exercise:
1. QueryRouter: Precision classification of structured/aggregate vs semantic queries.
2. NL2SQLEngine Sandboxing: Enforces SELECT-only, blocks mutation keywords, forbids
   stacked statements/semicolons, blocks comment injection, and enforces LIMIT caps.
3. Programmatic Row-Level ACL: Injects department-scoped subqueries into SQL without
   relying on LLM memory.
4. Acceptance Criteria: Executes 5 real aggregate benchmark queries against a seeded
   database and verifies exact numerical results and ACL isolation.
5. API Integration: Verifies /v1/ask and /v1/chat handle structured routing transparently.
"""
from __future__ import annotations

from pathlib import Path
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text

from biome_rag.api import create_app
from biome_rag.retrieval.router import (
    NL2SQLEngine,
    QueryRouter,
    RouteDecision,
    StructuredQueryResult,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def memory_db():
    """Create a seeded in-memory SQLite database mimicking enterprise_tickets."""
    engine = create_engine("sqlite:///:memory:")
    with engine.connect() as conn:
        conn.execute(
            text(
                """
                CREATE TABLE enterprise_tickets (
                    ticket_id VARCHAR PRIMARY KEY,
                    department VARCHAR,
                    route_or_system VARCHAR,
                    issue_summary VARCHAR,
                    detailed_description VARCHAR,
                    created_at TIMESTAMP,
                    priority_level VARCHAR,
                    resolved BOOLEAN
                )
                """
            )
        )
        # Seed controlled rows:
        # 10 total:
        # - 4 Logistics (2 Critical, 2 Medium; 3 Resolved, 1 Unresolved)
        # - 3 HR (1 High, 2 Low; 1 Resolved, 2 Unresolved)
        # - 3 Engineering (1 Critical, 2 High; 2 Resolved, 1 Unresolved)
        sample_rows = [
            ("T-1", "Logistics", "SYS-101", "Delivery route blocked", "Details...", "2024-01-01", "Critical", 1),
            ("T-2", "Logistics", "SYS-102", "GPS tracking down", "Details...", "2024-01-02", "Critical", 1),
            ("T-3", "Logistics", "SYS-103", "Fuel card expired", "Details...", "2024-01-03", "Medium", 1),
            ("T-4", "Logistics", "SYS-104", "Warehouse scanner glitch", "Details...", "2024-01-04", "Medium", 0),
            ("T-5", "HR", "SYS-201", "Payroll portal access", "Details...", "2024-01-05", "High", 1),
            ("T-6", "HR", "SYS-202", "Leave request pending", "Details...", "2024-01-06", "Low", 0),
            ("T-7", "HR", "SYS-203", "Badge reprint request", "Details...", "2024-01-07", "Low", 0),
            ("T-8", "Engineering", "SYS-301", "CI runner disk full", "Details...", "2024-01-08", "Critical", 1),
            ("T-9", "Engineering", "SYS-302", "Staging DB connection pool", "Details...", "2024-01-09", "High", 1),
            ("T-10", "Engineering", "SYS-303", "VPN certificate renewal", "Details...", "2024-01-10", "High", 0),
        ]
        for row in sample_rows:
            conn.execute(
                text(
                    """
                    INSERT INTO enterprise_tickets
                    (ticket_id, department, route_or_system, issue_summary, detailed_description, created_at, priority_level, resolved)
                    VALUES (:t_id, :dept, :sys, :sum, :det, :created, :pri, :res)
                    """
                ),
                {
                    "t_id": row[0],
                    "dept": row[1],
                    "sys": row[2],
                    "sum": row[3],
                    "det": row[4],
                    "created": row[5],
                    "pri": row[6],
                    "res": row[7],
                },
            )
        conn.commit()
    return engine


# ---------------------------------------------------------------------------
# 1. QueryRouter Classification Tests
# ---------------------------------------------------------------------------

class TestQueryRouter:
    def setup_method(self):
        self.router = QueryRouter()

    @pytest.mark.parametrize(
        "query",
        [
            "How many total tickets are in the database?",
            "How many tickets belong to the Logistics department?",
            "What is the breakdown of tickets by priority level?",
            "How many tickets are marked as resolved versus unresolved?",
            "Which department has the highest number of Critical priority tickets?",
            "Total number of tickets",
            "count of tickets by department",
            "show breakdown of tickets by resolved status",
            "average resolution count per department",
            "list all tickets where priority is Critical",
        ],
    )
    def test_classifies_structured_queries(self, query: str):
        assert self.router.classify(query) == RouteDecision.STRUCTURED

    @pytest.mark.parametrize(
        "query",
        [
            "How do I reset my company password?",
            "What is the policy for remote work expense reimbursement?",
            "Troubleshooting VPN connection errors on MacOS",
            "Steps to configure multi-factor authentication",
            "Explain the annual leave rollover policy",
            "Who can approve travel expenses?",
        ],
    )
    def test_classifies_semantic_queries(self, query: str):
        assert self.router.classify(query) == RouteDecision.SEMANTIC

    def test_empty_query_defaults_to_semantic(self):
        assert self.router.classify("") == RouteDecision.SEMANTIC
        assert self.router.classify("   ") == RouteDecision.SEMANTIC


# ---------------------------------------------------------------------------
# 2. NL2SQLEngine Sandboxing & Security Tests
# ---------------------------------------------------------------------------

class TestNL2SQLSecuritySandbox:
    def setup_method(self):
        self.engine = NL2SQLEngine()

    def test_valid_select_query_passes_with_limit(self):
        sql = "SELECT * FROM enterprise_tickets"
        validated = self.engine.validate_sql(sql)
        assert validated.startswith("SELECT * FROM enterprise_tickets")
        assert "LIMIT 50" in validated

    def test_oversized_limit_is_capped(self):
        sql = "SELECT * FROM enterprise_tickets LIMIT 500"
        validated = self.engine.validate_sql(sql)
        assert "LIMIT 50" in validated
        assert "500" not in validated

    def test_trailing_semicolon_is_stripped(self):
        sql = "SELECT COUNT(*) FROM enterprise_tickets;"
        validated = self.engine.validate_sql(sql)
        assert not validated.endswith(";")

    @pytest.mark.parametrize(
        "malicious_sql",
        [
            "DROP TABLE enterprise_tickets",
            "DELETE FROM enterprise_tickets WHERE id=1",
            "UPDATE enterprise_tickets SET resolved=1",
            "INSERT INTO enterprise_tickets (ticket_id) VALUES ('evil')",
            "ALTER TABLE enterprise_tickets ADD COLUMN evil VARCHAR",
            "TRUNCATE enterprise_tickets",
            "GRANT ALL PRIVILEGES ON enterprise_tickets TO attacker",
        ],
    )
    def test_mutation_keywords_are_blocked(self, malicious_sql: str):
        with pytest.raises(ValueError, match="Security violation: Forbidden SQL operation"):
            self.engine.validate_sql(malicious_sql)

    def test_stacked_statements_with_semicolon_are_blocked(self):
        stacked_sql = "SELECT * FROM enterprise_tickets; DROP TABLE enterprise_tickets"
        with pytest.raises(ValueError, match="Multiple statements or semicolons are forbidden"):
            self.engine.validate_sql(stacked_sql)

    def test_comment_notations_are_blocked(self):
        with pytest.raises(ValueError, match="SQL comments are forbidden"):
            self.engine.validate_sql("SELECT * FROM enterprise_tickets -- bypass")

        with pytest.raises(ValueError, match="SQL comments are forbidden"):
            self.engine.validate_sql("SELECT * FROM enterprise_tickets /* bypass */")


# ---------------------------------------------------------------------------
# 3. Programmatic Row-Level ACL Tests
# ---------------------------------------------------------------------------

class TestProgrammaticACL:
    def setup_method(self):
        self.engine = NL2SQLEngine(table_name="enterprise_tickets")

    def test_specific_department_scope_injects_subquery(self):
        sql = "SELECT COUNT(*) AS count FROM enterprise_tickets"
        secured = self.engine.apply_acl(sql, requester_scope=["logistics"])
        assert "lower(department) IN ('logistics')" in secured
        assert "FROM (SELECT * FROM enterprise_tickets WHERE lower(department) IN ('logistics')) AS enterprise_tickets" in secured

    def test_multiple_department_scopes(self):
        sql = "SELECT COUNT(*) AS count FROM enterprise_tickets"
        secured = self.engine.apply_acl(sql, requester_scope=["hr", "engineering"])
        assert "lower(department) IN ('hr', 'engineering')" in secured

    def test_wildcard_and_admin_scopes_bypass_injection(self):
        sql = "SELECT COUNT(*) AS count FROM enterprise_tickets"
        assert self.engine.apply_acl(sql, requester_scope=["*"]) == sql
        assert self.engine.apply_acl(sql, requester_scope=["admin"]) == sql
        assert self.engine.apply_acl(sql, requester_scope=None) == sql

    def test_generic_internal_scope_alone_bypasses_injection(self):
        sql = "SELECT COUNT(*) AS count FROM enterprise_tickets"
        assert self.engine.apply_acl(sql, requester_scope=["internal"]) == sql


# ---------------------------------------------------------------------------
# 4. Acceptance Criteria: 5 Core Benchmark Queries on Seeded DB
# ---------------------------------------------------------------------------

class TestAcceptanceQueries:
    def setup_method(self):
        pass

    def test_benchmark_query_1_total_tickets(self, memory_db):
        engine = NL2SQLEngine(engine=memory_db)
        res = engine.execute("How many total tickets are in the database?")
        assert res.row_count == 1
        assert res.rows[0]["total_tickets"] == 10
        assert "10" in res.answer
        assert res.confidence == 1.0

    def test_benchmark_query_2_department_tickets(self, memory_db):
        engine = NL2SQLEngine(engine=memory_db)
        res = engine.execute("How many tickets belong to the Logistics department?")
        assert res.row_count == 1
        assert res.rows[0]["ticket_count"] == 4
        assert "4" in res.answer

    def test_benchmark_query_3_priority_breakdown(self, memory_db):
        engine = NL2SQLEngine(engine=memory_db)
        res = engine.execute("What is the breakdown of tickets by priority level?")
        assert res.row_count >= 3
        priority_map = {r["priority_level"]: r["ticket_count"] for r in res.rows}
        # In sample rows: Critical=3, High=3, Medium=2, Low=2
        assert priority_map["Critical"] == 3
        assert priority_map["High"] == 3
        assert priority_map["Medium"] == 2
        assert priority_map["Low"] == 2
        assert "| Priority Level | Ticket Count |" in res.answer

    def test_benchmark_query_4_resolved_vs_unresolved(self, memory_db):
        engine = NL2SQLEngine(engine=memory_db)
        res = engine.execute("How many tickets are marked as resolved versus unresolved?")
        assert res.row_count == 2
        status_map = {bool(r["resolved"]): r["ticket_count"] for r in res.rows}
        assert status_map[True] == 6
        assert status_map[False] == 4

    def test_benchmark_query_5_highest_critical_department(self, memory_db):
        engine = NL2SQLEngine(engine=memory_db)
        res = engine.execute("Which department has the highest number of Critical priority tickets?")
        assert res.row_count == 1
        assert res.rows[0]["department"] == "Logistics"
        assert res.rows[0]["critical_count"] == 2
        assert "Logistics" in res.answer

    def test_acl_isolation_enforced_on_aggregate_query(self, memory_db):
        engine = NL2SQLEngine(engine=memory_db)
        # Logistics scope user asks for total tickets -> should only see 4, not 10!
        res_logistics = engine.execute(
            "How many total tickets are in the database?",
            requester_scope=["logistics"],
        )
        assert res_logistics.rows[0]["total_tickets"] == 4

        # HR scope user asks for total tickets -> should only see 3, not 10!
        res_hr = engine.execute(
            "How many total tickets are in the database?",
            requester_scope=["hr"],
        )
        assert res_hr.rows[0]["total_tickets"] == 3


# ---------------------------------------------------------------------------
# 5. FastAPI End-to-End Integration Tests
# ---------------------------------------------------------------------------

class TestAPIIntegrationPhase8:
    def test_api_routes_structured_query_to_nl2sql(self, tmp_path: Path):
        app = create_app(raw_dir=tmp_path / "raw", processed_dir=tmp_path / "processed", storage_dir=tmp_path / "index")
        client = TestClient(app)

        resp = client.post(
            "/v1/ask",
            json={"question": "How many total tickets are in the database?"},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["route"] == "structured"
        assert body["sql_query"] is not None
        assert "enterprise_tickets" in body["sql_query"]
        assert len(body["citations"]) > 0

    def test_api_route_override_forces_semantic(self, tmp_path: Path):
        app = create_app(raw_dir=tmp_path / "raw", processed_dir=tmp_path / "processed", storage_dir=tmp_path / "index")
        client = TestClient(app)

        resp = client.post(
            "/v1/ask",
            json={
                "question": "How many total tickets are in the database?",
                "route_override": "semantic",
            },
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["route"] == "semantic"
        assert body["sql_query"] is None

    def test_api_chat_returns_structured_metadata(self, tmp_path: Path):
        app = create_app(raw_dir=tmp_path / "raw", processed_dir=tmp_path / "processed", storage_dir=tmp_path / "index")
        client = TestClient(app)

        resp = client.post(
            "/v1/chat",
            json={
                "message": "What is the breakdown of tickets by priority level?",
                "session_id": "test_session_p8",
            },
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["route"] == "structured"
        assert body["sql_query"] is not None
        assert body["history_length"] >= 2
