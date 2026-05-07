"""CLI entrypoint for the Yokeru integration agent."""

import argparse
import asyncio
import logging
import signal

from .agent import YokeruIntegrationAgent
from .logging_setup import configure_logging
from .settings import get_settings

log = logging.getLogger(__name__)


def _install_shutdown_handlers(stop_event: asyncio.Event) -> None:
    """SIGTERM/SIGINT flip the stop_event rather than killing in-flight work.
    The durable buffer means partial work is safe to leave PENDING, but we
    still want a clean log line and a chance to close the HTTP client."""
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        try:
            loop.add_signal_handler(sig, stop_event.set)
        except NotImplementedError:
            # add_signal_handler isn't available on Windows; fall back to
            # default KeyboardInterrupt handling there.
            pass


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(prog="yokeru-agent")
    sub = p.add_subparsers(dest="command", required=True)

    run = sub.add_parser("run", help="Run a welfare check for a single patient")
    run.add_argument("patient_id", help="Patient ID in the configured EHR")
    run.add_argument(
        "--no-replay",
        action="store_true",
        help="Skip the recovery replay step",
    )

    sub.add_parser("replay", help="Replay any tasks left PENDING by a prior run")

    serve = sub.add_parser("serve", help="Run the FastAPI webhook server")
    serve.add_argument("--host", default="0.0.0.0")
    serve.add_argument("--port", type=int, default=8000)

    return p.parse_args()


async def _race_with_shutdown(coro, stop_event: asyncio.Event) -> None:
    """Run coro to completion unless a shutdown signal arrives first."""
    work = asyncio.create_task(coro)
    stop = asyncio.create_task(stop_event.wait())
    done, pending = await asyncio.wait({work, stop}, return_when=asyncio.FIRST_COMPLETED)
    if stop in done and not work.done():
        log.warning(
            "Shutdown signal received — cancelling in-flight work; PENDING rows will replay on next run"
        )
        work.cancel()
        try:
            await work
        except asyncio.CancelledError:
            pass
    else:
        stop.cancel()
        # surface any exception from the actual work
        await work


async def _run(patient_id: str, replay: bool) -> None:
    settings = get_settings()
    agent = YokeruIntegrationAgent.build(settings)
    stop_event = asyncio.Event()
    _install_shutdown_handlers(stop_event)

    async def _do() -> None:
        if replay:
            await agent.replay_pending()
        await agent.run_welfare_check(patient_id)

    try:
        await _race_with_shutdown(_do(), stop_event)
    finally:
        await agent.aclose()


async def _replay() -> None:
    settings = get_settings()
    agent = YokeruIntegrationAgent.build(settings)
    stop_event = asyncio.Event()
    _install_shutdown_handlers(stop_event)

    async def _do() -> None:
        n = await agent.replay_pending()
        log.info(f"Replayed {n} pending task(s)")

    try:
        await _race_with_shutdown(_do(), stop_event)
    finally:
        await agent.aclose()


def main() -> None:
    configure_logging()
    args = _parse_args()

    if args.command == "run":
        asyncio.run(_run(args.patient_id, replay=not args.no_replay))
    elif args.command == "replay":
        asyncio.run(_replay())
    elif args.command == "serve":
        import uvicorn

        uvicorn.run(
            "src.webhook:app",
            host=args.host,
            port=args.port,
            log_config=None,
        )


if __name__ == "__main__":
    main()
