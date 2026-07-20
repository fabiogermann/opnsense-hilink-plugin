"""
Unit tests for the RRD data store.

These tests run the real rrdtool CLI (installed in CI and present on
OPNsense via the package dependency) against a temporary directory.
They are skipped when the CLI is unavailable.

Regression context: data_store previously called the rrdtool Python
binding without importing it, so every operation raised NameError and
silently returned False/None. These tests assert real success values.
"""

import os
import shutil
import sys
import time

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../src/opnsense/scripts/hilink/lib'))

from data_store import DataStore, MetricData

pytestmark = pytest.mark.skipif(
    shutil.which("rrdtool") is None, reason="rrdtool CLI not installed"
)


def _ts(offset=0):
    """RRD-aligned timestamp (updates must align to the 30s step)."""
    return (int(time.time()) // 30 * 30) + offset


def _metric(ts, **kw):
    base = dict(
        timestamp=ts,
        signal_strength=-65.0,
        signal_quality=80.0,
        data_rx=1_000_000,
        data_tx=500_000,
        connection_state=1,
        network_type=3,
    )
    base.update(kw)
    return MetricData(**base)


@pytest.fixture
def store(tmp_path):
    return DataStore(base_path=str(tmp_path))


class TestDataStore:
    def test_create_rrd(self, store, tmp_path):
        # Regression: this used to raise NameError internally and return False
        assert store.create_rrd("modem-1") is True
        assert (tmp_path / "modem-1.rrd").exists()
        # idempotent on existing file
        assert store.create_rrd("modem-1") is True

    def test_update_creates_rrd_lazily(self, store, tmp_path):
        assert store.update("modem-auto", _metric(_ts(0))) is True
        assert (tmp_path / "modem-auto.rrd").exists()

    def test_update_and_fetch(self, store):
        assert store.create_rrd("modem-1") is True
        assert store.update("modem-1", _metric(_ts(-30))) is True
        assert store.update("modem-1", _metric(_ts(0))) is True

        data = store.fetch("modem-1", start_time=_ts(-120), end_time=_ts(0))
        assert data is not None
        assert "signal_strength" in data["metrics"]
        assert "data_rx" in data["metrics"]
        assert data["timestamps"]
        assert any(v is not None for v in data["metrics"]["signal_strength"])

    def test_unknown_modem_returns_none(self, store):
        assert store.fetch("no-such-modem") is None
        assert store.get_latest("no-such-modem") is None
        assert store.get_statistics("no-such-modem") is None

    def test_get_statistics(self, store):
        store.create_rrd("modem-1")
        store.update("modem-1", _metric(_ts(-60), signal_strength=-70.0))
        store.update("modem-1", _metric(_ts(-30), signal_strength=-60.0))
        stats = store.get_statistics("modem-1", start_time=_ts(-120), end_time=_ts(0))
        assert stats is not None
        assert "signal_strength" in stats
        sig = stats["signal_strength"]
        assert sig["min"] is not None and sig["max"] is not None
        assert sig["min"] <= sig["max"]
        assert "uptime_percentage" in stats

    def test_get_latest(self, store):
        # RRDtool only commits a PDP once the following update closes the
        # interval, so a lone update leaves every row NaN. Two updates are
        # the realistic minimum (the daemon writes every collect_interval).
        store.create_rrd("modem-1")
        store.update("modem-1", _metric(_ts(-30)))
        store.update("modem-1", _metric(_ts(0)))
        latest = store.get_latest("modem-1")
        assert latest is not None
        assert latest.signal_strength == pytest.approx(-65.0, abs=1.0)

    def test_cleanup_old_data(self, store, tmp_path):
        store.create_rrd("modem-old")
        old_file = tmp_path / "modem-old.rrd"
        old_time = time.time() - 40 * 86400
        os.utime(old_file, (old_time, old_time))
        assert store.cleanup_old_data(retention_days=30) == 1
        assert not old_file.exists()

    def test_generate_graph(self, store, tmp_path):
        store.create_rrd("modem-1")
        store.update("modem-1", _metric(_ts(-30)))
        store.update("modem-1", _metric(_ts(0)))
        out = tmp_path / "graph.png"
        assert store.generate_graph(
            "modem-1", str(out), start_time=_ts(-300), end_time=_ts(0)
        ) is True
        assert out.exists() and out.stat().st_size > 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
