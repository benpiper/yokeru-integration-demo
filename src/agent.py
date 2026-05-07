import logging
import uuid

import httpx
from tenacity import (
    AsyncRetrying,
    RetryError,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from .adapters import BaseEHRAdapter, PatientNotReachableError
from .breaker import BreakerOpenError, BreakerState, CircuitBreaker
from .db import CallBuffer
from .metrics import (
    breaker_state,
    calls_attempted_total,
    calls_delivered_total,
    calls_failed_total,
    http_retries_total,
)
from .schemas import YokeruCallTask
from .settings import Settings

log = logging.getLogger(__name__)


# httpx exceptions that represent transient failures worth retrying.
TRANSIENT_HTTPX_ERRORS = (
    httpx.ConnectError,
    httpx.ReadTimeout,
    httpx.WriteTimeout,
    httpx.PoolTimeout,
    httpx.RemoteProtocolError,
)


def _is_retryable_status(exc: BaseException) -> bool:
    """5xx and 429 are transient. 4xx (other than 429) are permanent."""
    if isinstance(exc, httpx.HTTPStatusError):
        return exc.response.status_code >= 500 or exc.response.status_code == 429
    return isinstance(exc, TRANSIENT_HTTPX_ERRORS)


class YokeruIntegrationAgent:
    """Orchestrates the welfare-check pipeline.

    Lifecycle:
      1. Adapter pulls patient from the customer EHR and maps to YokeruCallTask.
      2. Task is buffered to SQLite (durable until DELIVERED).
      3. Outbound POST to Yokeru API, guarded by retries + circuit breaker,
         with an Idempotency-Key so recovery never duplicates a real call.
      4. On success → marked DELIVERED. On permanent failure → FAILED_PERMANENT.
         On transient failure → left PENDING for the next run.
    """

    def __init__(
        self,
        settings: Settings,
        adapter: BaseEHRAdapter,
        client: httpx.AsyncClient,
        buffer: CallBuffer,
    ):
        self._settings = settings
        self._adapter = adapter
        self._client = client
        self._buffer = buffer
        self._breaker = CircuitBreaker(
            name="yokeru_api",
            failure_threshold=settings.breaker_failure_threshold,
            reset_timeout_s=settings.breaker_reset_timeout_s,
        )

    @classmethod
    def build(cls, settings: Settings) -> "YokeruIntegrationAgent":
        from .adapters import CernerFHIRAdapter

        timeout = httpx.Timeout(
            connect=settings.http_connect_timeout_s,
            read=settings.http_read_timeout_s,
            write=settings.http_read_timeout_s,
            pool=settings.http_connect_timeout_s,
        )
        client = httpx.AsyncClient(timeout=timeout)
        adapter = CernerFHIRAdapter(client=client, base_url=settings.fhir_base_url)
        buffer = CallBuffer(db_path=settings.db_path)
        return cls(settings=settings, adapter=adapter, client=client, buffer=buffer)

    async def aclose(self) -> None:
        await self._client.aclose()

    def _publish_breaker_state(self) -> None:
        mapping = {
            BreakerState.CLOSED: 0,
            BreakerState.HALF_OPEN: 1,
            BreakerState.OPEN: 2,
        }
        breaker_state.labels(name=self._breaker.name).set(mapping[self._breaker.state])

    async def _post_to_yokeru(self, task: YokeruCallTask, correlation_id: str) -> None:
        resp = await self._client.post(
            self._settings.yokeru_api_url,
            json=task.model_dump(),
            headers={
                # correlation_id doubles as the idempotency key — recovery
                # retries cannot produce a duplicate welfare call.
                "Idempotency-Key": correlation_id,
                "X-Correlation-Id": correlation_id,
            },
        )
        resp.raise_for_status()

    async def _execute_with_retries(self, task: YokeruCallTask, correlation_id: str) -> None:
        attempts = 0
        try:
            async for attempt in AsyncRetrying(
                stop=stop_after_attempt(self._settings.retry_max_attempts),
                wait=wait_exponential(
                    multiplier=1,
                    min=self._settings.retry_min_wait_s,
                    max=self._settings.retry_max_wait_s,
                ),
                retry=retry_if_exception_type((httpx.HTTPStatusError, *TRANSIENT_HTTPX_ERRORS)),
                reraise=True,
            ):
                with attempt:
                    attempts += 1
                    if attempts > 1:
                        http_retries_total.labels(target="yokeru_api").inc()
                        log.info(
                            f"Retrying Yokeru dispatch (attempt {attempts})",
                            extra={"correlation_id": correlation_id},
                        )
                    try:
                        await self._breaker.call(self._post_to_yokeru, task, correlation_id)
                    except httpx.HTTPStatusError as e:
                        if not _is_retryable_status(e):
                            # 4xx (except 429) — permanent. Don't retry.
                            log.warning(
                                f"Permanent HTTP error from Yokeru API: {e.response.status_code}",
                                extra={"correlation_id": correlation_id},
                            )
                            raise PatientNotReachableError(
                                f"Yokeru API rejected request: {e.response.status_code}"
                            ) from e
                        raise
                    finally:
                        self._publish_breaker_state()
        except RetryError as e:
            raise e.last_attempt.exception() from e

    async def run_welfare_check(self, patient_id: str) -> str:
        correlation_id = str(uuid.uuid4())
        log.info(
            f"Starting welfare check for patient {patient_id}",
            extra={"correlation_id": correlation_id},
        )
        calls_attempted_total.labels(adapter=self._adapter.name).inc()

        try:
            task = await self._adapter.fetch_patient(patient_id, correlation_id)
        except PatientNotReachableError as e:
            log.warning(
                f"Skipping patient {patient_id}: {e}",
                extra={"correlation_id": correlation_id},
            )
            calls_failed_total.labels(adapter=self._adapter.name, kind="permanent").inc()
            return correlation_id
        except httpx.HTTPStatusError as e:
            if 400 <= e.response.status_code < 500 and e.response.status_code != 429:
                log.warning(
                    f"EHR returned {e.response.status_code} for patient {patient_id} — permanent skip",
                    extra={"correlation_id": correlation_id},
                )
                calls_failed_total.labels(adapter=self._adapter.name, kind="permanent").inc()
                return correlation_id
            log.exception(
                f"Transient EHR failure for patient {patient_id}",
                extra={"correlation_id": correlation_id},
            )
            calls_failed_total.labels(adapter=self._adapter.name, kind="transient").inc()
            return correlation_id
        except TRANSIENT_HTTPX_ERRORS as e:
            # Connect/read/pool/protocol errors at the EHR fetch step. Without
            # this branch, the exception escapes the CLI and crashes the
            # process, which loses the chance to record a transient failure.
            log.warning(
                f"Transient EHR network failure for patient {patient_id}: {e!r}",
                extra={"correlation_id": correlation_id},
            )
            calls_failed_total.labels(adapter=self._adapter.name, kind="transient").inc()
            return correlation_id

        self._buffer.insert_pending(correlation_id, task)
        log.info("Task buffered to local SQLite", extra={"correlation_id": correlation_id})

        await self._dispatch(task, correlation_id)
        return correlation_id

    async def _dispatch(self, task: YokeruCallTask, correlation_id: str) -> None:
        self._buffer.increment_attempts(correlation_id)
        try:
            await self._execute_with_retries(task, correlation_id)
        except PatientNotReachableError as e:
            self._buffer.mark_permanent_failure(correlation_id, str(e))
            calls_failed_total.labels(adapter=self._adapter.name, kind="permanent").inc()
            log.warning(
                f"Marking task {correlation_id} as FAILED_PERMANENT: {e}",
                extra={"correlation_id": correlation_id},
            )
        except BreakerOpenError:
            calls_failed_total.labels(adapter=self._adapter.name, kind="transient").inc()
            log.warning(
                "Yokeru breaker OPEN — leaving task PENDING for next run",
                extra={"correlation_id": correlation_id},
            )
        except (httpx.HTTPStatusError, *TRANSIENT_HTTPX_ERRORS) as e:
            calls_failed_total.labels(adapter=self._adapter.name, kind="transient").inc()
            log.warning(
                f"Transient dispatch failure (will retry on next run): {e!r}",
                extra={"correlation_id": correlation_id},
            )
        else:
            self._buffer.mark_delivered(correlation_id)
            calls_delivered_total.labels(adapter=self._adapter.name).inc()
            log.info(
                "Welfare check successfully handed off to Yokeru",
                extra={"correlation_id": correlation_id},
            )

    async def replay_pending(self) -> int:
        """Re-dispatch any tasks left PENDING by a prior crash. Returns count handled."""
        rows = self._buffer.list_unsynced()
        if not rows:
            return 0
        log.info(
            f"Replaying {len(rows)} pending task(s) from prior runs",
            extra={"correlation_id": "RECOVERY"},
        )
        for cid, _patient_id, payload in rows:
            task = YokeruCallTask.model_validate_json(payload)
            await self._dispatch(task, cid)
        return len(rows)
