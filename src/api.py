"""REST API endpoints consumed by the React dashboard."""

import asyncio
import hashlib
import hmac
import json
import logging
import sqlite3
import uuid
from datetime import UTC, datetime
from contextlib import contextmanager
from collections.abc import Iterator

import httpx
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from .agent import YokeruIntegrationAgent
from .db import CallBuffer
from .settings import Settings

log = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["dashboard"])


# ── Response schemas ────────────────────────────────────────────────────

class CallRow(BaseModel):
    correlation_id: str
    patient_id: str
    status: str
    synced: int
    attempts: int
    reason: str | None
    outcome: str | None
    completed_at: str | None
    created_at: str
    updated_at: str


class StatsResponse(BaseModel):
    total: int
    pending: int
    delivered: int
    failed_permanent: int
    completed: int
    failed: int
    no_answer: int


class WebhookEventRow(BaseModel):
    event_id: str
    event_type: str
    received_at: str
    payload: str


class HealthResponse(BaseModel):
    status: str
    db_ok: bool
    breaker_state: str
    pending_count: int


class DispatchResponse(BaseModel):
    correlation_id: str
    message: str


class ReplayResponse(BaseModel):
    replayed: int
    message: str


class SimulateWebhookRequest(BaseModel):
    correlation_id: str
    event_type: str


class SimulateWebhookResponse(BaseModel):
    status: str
    event_id: str
    outcome: str | None = None


# ── Helpers ─────────────────────────────────────────────────────────────

@contextmanager
def _raw_conn(db_path: str) -> Iterator[sqlite3.Connection]:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        conn.execute("PRAGMA journal_mode=WAL")
        yield conn
    finally:
        conn.close()


# ── Route factories (called by webhook.py's create_app) ─────────────────

def register_api_routes(
    app_router: APIRouter,
    buffer: CallBuffer,
    settings: Settings,
    agent: YokeruIntegrationAgent | None = None,
) -> None:
    """Attach all /api/* routes. Called once during app startup."""

    @app_router.get("/calls", response_model=list[CallRow])
    async def list_calls(
        status: str | None = Query(None),
        outcome: str | None = Query(None),
        limit: int = Query(100, le=500),
        offset: int = Query(0, ge=0),
    ) -> list[dict]:
        clauses: list[str] = []
        params: list[str] = []
        if status:
            clauses.append("status = ?")
            params.append(status)
        if outcome:
            clauses.append("outcome = ?")
            params.append(outcome)
        where = (" WHERE " + " AND ".join(clauses)) if clauses else ""
        sql = (
            f"SELECT correlation_id, patient_id, status, synced, attempts, "
            f"reason, outcome, completed_at, created_at, updated_at "
            f"FROM call_buffer{where} ORDER BY created_at DESC LIMIT ? OFFSET ?"
        )
        params.extend([str(limit), str(offset)])
        with _raw_conn(settings.db_path) as conn:
            rows = conn.execute(sql, params).fetchall()
        return [dict(r) for r in rows]

    @app_router.get("/stats", response_model=StatsResponse)
    async def get_stats() -> dict:
        with _raw_conn(settings.db_path) as conn:
            row = conn.execute(
                "SELECT "
                "  COUNT(*) as total, "
                "  SUM(CASE WHEN status='PENDING' THEN 1 ELSE 0 END) as pending, "
                "  SUM(CASE WHEN status='DELIVERED' THEN 1 ELSE 0 END) as delivered, "
                "  SUM(CASE WHEN status='FAILED_PERMANENT' THEN 1 ELSE 0 END) as failed_permanent, "
                "  SUM(CASE WHEN outcome='completed' THEN 1 ELSE 0 END) as completed, "
                "  SUM(CASE WHEN outcome='failed' THEN 1 ELSE 0 END) as failed, "
                "  SUM(CASE WHEN outcome='no_answer' THEN 1 ELSE 0 END) as no_answer "
                "FROM call_buffer"
            ).fetchone()
        return dict(row)

    @app_router.get("/events", response_model=list[WebhookEventRow])
    async def list_events(
        limit: int = Query(50, le=200),
        offset: int = Query(0, ge=0),
    ) -> list[dict]:
        with _raw_conn(settings.db_path) as conn:
            rows = conn.execute(
                "SELECT event_id, event_type, received_at, payload "
                "FROM webhook_events ORDER BY received_at DESC LIMIT ? OFFSET ?",
                (limit, offset),
            ).fetchall()
        return [dict(r) for r in rows]

    @app_router.get("/health", response_model=HealthResponse)
    async def detailed_health() -> dict:
        db_ok = True
        pending_count = 0
        try:
            with _raw_conn(settings.db_path) as conn:
                row = conn.execute(
                    "SELECT COUNT(*) as c FROM call_buffer WHERE status='PENDING'"
                ).fetchone()
                pending_count = row["c"]
        except Exception:
            db_ok = False

        breaker = "unknown"
        if agent and hasattr(agent, "_breaker"):
            breaker = agent._breaker.state.value

        return {
            "status": "ok" if db_ok else "degraded",
            "db_ok": db_ok,
            "breaker_state": breaker,
            "pending_count": pending_count,
        }

    @app_router.post("/dispatch/{patient_id}", response_model=DispatchResponse)
    async def dispatch_call(patient_id: str) -> dict:
        if agent is None:
            raise HTTPException(status_code=503, detail="Agent not initialized")
        try:
            cid = await agent.run_welfare_check(patient_id)
        except Exception as e:
            log.exception(f"Dispatch failed for {patient_id}")
            raise HTTPException(status_code=500, detail=str(e)) from e
        return {"correlation_id": cid, "message": f"Welfare check dispatched for {patient_id}"}

    @app_router.post("/replay", response_model=ReplayResponse)
    async def replay_pending() -> dict:
        if agent is None:
            raise HTTPException(status_code=503, detail="Agent not initialized")
        try:
            n = await agent.replay_pending()
        except Exception as e:
            log.exception("Replay failed")
            raise HTTPException(status_code=500, detail=str(e)) from e
        return {"replayed": n, "message": f"Replayed {n} pending task(s)"}

    @app_router.post("/simulate-webhook", response_model=SimulateWebhookResponse)
    async def simulate_webhook(req: SimulateWebhookRequest) -> dict:
        payload = {
            "event_id": f"sim-{uuid.uuid4().hex[:8]}",
            "event_type": req.event_type,
            "correlation_id": req.correlation_id,
            "occurred_at": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
            "detail": {"simulated": True}
        }
        body = json.dumps(payload).encode("utf-8")
        secret = settings.webhook_signing_secret.encode("utf-8")
        signature = "sha256=" + hmac.new(secret, body, hashlib.sha256).hexdigest()
        
        async with httpx.AsyncClient() as client:
            try:
                resp = await client.post(
                    "http://127.0.0.1:8000/webhooks/yokeru",
                    content=body,
                    headers={
                        "Content-Type": "application/json",
                        "X-Yokeru-Signature": signature
                    }
                )
                resp.raise_for_status()
                return resp.json()
            except httpx.HTTPError as e:
                log.exception("Failed to send simulated webhook")
                raise HTTPException(status_code=500, detail=f"Webhook simulation failed: {e}") from e
