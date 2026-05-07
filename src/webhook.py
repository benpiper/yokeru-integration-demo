import hashlib
import hmac
import json
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request, status
from fastapi.responses import PlainTextResponse, Response
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest
from pydantic import ValidationError

from .db import EVENT_TYPE_TO_OUTCOME, CallBuffer
from .logging_setup import configure_logging
from .metrics import REGISTRY, webhooks_received_total
from .schemas import WebhookEvent
from .settings import Settings, get_settings

log = logging.getLogger(__name__)


def _verify_signature(secret: str, body: bytes, provided: str | None) -> bool:
    if not provided:
        return False
    expected = hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()
    candidate = provided.removeprefix("sha256=")
    return hmac.compare_digest(expected, candidate)


def create_app(settings: Settings | None = None, buffer: CallBuffer | None = None) -> FastAPI:
    @asynccontextmanager
    async def lifespan(_: FastAPI):
        configure_logging()
        yield

    app = FastAPI(title="Yokeru Integration Webhook", lifespan=lifespan)
    app.state.settings = settings or get_settings()
    app.state.buffer = buffer or CallBuffer(db_path=app.state.settings.db_path)

    @app.get("/healthz", response_class=PlainTextResponse)
    async def healthz() -> str:
        return "ok"

    @app.get("/metrics")
    async def metrics() -> Response:
        return Response(content=generate_latest(REGISTRY), media_type=CONTENT_TYPE_LATEST)

    @app.post("/webhooks/yokeru", status_code=status.HTTP_202_ACCEPTED)
    async def yokeru_webhook(request: Request) -> dict:
        body = await request.body()
        signature = request.headers.get("X-Yokeru-Signature")
        if not _verify_signature(app.state.settings.webhook_signing_secret, body, signature):
            webhooks_received_total.labels(kind="invalid_signature").inc()
            log.warning("Rejected webhook with invalid signature")
            raise HTTPException(status_code=401, detail="invalid signature")

        try:
            event = WebhookEvent.model_validate_json(body)
        except ValidationError as e:
            log.warning(f"Rejected malformed webhook: {e}")
            raise HTTPException(status_code=400, detail="invalid payload") from e

        is_new = app.state.buffer.record_webhook(
            event_id=event.event_id,
            event_type=event.event_type,
            payload=json.dumps(event.model_dump(mode="json")),
        )
        if not is_new:
            webhooks_received_total.labels(kind="duplicate").inc()
            log.info(
                f"Duplicate webhook {event.event_id} — already processed",
                extra={"correlation_id": event.correlation_id},
            )
            return {"status": "duplicate", "event_id": event.event_id}

        outcome = EVENT_TYPE_TO_OUTCOME[event.event_type]
        matched = app.state.buffer.record_call_outcome(event.correlation_id, outcome)
        if not matched:
            log.warning(
                f"Webhook {event.event_id} references unknown correlation_id "
                f"{event.correlation_id} — recorded event but no buffer row to update",
                extra={"correlation_id": event.correlation_id},
            )

        webhooks_received_total.labels(kind="new").inc()
        log.info(
            f"Accepted webhook {event.event_type} for {event.correlation_id} (outcome={outcome})",
            extra={"correlation_id": event.correlation_id},
        )
        return {"status": "accepted", "event_id": event.event_id, "outcome": outcome}

    return app


app = create_app()
