# OPNsense HiLink Modem Plugin Architecture

Current as of the 2026-07 overhaul. `TODO.md` tracks remaining work and known
limitations; this document describes what exists, not what was once planned.

## Overview

The plugin monitors and manages Huawei HiLink-based 4G/LTE USB modems. It
consists of a PHP MVC front end (OPNsense framework), a configd action set,
and two Python entry points: a long-running monitoring daemon and a one-shot
control CLI used by configd.

## Component diagram

```mermaid
graph TB
    subgraph "OPNsense"
        UI[Volt views<br/>index / settings]
        API[PHP API controllers<br/>Service / Settings / Monitor]
        MODEL[HiLink model<br/>mount: //OPNsense/hilink]
        CONF[configd<br/>actions_hilink.conf]
        CF[/conf/config.xml/]
    end

    subgraph "Python backend"
        SVC[hilink_service.py<br/>monitoring daemon]
        CTL[hilink_control.py<br/>one-shot CLI]
        LIB[lib: hilink_api /<br/>config_manager / data_store]
        RRD[(rrdtool CLI<br/>/var/db/hilink/rrd)]
    end

    MODEM[Huawei HiLink modem<br/>HTTP API @ 192.168.8.1]

    UI --> API
    API --> MODEL
    MODEL --> CF
    API --> CONF
    CONF -->|start/stop/restart/status<br/>via daemon(8)| SVC
    CONF -->|connect/disconnect/reboot/<br/>getstatus/getmetrics/probe/getprofiles/test| CTL
    SVC -->|reads| CF
    CTL -->|reads| CF
    SVC --> LIB
    CTL --> LIB
    LIB --> MODEM
    SVC -->|create/update/fetch| RRD
    CTL -->|fetch| RRD
```

Two data paths, deliberately separate:

- **Live path (control/status)**: every dashboard/status request goes
  PHP → configd → `hilink_control.py` → modem HTTP. It always reflects the
  modem's current state and costs ~1–3 s per call.
- **Historical path (metrics)**: the daemon polls each enabled modem every
  `collect_interval` seconds and writes to per-modem RRD files
  (`/var/db/hilink/rrd/<uuid>.rrd`) via the `rrdtool` CLI. `getmetrics`
  reads those files; it never touches the modem.

## Directory structure

```
opnsense-hilink-plugin/
├── src/
│   └── opnsense/
│       ├── mvc/
│       │   └── app/
│       │       ├── controllers/
│       │       │   └── OPNsense/HiLink/
│       │       │       ├── IndexController.php
│       │       │       ├── Api/
│       │       │       │   ├── ServiceController.php
│       │       │       │   ├── SettingsController.php
│       │       │       │   └── MonitorController.php
│       │       │       └── forms/
│       │       │           ├── generalSettings.xml
│       │       │           ├── alertSettings.xml
│       │       │           └── dialogModem.xml
│       │       ├── models/
│       │       │   └── OPNsense/HiLink/
│       │       │       ├── HiLink.php
│       │       │       ├── HiLink.xml
│       │       │       ├── Menu/Menu.xml
│       │       │       └── ACL/ACL.xml
│       │       └── views/
│       │           └── OPNsense/HiLink/
│       │               ├── index.volt
│       │               └── settings.volt
│       ├── scripts/
│       │   └── hilink/
│       │       ├── hilink_service.py      # async daemon (monitoring/RRD)
│       │       ├── hilink_control.py      # one-shot CLI used by configd
│       │       └── lib/
│       │           ├── __init__.py
│       │           ├── hilink_api.py      # async HiLink modem API wrapper
│       │           ├── config_manager.py  # XML/JSON config load/save/validate
│       │           └── data_store.py      # RRD storage via the rrdtool CLI
│       └── service/
│           └── conf/
│               └── actions.d/
│                   └── actions_hilink.conf
├── pkg/+MANIFEST
├── tools/build_pkg.sh
├── tests/unit/
├── docs/
└── .github/workflows/
```

There is deliberately **no** configd template and **no** www/ JS tree — the
Python service reads `/conf/config.xml` directly and the views use inline
JavaScript.

## Components

### PHP front end

- **IndexController** — serves the Dashboard (`index`) and Settings
  (`settings`) pages.
- **ServiceController** (`ApiMutableServiceControllerBase`) — start/stop/
  restart/status/test/reconfigure, plus `probe/<uuid>` (read-only settings
  import for the first-use wizard). `reconfigure` restarts the service when
  enabled, stops it when disabled — that is the whole "apply" story.
- **SettingsController** (`ApiMutableModelControllerBase`) — model get/set,
  bootgrid CRUD for modems, config export/import (API only, no UI).
- **MonitorController** — live status/signal/data, RRD metrics, overview,
  profiles, connect/disconnect/reboot. Validates every `modem_uuid`
  (format + existence in the model) before calling configd.

### configd actions (`actions_hilink.conf`)

- Lifecycle: `start`, `stop`, `restart`, `status` — `daemon(8)` owns
  daemonization and the pidfile (`/var/run/hilink.pid`); the Python daemon
  always runs in the foreground. `status` prints exactly `running`/`stopped`.
- Control: `connect`, `disconnect`, `reboot` (parameterized: modem uuid).
- Read: `getstatus`, `getmetrics`, `probe`, `getprofiles`, `test`.

### Python backend

- **hilink_service.py** — async daemon. Tasks: `monitor_loop` (collect
  metrics, connection supervision: reconnect with back-off, auto-connect,
  low-signal warning, data-limit disconnect), `config_reload_loop` (re-reads
  config.xml every 60 s, adds/removes/updates modem managers, applies
  `debug_logging`), `cleanup_loop` (daily RRD retention). Applies managed
  settings (roaming, network mode, band lock, auto-disconnect, PLMN search,
  active profile) on startup and reload.
- **hilink_control.py** — one-shot commands for configd; prints a single
  JSON document per invocation and exits non-zero on failure.
- **lib/hilink_api.py** — async HiLink API wrapper (httpx). WebUI 10/17/21
  session+login flows, token handling, status/signal/usage reads, dataswitch,
  reboot, network mode, roaming, auto-disconnect, band lock, PLMN search,
  APN profile list/select, settings probe. Modem numeric fields are parsed
  tolerantly (unit suffixes like `dBm`/`dB` are stripped).
- **lib/config_manager.py** — reads `/conf/config.xml` (preferred),
  plugin XML export, or JSON; validates; modem/alerts/general dataclasses.
  Passwords are base64-obfuscated with a `b64:` prefix only in
  plugin-managed files — never in config.xml.
- **lib/data_store.py** — RRD create/update/fetch/info/graph via the
  `rrdtool` **CLI** (the Python binding is not in the OPNsense package set),
  statistics, CSV export, retention cleanup.

## Configuration model

Mounted at `//OPNsense/hilink` in `/conf/config.xml`; modem uuids are XML
attributes (standard `ArrayField` behaviour). Sections:

- `general`: `enabled`, `update_interval` (dashboard refresh),
  `data_retention`, `debug_logging`, `wizard_completed`.
- `modems/modem`: connection (name/ip/credentials), behaviour
  (`auto_connect`, `roaming_enabled`, `network_mode`, reconnect policy,
  `auto_disconnect_min`, band bitmasks, PLMN search, `active_profile`),
  monitoring (`collect_interval`, `signal_threshold`, `data_limit_*`,
  `alert_email`). `max_idle_time` is a deprecated legacy field — honoured as
  a fallback by the service but not shown in the UI.
- `alerts`: thresholds + SMTP/email fields (delivery not yet implemented).

## Security boundaries

- `modem_uuid` is regex-validated **and** resolved against the model before
  any configd call; configd parameters go through `configdpRun`
  (parameterized, not string-interpolated).
- ACL `page-services-hilink` covers `ui/hilink/*` and `api/hilink/*`.
- Modem/SMTP passwords are plaintext in `config.xml` (OPNsense-standard);
  the `b64:` scheme is obfuscation for plugin-managed exports only.
- Values interpolated into modem-bound XML and into dashboard HTML are
  escaped.

## Packaging and CI

- `tools/build_pkg.sh` stages `src/opnsense` under `/usr/local/opnsense`,
  builds a real `.pkg` with `pkg create`, and rewrites the stamped host ABI
  to `freebsd:*:*` (via Python + zstandard) so Linux CI can produce packages.
- Workflows: `test.yml` (pytest matrix, black, pylint/mypy advisory, bandit,
  safety, PHP lint, service smoke test), `build.yml` (tag-driven package +
  GitHub release), `deploy-repo.yml` (GitHub Pages pkg repo).
- Runtime deps (stock OPNsense packages only): `python313`, `py313-httpx`,
  `rrdtool`.
