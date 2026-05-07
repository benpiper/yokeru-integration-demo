import httpx
import pytest

from src.adapters import CernerFHIRAdapter
from src.agent import YokeruIntegrationAgent
from src.db import CallBuffer
from src.settings import Settings


@pytest.fixture
def settings(tmp_path) -> Settings:
    return Settings(
        fhir_base_url="https://fhir.test/r4",
        yokeru_api_url="https://yokeru.test/dispatch",
        db_path=str(tmp_path / "state.db"),
        retry_max_attempts=3,
        retry_min_wait_s=0.0,
        retry_max_wait_s=0.0,
        breaker_failure_threshold=3,
        breaker_reset_timeout_s=0.05,
        webhook_signing_secret="test-secret",
    )


@pytest.fixture
def buffer(settings) -> CallBuffer:
    return CallBuffer(db_path=settings.db_path)


@pytest.fixture
async def client():
    async with httpx.AsyncClient(timeout=httpx.Timeout(2.0)) as c:
        yield c


@pytest.fixture
async def agent(settings, buffer, client) -> YokeruIntegrationAgent:
    adapter = CernerFHIRAdapter(client=client, base_url=settings.fhir_base_url)
    return YokeruIntegrationAgent(settings=settings, adapter=adapter, client=client, buffer=buffer)
