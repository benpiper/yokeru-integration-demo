import hashlib
import hmac
import json
import sqlite3

import pytest
from fastapi.testclient import TestClient

from src.db import CallBuffer
from src.schemas import YokeruCallTask
from src.webhook import create_app


@pytest.fixture
def webhook_buffer(settings):
    return CallBuffer(db_path=settings.db_path)


@pytest.fixture
def webhook_client(settings, webhook_buffer):
    app = create_app(settings=settings, buffer=webhook_buffer)
    return TestClient(app)


def _sign(secret: str, body: bytes) -> str:
    return "sha256=" + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()


def _event_payload(event_id="evt-1", correlation_id="cid-1"):
    return {
        "event_id": event_id,
        "event_type": "call.completed",
        "correlation_id": correlation_id,
        "occurred_at": "2026-05-07T12:00:00Z",
        "detail": {"duration_s": 42},
    }


def test_health_and_metrics(webhook_client):
    assert webhook_client.get("/healthz").status_code == 200
    metrics = webhook_client.get("/metrics")
    assert metrics.status_code == 200
    assert b"yokeru_webhooks_received_total" in metrics.content


def test_rejects_missing_signature(webhook_client):
    resp = webhook_client.post("/webhooks/yokeru", json=_event_payload())
    assert resp.status_code == 401


def test_rejects_bad_signature(webhook_client, settings):
    body = json.dumps(_event_payload()).encode()
    resp = webhook_client.post(
        "/webhooks/yokeru",
        content=body,
        headers={"X-Yokeru-Signature": "sha256=deadbeef", "Content-Type": "application/json"},
    )
    assert resp.status_code == 401


def test_accepts_valid_signature(webhook_client, settings):
    body = json.dumps(_event_payload()).encode()
    resp = webhook_client.post(
        "/webhooks/yokeru",
        content=body,
        headers={
            "X-Yokeru-Signature": _sign(settings.webhook_signing_secret, body),
            "Content-Type": "application/json",
        },
    )
    assert resp.status_code == 202
    assert resp.json()["status"] == "accepted"


def test_idempotent_replay(webhook_client, settings):
    body = json.dumps(_event_payload(event_id="evt-dup")).encode()
    sig = _sign(settings.webhook_signing_secret, body)
    headers = {"X-Yokeru-Signature": sig, "Content-Type": "application/json"}

    first = webhook_client.post("/webhooks/yokeru", content=body, headers=headers)
    second = webhook_client.post("/webhooks/yokeru", content=body, headers=headers)

    assert first.json()["status"] == "accepted"
    assert second.json()["status"] == "duplicate"


def test_rejects_malformed_payload(webhook_client, settings):
    body = b'{"not": "an event"}'
    resp = webhook_client.post(
        "/webhooks/yokeru",
        content=body,
        headers={
            "X-Yokeru-Signature": _sign(settings.webhook_signing_secret, body),
            "Content-Type": "application/json",
        },
    )
    assert resp.status_code == 400


def test_webhook_stamps_outcome_on_originating_call(webhook_client, webhook_buffer, settings):
    """End-to-end: dispatched call → webhook arrives → buffer row reflects outcome."""
    cid = "cid-roundtrip"
    webhook_buffer.insert_pending(cid, YokeruCallTask(patient_id="42", phone="555-0000"))
    webhook_buffer.mark_delivered(cid)

    body = json.dumps(_event_payload(event_id="evt-rt", correlation_id=cid)).encode()
    resp = webhook_client.post(
        "/webhooks/yokeru",
        content=body,
        headers={
            "X-Yokeru-Signature": _sign(settings.webhook_signing_secret, body),
            "Content-Type": "application/json",
        },
    )
    assert resp.status_code == 202
    assert resp.json()["outcome"] == "completed"

    with sqlite3.connect(settings.db_path) as conn:
        row = conn.execute(
            "SELECT outcome, completed_at FROM call_buffer WHERE correlation_id=?",
            (cid,),
        ).fetchone()
    assert row[0] == "completed"
    assert row[1] is not None


def test_webhook_for_unknown_correlation_id_still_accepted(webhook_client, settings):
    """A webhook for a call we never dispatched is logged but doesn't 4xx —
    the upstream isn't at fault; we just have no row to stamp."""
    body = json.dumps(_event_payload(event_id="evt-orphan", correlation_id="nope")).encode()
    resp = webhook_client.post(
        "/webhooks/yokeru",
        content=body,
        headers={
            "X-Yokeru-Signature": _sign(settings.webhook_signing_secret, body),
            "Content-Type": "application/json",
        },
    )
    assert resp.status_code == 202


@pytest.mark.parametrize(
    "event_type,expected_outcome",
    [
        ("call.completed", "completed"),
        ("call.failed", "failed"),
        ("call.no_answer", "no_answer"),
    ],
)
def test_event_type_to_outcome_mapping(
    webhook_client, webhook_buffer, settings, event_type, expected_outcome
):
    cid = f"cid-{event_type}"
    webhook_buffer.insert_pending(cid, YokeruCallTask(patient_id="1", phone="555-1111"))
    webhook_buffer.mark_delivered(cid)

    payload = _event_payload(event_id=f"evt-{event_type}", correlation_id=cid)
    payload["event_type"] = event_type
    body = json.dumps(payload).encode()
    resp = webhook_client.post(
        "/webhooks/yokeru",
        content=body,
        headers={
            "X-Yokeru-Signature": _sign(settings.webhook_signing_secret, body),
            "Content-Type": "application/json",
        },
    )
    assert resp.status_code == 202
    assert resp.json()["outcome"] == expected_outcome
