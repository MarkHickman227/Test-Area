import asyncio
from datetime import datetime, timezone
from types import SimpleNamespace

import pytest

from app.core.config import Settings
from app.services.scheduler import DiscoveryScheduler


def _settings(**overrides) -> Settings:
    values = {
        "SCHEDULER_ENABLED": "false",
        "DISCOVERY_SCHEDULE_MODE": "twice_daily",
        "DISCOVERY_TIMES": "08:00,20:00",
        "DISCOVERY_TIMEZONE": "Europe/London",
        "PERPLEXITY_API_KEY": "replace-with-perplexity-api-key",
        "SUPABASE_URL": "https://your-project.supabase.co",
        "SUPABASE_SERVICE_KEY": "replace-with-service-role-key",
    }
    values.update(overrides)
    return Settings(**values)


@pytest.mark.asyncio
async def test_run_once_skips_without_perplexity():
    scheduler = DiscoveryScheduler(_settings())
    result = await scheduler.run_once(trigger="test")
    assert result["status"] == "skipped"
    assert "PERPLEXITY" in result["reason"]


@pytest.mark.asyncio
async def test_run_once_rejects_concurrent_calls(monkeypatch):
    settings = _settings(
        PERPLEXITY_API_KEY="pplx-test-key",
        SUPABASE_URL="https://newproject.supabase.co",
        SUPABASE_SERVICE_KEY=(
            "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9."
            "eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Im5ld3Byb2plY3QiLCJyb2xlIjoic2VydmljZV9yb2xlIn0."
            "signature"
        ),
        ANTHROPIC_API_KEY="anthropic-test-key",
    )
    scheduler = DiscoveryScheduler(settings)

    started = asyncio.Event()
    release = asyncio.Event()

    async def slow_pipeline():
        started.set()
        await release.wait()
        return {"discovered": 1, "enriched": 1, "scored": 1, "generated": 1}

    monkeypatch.setattr(scheduler, "_run_pipeline", slow_pipeline)

    task = asyncio.create_task(scheduler.run_once(trigger="primary"))
    await started.wait()
    rejected = await scheduler.run_once(trigger="secondary")
    release.set()
    primary = await task

    assert rejected["status"] == "rejected"
    assert primary["status"] == "ok"
    assert primary["stats"]["discovered"] == 1


@pytest.mark.asyncio
async def test_run_backfill_skips_without_anthropic():
    scheduler = DiscoveryScheduler(_settings())
    result = await scheduler.run_backfill(trigger="test")
    assert result["status"] == "skipped"
    assert "ANTHROPIC" in result["reason"] or "database" in result["reason"].lower() or "Supabase" in result["reason"]


@pytest.mark.asyncio
async def test_run_backfill_does_not_require_perplexity(monkeypatch):
    settings = _settings(
        PERPLEXITY_API_KEY="replace-with-perplexity-api-key",
        SUPABASE_URL="https://newproject.supabase.co",
        SUPABASE_SERVICE_KEY=(
            "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9."
            "eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Im5ld3Byb2plY3QiLCJyb2xlIjoic2VydmljZV9yb2xlIn0."
            "signature"
        ),
        ANTHROPIC_API_KEY="anthropic-test-key",
    )
    scheduler = DiscoveryScheduler(settings)

    async def fake_backfill(*, limit):
        return {"discovered": 0, "processed": 3, "scored": 3, "generated": 1}

    monkeypatch.setattr(scheduler, "_run_backfill", fake_backfill)
    result = await scheduler.run_backfill(trigger="api", limit=10)

    assert result["status"] == "ok"
    assert result["stats"]["scored"] == 3
    assert result["stats"]["discovered"] == 0


def test_scheduler_status_shape():
    scheduler = DiscoveryScheduler(_settings())
    status = scheduler.status()
    assert status["enabled"] is False
    assert status["mode"] == "twice_daily"
    assert status["times"] == ["08:00", "20:00"]
    assert status["running"] is False
