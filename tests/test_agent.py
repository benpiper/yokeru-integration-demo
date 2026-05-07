import httpx
import pytest
import respx

from src.schemas import YokeruCallTask


def _patient_response(pid="123", phone="555-1234"):
    return httpx.Response(
        200,
        json={
            "id": pid,
            "telecom": [{"system": "phone", "value": phone}],
            "communication": [{"language": {"text": "en"}}],
        },
    )


@pytest.mark.asyncio
async def test_happy_path_buffers_then_marks_delivered(agent, settings, buffer):
    with respx.mock(assert_all_called=True) as mock:
        mock.get(f"{settings.fhir_base_url}/Patient/123").mock(return_value=_patient_response())
        post = mock.post(settings.yokeru_api_url).mock(
            return_value=httpx.Response(202, json={"ok": True})
        )

        cid = await agent.run_welfare_check("123")

    # Idempotency-Key matches the correlation_id
    assert post.calls.last.request.headers["Idempotency-Key"] == cid

    rows = buffer.list_unsynced()
    assert rows == []  # everything DELIVERED


@pytest.mark.asyncio
async def test_transient_5xx_then_success_retries(agent, settings, buffer):
    with respx.mock() as mock:
        mock.get(f"{settings.fhir_base_url}/Patient/123").mock(return_value=_patient_response())
        route = mock.post(settings.yokeru_api_url).mock(
            side_effect=[
                httpx.Response(503),
                httpx.Response(503),
                httpx.Response(202, json={"ok": True}),
            ]
        )
        await agent.run_welfare_check("123")

    assert route.call_count == 3
    assert buffer.list_unsynced() == []


@pytest.mark.asyncio
async def test_4xx_marks_permanent_failure_no_retry(agent, settings, buffer):
    with respx.mock() as mock:
        mock.get(f"{settings.fhir_base_url}/Patient/123").mock(return_value=_patient_response())
        route = mock.post(settings.yokeru_api_url).mock(
            return_value=httpx.Response(422, json={"error": "bad payload"})
        )
        await agent.run_welfare_check("123")

    assert route.call_count == 1  # no retries on 4xx
    # Task is marked FAILED_PERMANENT (synced=1, not unsynced)
    assert buffer.list_unsynced() == []


@pytest.mark.asyncio
async def test_persistent_5xx_leaves_task_pending(agent, settings, buffer):
    with respx.mock() as mock:
        mock.get(f"{settings.fhir_base_url}/Patient/123").mock(return_value=_patient_response())
        mock.post(settings.yokeru_api_url).mock(return_value=httpx.Response(503))
        await agent.run_welfare_check("123")

    rows = buffer.list_unsynced()
    assert len(rows) == 1
    assert rows[0][1] == "123"


@pytest.mark.asyncio
async def test_replay_pending_redispatches(agent, settings, buffer):
    task = YokeruCallTask(patient_id="999", phone="555-9999")
    buffer.insert_pending("recovered-cid", task)

    with respx.mock(assert_all_called=True) as mock:
        post = mock.post(settings.yokeru_api_url).mock(return_value=httpx.Response(202))
        n = await agent.replay_pending()

    assert n == 1
    # Idempotency key uses the original correlation_id — no duplicate calls
    assert post.calls.last.request.headers["Idempotency-Key"] == "recovered-cid"
    assert buffer.list_unsynced() == []


@pytest.mark.asyncio
async def test_ehr_connect_error_does_not_crash_and_records_transient(agent, settings, buffer):
    """A network-level failure during EHR fetch must be classified as a
    transient EHR failure, not propagated as an unhandled exception."""
    with respx.mock() as mock:
        mock.get(f"{settings.fhir_base_url}/Patient/123").mock(
            side_effect=httpx.ConnectError("dns failed")
        )
        # Should return a correlation_id, not raise.
        cid = await agent.run_welfare_check("123")

    assert isinstance(cid, str) and cid
    # No buffer row should exist — the fetch happened before the buffer write.
    assert buffer.list_unsynced() == []


@pytest.mark.asyncio
async def test_ehr_read_timeout_does_not_crash_and_records_transient(agent, settings, buffer):
    with respx.mock() as mock:
        mock.get(f"{settings.fhir_base_url}/Patient/123").mock(
            side_effect=httpx.ReadTimeout("upstream too slow")
        )
        cid = await agent.run_welfare_check("123")

    assert isinstance(cid, str) and cid
    assert buffer.list_unsynced() == []


@pytest.mark.asyncio
async def test_breaker_opens_under_sustained_failure(agent, settings, buffer):
    """After threshold consecutive failures, breaker fast-fails new dispatches."""
    with respx.mock() as mock:
        mock.get(f"{settings.fhir_base_url}/Patient/123").mock(return_value=_patient_response())
        post = mock.post(settings.yokeru_api_url).mock(return_value=httpx.Response(503))

        # First call exhausts retries (3 attempts), bumping breaker to OPEN.
        await agent.run_welfare_check("123")
        first_attempts = post.call_count
        assert first_attempts == settings.retry_max_attempts

        # Subsequent dispatches fast-fail without contacting upstream.
        await agent.run_welfare_check("123")
        assert post.call_count == first_attempts  # no further upstream calls
