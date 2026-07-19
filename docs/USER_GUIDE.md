# HiLink Plugin User Guide

This guide covers installing, configuring, and operating the HiLink plugin
for Huawei HiLink-based 4G/LTE USB modems on OPNsense.

For OPNsense-side setup details (package repo, NAT-mode notes), see
[SETUP.md](SETUP.md). For the REST API, see [API.md](API.md).

## Supported devices

| Model | Status |
|---|---|
| Huawei E3372h-320 | ✅ Tested (primary development device) |
| Huawei E3372s-153 | ✅ Tested |
| Huawei E3372h-153 | ✅ Tested |
| Huawei E8372h series | 📋 Planned |

## Installation

See [SETUP.md](SETUP.md). After installing, navigate to
**Services → HiLink → Dashboard**.

## First-use wizard

The first time you open **Services → HiLink → Settings** with no modem
configured, a wizard runs:

1. Enter the modem's **name**, **IP address** (usually `192.168.8.1`), and
   **web-UI credentials** (`admin` + your modem password).
2. Choose how to populate the settings:
   - **Import current settings from the modem** (recommended) — reads
     network mode, roaming, auto-disconnect and auto-connect from the modem
     so nothing is overwritten.
   - **Import from a `nvram.bak` backup** — for when the modem is currently
     unreachable (download `http://192.168.8.1/nvram.bak` from the modem's
     own UI beforehand).
   - **Start with plugin defaults** — roaming off, automatic network mode;
     these are applied to the modem once it is reachable.

The modem is created **disabled** and only enabled after its settings are
final, so the service never pushes defaults onto an unconfigured device.
The wizard runs once; skipping it marks it as completed.

## Dashboard

**Services → HiLink → Dashboard** shows:

- **Service status** — running/stopped, enabled flag, modem count, and
  Start / Stop / Restart controls.
- **One card per enabled modem** — connection state, network type, operator,
  WAN IP, signal (dBm + bars + quality), and monthly data usage against the
  configured limit.
- **Per-modem actions** — Connect, Disconnect, Reboot (with confirmation).

The dashboard refreshes automatically at the interval configured under
Settings → General → *Update interval* (default 30 s). Each refresh queries
the modem live, so a card can take 1–3 s to update; an unreachable modem
shows as "Unreachable" without affecting the others.

## Settings

**Services → HiLink → Settings**, three tabs. Changes take effect after
**Save & Apply** (which restarts the service).

### General

- **Enable HiLink service** — master switch.
- **Update interval** — dashboard refresh interval in seconds (10–300).
- **Data retention** — days of RRD history to keep (1–365); older RRD files
  are cleaned daily.
- **Debug logging** (advanced) — verbose service logging to
  `/var/log/hilink/service.log`.

### Modems

A grid of configured modems with add / edit / delete / toggle. An upload
button imports a modem from a `nvram.bak` backup file.

Per-modem settings (advanced fields are collapsed by default):

| Field | Notes |
|---|---|
| Enabled | Toggle monitoring/control for this modem |
| Name | Letters, numbers, underscore, hyphen (no spaces) |
| IP address | Modem management address, usually `192.168.8.1` |
| Username / Password | Modem web-UI credentials; empty password = no login |
| Auto connect | Reconnect the data session automatically when it drops |
| Allow roaming | Enable data roaming |
| Network mode | Automatic / 4G preferred / 3G preferred / 4G only / 3G only |
| Reconnect interval (adv.) | Seconds between reconnect attempts (10–3600) |
| Max reconnect attempts (adv.) | Attempts before a 5× back-off (1–10) |
| Auto disconnect (adv.) | Drop the data session after N idle minutes (0 = disabled) |
| LTE band bitmask (adv.) | Hex band lock; `7FFFFFFFFFFFFFFF` = all bands |
| 3G/2G band bitmask (adv.) | Hex band lock; `3FFFFFFF` = all bands |
| Network search (adv.) | Automatic or manual PLMN selection |
| Manual PLMN code / RAT (adv.) | Used only in manual search mode |
| Active APN profile (adv.) | Dropdown populated live from the modem's profile list |
| Collect interval (adv.) | Seconds between metric collections (10–300) |
| Signal threshold (adv.) | Log a warning below this RSSI (-120 to -50 dBm) |
| Enforce data limit | Disconnect when the monthly limit is reached |
| Data limit (MB) | Monthly cap used by enforcement and the dashboard bar |
| Alert email (adv.) | Stored for a future release (see note below) |

### Alerts

Threshold and email fields. **Note:** alert delivery is not yet implemented —
low-signal and data-limit conditions are written to the service log, and the
data-limit condition additionally disconnects the modem. The email/SMTP
fields are stored for a future release.

## Monitoring data

The service stores per-modem metrics (signal strength/quality, data
counters, connection state, network type) in RRD files under
`/var/db/hilink/rrd/<uuid>.rrd`, collected every *Collect interval* seconds
and kept for *Data retention* days. The data is available via
`GET /api/hilink/monitor/metrics`. The dashboard currently does not render
charts (OPNsense ships no charting library and CSP forbids CDNs).

## Troubleshooting

- **Menu item missing** — hard-refresh the browser (Ctrl+Shift+R) or
  re-login; OPNsense caches the menu. If it persists, clear the compiled
  template cache: `rm -f /var/lib/php/cache/OPNsense* && service php_fpm reload`.
- **Modem unreachable** — verify the modem is in HiLink mode (not serial),
  reachable at its IP (`ping 192.168.8.1`), and that credentials are correct.
  Use *Settings → Test configuration* (API: `POST /api/hilink/service/test`)
  to probe all enabled modems.
- **Service won't start** — `configctl hilink status`, then check
  `/var/log/hilink/service.log`. Enable *Debug logging* for detail.
- **No historical metrics** — confirm the `rrdtool` package is installed and
  `/var/db/hilink/rrd/` is writable; RRD files appear after the first
  successful collection cycle.
- **Changes had no effect** — settings only apply on **Save & Apply**
  (service restart). The service also reloads its configuration once per
  minute on its own.

## FAQ

**Can it set the modem to bridge/passthrough mode?**
No — HiLink devices expose no API for NAT/bridge mode. Configure that in the
modem's own web UI (see SETUP.md).

**Multiple modems?**
The backend is multi-modem capable and the dashboard shows one card per
enabled modem. Live status is fetched per modem, so each additional modem
adds 1–3 s to a full dashboard refresh.

**Where are the logs?**
`/var/log/hilink/service.log`.
