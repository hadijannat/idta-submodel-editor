from app.services.semantic.rate_limit import RateLimiter
from app.services.semantic.cache import TTLCache


def test_rate_limiter_blocks():
    limiter = RateLimiter(limit_per_minute=2)
    assert limiter.allow()
    assert limiter.allow()
    assert not limiter.allow()


def test_ttl_cache_expires():
    cache = TTLCache(maxsize=2, ttl_seconds=0)
    cache.set("key", "value")
    assert cache.get("key") is None
