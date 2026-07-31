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

_jobs: list[tuple[str, callable]] = []


def register_job(name: str, fn):
    """Her tick'te çalıştırılacak bir işi kaydeder."""
    _jobs.append((name, fn))


def clear_jobs():
    """Kayıtlı işleri temizler (testler arası izolasyon için)."""
    _jobs.clear()


async def run_tick():
    """Kayıtlı tüm işleri bir kez çalıştırır; hatalar loglanır, döngüyü durdurmaz."""
    for name, fn in _jobs:
        try:
            fn()
        except Exception:
            log.exception("Zamanlanmış görev başarısız: %s", name)


async def run_forever(tick_seconds: float = TICK_SECONDS):
    log.info("Zamanlayıcı başladı (tick=%ss, %d iş kayıtlı)", tick_seconds, len(_jobs))
    try:
        while True:
            await run_tick()
            await asyncio.sleep(tick_seconds)
    except asyncio.CancelledError:
        log.info("Zamanlayıcı durduruldu")
        raise
