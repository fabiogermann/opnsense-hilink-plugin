# HiLink Plugin API

REST API exposed by the plugin under `/api/hilink/`. All endpoints require
standard OPNsense authentication (session cookie or API key) and the
`page-services-hilink` privilege.

Responses are JSON. Success responses use `"status": "ok"`; failures use
`"status": "error"` or `{"error": "..."}` depending on the endpoint.

## Service — `/api/hilink/service/`

### `GET /api/hilink/service/status`
Service state from configd plus the enabled flag from the model.

```json
{"status": "running", "running": true, "enabled": true}
```
`status` is exactly `running` or `stopped` (output of the configd action).

### `POST /api/hilink/service/start` · `/stop` · `/restart`
```json
{"response": "...", "status": "ok"}
```
Returns `{"response": "error", "status": "failed"}` for non-POST requests.

### `POST /api/hilink/service/reconfigure`
Restarts the service when enabled, stops it when disabled. Called by the UI
after "Save & Apply".
```json
{"status": "ok"}
```

### `POST /api/hilink/service/test`
Validates configuration and probes each enabled modem (runs
`hilink_control.py test`). May take several seconds per unreachable modem.
```json
{"status": "ok", "message": "{\"status\": \"success\", \"modems\": {\"HiLinkModem\": \"reachable\"}}"}
```
`message` is the raw JSON document produced by the backend test command.

### `POST /api/hilink/service/probe/<uuid>`
Reads the modem's current settings without changing anything (used by the
first-use wizard). `<uuid>` must be a valid modem UUID.
```json
{"status": "ok", "uuid": "…", "settings": {"network_mode": "auto", "roaming_enabled": false, "max_idle_time": 0, "auto_disconnect_min": 0, "auto_connect": true, "device_name": "E3372h-320"}}
```

## Settings — `/api/hilink/settings/`

### `GET /api/hilink/settings/get`
Full model under the `hilink` key (standard OPNsense model shape):
```json
{"hilink": {"general": {"enabled": "1", "update_interval": "30", "data_retention": "30", "debug_logging": "0", "wizard_completed": "1"}, "modems": {"modem": {"<uuid>": {"enabled": "1", "name": "…", …}}}, "alerts": {…}}}
```

### `POST /api/hilink/settings/set`
Standard model save. Returns `{"result": "saved"}` or
`{"result": "failed", "validations": {...}}`.

### Modem CRUD (bootgrid endpoints)
| Endpoint | Method | Purpose |
|---|---|---|
| `GET/POST /api/hilink/settings/searchModem` | search | Bootgrid rows (`enabled, name, ip_address, network_mode, auto_connect`) |
| `GET /api/hilink/settings/getModem/<uuid>` | get | One modem (or empty template without uuid) |
| `POST /api/hilink/settings/addModem/` | add | Returns `{"result":"saved","uuid":"…"}` |
| `POST /api/hilink/settings/setModem/<uuid>` | set | Update one modem |
| `POST /api/hilink/settings/delModem/<uuid>` | del | Delete one modem |
| `POST /api/hilink/settings/toggleModem/<uuid>[/<enabled>]` | toggle | Enable/disable |

### `GET /api/hilink/settings/export`
Configuration as a JSON payload (general, alerts, modems incl. uuids).
### `POST /api/hilink/settings/import`
Replace configuration from an export payload (new uuids are generated).
Neither endpoint is currently wired into the UI.

## Monitor — `/api/hilink/monitor/`

Status endpoints fetch live data from the modem on every call
(PHP → configd → `hilink_control.py` → modem HTTP), so each request costs
roughly 1–3 s per modem.

All take an optional `modem_uuid` parameter (query string or POST). When
omitted, the first enabled modem is used. Unknown/invalid uuids are rejected
before reaching configd.

### `GET /api/hilink/monitor/status`
```json
{"status": "ok", "data": {
  "connected": true, "connection_status": "CONNECTED", "network_type": "LTE (4G)",
  "network_operator": "…", "wan_ip": "10.x.x.x", "sim_status": "1",
  "device_name": "E3372h-320", "imei": "…", "iccid": "…",
  "connection_time": 3600, "roaming": false, "uuid": "…",
  "signal":  {"rssi": -65, "rsrp": -95, "rsrq": -10, "sinr": 15, "signal_bars": 5, "signal_quality": "excellent", "cell_id": 12345, "band": "3", "frequency": 1800},
  "usage":   {"session_upload": 0, "session_download": 0, "session_total": 0, "total_upload": 0, "total_download": 0, "total_total": 0, "monthly_upload": 0, "monthly_download": 0, "monthly_total": 0}
}}
```
Errors: `{"error": "No modem configured or enabled"}`, `{"error": "Unknown modem"}`,
`{"error": "Failed to get modem status"}`.

### `GET /api/hilink/monitor/signal` · `/data`
The `signal` / `usage` sub-objects of `/status` respectively:
```json
{"status": "ok", "data": {"rssi": -65, …}}
```

### `GET /api/hilink/monitor/metrics`
Historical RRD metrics for one modem (fixed window: last hour, 30 s
resolution). Query parameters other than `modem_uuid` are not supported.
```json
{"status": "ok", "data": {"start": 1754900000, "end": 1754903600, "step": 30,
  "timestamps": [1754900000, …],
  "metrics": {"signal_strength": [-65, …], "signal_quality": [80, …], "data_rx": […], "data_tx": […], "connection_state": [1, …], "network_type": [3, …]}}}
```
`{"error": "No metrics available"}` when no RRD exists yet.

### `GET /api/hilink/monitor/overview`
Enabled modems for the dashboard cards.
```json
{"status": "ok", "modems": [{"uuid": "…", "name": "…", "ip_address": "192.168.8.1", "data_limit_enabled": false, "data_limit_mb": 10240, "enabled": true}], "total": 1}
```

### `GET /api/hilink/monitor/profiles`
APN profiles on the modem and the active one.
```json
{"status": "ok", "uuid": "…", "active": "1", "profiles": [{"Index": "1", "Name": "…", "Apn": "…", "Username": "…", "AuthName": "…", "DialNumber": "*99#", "IpType": "…"}]}
```

### `POST /api/hilink/monitor/connect` · `/disconnect` · `/reboot`
`modem_uuid` is required (query string or POST body).
```json
{"status": "ok", "message": "Connect command sent", "response": "{\"status\": \"ok\", \"command\": \"connect\"}"}
```
`status` reflects the backend result (`error` when the modem command failed).

### `GET /api/hilink/monitor/alerts`
Reserved for future alert delivery. Currently always:
```json
{"status": "ok", "alerts": [], "count": 0}
```
Alert conditions (low signal, data limit) are evaluated by the backend
service and written to `/var/log/hilink/service.log`; the data-limit
condition additionally disconnects the modem.

## Notes

- There is **no WebSocket API** and **no rate limiting**; earlier revisions
  of this document described both aspirationally.
- `network_type` numeric codes from the modem are translated to readable
  names (`LTE (4G)`, `HSPA+ (3G)`, …).
- All byte counters are integers (bytes) as reported by the modem; monthly
  figures come from the modem's own month statistics.
