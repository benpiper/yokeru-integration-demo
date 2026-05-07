import httpx
import pytest
import respx

from src.adapters import CernerFHIRAdapter, PatientNotReachableError


@pytest.mark.asyncio
async def test_maps_fhir_patient_to_yokeru_task(client, settings):
    adapter = CernerFHIRAdapter(client=client, base_url=settings.fhir_base_url)
    with respx.mock(base_url=settings.fhir_base_url, assert_all_called=True) as mock:
        mock.get("/Patient/123").mock(
            return_value=httpx.Response(
                200,
                json={
                    "id": "123",
                    "telecom": [{"system": "phone", "value": "555-1234"}],
                    "communication": [{"language": {"text": "es"}}],
                },
            )
        )
        task = await adapter.fetch_patient("123", "cid-1")

    assert task.patient_id == "123"
    assert task.phone == "555-1234"
    assert task.language == "es"


@pytest.mark.asyncio
async def test_missing_phone_raises_permanent_error(client, settings):
    adapter = CernerFHIRAdapter(client=client, base_url=settings.fhir_base_url)
    with respx.mock(base_url=settings.fhir_base_url) as mock:
        mock.get("/Patient/999").mock(
            return_value=httpx.Response(
                200,
                json={"id": "999", "telecom": [], "communication": []},
            )
        )
        with pytest.raises(PatientNotReachableError):
            await adapter.fetch_patient("999", "cid-2")
