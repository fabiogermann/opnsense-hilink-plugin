# HiLink Plugin — OPNsense Setup Guide

How to install and configure the HiLink modem plugin on OPNsense.

## Supported / tested devices

| Model | Status | Notes |
|---|---|---|
| Huawei E3372h-320 | ✅ Tested | Primary development device (verified on OPNsense 26.7 / FreeBSD 15.1, Python 3.13) |
| Huawei E3372s-153 | ✅ Tested | |
| Huawei E3372h-153 | ✅ Tested | |
| Huawei E8372h series | 📋 Planned | |

All HiLink-compatible Huawei modems that expose the standard `/api/...` HTTP interface
(default IP `192.168.8.1`) should work; the list above is what has been verified.

## Requirements

- OPNsense 24.7+ (25.1+ recommended) — the plugin uses only packages OPNsense ships
  (Python 3.13, `py313-httpx`, `rrdtool`), so `pkg add` installs cleanly on a stock box.
- A HiLink-compatible Huawei USB modem, reachable at `192.168.8.1` (default).

## Installation

### From the package repository
```bash
fetch -o /usr/local/etc/pkg/repos/HiLink.conf \
  https://fabiogermann.github.io/opnsense-hilink-plugin/HiLink.conf
pkg update && pkg install os-hilink
```

### Direct from a release
```bash
pkg add https://github.com/fabiogermann/opnsense-hilink-plugin/releases/latest/download/os-hilink-0.1.12.pkg
```

After install, navigate to **Services → HiLink**.

## First-use setup

On first open, the plugin shows a **first-use wizard** if no modem is configured yet. Enter:
- **Name** — a friendly label
- **IP address** — the modem's address (usually `192.168.8.1`)
- **Username / Password** — the modem's web-UI credentials (`admin` / none by default)

Then choose how to populate the settings:
- **Import current settings from the modem** (recommended) — reads network mode, roaming,
  auto-disconnect and bands from the modem so nothing is overwritten.
- **Import from a `nvram.bak` backup** — for when the modem isn't currently reachable.
- **Start with plugin defaults** — applies the plugin defaults to the modem.

## Per-modem configuration

Edit a modem to set (advanced fields are under the advanced section):

- **Network mode** — Automatic / 4G Preferred / 3G Preferred / 4G Only / 3G Only.
- **Allow roaming** — enable data roaming.
- **Auto disconnect (min)** — drop the data session after N idle minutes (0 = disabled).
- **LTE band bitmask** / **3G-2G band bitmask** — lock to specific bands (hex bitmask;
  leave at `ALL` = automatic). LTE band N = `2**(N-1)` (e.g. `80005` = B1+B3+B20).
- **Network search** — Automatic (modem chooses operator) or Manual (lock to a PLMN +
  optional RAT).
- **Data limit** — enforce a monthly cap.

Save, then **Start** the service (or it starts automatically if enabled).

## NAT mode — must be configured in the modem's own UI

Huawei HiLink USB sticks (E3372 series) operate in **router/NAT mode by default** and do
**not** expose a NAT on/off toggle through the HiLink API. There is no standard
`/api/...` endpoint for NAT / router-vs-bridge mode on these devices, so the plugin
cannot set it.

**Configure NAT mode in the modem's own web UI** at `http://192.168.8.1` (log in with the
modem's credentials), under the modem's network/settings pages — not through this plugin.
If a future modem model exposes a NAT endpoint, it can be added as a plugin feature.

## Troubleshooting

- **No menu item** — hard-refresh the WebUI (Ctrl+Shift+R) or re-login; OPNsense caches the menu.
- **Page not found on Settings** — ensure you're on the latest version (the Settings URL was
  corrected to `/ui/hilink/index/settings`).
- **Service stays "Stopped"** — check `/var/log/opnsense/` and run the service in the foreground:
  `python3.13 /usr/local/opnsense/scripts/hilink/hilink_service.py --foreground --debug`.
- **Modem unreachable** — verify the IP (`192.168.8.1`) and that the modem is in HiLink mode
  (not serial/PPP mode).
