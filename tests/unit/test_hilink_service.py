"""
Unit tests for the HiLink service daemon (ModemManager behaviour).

Covers reconnect throttling/back-off, data-limit enforcement, metric
collection mapping, and the legacy max_idle_time fallback — none of which
requires a live modem (HiLinkModem is mocked).
"""

import os
import sys
import tempfile
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock

import pytest

# hilink_service creates its log directory at import time
os.environ.setdefault("HILINK_LOG_DIR", tempfile.mkdtemp(prefix="hilink-test-logs-"))

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../src/opnsense/scripts/hilink'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../src/opnsense/scripts/hilink/lib'))

from hilink_service import ModemManager  # noqa: E402
from config_manager import ModemConfig  # noqa: E402
from hilink_api import ConnectionStatus, DataUsage, ModemStatus, SignalInfo  # noqa: E402


def _status(connected=True):
    return ModemStatus(
        connected=connected,
        connection_status=(
            ConnectionStatus.CONNECTED if connected else ConnectionStatus.DISCONNECTED
        ),
        network_type="LTE (4G)",
        network_operator="Carrier",
        wan_ip="10.0.0.1",
        sim_status="1",
        device_name="E3372h-320",
        imei="",
        iccid="",
        connection_time=0,
        roaming=False,
    )


def _signal(rssi=-65):
    return SignalInfo(
        rssi=rssi, rsrp=-95, rsrq=-10, sinr=15,
        signal_bars=5, signal_quality="excellent",
        cell_id=1, band="3", frequency=1800,
    )


def _usage(monthly_total=0):
    return DataUsage(
        session_upload=0, session_download=0, session_total=0,
        total_upload=500, total_download=1000, total_total=1500,
        monthly_upload=monthly_total, monthly_download=0,
        monthly_total=monthly_total,
    )


@pytest.fixture
def manager():
    config = ModemConfig(
        uuid="test-uuid",
        name="TestModem",
        reconnect_interval=60,
        max_reconnect_attempts=3,
    )
    store = MagicMock()
    mgr = ModemManager(config, store)
    mgr.modem = AsyncMock()
    mgr.connected = True
    return mgr


class TestReconnectLogic:
    @pytest.mark.asyncio
    async def test_disabled_modem_is_skipped(self, manager):
        manager.config.enabled = False
        manager.connected = False
        assert await manager.check_connection() is True

    @pytest.mark.asyncio
    async def test_reconnect_attempts_reset_on_success(self, manager):
        manager.connected = False
        manager.reconnect_attempts = 2
        manager.initialize = AsyncMock(return_value=True)
        assert await manager.check_connection() is True
        assert manager.reconnect_attempts == 0

    @pytest.mark.asyncio
    async def test_reconnect_interval_throttles_attempts(self, manager):
        manager.connected = False
        manager.last_reconnect_attempt = datetime.now()  # just tried
        manager.initialize = AsyncMock(return_value=True)
        assert await manager.check_connection() is False
        manager.initialize.assert_not_called()

    @pytest.mark.asyncio
    async def test_backoff_after_max_attempts(self, manager):
        manager.connected = False
        manager.reconnect_attempts = 3  # == max_reconnect_attempts
        # past the normal interval but inside the 5x back-off window
        manager.last_reconnect_attempt = datetime.now() - timedelta(seconds=61)
        manager.initialize = AsyncMock(return_value=False)
        assert await manager.check_connection() is False
        manager.initialize.assert_not_called()

    @pytest.mark.asyncio
    async def test_fresh_round_after_backoff_window(self, manager):
        manager.connected = False
        manager.reconnect_attempts = 3
        manager.last_reconnect_attempt = datetime.now() - timedelta(seconds=301)
        manager.initialize = AsyncMock(return_value=True)
        assert await manager.check_connection() is True
        assert manager.reconnect_attempts == 0


class TestDataLimit:
    @pytest.mark.asyncio
    async def test_data_limit_disconnects(self, manager):
        manager.config.data_limit_enabled = True
        manager.config.data_limit_mb = 1  # 1 MB
        manager.last_usage = _usage(monthly_total=2 * 1024 * 1024)
        manager.last_status = _status(connected=True)
        assert await manager.check_connection() is True
        manager.modem.disconnect_modem.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_under_limit_no_disconnect(self, manager):
        manager.config.data_limit_enabled = True
        manager.config.data_limit_mb = 1024
        manager.last_usage = _usage(monthly_total=10 * 1024 * 1024)  # 10 MB
        manager.last_status = _status(connected=True)
        assert await manager.check_connection() is True
        manager.modem.disconnect_modem.assert_not_called()


class TestCollectMetrics:
    @pytest.mark.asyncio
    async def test_collect_requires_connection(self, manager):
        manager.connected = False
        assert await manager.collect_metrics() is False

    @pytest.mark.asyncio
    async def test_collect_stores_mapped_metric(self, manager):
        manager.modem.get_status = AsyncMock(return_value=_status(connected=True))
        manager.modem.get_signal_info = AsyncMock(return_value=_signal(rssi=-65))
        manager.modem.get_data_usage = AsyncMock(return_value=_usage())

        assert await manager.collect_metrics() is True
        manager.data_store.update.assert_called_once()
        uuid_arg, metric = manager.data_store.update.call_args[0]
        assert uuid_arg == "test-uuid"
        assert metric.network_type == 3  # "LTE (4G)" -> 4G bucket
        assert metric.connection_state == 1
        assert metric.signal_strength == -65
        assert metric.data_rx == 1000
        assert metric.data_tx == 500

    @pytest.mark.asyncio
    async def test_collect_handles_modem_failure(self, manager):
        manager.modem.get_status = AsyncMock(side_effect=Exception("boom"))
        assert await manager.collect_metrics() is False


class TestApplySettings:
    def _neutral_config(self, manager):
        manager.config.network_mode = "auto"
        manager.config.lte_band = "7FFFFFFFFFFFFFFF"
        manager.config.network_band = "3FFFFFFF"
        manager.config.network_search = "auto"
        manager.config.active_profile = ""

    @pytest.mark.asyncio
    async def test_legacy_max_idle_time_fallback(self, manager):
        """max_idle_time (seconds) applies when auto_disconnect_min is unset"""
        self._neutral_config(manager)
        manager.config.auto_disconnect_min = 0
        manager.config.max_idle_time = 1800  # 30 minutes
        assert await manager.apply_settings() is True
        manager.modem.set_auto_disconnect.assert_awaited_once_with(30)

    @pytest.mark.asyncio
    async def test_auto_disconnect_min_wins(self, manager):
        self._neutral_config(manager)
        manager.config.auto_disconnect_min = 15
        manager.config.max_idle_time = 1800
        assert await manager.apply_settings() is True
        manager.modem.set_auto_disconnect.assert_awaited_once_with(15)

    @pytest.mark.asyncio
    async def test_no_idle_setting_no_call(self, manager):
        self._neutral_config(manager)
        manager.config.auto_disconnect_min = 0
        manager.config.max_idle_time = 0
        assert await manager.apply_settings() is True
        manager.modem.set_auto_disconnect.assert_not_called()

    @pytest.mark.asyncio
    async def test_apply_settings_handles_modem_error(self, manager):
        self._neutral_config(manager)
        manager.modem.set_roaming = AsyncMock(side_effect=Exception("boom"))
        assert await manager.apply_settings() is False


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
