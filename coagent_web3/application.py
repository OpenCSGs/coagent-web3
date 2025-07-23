import asyncio

from coagent.core.util import wait_for_shutdown
from .service import Service


class Application:
    def __init__(self, *services: Service):
        self.services: list[Service] = list(services)

    async def register(self, *services: Service) -> None:
        self.services.extend(services)

    async def start(self) -> None:
        for service in self.services:
            await service.start()

    async def stop(self) -> None:
        for service in self.services:
            await service.stop()

    async def run(self) -> None:
        await self.start()
        try:
            await wait_for_shutdown()
        except asyncio.CancelledError:
            pass
        finally:
            await self.stop()
