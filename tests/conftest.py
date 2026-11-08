import pytest


@pytest.fixture(autouse=True)
def _offline(monkeypatch):
    """Tests read cached data only: no network, and no rewrites of tracked cache files (data/l1, data/l2)."""
    monkeypatch.setenv("QSITE_OFFLINE", "1")
