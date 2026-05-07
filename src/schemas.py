from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class YokeruCallTask(BaseModel):
    """Validated payload sent to the Yokeru voice-agent dispatch API."""

    patient_id: str
    phone: str
    language: str = "en"
    reason: str = "Welfare Check"


TaskStatus = Literal["PENDING", "DELIVERED", "FAILED_PERMANENT"]


class WebhookEvent(BaseModel):
    """Inbound event from Yokeru (e.g., call completed/failed)."""

    event_id: str = Field(description="Unique event UUID — used as the idempotency key.")
    event_type: Literal["call.completed", "call.failed", "call.no_answer"]
    correlation_id: str = Field(description="Correlation ID we sent on the original call.")
    occurred_at: datetime
    detail: dict = Field(default_factory=dict)
