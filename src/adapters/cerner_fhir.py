import logging

from ..schemas import YokeruCallTask
from .base import BaseEHRAdapter, PatientNotReachableError

log = logging.getLogger(__name__)


class CernerFHIRAdapter(BaseEHRAdapter):
    """Adapter for the Cerner FHIR R4 API."""

    name = "cerner_fhir"

    def __init__(self, client, base_url: str):
        super().__init__(client)
        self._base_url = base_url.rstrip("/")

    async def fetch_patient(self, patient_id: str, correlation_id: str) -> YokeruCallTask:
        log.info(
            "Fetching patient from Cerner FHIR",
            extra={"correlation_id": correlation_id},
        )
        resp = await self._client.get(
            f"{self._base_url}/Patient/{patient_id}",
            headers={"Accept": "application/fhir+json"},
        )
        resp.raise_for_status()
        data = resp.json()

        phone = next(
            (t.get("value") for t in data.get("telecom", []) if t.get("system") == "phone"),
            None,
        )
        if not phone:
            raise PatientNotReachableError(f"Patient {patient_id} has no phone number on file")

        language = data.get("communication", [{}])[0].get("language", {}).get("text", "en")

        task = YokeruCallTask(patient_id=data["id"], phone=phone, language=language)
        log.info(
            "Mapped Cerner patient to Yokeru schema",
            extra={"correlation_id": correlation_id},
        )
        return task
