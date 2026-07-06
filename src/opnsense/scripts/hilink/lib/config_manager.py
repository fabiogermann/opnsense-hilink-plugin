"""
Configuration manager for HiLink plugin
Handles loading, saving, and validating configuration
"""

import os
import json
import logging
import defusedxml
import defusedxml.ElementTree as DefusedET
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, asdict, field
from pathlib import Path
import uuid

logger = logging.getLogger(__name__)


@dataclass
class ModemConfig:
    """Configuration for a single modem"""

    uuid: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = "HiLink Modem"
    enabled: bool = True
    ip_address: str = "192.168.8.1"
    username: str = "admin"
    password: str = ""
    auto_connect: bool = True
    roaming_enabled: bool = False
    max_idle_time: int = 0  # 0 = disabled
    network_mode: str = "auto"  # auto, 4g_preferred, 3g_preferred, 4g_only, 3g_only
    reconnect_interval: int = 60  # seconds
    max_reconnect_attempts: int = 3

    # Monitoring settings
    collect_interval: int = 30  # seconds
    signal_threshold: int = -90  # dBm
    data_limit_enabled: bool = False
    data_limit_mb: int = 10240  # MB
    alert_email: str = ""

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ModemConfig":
        """Create from dictionary"""
        return cls(**data)


@dataclass
class GeneralConfig:
    """General plugin configuration"""

    enabled: bool = True
    update_interval: int = 30  # seconds
    data_retention: int = 30  # days
    debug_logging: bool = False

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "GeneralConfig":
        """Create from dictionary"""
        return cls(**data)


@dataclass
class AlertConfig:
    """Alert configuration"""

    low_signal_threshold: int = -90  # dBm
    data_limit_enabled: bool = False
    data_limit_mb: int = 10240  # MB
    email_alerts: bool = False
    email_to: str = ""
    email_from: str = ""
    smtp_server: str = ""
    smtp_port: int = 587
    smtp_username: str = ""
    smtp_password: str = ""
    smtp_use_tls: bool = True

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "AlertConfig":
        """Create from dictionary"""
        return cls(**data)


class ConfigManager:
    """Manages HiLink plugin configuration"""

    # Configuration paths - can be overridden by environment variables
    CONFIG_BASE_PATH = os.environ.get("HILINK_CONFIG_DIR", "/usr/local/etc/hilink")
    CONFIG_FILE = "config.json"
    CONFIG_XML_PATH = (
        os.environ.get("OPNSENSE_CONFIG_DIR", "/usr/local/etc/OPNsense") + "/hilink"
    )
    CONFIG_XML_FILE = "hilink.xml"
    # The OPNsense system configuration is the source of truth on a firewall
    SYSTEM_CONFIG_XML = os.environ.get("OPNSENSE_SYSTEM_CONFIG", "/conf/config.xml")

    # Prefix marking values stored base64 encoded by this plugin
    B64_PREFIX = "b64:"

    def __init__(self, config_path: Optional[str] = None):
        """
        Initialize configuration manager

        Args:
            config_path: Optional custom configuration path
        """
        # Allow environment variable override
        default_path = os.environ.get("HILINK_CONFIG_DIR", self.CONFIG_BASE_PATH)
        self.config_path = Path(config_path or default_path)
        self.config_file = self.config_path / self.CONFIG_FILE

        # XML path: env override wins, an explicit config path keeps the
        # plugin XML next to the JSON, otherwise use the system default
        xml_base = os.environ.get("OPNSENSE_CONFIG_DIR")
        if xml_base is not None:
            self.xml_path = Path(xml_base) / "hilink"
        elif config_path:
            self.xml_path = self.config_path
        else:
            self.xml_path = Path("/usr/local/etc/OPNsense") / "hilink"
        self.xml_file = self.xml_path / self.CONFIG_XML_FILE

        # Configuration data
        self.general: GeneralConfig = GeneralConfig()
        self.modems: List[ModemConfig] = []
        self.alerts: AlertConfig = AlertConfig()

        # Ensure directories exist
        self._ensure_directories()

    def _ensure_directories(self):
        """Ensure configuration directories exist (best effort)"""
        for path in (self.config_path, self.xml_path):
            try:
                path.mkdir(parents=True, exist_ok=True)
            except OSError as e:
                logger.warning(f"Could not create directory {path}: {e}")

    def load(self) -> bool:
        """
        Load configuration from file

        Returns:
            True if configuration loaded successfully
        """
        # Prefer the OPNsense system configuration when it contains our section
        system_config = Path(self.SYSTEM_CONFIG_XML)
        if system_config.exists() and self._load_from_xml(system_config):
            return True
        # Then a plugin specific XML export
        if self.xml_file.exists():
            return self._load_from_xml(self.xml_file)
        # Fall back to JSON
        if self.config_file.exists():
            return self._load_from_json()

        logger.info("No configuration found, using defaults")
        self._create_default_config()
        return True

    def _load_from_json(self) -> bool:
        """Load configuration from JSON file"""
        try:
            with open(self.config_file, "r") as f:
                data = json.load(f)

            # Load general config
            if "general" in data:
                self.general = GeneralConfig.from_dict(data["general"])

            # Load modems
            self.modems = []
            if "modems" in data:
                for modem_data in data["modems"]:
                    self.modems.append(ModemConfig.from_dict(modem_data))

            # Load alerts
            if "alerts" in data:
                self.alerts = AlertConfig.from_dict(data["alerts"])

            logger.info(f"Configuration loaded from {self.config_file}")
            return True

        except Exception as e:
            logger.error(f"Failed to load configuration: {e}")
            return False

    @staticmethod
    def _findint(elem, name: str, default: int) -> int:
        """Read an integer child element, tolerating missing or empty values"""
        text = elem.findtext(name)
        if text is None or not str(text).strip():
            return default
        try:
            return int(text)
        except ValueError:
            return default

    def _load_from_xml(self, xml_file: Optional[Path] = None) -> bool:
        """Load configuration from OPNsense XML format

        Understands both the plugin export format and the OPNsense system
        configuration (/conf/config.xml), where modem entries carry their
        uuid as an XML attribute.
        """
        if xml_file is None:
            xml_file = self.xml_file
        try:
            tree = DefusedET.parse(xml_file)
            root = tree.getroot()

            # Find hilink section
            hilink = root.find(".//hilink")
            if hilink is None:
                logger.warning(f"No hilink section in {xml_file}")
                return False

            # Load general config
            general = hilink.find("general")
            if general is not None:
                self.general = GeneralConfig(
                    enabled=general.findtext("enabled", "1") == "1",
                    update_interval=self._findint(general, "update_interval", 30),
                    data_retention=self._findint(general, "data_retention", 30),
                    debug_logging=general.findtext("debug_logging", "0") == "1",
                )

            # Load modems
            self.modems = []
            modems = hilink.find("modems")
            if modems is not None:
                for modem_elem in modems.findall("modem"):
                    # OPNsense stores the uuid as attribute, plugin exports as child
                    modem_uuid = (
                        modem_elem.get("uuid")
                        or modem_elem.findtext("uuid")
                        or str(uuid.uuid4())
                    )
                    modem = ModemConfig(
                        uuid=modem_uuid,
                        name=modem_elem.findtext("name") or "HiLink Modem",
                        enabled=modem_elem.findtext("enabled", "1") == "1",
                        ip_address=modem_elem.findtext("ip_address") or "192.168.8.1",
                        username=modem_elem.findtext("username") or "admin",
                        password=self._decrypt_password(
                            modem_elem.findtext("password", "") or ""
                        ),
                        auto_connect=modem_elem.findtext("auto_connect", "1") == "1",
                        roaming_enabled=modem_elem.findtext("roaming_enabled", "0")
                        == "1",
                        max_idle_time=self._findint(modem_elem, "max_idle_time", 0),
                        network_mode=modem_elem.findtext("network_mode") or "auto",
                        reconnect_interval=self._findint(
                            modem_elem, "reconnect_interval", 60
                        ),
                        max_reconnect_attempts=self._findint(
                            modem_elem, "max_reconnect_attempts", 3
                        ),
                        collect_interval=self._findint(
                            modem_elem, "collect_interval", 30
                        ),
                        signal_threshold=self._findint(
                            modem_elem, "signal_threshold", -90
                        ),
                        data_limit_enabled=modem_elem.findtext(
                            "data_limit_enabled", "0"
                        )
                        == "1",
                        data_limit_mb=self._findint(modem_elem, "data_limit_mb", 10240),
                        alert_email=modem_elem.findtext("alert_email", "") or "",
                    )
                    self.modems.append(modem)

            # Load alerts
            alerts = hilink.find("alerts")
            if alerts is not None:
                self.alerts = AlertConfig(
                    low_signal_threshold=self._findint(
                        alerts, "low_signal_threshold", -90
                    ),
                    data_limit_enabled=alerts.findtext("data_limit_enabled", "0")
                    == "1",
                    data_limit_mb=self._findint(alerts, "data_limit_mb", 10240),
                    email_alerts=alerts.findtext("email_alerts", "0") == "1",
                    email_to=alerts.findtext("email_to", "") or "",
                    email_from=alerts.findtext("email_from", "") or "",
                    smtp_server=alerts.findtext("smtp_server", "") or "",
                    smtp_port=self._findint(alerts, "smtp_port", 587),
                    smtp_username=alerts.findtext("smtp_username", "") or "",
                    smtp_password=self._decrypt_password(
                        alerts.findtext("smtp_password", "") or ""
                    ),
                    smtp_use_tls=alerts.findtext("smtp_use_tls", "1") == "1",
                )

            logger.info(f"Configuration loaded from {xml_file}")
            return True

        except Exception as e:
            logger.error(f"Failed to load XML configuration from {xml_file}: {e}")
            return False

    def save(self) -> bool:
        """
        Save configuration to file

        Returns:
            True if configuration saved successfully
        """
        # Save to both JSON and XML
        json_saved = self._save_to_json()
        xml_saved = self._save_to_xml()

        return json_saved and xml_saved

    def _save_to_json(self) -> bool:
        """Save configuration to JSON file"""
        try:
            data = {
                "general": self.general.to_dict(),
                "modems": [modem.to_dict() for modem in self.modems],
                "alerts": self.alerts.to_dict(),
            }

            with open(self.config_file, "w") as f:
                json.dump(data, f, indent=2)

            logger.info(f"Configuration saved to {self.config_file}")
            return True

        except Exception as e:
            logger.error(f"Failed to save configuration: {e}")
            return False

    def _save_to_xml(self) -> bool:
        """Save configuration to OPNsense XML format"""
        try:
            # Create root element using standard ElementTree
            import xml.etree.ElementTree as StandardET  # nosec

            root = StandardET.Element("opnsense")
            hilink = StandardET.SubElement(root, "hilink")

            # Save general config
            general = StandardET.SubElement(hilink, "general")
            StandardET.SubElement(general, "enabled").text = (
                "1" if self.general.enabled else "0"
            )
            StandardET.SubElement(general, "update_interval").text = str(
                self.general.update_interval
            )
            StandardET.SubElement(general, "data_retention").text = str(
                self.general.data_retention
            )
            StandardET.SubElement(general, "debug_logging").text = (
                "1" if self.general.debug_logging else "0"
            )

            # Save modems
            modems = StandardET.SubElement(hilink, "modems")
            for modem in self.modems:
                modem_elem = StandardET.SubElement(modems, "modem")
                StandardET.SubElement(modem_elem, "uuid").text = modem.uuid
                StandardET.SubElement(modem_elem, "name").text = modem.name
                StandardET.SubElement(modem_elem, "enabled").text = (
                    "1" if modem.enabled else "0"
                )
                StandardET.SubElement(modem_elem, "ip_address").text = modem.ip_address
                StandardET.SubElement(modem_elem, "username").text = modem.username
                StandardET.SubElement(modem_elem, "password").text = (
                    self._encrypt_password(modem.password)
                )
                StandardET.SubElement(modem_elem, "auto_connect").text = (
                    "1" if modem.auto_connect else "0"
                )
                StandardET.SubElement(modem_elem, "roaming_enabled").text = (
                    "1" if modem.roaming_enabled else "0"
                )
                StandardET.SubElement(modem_elem, "max_idle_time").text = str(
                    modem.max_idle_time
                )
                StandardET.SubElement(modem_elem, "network_mode").text = (
                    modem.network_mode
                )
                StandardET.SubElement(modem_elem, "reconnect_interval").text = str(
                    modem.reconnect_interval
                )
                StandardET.SubElement(modem_elem, "max_reconnect_attempts").text = str(
                    modem.max_reconnect_attempts
                )
                StandardET.SubElement(modem_elem, "collect_interval").text = str(
                    modem.collect_interval
                )
                StandardET.SubElement(modem_elem, "signal_threshold").text = str(
                    modem.signal_threshold
                )
                StandardET.SubElement(modem_elem, "data_limit_enabled").text = (
                    "1" if modem.data_limit_enabled else "0"
                )
                StandardET.SubElement(modem_elem, "data_limit_mb").text = str(
                    modem.data_limit_mb
                )
                StandardET.SubElement(modem_elem, "alert_email").text = (
                    modem.alert_email
                )

            # Save alerts
            alerts = StandardET.SubElement(hilink, "alerts")
            StandardET.SubElement(alerts, "low_signal_threshold").text = str(
                self.alerts.low_signal_threshold
            )
            StandardET.SubElement(alerts, "data_limit_enabled").text = (
                "1" if self.alerts.data_limit_enabled else "0"
            )
            StandardET.SubElement(alerts, "data_limit_mb").text = str(
                self.alerts.data_limit_mb
            )
            StandardET.SubElement(alerts, "email_alerts").text = (
                "1" if self.alerts.email_alerts else "0"
            )
            StandardET.SubElement(alerts, "email_to").text = self.alerts.email_to
            StandardET.SubElement(alerts, "email_from").text = self.alerts.email_from
            StandardET.SubElement(alerts, "smtp_server").text = self.alerts.smtp_server
            StandardET.SubElement(alerts, "smtp_port").text = str(self.alerts.smtp_port)
            StandardET.SubElement(alerts, "smtp_username").text = (
                self.alerts.smtp_username
            )
            StandardET.SubElement(alerts, "smtp_password").text = (
                self._encrypt_password(self.alerts.smtp_password)
            )
            StandardET.SubElement(alerts, "smtp_use_tls").text = (
                "1" if self.alerts.smtp_use_tls else "0"
            )

            # Write to file
            self.xml_path.mkdir(parents=True, exist_ok=True)
            tree = StandardET.ElementTree(root)
            tree.write(self.xml_file, encoding="utf-8", xml_declaration=True)

            logger.info(f"Configuration saved to {self.xml_file}")
            return True

        except Exception as e:
            logger.error(f"Failed to save XML configuration: {e}")
            return False

    def _create_default_config(self):
        """Create default configuration"""
        # Add a default modem
        self.modems = [ModemConfig()]

    def _encrypt_password(self, password: str) -> str:
        """
        Obfuscate password for plugin-managed storage.

        Values are prefixed so that plaintext passwords coming from the
        OPNsense system configuration are never mistaken for encoded ones.
        """
        import base64

        if password:
            return self.B64_PREFIX + base64.b64encode(password.encode()).decode()
        return ""

    def _decrypt_password(self, encrypted: str) -> str:
        """Reverse _encrypt_password; unprefixed values pass through unchanged"""
        import base64

        if not encrypted:
            return ""
        if not encrypted.startswith(self.B64_PREFIX):
            return encrypted
        try:
            return base64.b64decode(encrypted[len(self.B64_PREFIX) :].encode()).decode()
        except Exception:
            return encrypted

    def add_modem(self, modem: ModemConfig) -> bool:
        """
        Add a new modem configuration

        Args:
            modem: Modem configuration to add

        Returns:
            True if modem added successfully
        """
        # Check for duplicate UUID
        for existing in self.modems:
            if existing.uuid == modem.uuid:
                logger.error(f"Modem with UUID {modem.uuid} already exists")
                return False

        self.modems.append(modem)
        logger.info(f"Added modem {modem.name} ({modem.uuid})")
        return True

    def remove_modem(self, modem_uuid: str) -> bool:
        """
        Remove a modem configuration

        Args:
            modem_uuid: UUID of modem to remove

        Returns:
            True if modem removed successfully
        """
        for i, modem in enumerate(self.modems):
            if modem.uuid == modem_uuid:
                removed = self.modems.pop(i)
                logger.info(f"Removed modem {removed.name} ({removed.uuid})")
                return True

        logger.error(f"Modem with UUID {modem_uuid} not found")
        return False

    def get_modem(self, modem_uuid: str) -> Optional[ModemConfig]:
        """
        Get modem configuration by UUID

        Args:
            modem_uuid: UUID of modem

        Returns:
            Modem configuration or None if not found
        """
        for modem in self.modems:
            if modem.uuid == modem_uuid:
                return modem
        return None

    def update_modem(self, modem_uuid: str, updates: Dict[str, Any]) -> bool:
        """
        Update modem configuration

        Args:
            modem_uuid: UUID of modem to update
            updates: Dictionary of fields to update

        Returns:
            True if modem updated successfully
        """
        modem = self.get_modem(modem_uuid)
        if not modem:
            logger.error(f"Modem with UUID {modem_uuid} not found")
            return False

        # Update fields
        for key, value in updates.items():
            if hasattr(modem, key):
                setattr(modem, key, value)
            else:
                logger.warning(f"Unknown modem field: {key}")

        logger.info(f"Updated modem {modem.name} ({modem.uuid})")
        return True

    def validate(self) -> List[str]:
        """
        Validate configuration

        Returns:
            List of validation errors (empty if valid)
        """
        errors = []

        # Validate general config
        if self.general.update_interval < 10 or self.general.update_interval > 300:
            errors.append("Update interval must be between 10 and 300 seconds")

        if self.general.data_retention < 1 or self.general.data_retention > 365:
            errors.append("Data retention must be between 1 and 365 days")

        # Validate modems
        if not self.modems:
            errors.append("At least one modem must be configured")

        for modem in self.modems:
            # Validate IP address format
            import ipaddress

            try:
                ipaddress.ip_address(modem.ip_address)
            except ValueError:
                errors.append(
                    f"Invalid IP address for modem {modem.name}: {modem.ip_address}"
                )

            # Validate network mode
            valid_modes = ["auto", "4g_preferred", "3g_preferred", "4g_only", "3g_only"]
            if modem.network_mode not in valid_modes:
                errors.append(
                    f"Invalid network mode for modem {modem.name}: {modem.network_mode}"
                )

            # Validate signal threshold
            if modem.signal_threshold < -120 or modem.signal_threshold > -50:
                errors.append(
                    f"Signal threshold for modem {modem.name} must be between -120 and -50 dBm"
                )

        # Validate alerts
        if self.alerts.email_alerts:
            if not self.alerts.email_to:
                errors.append("Email recipient required when email alerts are enabled")
            if not self.alerts.smtp_server:
                errors.append("SMTP server required when email alerts are enabled")

        return errors

    def export_config(self, filepath: str) -> bool:
        """
        Export configuration to file

        Args:
            filepath: Path to export file

        Returns:
            True if export successful
        """
        try:
            data = {
                "general": self.general.to_dict(),
                "modems": [modem.to_dict() for modem in self.modems],
                "alerts": self.alerts.to_dict(),
            }

            with open(filepath, "w") as f:
                json.dump(data, f, indent=2)

            logger.info(f"Configuration exported to {filepath}")
            return True

        except Exception as e:
            logger.error(f"Failed to export configuration: {e}")
            return False

    def import_config(self, filepath: str) -> bool:
        """
        Import configuration from file

        Args:
            filepath: Path to import file

        Returns:
            True if import successful
        """
        try:
            with open(filepath, "r") as f:
                data = json.load(f)

            # Load general config
            if "general" in data:
                self.general = GeneralConfig.from_dict(data["general"])

            # Load modems
            self.modems = []
            if "modems" in data:
                for modem_data in data["modems"]:
                    self.modems.append(ModemConfig.from_dict(modem_data))

            # Load alerts
            if "alerts" in data:
                self.alerts = AlertConfig.from_dict(data["alerts"])

            # Validate imported config
            errors = self.validate()
            if errors:
                logger.error(f"Imported configuration has errors: {errors}")
                return False

            logger.info(f"Configuration imported from {filepath}")
            return True

        except Exception as e:
            logger.error(f"Failed to import configuration: {e}")
            return False


# Example usage
if __name__ == "__main__":
    # Create config manager
    config = ConfigManager()

    # Load configuration
    config.load()

    # Add a modem
    modem = ModemConfig(  # nosec
        name="Primary 4G Modem",
        ip_address="192.168.8.1",
        username="admin",
        password="admin123",
    )
    config.add_modem(modem)

    # Save configuration
    config.save()

    # Validate configuration
    errors = config.validate()
    if errors:
        print("Configuration errors:", errors)
    else:
        print("Configuration is valid")
