from abc import ABC, abstractmethod

import httpx

from ..schemas import YokeruCallTask


class PatientNotReachableError(ValueError):
    """Permanent failure — patient record exists but can't be called (no phone, etc.).
    The agent treats this as non-retryable."""


class BaseEHRAdapter(ABC):
    """Maps a customer EHR's patient representation to a YokeruCallTask.

    Each customer system gets its own subclass. Adapters are responsible for:
      - Issuing the upstream HTTP request to fetch a patient.
      - Translating vendor-specific fields into the canonical YokeruCallTask.
      - Raising PatientNotReachableError for permanent issues (e.g., no phone
        on file) so the agent doesn't waste retries.
    """

    name: str = "base"

    def __init__(self, client: httpx.AsyncClient):
        self._client = client

    @abstractmethod
    async def fetch_patient(self, patient_id: str, correlation_id: str) -> YokeruCallTask: ...
