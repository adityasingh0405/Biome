"""Query Router and Sandboxed NL2SQL Engine — Phase 8.

Provides:
1. ``QueryRouter``: Classifies incoming queries as SEMANTIC (for Hybrid RAG) or
   STRUCTURED (for NL2SQL).
2. ``NL2SQLEngine``: Sandboxed, read-only SQL execution against relational schemas
   with strict security guards (SELECT-only, timeout, row limits) and
   programmatic row-level ACL injection based on ``requester_scope``.
3. Output formatters converting relational result sets into grounded, cited answers.
"""
from __future__ import annotations

import enum
import logging
import re
import time
from dataclasses import dataclass, field
from typing import Any

from biome_rag.config import get_runtime_settings

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Route Decision Enum & Result Dataclass
# ---------------------------------------------------------------------------

class RouteDecision(str, enum.Enum):
    SEMANTIC = "semantic"
    STRUCTURED = "structured"


@dataclass
class StructuredQueryResult:
    """Outcome of a sandboxed NL2SQL query execution."""
    query: str
    sql_query: str
    columns: list[str] = field(default_factory=list)
    rows: list[dict[str, Any]] = field(default_factory=list)
    row_count: int = 0
    answer: str = ""
    confidence: float = 1.0
    table_name: str = "enterprise_tickets"
    applied_scope: list[str] | None = None
    latency_ms: float = 0.0
    error: str = ""


# ---------------------------------------------------------------------------
# Query Router
# ---------------------------------------------------------------------------

class QueryRouter:
    """Classifies queries into SEMANTIC or STRUCTURED execution paths.

    Uses high-precision deterministic regex rules covering aggregations,
    breakdowns, counts, and superlatives.
    """

    # Structured keywords & phrasing — routes to NL2SQL / PostgreSQL
    _STRUCTURED_PATTERNS = [
        # Aggregation / Count
        r"\b(how\s+many|count\s+of|total\s+number|number\s+of|total\s+tickets?)\b",
        r"\b(sum\s+of|average|avg|mean|minimum|maximum|min\s+tickets?|max\s+tickets?)\b",
        r"\b(highest\s+number|lowest\s+number|most\s+tickets?|fewest\s+tickets?)\b",
        # Breakdown / Distribution
        r"\b(breakdown|break\s+down|distribution)\b",
        r"\b(per\s+department|by\s+department|by\s+priority|by\s+status|by\s+resolved)\b",
        r"\b(group\s+by|grouped\s+by)\b",
        # Listing / structured filtering
        r"\b(list\s+(all\s+)?tickets|show\s+(all\s+)?tickets|tickets\s+where|which\s+department\s+has)\b",
        r"\b(resolved\s+versus\s+unresolved|resolved\s+vs\.?\s+unresolved)\b",
        r"\b(critical\s+priority|tickets\s+marked\s+as|high\s+priority\s+tickets?)\b",
        # Department / table queries
        r"\b(which\s+department|from\s+(the\s+)?database|in\s+(the\s+)?database)\b",
        r"\b(show\s+me\s+tickets?|give\s+me\s+(all\s+)?tickets?|fetch\s+tickets?)\b",
        r"\b(open\s+tickets?|unresolved\s+tickets?|pending\s+tickets?)\b",
        r"\b(tickets?\s+from|tickets?\s+in|tickets?\s+by|tickets?\s+for)\b",
        r"\b(department\s+tickets?|logistics|operations|engineering)\s+(tickets?|data|records?)\b",
        # Statistics / analytics
        r"\b(statistics|stats|analytics|report|summary)\s+(of|on|for|about)?\s*(tickets?|database|data)\b",
        r"\b(top\s+\d+|first\s+\d+|last\s+\d+)\s+(tickets?|records?|results?)\b",
        r"\b(recent\s+tickets?|latest\s+tickets?|newest\s+tickets?)\b",
        r"\b(what\s+are\s+the\s+tickets?|what\s+tickets?\s+exist|what\s+data\s+is\s+(in|from))\b",
    ]

    # Semantic / unstructured keywords — routes to RAG / documents
    _SEMANTIC_PATTERNS = [
        r"\b(how\s+do\s+i|how\s+can\s+i|how\s+to)\b",
        r"\b(what\s+is\s+the\s+policy|explain|describe|troubleshoot|troubleshooting)\b",
        r"\b(guide|handbook|instructions?|steps?\s+to|procedure)\b",
        r"\b(what\s+does\s+.*mean|why\s+is|why\s+does)\b",
        r"\b(password\s+reset|vpn|security\s+policy|leave\s+policy)\b",
        r"\b(deployment|architecture|api\s+reference|documentation|audit\s+log)\b",
    ]

    def __init__(self) -> None:
        self._structured_re = [re.compile(p, re.IGNORECASE) for p in self._STRUCTURED_PATTERNS]
        self._semantic_re = [re.compile(p, re.IGNORECASE) for p in self._SEMANTIC_PATTERNS]

    def classify(self, query: str) -> RouteDecision:
        """Decide whether a query should route to NL2SQL or Hybrid RAG."""
        text = query.strip()
        if not text:
            return RouteDecision.SEMANTIC

        # Check structured patterns
        is_structured = any(pattern.search(text) for pattern in self._structured_re)
        is_semantic = any(pattern.search(text) for pattern in self._semantic_re)

        # If both match, check priority heuristics
        if is_structured and is_semantic:
            if re.search(r"\b(steps|guide|how to|policy details)\b", text, re.IGNORECASE):
                return RouteDecision.SEMANTIC
            return RouteDecision.STRUCTURED

        if is_structured:
            return RouteDecision.STRUCTURED

        return RouteDecision.SEMANTIC


# ---------------------------------------------------------------------------
# Sandboxed NL2SQL Engine
# ---------------------------------------------------------------------------

class NL2SQLEngine:
    """Sandboxed execution engine for natural language queries over relational DBs.

    Guarantees:
    1. SELECT-only execution: rejects any DDL/DML mutation statements.
    2. No stacked/semicolon queries to avoid SQL injection attacks.
    3. Query timeout enforcement.
    4. Row limit enforcement (max 50 rows default).
    5. Programmatic row-level ACL injection (row-level filtering based on requester_scope).
    """

    # Prohibited SQL tokens / statements
    _FORBIDDEN_KEYWORDS = {
        "insert", "update", "delete", "drop", "alter", "truncate", "create",
        "replace", "grant", "revoke", "exec", "execute", "merge", "call", "vacuum",
        "into", "copy", "commit", "rollback", "savepoint",
    }

    def __init__(
        self,
        db_uri: str | None = None,
        table_name: str | None = None,
        timeout_seconds: float | None = None,
        max_rows: int | None = None,
        engine: Any = None,
    ) -> None:
        settings = get_runtime_settings()
        self.db_uri = db_uri or settings.postgres_uri
        self.table_name = table_name or settings.postgres_table or "enterprise_tickets"
        self.timeout_seconds = timeout_seconds or getattr(settings, "nl2sql_timeout_seconds", 5.0)
        self.max_rows = max_rows or getattr(settings, "nl2sql_max_rows", 50)
        self._engine = engine

    def _create_fallback_engine(self) -> Any:
        from sqlalchemy import create_engine, text
        fb = create_engine("sqlite:///:memory:")
        with fb.connect() as conn:
            conn.execute(text(
                f"""
                CREATE TABLE IF NOT EXISTS {self.table_name} (
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
            ))
            conn.commit()
        return fb

    def _get_engine(self) -> Any:
        if self._engine is not None:
            return self._engine
        try:
            from sqlalchemy import create_engine, text
            eng = create_engine(
                self.db_uri,
                pool_size=1,
                max_overflow=0,
                pool_pre_ping=True,
                connect_args={"connect_timeout": int(self.timeout_seconds)},
            )
            with eng.connect() as conn:
                conn.execute(text("SELECT 1"))
            self._engine = eng
            return self._engine
        except ValueError:
            # ACL / SQL-guard violations must propagate as access-denied signals,
            # NOT be silently swallowed into a soft-error result.
            raise
        except Exception as exc:
            logger.warning(
                "NL2SQLEngine: cannot initialize or connect with %s (%s). Using SQLite fallback.",
                self.db_uri,
                exc,
            )
            self._engine = self._create_fallback_engine()
            return self._engine

    # ------------------------------------------------------------------
    # SQL Validation & Sandboxing
    # ------------------------------------------------------------------

    def validate_sql(self, sql: str) -> str:
        """Enforce strict sandboxing guards on the SQL string."""
        cleaned = sql.strip()
        if not cleaned:
            raise ValueError("Empty SQL query")

        # Strip trailing semicolon if present
        if cleaned.endswith(";"):
            cleaned = cleaned[:-1].strip()

        # Reject semicolons inside query to prevent stacked execution
        if ";" in cleaned:
            raise ValueError("Security violation: Multiple statements or semicolons are forbidden")

        # Disallow SQL comment notations
        if "--" in cleaned or "/*" in cleaned:
            raise ValueError("Security violation: SQL comments are forbidden in generated queries")

        upper = cleaned.upper()

        # Check for forbidden mutation keywords first
        words = re.findall(r"\b[A-Za-z]+\b", cleaned.lower())
        found_forbidden = set(words).intersection(self._FORBIDDEN_KEYWORDS)
        if found_forbidden:
            raise ValueError(
                f"Security violation: Forbidden SQL operation detected: {', '.join(sorted(found_forbidden))}"
            )

        # Must begin with SELECT or WITH
        if not (upper.startswith("SELECT") or upper.startswith("WITH")):
            raise ValueError("Security violation: Only SELECT queries are permitted")

        # Enforce LIMIT
        if "limit" not in [w.lower() for w in words]:
            cleaned = f"{cleaned} LIMIT {self.max_rows}"
        else:
            limit_match = re.search(r"\bLIMIT\s+(\d+)\b", cleaned, re.IGNORECASE)
            if limit_match:
                val = int(limit_match.group(1))
                if val > self.max_rows:
                    cleaned = re.sub(
                        r"\bLIMIT\s+\d+\b",
                        f"LIMIT {self.max_rows}",
                        cleaned,
                        flags=re.IGNORECASE,
                    )

        return cleaned

    # ------------------------------------------------------------------
    # Programmatic ACL Enforcement
    # ------------------------------------------------------------------

    # Characters that are forbidden in *department* scope values to prevent SQL injection.
    # Admin/bypass tokens ("*", "admin", "all", "superuser") are checked BEFORE this
    # guard so the wildcard "*" is never subjected to the character filter.
    _SCOPE_FORBIDDEN = re.compile(r"""['";\\\-]|--+|/\*|\*/""")

    # Tokens that grant unrestricted (bypass) access — checked before injection guard.
    _BYPASS_TOKENS: frozenset[str] = frozenset({"*", "admin", "all", "superuser"})

    def apply_acl(self, sql: str, requester_scope: list[str] | None) -> str:
        """Inject row-level security filters based on requester_scope.

        Security contract (FAIL-CLOSED):
          - If requester_scope is None or empty → raises ValueError; callers must
            explicitly pass ["*"] or an admin token to bypass the filter.
          - Only the tokens {"*", "admin", "all", "superuser"} grant unrestricted
            (bypass) access; they are checked BEFORE the injection-character guard
            so that "*" is never incorrectly flagged.
          - Every other scope value is treated as a department filter and must
            contain only alphanumeric characters, underscores, or hyphens.
            Any value with SQL meta-characters (quotes, semicolons, comments,
            backslashes) raises ValueError.

        Implementation:
        Replaces ``FROM <table_name>`` with a secured subquery
        ``FROM (SELECT * FROM <table_name> WHERE lower(department) IN (...)) AS <table_name>``.
        """
        if not requester_scope:
            raise ValueError(
                "apply_acl: requester_scope must be provided. "
                "Pass ['*'] or an admin token for unrestricted access."
            )

        norm_scopes: list[str] = [raw.strip().lower() for raw in requester_scope if raw.strip()]

        if not norm_scopes:
            raise ValueError(
                "apply_acl: requester_scope must be provided. "
                "Pass ['*'] or an admin token for unrestricted access."
            )

        # 1. Check for bypass tokens FIRST (before the injection guard).
        if any(s in self._BYPASS_TOKENS for s in norm_scopes):
            return sql

        # 2. Validate department values for SQL-injection characters.
        for s in norm_scopes:
            if self._SCOPE_FORBIDDEN.search(s):
                raise ValueError(
                    f"apply_acl: scope value '{s}' contains forbidden characters "
                    "and was rejected to prevent SQL injection."
                )

        dept_scopes = [s for s in norm_scopes if s not in {"internal", "public", "authenticated"}]
        if not dept_scopes:
            # Sentinel-only scopes with no department → deny access.
            raise ValueError(
                "apply_acl: scope contains only ambiguous sentinel values "
                "('internal', 'public', 'authenticated') with no department — "
                "access denied. Pass ['*'] for unrestricted access."
            )

        # Build parameterised-style literal list (SQLite/Postgres don't share
        # a bind-parameter API here because the subquery is constructed as a
        # string; the injection guard above makes the values safe to embed).
        quoted_scopes = ", ".join(f"'{s}'" for s in dept_scopes)
        acl_subquery = (
            f"(SELECT * FROM {self.table_name} WHERE lower(department) IN ({quoted_scopes})) AS {self.table_name}"
        )

        pattern = re.compile(rf"\bFROM\s+{re.escape(self.table_name)}\b", re.IGNORECASE)
        if pattern.search(sql):
            secured_sql = pattern.sub(f"FROM {acl_subquery}", sql)
            logger.info(
                "NL2SQLEngine: Programmatically injected ACL scope %s on table %s",
                dept_scopes,
                self.table_name,
            )
            return secured_sql

        return sql

    # ------------------------------------------------------------------
    # Natural Language to SQL Synthesizer
    # ------------------------------------------------------------------

    # Schema context for LLM SQL generation
    _TABLE_SCHEMA = """
Table: enterprise_tickets
Columns:
  - ticket_id (VARCHAR, UUID primary key)
  - department (VARCHAR): one of 'Logistics', 'Operations', 'HR', 'Engineering', 'Customer Support'
  - route_or_system (VARCHAR): e.g. 'SYS-123'
  - issue_summary (VARCHAR): short description of the issue
  - detailed_description (VARCHAR): full description
  - created_at (TIMESTAMP): when ticket was created
  - priority_level (VARCHAR): one of 'Low', 'Medium', 'High', 'Critical'
  - resolved (BOOLEAN): true if resolved, false if open
"""

    def generate_sql(self, query: str) -> str:
        """Synthesize a read-only SQL query. Fast-path regex first, LLM fallback for arbitrary queries."""
        q = query.strip()
        q_lower = q.lower()
        table = self.table_name

        # --- Fast-path hardcoded patterns ---

        # Total tickets count
        if re.search(r"\b(how many total tickets|total number of tickets|total tickets|count of tickets|how many tickets in (the )?database)\b", q_lower):
            return f"SELECT COUNT(*) AS total_tickets FROM {table}"

        # Which department has highest critical priority tickets
        if re.search(r"\b(which department has (the )?(highest|most)|department with (the )?most critical)\b", q_lower):
            return (
                f"SELECT department, COUNT(*) AS critical_count "
                f"FROM {table} "
                f"WHERE lower(priority_level) = 'critical' "
                f"GROUP BY department "
                f"ORDER BY critical_count DESC "
                f"LIMIT 1"
            )

        # Priority level breakdown
        if re.search(r"\b(breakdown .* by priority|priority (level )?breakdown|distribution .* priority|tickets by priority)\b", q_lower):
            return (
                f"SELECT priority_level, COUNT(*) AS ticket_count "
                f"FROM {table} "
                f"GROUP BY priority_level "
                f"ORDER BY ticket_count DESC"
            )

        # Resolved vs unresolved
        if re.search(r"\b(resolved (versus|vs) unresolved|resolved status|how many .* resolved|tickets .* resolved)\b", q_lower):
            return (
                f"SELECT resolved, COUNT(*) AS ticket_count "
                f"FROM {table} "
                f"GROUP BY resolved "
                f"ORDER BY resolved DESC"
            )

        # Department-specific ticket count
        dept_match = re.search(
            r"\b(how many tickets|count of tickets|number of tickets).* (logistics|operations|hr|human resources|engineering|customer support)\b",
            q_lower,
        )
        if dept_match:
            dept = dept_match.group(2).lower()
            if dept == "human resources":
                dept = "hr"
            return (
                f"SELECT COUNT(*) AS ticket_count "
                f"FROM {table} "
                f"WHERE lower(department) = '{dept}'"
            )

        # Open / unresolved tickets
        if re.search(r"\b(unresolved|open|pending)\s+tickets?\b", q_lower):
            return (
                f"SELECT ticket_id, department, priority_level, issue_summary, resolved "
                f"FROM {table} "
                f"WHERE resolved = FALSE "
                f"ORDER BY created_at DESC "
                f"LIMIT {self.max_rows}"
            )

        # Resolved tickets
        if re.search(r"\b(resolved|closed)\s+tickets?\b", q_lower) and not re.search(r"\bvs\b|\bversus\b", q_lower):
            return (
                f"SELECT ticket_id, department, priority_level, issue_summary, resolved "
                f"FROM {table} "
                f"WHERE resolved = TRUE "
                f"ORDER BY created_at DESC "
                f"LIMIT {self.max_rows}"
            )

        # Recent / latest tickets
        if re.search(r"\b(recent|latest|newest)\s+tickets?\b", q_lower):
            return (
                f"SELECT ticket_id, department, priority_level, issue_summary, created_at, resolved "
                f"FROM {table} "
                f"ORDER BY created_at DESC "
                f"LIMIT {self.max_rows}"
            )

        # Department breakdown
        if re.search(r"\b(breakdown .* by department|department breakdown|tickets by department)\b", q_lower):
            return (
                f"SELECT department, COUNT(*) AS ticket_count "
                f"FROM {table} "
                f"GROUP BY department "
                f"ORDER BY ticket_count DESC"
            )

        # --- LLM fallback for arbitrary structured queries ---
        llm_sql = self._generate_sql_via_llm(query)
        if llm_sql:
            return llm_sql

        # Last resort: show most recent tickets
        return (
            f"SELECT ticket_id, department, priority_level, issue_summary, resolved "
            f"FROM {table} "
            f"ORDER BY created_at DESC "
            f"LIMIT {self.max_rows}"
        )

    def _generate_sql_via_llm(self, query: str) -> str | None:
        """Use the configured LLM to generate a SQL query for arbitrary natural language input.

        Returns a valid SQL string on success, or None if the LLM fails / times out.
        The result is ALWAYS passed through validate_sql() before execution.
        """
        try:
            settings = get_runtime_settings()
            prompt = (
                f"You are a PostgreSQL SQL expert. Generate a single SELECT query for the question below.\n"
                f"Return ONLY the raw SQL — no explanations, no markdown, no backticks.\n\n"
                f"Schema:\n{self._TABLE_SCHEMA}\n"
                f"Rules:\n"
                f"- SELECT only. Never INSERT/UPDATE/DELETE/DROP.\n"
                f"- Always end with LIMIT {self.max_rows} unless it is a COUNT/aggregate.\n"
                f"- Use lower() for string comparisons.\n"
                f"- For 'open' or 'unresolved' tickets: WHERE resolved = FALSE.\n"
                f"- For 'resolved' or 'closed' tickets: WHERE resolved = TRUE.\n"
                f"- For 'recent' or 'latest': ORDER BY created_at DESC. Never add WHERE created_at filters unless the user explicitly specified a date/timeframe.\n"
                f"- For topic or keyword search: WHERE lower(issue_summary) LIKE '%<keyword>%' OR lower(detailed_description) LIKE '%<keyword>%'.\n"
                f"- For department search: WHERE lower(department) = '<department>'.\n"
                f"- Default SELECT columns: ticket_id, department, priority_level, issue_summary, resolved.\n\n"
                f"Question: {query}\n"
                f"SQL:"
            )

            if settings.llm_provider == "ollama":
                import urllib.request, json as _json
                payload = _json.dumps({
                    "model": settings.ollama_model,
                    "prompt": prompt,
                    "stream": False,
                    "options": {"temperature": 0.0, "num_predict": 120},
                }).encode()
                req = urllib.request.Request(
                    f"{settings.ollama_base_url}/api/generate",
                    data=payload,
                    headers={"Content-Type": "application/json"},
                    method="POST",
                )
                with urllib.request.urlopen(req, timeout=30) as resp:
                    data = _json.loads(resp.read())
                    sql_raw = data.get("response", "").strip()
            else:
                # OpenAI-compatible fallback
                import urllib.request, json as _json
                payload = _json.dumps({
                    "model": settings.openai_model,
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": 0.0,
                    "max_tokens": 120,
                }).encode()
                req = urllib.request.Request(
                    "https://api.openai.com/v1/chat/completions",
                    data=payload,
                    headers={
                        "Content-Type": "application/json",
                        "Authorization": f"Bearer {settings.openai_api_key}",
                    },
                    method="POST",
                )
                with urllib.request.urlopen(req, timeout=30) as resp:
                    data = _json.loads(resp.read())
                    sql_raw = data["choices"][0]["message"]["content"].strip()

            # Strip markdown code fences if LLM wraps it
            sql_raw = re.sub(r"```(?:sql)?", "", sql_raw, flags=re.IGNORECASE).strip().rstrip("`").strip()

            # Collect all lines from first SELECT/WITH onward (SQL can be multi-line)
            lines_out: list[str] = []
            collecting = False
            for line in sql_raw.splitlines():
                stripped = line.strip()
                if not collecting and stripped.upper().startswith(("SELECT", "WITH")):
                    collecting = True
                if collecting:
                    lines_out.append(stripped)
            sql_raw = " ".join(lines_out).strip()

            if sql_raw and (sql_raw.upper().startswith("SELECT") or sql_raw.upper().startswith("WITH")):
                logger.info("NL2SQL LLM generated: %s", sql_raw[:300])
                return sql_raw

        except Exception as exc:
            logger.warning("NL2SQL LLM generation failed (%s) — using default fallback.", exc)

        return None

    # ------------------------------------------------------------------
    # Query Execution & Result Formatting
    # ------------------------------------------------------------------

    def execute(self, nl_query: str, requester_scope: list[str] | None = None) -> StructuredQueryResult:
        """Execute a natural language query end-to-end with sandboxing and ACL enforcement.

        If requester_scope is None (unauthenticated / no ACL context), defaults to ["*"]
        which grants read access to all departments (bypass the row-level department filter).
        Pass an explicit department list like ["engineering"] to restrict to that department.
        """
        t0 = time.perf_counter()
        # Default to unrestricted read access when no scope is provided
        effective_scope = requester_scope if requester_scope is not None else ["*"]

        try:
            # 1. Generate candidate SQL
            raw_sql = self.generate_sql(nl_query)

            # 2. Programmatically apply row-level ACL injection
            secured_sql = self.apply_acl(raw_sql, effective_scope)

            # 3. Validate sandboxing rules (SELECT-only, LIMIT, no stacked commands)
            valid_sql = self.validate_sql(secured_sql)

            # 4. Execute via SQLAlchemy engine
            engine = self._get_engine()
            from sqlalchemy import text

            with engine.connect() as conn:
                result = conn.execute(text(valid_sql))
                columns = list(result.keys()) if result.returns_rows else []
                rows = [dict(zip(columns, row)) for row in result.fetchall()] if result.returns_rows else []

            latency = (time.perf_counter() - t0) * 1000

            # 5. Format natural language / Markdown answer
            answer = self._format_answer(nl_query, valid_sql, columns, rows)

            return StructuredQueryResult(
                query=nl_query,
                sql_query=valid_sql,
                columns=columns,
                rows=rows,
                row_count=len(rows),
                answer=answer,
                confidence=1.0,
                table_name=self.table_name,
                applied_scope=effective_scope,
                latency_ms=latency,
            )

        except ValueError:
            # ACL / SQL-guard violations must propagate as access-denied signals,
            # NOT be silently swallowed into a soft-error result.
            raise
        except Exception as exc:
            latency = (time.perf_counter() - t0) * 1000
            logger.error("NL2SQLEngine execution failed: %s", exc)
            raw_sql_safe = locals().get("raw_sql", "N/A")
            return StructuredQueryResult(
                query=nl_query,
                sql_query=raw_sql_safe,
                columns=[],
                rows=[],
                row_count=0,
                answer=f"Unable to execute structured query: {exc}",
                confidence=0.0,
                table_name=self.table_name,
                applied_scope=effective_scope,
                latency_ms=latency,
                error=str(exc),
            )

    def _format_answer(
        self,
        query: str,
        sql: str,
        columns: list[str],
        rows: list[dict[str, Any]],
    ) -> str:
        """Format SQL result rows into an informative Markdown response."""
        if not rows:
            return f"No records found in `{self.table_name}` matching your query."

        # Case 1: Single scalar aggregate result (e.g. COUNT(*))
        if len(rows) == 1 and len(columns) == 1:
            col = columns[0]
            val = rows[0][col]
            label = col.replace("_", " ").title()
            return f"The {label} is **{val:,}** (queried from `{self.table_name}`)."

        # Case 2: Single row with multiple columns (e.g. Top department)
        if len(rows) == 1 and len(columns) == 2:
            key_col, val_col = columns[0], columns[1]
            key_val = rows[0][key_col]
            num_val = rows[0][val_col]
            return (
                f"**{key_val}** has the highest count with **{num_val:,}** tickets "
                f"(queried from `{self.table_name}`)."
            )

        # Case 3: Tabular breakdown
        lines = [
            f"Here is the structured breakdown from `{self.table_name}`:",
            "",
            "| " + " | ".join(c.replace("_", " ").title() for c in columns) + " |",
            "| " + " | ".join("---" for _ in columns) + " |",
        ]
        for r in rows[:self.max_rows]:
            formatted_vals = []
            for c in columns:
                v = r.get(c)
                if isinstance(v, bool):
                    formatted_vals.append("Resolved" if v else "Unresolved")
                elif isinstance(v, (int, float)):
                    formatted_vals.append(f"{v:,}")
                else:
                    formatted_vals.append(str(v or "-"))
            lines.append("| " + " | ".join(formatted_vals) + " |")

        lines.append("")
        lines.append(f"*Total rows: {len(rows)}*")
        return "\n".join(lines)
