import asyncio

from coagent.core import AgentSpec
from coagent.core.types import Runtime
from coagent.runtimes import LocalRuntime, NATSRuntime  # noqa: F401
from coagent.a2a.app import FastA2A
import httpx
from hypercorn.asyncio import serve
from hypercorn.config import Config

from coagent_web3.core import Service


class Plugin(Service):
    def __init__(
        self,
        runtime: Runtime,
        agent: AgentSpec,
        host: str = "127.0.0.1",
        port: int = 8000,
        debug: bool = False,
    ) -> None:
        httpx_client = httpx.AsyncClient()
        self.app = FastA2A(
            runtime=runtime,
            base_url=f"http://localhost:{port}",
            httpx_client=httpx_client,
            debug=debug,
            lifespan=None,  # runtime lifecycle is managed outside.
        )
        self.host = host
        self.port = port

        self.task: asyncio.Task | None = None
        self.stop_event = asyncio.Event()

    async def start(self) -> None:
        self.task = asyncio.create_task(self._run())

    async def stop(self) -> None:
        self.task.cancel()
        self.stop_event.set()

    async def _run(self) -> None:
        config = Config()
        config.bind = [f"{self.host}:{self.port}"]
        try:
            await serve(self.app, config, shutdown_trigger=self._shutdown)
        except asyncio.CancelledError:
            pass

    async def _shutdown(self) -> None:
        await self.stop_event.wait()
