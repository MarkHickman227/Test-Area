import asyncio
import logging

from app.core.config import Settings, get_settings
from app.services.repository import SupabaseRepository

logger = logging.getLogger(__name__)


class DiscoveryScheduler:
    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self._task: asyncio.Task[None] | None = None
        self._stopped = asyncio.Event()

    def start(self) -> None:
        if not self.settings.scheduler_enabled or self._task:
            return
        self._task = asyncio.create_task(self._run(), name="applypilot-discovery")

    async def stop(self) -> None:
        self._stopped.set()
        if self._task:
            await self._task

    async def _run(self) -> None:
        while not self._stopped.is_set():
            try:
                await self.run_once()
            except Exception:
                logger.exception("Discovery cycle failed")
            try:
                await asyncio.wait_for(
                    self._stopped.wait(),
                    timeout=self.settings.discovery_interval_minutes * 60,
                )
            except asyncio.TimeoutError:
                continue

    async def run_once(self) -> None:
        if not self.settings.perplexity_configured:
            logger.info("Skipping discovery because PERPLEXITY_API_KEY is not configured")
            return
        try:
            repository = SupabaseRepository(self.settings)
            preferences = await repository.get_preferences()
        except RuntimeError:
            logger.info("Skipping discovery because Supabase is not configured")
            return

        if not preferences:
            logger.info("Skipping discovery because preferences have not been saved")
            return
        logger.info(
            "Discovery is configured for %s titles across %s locations",
            len(preferences.target_titles),
            len(preferences.locations),
        )
