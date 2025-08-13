"""
Data store for HiLink plugin
Handles RRD database operations and historical data management
"""

import os
import time
import logging
import rrdtool
from typing import Dict, Any, List, Optional, Tuple
from pathlib import Path
from datetime import datetime, timedelta
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class MetricData:
    """Container for metric data"""

    timestamp: int
    signal_strength: float  # dBm
    data_rx: int  # bytes
    data_tx: int  # bytes
    connection_state: int  # 0=disconnected, 1=connected
    signal_quality: float  # percentage
    network_type: int  # 0=none, 1=2G, 2=3G, 3=4G, 4=5G


class DataStore:
    """Manages RRD databases for HiLink metrics"""

    # RRD database configuration
    RRD_BASE_PATH = "/var/db/hilink/rrd"
    RRD_STEP = 30  # seconds between updates

    # Data source definitions
    DATA_SOURCES = {
        "signal_strength": {"type": "GAUGE", "heartbeat": 120, "min": -120, "max": -40},
        "signal_quality": {"type": "GAUGE", "heartbeat": 120, "min": 0, "max": 100},
        "data_rx": {"type": "COUNTER", "heartbeat": 120, "min": 0, "max": "U"},
        "data_tx": {"type": "COUNTER", "heartbeat": 120, "min": 0, "max": "U"},
        "connection_state": {"type": "GAUGE", "heartbeat": 120, "min": 0, "max": 1},
        "network_type": {"type": "GAUGE", "heartbeat": 120, "min": 0, "max": 5},
    }

    # RRA (Round Robin Archive) definitions
    # Keep: 5-minute avg for 2 days, hourly avg for 2 weeks, daily avg for 2 years
    RRA_DEFINITIONS = [
        "RRA:AVERAGE:0.5:1:5760",  # 30-sec samples for 2 days
        "RRA:AVERAGE:0.5:10:8640",  # 5-min average for 30 days
        "RRA:AVERAGE:0.5:120:4320",  # 1-hour average for 180 days
        "RRA:AVERAGE:0.5:2880:730",  # 1-day average for 2 years
        "RRA:MIN:0.5:10:8640",  # 5-min minimum for 30 days
        "RRA:MAX:0.5:10:8640",  # 5-min maximum for 30 days
        "RRA:MIN:0.5:120:4320",  # 1-hour minimum for 180 days
        "RRA:MAX:0.5:120:4320",  # 1-hour maximum for 180 days
    ]

    def __init__(self, base_path: Optional[str] = None):
        """
        Initialize data store

        Args:
            base_path: Optional custom base path for RRD files
        """
        self.base_path = Path(base_path or self.RRD_BASE_PATH)
        self.base_path.mkdir(parents=True, exist_ok=True)

        # Cache for RRD file paths
        self._rrd_files: Dict[str, Path] = {}

    def get_rrd_path(self, modem_uuid: str) -> Path:
        """
        Get RRD file path for a modem

        Args:
            modem_uuid: UUID of the modem

        Returns:
            Path to RRD file
        """
        if modem_uuid not in self._rrd_files:
            self._rrd_files[modem_uuid] = self.base_path / f"{modem_uuid}.rrd"
        return self._rrd_files[modem_uuid]

    def create_rrd(self, modem_uuid: str, retention_days: int = 30) -> bool:
        """
        Create RRD database for a modem

        Args:
            modem_uuid: UUID of the modem
            retention_days: Data retention period in days

        Returns:
            True if RRD created successfully
        """
        rrd_path = self.get_rrd_path(modem_uuid)

        # Skip if already exists
        if rrd_path.exists():
            logger.debug(f"RRD already exists for modem {modem_uuid}")
            return True

        try:
            # Build data source definitions
            ds_defs = []
            for name, config in self.DATA_SOURCES.items():
                ds_def = f"DS:{name}:{config['type']}:{config['heartbeat']}:{config['min']}:{config['max']}"
                ds_defs.append(ds_def)

            # Create RRD
            rrdtool.create(
                str(rrd_path),
                "--start",
                "now-1h",
                "--step",
                str(self.RRD_STEP),
                *ds_defs,
                *self.RRA_DEFINITIONS,
            )

            logger.info(f"Created RRD for modem {modem_uuid} at {rrd_path}")
            return True

        except Exception as e:
            logger.error(f"Failed to create RRD for modem {modem_uuid}: {e}")
            return False

    def update(self, modem_uuid: str, data: MetricData) -> bool:
        """
        Update RRD with new metric data

        Args:
            modem_uuid: UUID of the modem
            data: Metric data to store

        Returns:
            True if update successful
        """
        rrd_path = self.get_rrd_path(modem_uuid)

        # Create RRD if it doesn't exist
        if not rrd_path.exists():
            if not self.create_rrd(modem_uuid):
                return False

        try:
            # Prepare update values
            values = [
                str(data.timestamp),
                str(data.signal_strength),
                str(data.signal_quality),
                str(data.data_rx),
                str(data.data_tx),
                str(data.connection_state),
                str(data.network_type),
            ]

            # Update RRD
            rrdtool.update(str(rrd_path), ":".join(values))

            logger.debug(f"Updated RRD for modem {modem_uuid}")
            return True

        except Exception as e:
            logger.error(f"Failed to update RRD for modem {modem_uuid}: {e}")
            return False

    def fetch(
        self,
        modem_uuid: str,
        start_time: Optional[int] = None,
        end_time: Optional[int] = None,
        resolution: Optional[int] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        Fetch data from RRD

        Args:
            modem_uuid: UUID of the modem
            start_time: Start timestamp (default: 1 hour ago)
            end_time: End timestamp (default: now)
            resolution: Data resolution in seconds (default: auto)

        Returns:
            Dictionary with timestamps and metric data
        """
        rrd_path = self.get_rrd_path(modem_uuid)

        if not rrd_path.exists():
            logger.warning(f"RRD not found for modem {modem_uuid}")
            return None

        try:
            # Set defaults
            if end_time is None:
                end_time = int(time.time())
            if start_time is None:
                start_time = end_time - 3600  # 1 hour ago

            # Fetch data
            result = rrdtool.fetch(
                str(rrd_path),
                "AVERAGE",
                "--start",
                str(start_time),
                "--end",
                str(end_time),
                "--resolution",
                str(resolution) if resolution else "30",
            )

            # Parse result
            (start, end, step), ds_names, data = result

            # Build response
            response = {
                "start": start,
                "end": end,
                "step": step,
                "timestamps": [],
                "metrics": {name: [] for name in ds_names},
            }

            # Process data points
            current_time = start
            for row in data:
                response["timestamps"].append(current_time)
                for i, name in enumerate(ds_names):
                    value = row[i]
                    # Convert None to null for JSON serialization
                    response["metrics"][name].append(
                        value if value is not None else None
                    )
                current_time += step

            return response

        except Exception as e:
            logger.error(f"Failed to fetch data for modem {modem_uuid}: {e}")
            return None

    def get_latest(self, modem_uuid: str) -> Optional[MetricData]:
        """
        Get latest metric data for a modem

        Args:
            modem_uuid: UUID of the modem

        Returns:
            Latest metric data or None
        """
        rrd_path = self.get_rrd_path(modem_uuid)

        if not rrd_path.exists():
            return None

        try:
            # Get last update info
            info = rrdtool.info(str(rrd_path))
            last_update = info.get("last_update", 0)

            # Fetch last data point
            data = self.fetch(
                modem_uuid,
                start_time=last_update - 60,
                end_time=last_update,
                resolution=self.RRD_STEP,
            )

            if not data or not data["timestamps"]:
                return None

            # Get last non-null values
            last_idx = -1
            while last_idx >= -len(data["timestamps"]):
                metrics = data["metrics"]
                if metrics["signal_strength"][last_idx] is not None:
                    return MetricData(
                        timestamp=data["timestamps"][last_idx],
                        signal_strength=metrics["signal_strength"][last_idx],
                        signal_quality=metrics["signal_quality"][last_idx] or 0,
                        data_rx=int(metrics["data_rx"][last_idx] or 0),
                        data_tx=int(metrics["data_tx"][last_idx] or 0),
                        connection_state=int(
                            metrics["connection_state"][last_idx] or 0
                        ),
                        network_type=int(metrics["network_type"][last_idx] or 0),
                    )
                last_idx -= 1

            return None

        except Exception as e:
            logger.error(f"Failed to get latest data for modem {modem_uuid}: {e}")
            return None

    def get_statistics(
        self,
        modem_uuid: str,
        start_time: Optional[int] = None,
        end_time: Optional[int] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        Get statistics for a time period

        Args:
            modem_uuid: UUID of the modem
            start_time: Start timestamp
            end_time: End timestamp

        Returns:
            Statistics dictionary
        """
        data = self.fetch(modem_uuid, start_time, end_time)

        if not data:
            return None

        try:
            stats = {}

            # Calculate statistics for each metric
            for metric_name, values in data["metrics"].items():
                # Filter out None values
                valid_values = [v for v in values if v is not None]

                if not valid_values:
                    stats[metric_name] = {
                        "min": None,
                        "max": None,
                        "avg": None,
                        "last": None,
                    }
                else:
                    stats[metric_name] = {
                        "min": min(valid_values),
                        "max": max(valid_values),
                        "avg": sum(valid_values) / len(valid_values),
                        "last": valid_values[-1],
                    }

            # Calculate uptime percentage
            connection_values = [
                v for v in data["metrics"]["connection_state"] if v is not None
            ]
            if connection_values:
                uptime_percentage = (
                    sum(connection_values) / len(connection_values)
                ) * 100
                stats["uptime_percentage"] = round(uptime_percentage, 2)
            else:
                stats["uptime_percentage"] = 0

            # Calculate total data transferred
            rx_values = [v for v in data["metrics"]["data_rx"] if v is not None]
            tx_values = [v for v in data["metrics"]["data_tx"] if v is not None]

            if rx_values and tx_values:
                # For COUNTER type, the difference between first and last gives total
                stats["total_data_rx"] = (
                    int(rx_values[-1] - rx_values[0]) if len(rx_values) > 1 else 0
                )
                stats["total_data_tx"] = (
                    int(tx_values[-1] - tx_values[0]) if len(tx_values) > 1 else 0
                )
                stats["total_data"] = stats["total_data_rx"] + stats["total_data_tx"]
            else:
                stats["total_data_rx"] = 0
                stats["total_data_tx"] = 0
                stats["total_data"] = 0

            return stats

        except Exception as e:
            logger.error(f"Failed to calculate statistics for modem {modem_uuid}: {e}")
            return None

    def cleanup_old_data(self, retention_days: int = 30) -> int:
        """
        Clean up old RRD files

        Args:
            retention_days: Keep files modified within this many days

        Returns:
            Number of files deleted
        """
        deleted_count = 0
        cutoff_time = time.time() - (retention_days * 86400)

        try:
            for rrd_file in self.base_path.glob("*.rrd"):
                if rrd_file.stat().st_mtime < cutoff_time:
                    rrd_file.unlink()
                    deleted_count += 1
                    logger.info(f"Deleted old RRD file: {rrd_file}")

        except Exception as e:
            logger.error(f"Error during cleanup: {e}")

        return deleted_count

    def export_to_csv(
        self,
        modem_uuid: str,
        output_path: str,
        start_time: Optional[int] = None,
        end_time: Optional[int] = None,
    ) -> bool:
        """
        Export RRD data to CSV file

        Args:
            modem_uuid: UUID of the modem
            output_path: Path to output CSV file
            start_time: Start timestamp
            end_time: End timestamp

        Returns:
            True if export successful
        """
        data = self.fetch(modem_uuid, start_time, end_time)

        if not data:
            return False

        try:
            import csv

            with open(output_path, "w", newline="") as csvfile:
                # Prepare headers
                headers = ["timestamp", "datetime"] + list(data["metrics"].keys())
                writer = csv.DictWriter(csvfile, fieldnames=headers)
                writer.writeheader()

                # Write data rows
                for i, timestamp in enumerate(data["timestamps"]):
                    row = {
                        "timestamp": timestamp,
                        "datetime": datetime.fromtimestamp(timestamp).isoformat(),
                    }

                    for metric_name, values in data["metrics"].items():
                        row[metric_name] = values[i] if values[i] is not None else ""

                    writer.writerow(row)

            logger.info(f"Exported data to {output_path}")
            return True

        except Exception as e:
            logger.error(f"Failed to export data to CSV: {e}")
            return False

    def generate_graph(
        self,
        modem_uuid: str,
        output_path: str,
        metric: str = "signal_strength",
        width: int = 800,
        height: int = 400,
        start_time: Optional[int] = None,
        end_time: Optional[int] = None,
        title: Optional[str] = None,
    ) -> bool:
        """
        Generate graph from RRD data

        Args:
            modem_uuid: UUID of the modem
            output_path: Path to output image file
            metric: Metric to graph
            width: Graph width in pixels
            height: Graph height in pixels
            start_time: Start timestamp
            end_time: End timestamp
            title: Graph title

        Returns:
            True if graph generated successfully
        """
        rrd_path = self.get_rrd_path(modem_uuid)

        if not rrd_path.exists():
            logger.warning(f"RRD not found for modem {modem_uuid}")
            return False

        try:
            # Set defaults
            if end_time is None:
                end_time = int(time.time())
            if start_time is None:
                start_time = end_time - 86400  # 24 hours ago
            if title is None:
                title = f"{metric.replace('_', ' ').title()} - Modem {modem_uuid[:8]}"

            # Define graph parameters based on metric
            if metric == "signal_strength":
                vertical_label = "Signal (dBm)"
                upper_limit = -40
                lower_limit = -120
                line_color = "#0066CC"
            elif metric == "signal_quality":
                vertical_label = "Quality (%)"
                upper_limit = 100
                lower_limit = 0
                line_color = "#00CC66"
            elif metric in ("data_rx", "data_tx"):
                vertical_label = "Data (bytes/sec)"
                upper_limit = None
                lower_limit = 0
                line_color = "#CC6600" if metric == "data_rx" else "#CC0066"
            else:
                vertical_label = metric.replace("_", " ").title()
                upper_limit = None
                lower_limit = None
                line_color = "#666666"

            # Build graph command
            graph_args = [
                str(output_path),
                "--start",
                str(start_time),
                "--end",
                str(end_time),
                "--width",
                str(width),
                "--height",
                str(height),
                "--title",
                title,
                "--vertical-label",
                vertical_label,
                "--watermark",
                f'Generated {datetime.now().strftime("%Y-%m-%d %H:%M")}',
                f"DEF:{metric}={rrd_path}:{metric}:AVERAGE",
                f'LINE2:{metric}{line_color}:{metric.replace("_", " ").title()}',
            ]

            if upper_limit is not None:
                graph_args.extend(["--upper-limit", str(upper_limit)])
            if lower_limit is not None:
                graph_args.extend(["--lower-limit", str(lower_limit)])

            # Generate graph
            rrdtool.graph(*graph_args)

            logger.info(f"Generated graph at {output_path}")
            return True

        except Exception as e:
            logger.error(f"Failed to generate graph: {e}")
            return False


# Example usage
if __name__ == "__main__":
    import asyncio
    from hilink_api import HiLinkModem

    async def test_data_store():
        # Create data store
        store = DataStore()

        # Test modem UUID
        modem_uuid = "test-modem-001"

        # Create RRD
        store.create_rrd(modem_uuid)

        # Simulate some data updates
        for i in range(10):
            data = MetricData(
                timestamp=int(time.time()),
                signal_strength=-65 - i,
                signal_quality=80 - i * 2,
                data_rx=1000000 * i,
                data_tx=500000 * i,
                connection_state=1,
                network_type=3,  # 4G
            )
            store.update(modem_uuid, data)
            time.sleep(30)  # Wait 30 seconds

        # Fetch data
        result = store.fetch(modem_uuid)
        print("Fetched data:", result)

        # Get statistics
        stats = store.get_statistics(modem_uuid)
        print("Statistics:", stats)

        # Export to CSV
        store.export_to_csv(modem_uuid, "/tmp/modem_data.csv")

        # Generate graph
        store.generate_graph(
            modem_uuid, "/tmp/signal_strength.png", metric="signal_strength"
        )

    # Run test
    # asyncio.run(test_data_store())
