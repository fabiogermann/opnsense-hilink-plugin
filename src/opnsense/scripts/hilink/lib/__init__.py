"""
HiLink Plugin Library
OPNsense plugin for Huawei HiLink modem management
"""

__version__ = "1.0.0"
__author__ = "HiLink Plugin Team"

from .hilink_api import HiLinkModem, ModemStatus, SignalInfo, DataUsage, NetworkMode
from .config_manager import ConfigManager
from .data_store import DataStore

__all__ = [
    "HiLinkModem",
    "ModemStatus",
    "SignalInfo",
    "DataUsage",
    "NetworkMode",
    "ConfigManager",
    "DataStore",
]
