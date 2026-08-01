"""Reliable discovery scheduler with twice-daily and interval modes."""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import Any

from app.core.config import Settings, get_settings
from app.services.pipeline import Pipeline
from app.services.schedule import next_run_after, seconds_until

logger = logging.getLogger(__name__)

MAX_ATTEMPTS = 3
RETRY_BASE_SECONDS = 30


class DiscoveryScheduler:
    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self._task: asyncio.Task[None] | None = None
        self._stopped = asyncio.Event()
        self._lock = asyncio.Lock()
        self._running = False
        self._last_started_at: datetime | None = None
        self._last_finished_at: datetime | None = None
        self._last_status: str | None = None
        self._last_stats: dict[str, Any] | None = None
        self._last_error: str | None = None
        self._next_run_at: datetime | None = None
        self._run_count = 0

    def start(self) -> None:
        if not self.settings.scheduler_enabled or self._task:
            return
        self._task = asyncio.create_task(self._run_loop(), name="applypilot-discovery")
        logger.info(
            "Discovery scheduler started mode=%s times=%s timezone=%s",
            self.settings.discovery_schedule_mode,
            self.settings.discovery_times,
            self.settings.discovery_timezone,
        )

    async def stop(self) -> None:
        self._stopped.set()
        if self._task:
            await self._task
            self._task = None

    def status(self) -> dict[str, Any]:
        return {
            "enabled": self.settings.scheduler_enabled,
            "mode": self.settings.discovery_schedule_mode,
            "times": self.settings.discovery_time_list,
            "timezone": self.settings.discovery_timezone,
            "interval_minutes": self.settings.discovery_interval_minutes,
            "running": self._running,
            "next_run_at": self._next_run_at.isoformat() if self._next_run_at else None,
            "last_started_at": (
                self._last_started_at.isoformat() if self._last_started_at else None
            ),
            "last_finished_at": (
                self._last_finished_at.isoformat() if self._last_finished_at else None
            ),
            "last_status": self._last_status,
            "last_stats": self._last_stats,
            "last_error": self._last_error,
            "run_count": self._run_count,
        }

    async def _run_loop(self) -> None:
        while not self._stopped.is_set():
            delay = self._seconds_until_next_run()
            logger.info("Next discovery run in %.0f seconds (at %s)", delay, self._next_run_at)
            try:
                await asyncio.wait_for(self._stopped.wait(), timeout=delay)
                break
            except asyncio.TimeoutError:
                pass

            result = await self.run_once(trigger="scheduler")
            if result.get("status") == "skipped":
                logger.info("Scheduled discovery skipped: %s", result.get("reason"))

    def _seconds_until_next_run(self) -> float:
        now = datetime.now(timezone.utc)
        if self.settings.discovery_schedule_mode == "twice_daily":
            self._next_run_at = next_run_after(
                now,
                self.settings.parsed_discovery_times,
                self.settings.discovery_timezone,
            )
            return seconds_until(self._next_run_at, now)

        self._next_run_at = now
        return float(self.settings.discovery_interval_minutes * 60)

    async def run_once(self, *, trigger: str = "manual") -> dict[str, Any]:
        """Run one discovery cycle. Concurrent calls are rejected safely."""
        if self._lock.locked() or self._running:
            return {
                "status": "rejected",
                "reason": "pipeline_already_running",
                "trigger": trigger,
            }

        async with self._lock:
            self._running = True
            self._last_started_at = datetime.now(timezone.utc)
            self._last_error = None
            try:
                result = await self._execute_with_retries(trigger=trigger)
                self._last_status = result["status"]
                self._last_stats = result.get("stats")
                if result["status"] == "ok":
                    self._run_count += 1
                if result["status"] in {"skipped", "error"}:
                    self._last_error = result.get("reason") or result.get("error")
                return result
            finally:
                self._running = False
                self._last_finished_at = datetime.now(timezone.utc)

    async def _execute_with_retries(self, *, trigger: str) -> dict[str, Any]:
        readiness = self._readiness_check()
        if readiness is not None:
            return {**readiness, "trigger": trigger}

        last_error: Exception | None = None
        for attempt in range(1, MAX_ATTEMPTS + 1):
            try:
                stats = await self._run_pipeline()
                logger.info(
                    "Discovery cycle finished trigger=%s attempt=%s stats=%s",
                    trigger,
                    attempt,
                    stats,
                )
                return {
                    "status": "ok",
                    "trigger": trigger,
                    "attempt": attempt,
                    "stats": stats,
                }
            except PreferencesMissingError as exc:
                return {
                    "status": "skipped",
                    "reason": str(exc),
                    "trigger": trigger,
                }
            except Exception as exc:
                last_error = exc
                logger.exception(
                    "Discovery cycle failed trigger=%s attempt=%s/%s",
                    trigger,
                    attempt,
                    MAX_ATTEMPTS,
                )
                if attempt < MAX_ATTEMPTS:
                    backoff = RETRY_BASE_SECONDS * (2 ** (attempt - 1))
                    await asyncio.sleep(backoff)

        return {
            "status": "error",
            "trigger": trigger,
            "attempts": MAX_ATTEMPTS,
            "error": str(last_error) if last_error else "unknown_error",
        }

    def _readiness_check(self) -> dict[str, Any] | None:
        if not self.settings.perplexity_configured:
            return {
                "status": "skipped",
                "reason": "PERPLEXITY_API_KEY is not configured",
            }
        if not (
            self.settings.supabase_configured or self.settings.database_configured
        ):
            return {
                "status": "skipped",
                "reason": "Supabase/database is not configured",
            }
        return None

    async def _run_pipeline(self) -> dict[str, int]:
        from app.api.deps import get_repository

        repository = get_repository()
        preferences = await repository.get_preferences()
        if not preferences:
            # Use a dedicated skip exception so retries are not wasted.
            raise PreferencesMissingError("Preferences have not been saved")

        logger.info(
            "Starting discovery for %s titles across %s locations",
            len(preferences.target_titles),
            len(preferences.locations),
        )
        pipeline = Pipeline(self.settings)
        return await pipeline.run(repository, preferences)


class PreferencesMissingError(RuntimeError):
    """Raised when discovery cannot run because preferences are unset."""
