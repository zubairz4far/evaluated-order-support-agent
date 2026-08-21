from __future__ import annotations

from typing import Protocol

from .models import AgentTrace
from .serialization import trace_from_dict, trace_to_dict


class TraceStore(Protocol):
    def save(self, trace: AgentTrace, *, replay_id: str | None = None) -> None: ...
    def get(self, trace_id: str) -> AgentTrace | None: ...
    def list(self, limit: int = 100) -> list[AgentTrace]: ...


class InMemoryTraceStore:
    def __init__(self) -> None:
        self._rows: dict[str, AgentTrace] = {}
        self._order: list[str] = []

    def save(self, trace: AgentTrace, *, replay_id: str | None = None) -> None:
        if trace.trace_id not in self._rows:
            self._order.append(trace.trace_id)
        self._rows[trace.trace_id] = trace

    def get(self, trace_id: str) -> AgentTrace | None:
        return self._rows.get(trace_id)

    def list(self, limit: int = 100) -> list[AgentTrace]:
        if limit <= 0:
            return []
        ids = self._order[-limit:]
        return [self._rows[trace_id] for trace_id in reversed(ids)]


class PostgresTraceStore:
    """PostgreSQL-backed trace storage.

    psycopg is imported lazily so ToolGuard's core tests and CLI remain
    dependency-light. Install the `observability` extra to use this backend.
    """

    SCHEMA_SQL = """
    CREATE TABLE IF NOT EXISTS toolguard_traces (
        trace_id TEXT PRIMARY KEY,
        replay_id TEXT,
        captured_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        payload JSONB NOT NULL,
        latency_ms DOUBLE PRECISION,
        input_tokens BIGINT,
        output_tokens BIGINT,
        cost_usd DOUBLE PRECISION
    );
    CREATE INDEX IF NOT EXISTS idx_toolguard_traces_captured_at
        ON toolguard_traces (captured_at DESC);
    CREATE INDEX IF NOT EXISTS idx_toolguard_traces_replay_id
        ON toolguard_traces (replay_id) WHERE replay_id IS NOT NULL;
    """

    def __init__(self, dsn: str) -> None:
        self.dsn = dsn

    def _connect(self):
        try:
            import psycopg
        except ImportError as exc:
            raise RuntimeError(
                "PostgresTraceStore requires the observability extra: "
                "pip install -e '.[observability]'"
            ) from exc
        return psycopg.connect(self.dsn)

    def init_schema(self) -> None:
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(self.SCHEMA_SQL)

    def save(self, trace: AgentTrace, *, replay_id: str | None = None) -> None:
        try:
            from psycopg.types.json import Jsonb
        except ImportError as exc:
            raise RuntimeError(
                "PostgresTraceStore requires the observability extra: "
                "pip install -e '.[observability]'"
            ) from exc
        payload = trace_to_dict(trace)
        sql = """
        INSERT INTO toolguard_traces (
            trace_id, replay_id, payload, latency_ms, input_tokens, output_tokens, cost_usd
        ) VALUES (%s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (trace_id) DO UPDATE SET
            replay_id = EXCLUDED.replay_id,
            payload = EXCLUDED.payload,
            latency_ms = EXCLUDED.latency_ms,
            input_tokens = EXCLUDED.input_tokens,
            output_tokens = EXCLUDED.output_tokens,
            cost_usd = EXCLUDED.cost_usd;
        """
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    sql,
                    (
                        trace.trace_id,
                        replay_id,
                        Jsonb(payload),
                        trace.latency_ms,
                        trace.input_tokens,
                        trace.output_tokens,
                        trace.cost_usd,
                    ),
                )

    def get(self, trace_id: str) -> AgentTrace | None:
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT payload FROM toolguard_traces WHERE trace_id = %s",
                    (trace_id,),
                )
                row = cur.fetchone()
        return trace_from_dict(row[0]) if row else None

    def list(self, limit: int = 100) -> list[AgentTrace]:
        if limit <= 0:
            return []
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT payload FROM toolguard_traces ORDER BY captured_at DESC LIMIT %s",
                    (limit,),
                )
                rows = cur.fetchall()
        return [trace_from_dict(row[0]) for row in rows]
