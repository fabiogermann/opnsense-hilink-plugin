#!/usr/bin/env python3
"""
HiLink Service Daemon
Main service that manages HiLink modem connections and monitoring
"""

import asyncio
import signal
import sys
import os
import logging
import argparse
from typing import Dict, Optional, List
from pathlib import Path
import daemon
import lockfile
from datetime import datetime, timedelta

# Add lib directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "lib"))

from hilink_api import HiLinkModem, ModemStatus, SignalInfo, DataUsage, NetworkMode
from config_manager import ConfigManager, ModemConfig
from data_store import DataStore, MetricData

# Configure logging
LOG_DIR = Path("/var/log/hilink")
LOG_DIR.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.FileHandler(LOG_DIR / "service.log"), logging.StreamHandler()],
)

logger = logging.getLogger(__name__)


class ModemManager:
    """Manages a single modem connection and monitoring"""

    def __init__(self, config: ModemConfig, data_store: DataStore):
        """
        Initialize modem manager

        Args:
            config: Modem configuration
            data_store: Data store instance
        """
        self.config = config
        self.data_store = data_store
        self.modem: Optional[HiLinkModem] = None
        self.connected = False
        self.last_status: Optional[ModemStatus] = None
        self.last_signal: Optional[SignalInfo] = None
        self.last_usage: Optional[DataUsage] = None
        self.reconnect_attempts = 0
        self.last_collection = datetime.now()

    async def initialize(self) -> bool:
        """Initialize modem connection"""
        try:
            self.modem = HiLinkModem(
                host=self.config.ip_address,
                username=self.config.username,
                password=self.config.password,
                name=self.config.name,
            )

            await self.modem.connect()
            self.connected = True

            # Create RRD if needed
            self.data_store.create_rrd(self.config.uuid)

            logger.info(f"Initialized modem {self.config.name} ({self.config.uuid})")
            return True

        except Exception as e:
            logger.error(f"Failed to initialize modem {self.config.name}: {e}")
            self.connected = False
            return False

    async def cleanup(self):
        """Clean up modem connection"""
        if self.modem:
            await self.modem.disconnect()
            self.modem = None
            self.connected = False

    async def collect_metrics(self) -> bool:
        """Collect and store modem metrics"""
        if not self.connected or not self.modem:
            return False

        try:
            # Get current data
            self.last_status = await self.modem.get_status()
            self.last_signal = await self.modem.get_signal_info()
            self.last_usage = await self.modem.get_data_usage()

            # Map network type to numeric value
            network_type_map = {
                "No Service": 0,
                "2G": 1,
                "GSM": 1,
                "3G": 2,
                "WCDMA": 2,
                "UMTS": 2,
                "4G": 3,
                "LTE": 3,
                "5G": 4,
            }

            network_type_value = 0
            for key, value in network_type_map.items():
                if key in self.last_status.network_type:
                    network_type_value = value
                    break

            # Store in RRD
            metric_data = MetricData(
                timestamp=int(datetime.now().timestamp()),
                signal_strength=self.last_signal.rssi,
                signal_quality=(self.last_signal.signal_bars / 5)
                * 100,  # Convert to percentage
                data_rx=self.last_usage.total_download,
                data_tx=self.last_usage.total_upload,
                connection_state=1 if self.last_status.connected else 0,
                network_type=network_type_value,
            )

            self.data_store.update(self.config.uuid, metric_data)
            self.last_collection = datetime.now()

            logger.debug(f"Collected metrics for modem {self.config.name}")
            return True

        except Exception as e:
            logger.error(f"Failed to collect metrics for modem {self.config.name}: {e}")
            return False

    async def check_connection(self) -> bool:
        """Check and manage modem connection"""
        if not self.config.enabled:
            return True

        if not self.connected:
            # Try to reconnect
            if self.reconnect_attempts < self.config.max_reconnect_attempts:
                logger.info(
                    f"Attempting to reconnect modem {self.config.name} (attempt {self.reconnect_attempts + 1})"
                )
                if await self.initialize():
                    self.reconnect_attempts = 0
                    return True
                else:
                    self.reconnect_attempts += 1
                    return False
            else:
                logger.error(
                    f"Max reconnect attempts reached for modem {self.config.name}"
                )
                return False

        # Check if auto-connect is enabled and modem is disconnected
        if (
            self.config.auto_connect
            and self.last_status
            and not self.last_status.connected
        ):
            logger.info(f"Auto-connecting modem {self.config.name}")
            await self.modem.connect_modem()

        # Check signal threshold
        if self.last_signal and self.last_signal.rssi < self.config.signal_threshold:
            logger.warning(
                f"Low signal on modem {self.config.name}: {self.last_signal.rssi} dBm"
            )

        # Check data limit
        if self.config.data_limit_enabled and self.last_usage:
            data_used_mb = self.last_usage.monthly_total / 1024 / 1024
            if data_used_mb >= self.config.data_limit_mb:
                logger.warning(
                    f"Data limit reached on modem {self.config.name}: {data_used_mb:.2f} MB"
                )
                if self.last_status and self.last_status.connected:
                    logger.info(
                        f"Disconnecting modem {self.config.name} due to data limit"
                    )
                    await self.modem.disconnect_modem()

        return True

    async def apply_settings(self) -> bool:
        """Apply configuration settings to modem"""
        if not self.connected or not self.modem:
            return False

        try:
            # Set roaming
            await self.modem.set_roaming(self.config.roaming_enabled)

            # Set network mode
            mode_map = {
                "auto": NetworkMode.AUTO,
                "4g_preferred": NetworkMode.LTE_WCDMA_GSM,
                "3g_preferred": NetworkMode.WCDMA_GSM,
                "4g_only": NetworkMode.LTE_ONLY,
                "3g_only": NetworkMode.WCDMA_ONLY,
            }

            if self.config.network_mode in mode_map:
                await self.modem.set_network_mode(mode_map[self.config.network_mode])

            logger.info(f"Applied settings to modem {self.config.name}")
            return True

        except Exception as e:
            logger.error(f"Failed to apply settings to modem {self.config.name}: {e}")
            return False


class HiLinkService:
    """Main HiLink service daemon"""

    def __init__(self, config_path: Optional[str] = None):
        """
        Initialize HiLink service

        Args:
            config_path: Optional custom configuration path
        """
        self.config_manager = ConfigManager(config_path)
        self.data_store = DataStore()
        self.modem_managers: Dict[str, ModemManager] = {}
        self.running = False
        self.tasks: List[asyncio.Task] = []

    async def initialize(self) -> bool:
        """Initialize the service"""
        # Load configuration
        if not self.config_manager.load():
            logger.error("Failed to load configuration")
            return False

        # Validate configuration
        errors = self.config_manager.validate()
        if errors:
            logger.error(f"Configuration validation errors: {errors}")
            return False

        # Initialize modem managers
        for modem_config in self.config_manager.modems:
            if modem_config.enabled:
                manager = ModemManager(modem_config, self.data_store)
                if await manager.initialize():
                    self.modem_managers[modem_config.uuid] = manager
                    await manager.apply_settings()

        if not self.modem_managers:
            logger.warning("No modems initialized")

        logger.info(f"Service initialized with {len(self.modem_managers)} modem(s)")
        return True

    async def cleanup(self):
        """Clean up service resources"""
        # Cancel all tasks
        for task in self.tasks:
            task.cancel()

        # Wait for tasks to complete
        if self.tasks:
            await asyncio.gather(*self.tasks, return_exceptions=True)

        # Clean up modem managers
        for manager in self.modem_managers.values():
            await manager.cleanup()

        logger.info("Service cleanup completed")

    async def monitor_loop(self):
        """Main monitoring loop"""
        logger.info("Starting monitoring loop")

        while self.running:
            try:
                # Collect metrics from all modems
                for manager in self.modem_managers.values():
                    if manager.config.enabled:
                        # Check if it's time to collect
                        time_since_last = (
                            datetime.now() - manager.last_collection
                        ).total_seconds()
                        if time_since_last >= manager.config.collect_interval:
                            await manager.collect_metrics()

                        # Check connection status
                        await manager.check_connection()

                # Wait before next iteration
                await asyncio.sleep(5)

            except Exception as e:
                logger.error(f"Error in monitoring loop: {e}")
                await asyncio.sleep(10)

        logger.info("Monitoring loop stopped")

    async def config_reload_loop(self):
        """Configuration reload loop"""
        logger.info("Starting configuration reload loop")

        while self.running:
            try:
                # Wait for reload interval
                await asyncio.sleep(60)  # Check every minute

                # Reload configuration
                if self.config_manager.load():
                    # Check for changes
                    current_uuids = set(self.modem_managers.keys())
                    new_uuids = set(
                        m.uuid for m in self.config_manager.modems if m.enabled
                    )

                    # Remove deleted modems
                    for uuid in current_uuids - new_uuids:
                        logger.info(f"Removing modem {uuid}")
                        await self.modem_managers[uuid].cleanup()
                        del self.modem_managers[uuid]

                    # Add new modems
                    for uuid in new_uuids - current_uuids:
                        modem_config = self.config_manager.get_modem(uuid)
                        if modem_config:
                            logger.info(f"Adding modem {modem_config.name}")
                            manager = ModemManager(modem_config, self.data_store)
                            if await manager.initialize():
                                self.modem_managers[uuid] = manager
                                await manager.apply_settings()

                    # Update existing modems
                    for uuid in current_uuids & new_uuids:
                        modem_config = self.config_manager.get_modem(uuid)
                        if modem_config:
                            self.modem_managers[uuid].config = modem_config
                            await self.modem_managers[uuid].apply_settings()

            except Exception as e:
                logger.error(f"Error in config reload loop: {e}")

        logger.info("Configuration reload loop stopped")

    async def cleanup_loop(self):
        """Data cleanup loop"""
        logger.info("Starting cleanup loop")

        while self.running:
            try:
                # Wait for cleanup interval (daily)
                await asyncio.sleep(86400)

                # Clean up old RRD data
                retention_days = self.config_manager.general.data_retention
                deleted = self.data_store.cleanup_old_data(retention_days)
                if deleted > 0:
                    logger.info(f"Cleaned up {deleted} old RRD files")

            except Exception as e:
                logger.error(f"Error in cleanup loop: {e}")

        logger.info("Cleanup loop stopped")

    async def run(self):
        """Run the service"""
        logger.info("Starting HiLink service")
        self.running = True

        # Initialize service
        if not await self.initialize():
            logger.error("Service initialization failed")
            return

        # Start background tasks
        self.tasks = [
            asyncio.create_task(self.monitor_loop()),
            asyncio.create_task(self.config_reload_loop()),
            asyncio.create_task(self.cleanup_loop()),
        ]

        # Wait for tasks
        try:
            await asyncio.gather(*self.tasks)
        except asyncio.CancelledError:
            logger.info("Service tasks cancelled")

        # Cleanup
        await self.cleanup()
        logger.info("HiLink service stopped")

    async def stop(self):
        """Stop the service"""
        logger.info("Stopping HiLink service")
        self.running = False

        # Cancel tasks
        for task in self.tasks:
            task.cancel()


def handle_signal(signum, frame):
    """Signal handler for graceful shutdown"""
    logger.info(f"Received signal {signum}")
    asyncio.create_task(service.stop())


async def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(description="HiLink Service Daemon")
    parser.add_argument("--config", help="Configuration directory path", default=None)
    parser.add_argument(
        "--foreground", action="store_true", help="Run in foreground (don't daemonize)"
    )
    parser.add_argument("--debug", action="store_true", help="Enable debug logging")
    parser.add_argument(
        "--pidfile", help="PID file path", default="/var/run/hilink.pid"
    )

    args = parser.parse_args()

    # Set debug logging if requested
    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)

    # Create service instance
    global service
    service = HiLinkService(args.config)

    # Set up signal handlers
    signal.signal(signal.SIGTERM, handle_signal)
    signal.signal(signal.SIGINT, handle_signal)

    if args.foreground:
        # Run in foreground
        await service.run()
    else:
        # Daemonize
        context = daemon.DaemonContext(
            working_directory="/",
            umask=0o002,
            pidfile=lockfile.FileLock(args.pidfile),
            files_preserve=[
                handler.stream.fileno()
                for handler in logging.getLogger().handlers
                if hasattr(handler, "stream")
            ],
        )

        with context:
            # Run service
            asyncio.run(service.run())


if __name__ == "__main__":
    # Run main
    asyncio.run(main())
