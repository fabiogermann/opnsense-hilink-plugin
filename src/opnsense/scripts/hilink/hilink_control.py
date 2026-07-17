#!/usr/bin/env python3
"""
HiLink Control CLI
One-shot commands invoked by configd (see actions_hilink.conf):

    hilink_control.py status <uuid>       print modem status/signal/usage JSON
    hilink_control.py metrics <uuid>      print historical metrics JSON
    hilink_control.py connect <uuid>      connect the mobile data session
    hilink_control.py disconnect <uuid>   disconnect the mobile data session
    hilink_control.py reboot <uuid>       reboot the modem
    hilink_control.py probe <uuid>        read current settings from the modem
    hilink_control.py test                validate configuration and reachability
"""

import argparse
import asyncio
import dataclasses
import json
import os
import re
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "lib"))

from hilink_api import HiLinkModem  # noqa: E402
from config_manager import ConfigManager, ModemConfig  # noqa: E402
from data_store import DataStore  # noqa: E402


def output(data) -> None:
    """Print a JSON document to stdout"""
    print(json.dumps(data))


def fail(message: str) -> None:
    """Print a JSON error and exit non-zero"""
    output({"status": "error", "message": message})
    sys.exit(1)


def load_modem_config(config_path, modem_uuid: str) -> ModemConfig:
    """Load configuration and resolve the requested modem"""
    config = ConfigManager(config_path)
    if not config.load():
        fail("Failed to load configuration")

    modem = config.get_modem(modem_uuid)
    if modem is None:
        fail(f"Modem {modem_uuid} not found in configuration")
    return modem


async def get_status(modem_config: ModemConfig) -> dict:
    """Collect status, signal and usage information from a modem"""
    modem = HiLinkModem(
        host=modem_config.ip_address,
        username=modem_config.username,
        password=modem_config.password,
        name=modem_config.name,
    )
    async with modem:
        status = await modem.get_status()
        signal = await modem.get_signal_info()
        usage = await modem.get_data_usage()

    result = dataclasses.asdict(status)
    result["connection_status"] = status.connection_status.name
    result["uuid"] = modem_config.uuid
    result["signal"] = dataclasses.asdict(signal)
    result["usage"] = dataclasses.asdict(usage)
    return result


async def run_command(modem_config: ModemConfig, command: str) -> dict:
    """Run a control command against a modem"""
    modem = HiLinkModem(
        host=modem_config.ip_address,
        username=modem_config.username,
        password=modem_config.password,
        name=modem_config.name,
    )
    async with modem:
        if command == "connect":
            ok = await modem.connect_modem()
        elif command == "disconnect":
            ok = await modem.disconnect_modem()
        elif command == "reboot":
            ok = await modem.reboot()
        else:
            return {"status": "error", "message": f"Unknown command {command}"}

    return {"status": "ok" if ok else "error", "command": command}


async def probe_settings(modem_config: ModemConfig) -> dict:
    """Read the modem's current settings without changing anything"""
    modem = HiLinkModem(
        host=modem_config.ip_address,
        username=modem_config.username,
        password=modem_config.password,
        name=modem_config.name,
    )
    async with modem:
        settings = await modem.get_settings()

    return {"status": "ok", "uuid": modem_config.uuid, "settings": settings}


async def list_profiles(modem_config: ModemConfig) -> dict:
    """List the modem's APN profiles and the active one"""
    modem = HiLinkModem(
        host=modem_config.ip_address,
        username=modem_config.username,
        password=modem_config.password,
        name=modem_config.name,
    )
    async with modem:
        profiles = await modem.get_profiles()
        active = await modem.get_active_profile()

    return {
        "status": "ok",
        "uuid": modem_config.uuid,
        "active": active,
        "profiles": profiles,
    }


async def run_test(config_path) -> dict:
    """Validate the configuration and probe each enabled modem"""
    config = ConfigManager(config_path)
    if not config.load():
        return {"status": "error", "message": "Failed to load configuration"}

    errors = config.validate()
    if errors:
        return {"status": "error", "message": "; ".join(errors)}

    results = {}
    for modem_config in config.modems:
        if not modem_config.enabled:
            results[modem_config.name] = "skipped (disabled)"
            continue
        try:
            await get_status(modem_config)
            results[modem_config.name] = "reachable"
        except Exception as e:
            results[modem_config.name] = f"unreachable: {e}"

    reachable = any(v == "reachable" for v in results.values())
    return {
        "status": "success" if reachable or not results else "error",
        "modems": results,
    }


def main():
    parser = argparse.ArgumentParser(description="HiLink modem control")
    parser.add_argument(
        "command",
        choices=[
            "status",
            "metrics",
            "connect",
            "disconnect",
            "reboot",
            "probe",
            "profiles",
            "test",
        ],
    )
    parser.add_argument("uuid", nargs="?", help="Modem UUID")
    parser.add_argument("--config", help="Configuration directory path", default=None)
    args = parser.parse_args()

    if args.command == "test":
        output(asyncio.run(run_test(args.config)))
        return

    if not args.uuid:
        fail("Modem UUID required")

    if not re.fullmatch(r"[0-9a-fA-F-]{1,64}", args.uuid):
        fail("Invalid modem UUID")

    if args.command == "metrics":
        data = DataStore().fetch(args.uuid)
        if data is None:
            fail("No metrics available")
        output(data)
        return

    modem_config = load_modem_config(args.config, args.uuid)
    try:
        if args.command == "status":
            output(asyncio.run(get_status(modem_config)))
        elif args.command == "probe":
            output(asyncio.run(probe_settings(modem_config)))
        elif args.command == "profiles":
            output(asyncio.run(list_profiles(modem_config)))
        else:
            output(asyncio.run(run_command(modem_config, args.command)))
    except Exception as e:
        fail(str(e))


if __name__ == "__main__":
    main()
