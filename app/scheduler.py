"""Arka plan zamanlayıcı — periyodik görevleri tek process içinde çalıştırır.

Redis/Celery gibi ek altyapı gerektirmez; FastAPI ile aynı process içinde
asyncio görevi olarak çalışır, `lifespan` ile başlar/durur. Her iş kendi
try/except'i içinde çalışır — biri patlarsa döngü durmaz, loglanıp bir
sonraki tick'te devam eder.

Diğer modüller (database, main) kendi işlerini `register_job` ile kaydeder;
bu modül hangi işlerin var olduğunu bilmez — döngüsel import'u önler ve
işleri testlerde bağımsız çağırmayı kolaylaştırır.
"""
import asyncio
import logging

log = logging.getLogger("meil.scheduler")

TICK_SECONDS = 60
SYNC_EVERY_TICKS = 15  # ~15 dakikada bir (hesap senkronu gibi ağır işler için)

_jobs: list[dict] = []


def register_job(name: str, fn, every: int = 1):
    """Bir iş kaydeder. `every=1` (varsayılan) her tick'te, `every=N` her N
    tick'te bir çalışır (ör. `SYNC_EVERY_TICKS` ile ağır işleri seyrekleştirmek için)."""
    _jobs.append({"name": name, "fn": fn, "every": max(1, every), "counter": 0})


def clear_jobs():
    """Kayıtlı işleri temizler (testler arası izolasyon için)."""
    _jobs.clear()


async def run_tick():
    """Zamanı gelen işleri bir kez çalıştırır; hatalar loglanır, döngüyü durdurmaz."""
    for job in _jobs:
        job["counter"] += 1
        if job["counter"] % job["every"] != 0:
            continue
        try:
            job["fn"]()
        except Exception:
            log.exception("Zamanlanmış görev başarısız: %s", job["name"])


async def run_forever(tick_seconds: float = TICK_SECONDS):
    log.info("Zamanlayıcı başladı (tick=%ss, %d iş kayıtlı)", tick_seconds, len(_jobs))
    try:
        while True:
            await run_tick()
            await asyncio.sleep(tick_seconds)
    except asyncio.CancelledError:
        log.info("Zamanlayıcı durduruldu")
        raise
