"""Zamanlayıcı iskeleti testleri.

Sonsuz döngü (`run_forever`) test edilmez; `run_tick()` doğrudan çağrılır.
"""
import asyncio

import pytest

from app import scheduler


@pytest.fixture(autouse=True)
def _clean_jobs():
    scheduler.clear_jobs()
    yield
    scheduler.clear_jobs()


def test_run_tick_calls_registered_jobs():
    calls = []
    scheduler.register_job("a", lambda: calls.append("a"))
    scheduler.register_job("b", lambda: calls.append("b"))

    asyncio.run(scheduler.run_tick())

    assert calls == ["a", "b"]


def test_run_tick_survives_failing_job():
    calls = []

    def boom():
        raise RuntimeError("kasıtlı hata")

    scheduler.register_job("boom", boom)
    scheduler.register_job("after", lambda: calls.append("after"))

    asyncio.run(scheduler.run_tick())  # patlamamalı

    assert calls == ["after"]


def test_run_tick_with_no_jobs_is_a_no_op():
    asyncio.run(scheduler.run_tick())  # hata fırlatmamalı


def test_register_job_appends_and_clear_resets():
    scheduler.register_job("x", lambda: None)
    assert len(scheduler._jobs) == 1
    scheduler.clear_jobs()
    assert scheduler._jobs == []


def test_every_n_job_only_runs_on_the_nth_tick():
    calls = []
    scheduler.register_job("seyrek", lambda: calls.append(1), every=3)

    asyncio.run(scheduler.run_tick())
    asyncio.run(scheduler.run_tick())
    assert calls == []          # 1. ve 2. tick'te çalışmamalı

    asyncio.run(scheduler.run_tick())
    assert calls == [1]         # 3. tick'te çalışmalı

    asyncio.run(scheduler.run_tick())
    asyncio.run(scheduler.run_tick())
    assert calls == [1]         # 4. ve 5. tick'te çalışmamalı

    asyncio.run(scheduler.run_tick())
    assert calls == [1, 1]      # 6. tick'te tekrar çalışmalı
