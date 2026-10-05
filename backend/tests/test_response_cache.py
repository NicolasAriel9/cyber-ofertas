from app import cache as cache_module
from app.cache import ResponseCache


def test_serves_the_stored_copy_and_refreshes_it_in_the_background(monkeypatch):
    calls = []

    def compute(db):
        calls.append(db)
        return len(calls)

    cache = ResponseCache()
    assert cache.get("k", compute, db="request") == 1  # disabled: always the database
    cache.enabled = True
    assert cache.get("k", compute, db="request") == 2
    assert cache.get("k", compute, db="request") == 2  # stored copy, no query

    class FakeSession:
        def __enter__(self):
            return "background"

        def __exit__(self, *exc):
            return False

    monkeypatch.setattr(cache_module, "SessionLocal", FakeSession)
    monkeypatch.setattr(cache_module, "TTL", 0)
    cache._refresh_due()
    assert calls[-1] == "background"
    assert cache.get("k", compute, db="request") == 3

    monkeypatch.setattr(cache_module, "KEEP_FOR", -1)  # nobody asked for it lately
    cache._refresh_due()
    assert cache._entries == {}
