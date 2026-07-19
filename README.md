# OPNsense HiLink Modem Plugin

A plugin for monitoring and managing Huawei HiLink-based 4G/LTE USB modems in OPNsense.

## Features

- Real-time modem monitoring (signal strength, connection status, data usage)
- Auto-connect/disconnect with configurable retry
- Roaming and network mode selection (4G/3G/2G)
- Data usage tracking with monthly limits (enforced by disconnect; alerts are logged — email delivery is not yet implemented)
- Historical metrics with configurable retention (RRD)
- Web dashboard with live updates and REST API

## Supported Devices

| Model | Status |
|---|---|
| Huawei E3372h-320 | ✅ Tested (primary development device) |
| Huawei E3372s-153 | ✅ Tested |
| Huawei E3372h-153 | ✅ Tested |
| Huawei E8372h series | 📋 Planned |

See [docs/SETUP.md](docs/SETUP.md) for the OPNsense setup guide, including NAT-mode notes.

## Requirements

- OPNsense 24.7+ (25.1+ recommended; verified on 26.7)
- Python 3.13 (installed automatically via the `python313` package dependency)
- A HiLink-compatible Huawei USB modem

## Installation

### From the package repository

```bash
fetch -o /usr/local/etc/pkg/repos/HiLink.conf \
  https://fabiogermann.github.io/opnsense-hilink-plugin/HiLink.conf
pkg update && pkg install os-hilink
```

### Direct from a release

Download the current `os-hilink-*.pkg` asset from the
[releases page](https://github.com/fabiogermann/opnsense-hilink-plugin/releases/latest),
copy it to the firewall, then:

```bash
pkg add os-hilink-<version>.pkg
```

Then navigate to **Services → HiLink** to configure.

### From source

```bash
git clone https://github.com/fabiogermann/opnsense-hilink-plugin.git
cd opnsense-hilink-plugin
make build
sudo make install        # requires root; restarts configd
```

## Configuration

1. Go to **Services → HiLink** and add a modem.
2. Set the modem IP (usually `192.168.8.1`), username (`admin`), and password.
3. Enable auto-connect, set network mode and data retention as needed.
4. Save and apply.

## Development

```bash
pip install -r requirements-dev.txt
make test       # unit tests with coverage
make package    # build the FreeBSD .pkg
```

Project layout: `src/opnsense/{mvc,scripts,service}/` (web UI, backend services, service config), `tests/`, `pkg/` (manifest), `Makefile`.

## Troubleshooting

- **Modem not detected**: verify IP `192.168.8.1`, USB connection, and that the modem is in HiLink mode (not serial).
- **No data collection**: check `configctl hilink status`, logs in `/var/log/hilink/service.log`, and RRD permissions under `/var/db/hilink/rrd`.
- **Debug mode**: Services → HiLink → Settings → General → enable *Debug logging* (advanced), then Save & Apply. Verbose output goes to `/var/log/hilink/service.log`.

## License

MIT — see [LICENSE](LICENSE).

## Acknowledgments

- Based on the [HiLink API](https://github.com/chanakalin/hilinkapi) Python library
- OPNsense development team for the plugin framework
