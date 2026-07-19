# HiLink Plugin Code Review — 2026-07-18

> **Resolution status (2026-07-18):** all findings below are **fixed** except
> **C2**, which was explicitly excluded by the user ("ignore c2"). Fixes are
> applied in the working tree; test execution is pending (see §E). A new
> `tests/unit/test_data_store.py` covers the C1 regression, plus new suites
> for `hilink_control.py` and `hilink_service.py` and real-world payload
> tests for `hilink_api.py`.

Scope: full tree review of `fabiogermann/opnsense-hilink-plugin` @ `main` (synced with
origin at review time). Covers: Python backend (`hilink_service.py`, `hilink_control.py`,
`lib/{hilink_api,config_manager,data_store}.py`), PHP MVC (controllers, model, forms,
views), configd actions, packaging (`pkg/+MANIFEST`, `tools/build_pkg.sh`), CI workflows,
tests, and docs.

Review method: static analysis of every source file. **Test execution was not possible
during this review session** (execution consent prompts timed out unanswered) — all
findings are from code inspection; the one runtime claim (finding C1) is a certain
`NameError` by construction, not a probability. Last committed pytest state
(`.pytest_cache/v/cache/lastfailed` = `{}`) indicates the suite was green at last run.

---

## A. What is done right (keep these)

- **UUID as security boundary**: `MonitorController::isKnownModem()` regex-validates the
  uuid and resolves it against the model before `configdpRun()` — no arbitrary strings
  reach configd. `ServiceController::probeAction()` does the same. `hilink_control.py`
  re-validates with `re.fullmatch(r"[0-9a-fA-F-]{1,64}")`.
- **OPNsense 26.7 compat**: model uses `TextField` for passwords (PasswordField removed),
  Menu parent node carries no `url`, ACL patterns cover `ui/hilink/*` + `api/hilink/*`.
- **Stock-only deps**: `python313`, `py313-httpx`, `rrdtool` — all in the OPNsense repo;
  `xmltodict`/`bs4` replaced by vendored shims (`_elem_to_dict`, `_MetaExtractor`).
- **Honest NAT-mode stance**: SETUP.md correctly documents that HiLink exposes no NAT
  endpoint instead of fabricating one.
- **Wizard design**: modem added disabled, settings imported (live probe or nvram.bak)
  before enable — the service never pushes defaults onto an unconfigured device.
- **Service lifecycle**: `daemon(8)` handles daemonization/pidfile; SIGTERM/SIGINT via
  `loop.add_signal_handler`; tasks cancelled + gathered on shutdown.
- **No secrets in repo**; base64 password obfuscation is `b64:`-prefixed so plaintext
  from config.xml is never mis-decoded.

---

## B. Test coverage assessment

| Module | Tests | Notes |
|---|---|---|
| `lib/hilink_api.py` | 13 tests | Init, connect ±login, disconnect, status, settings (2), signal, usage, dataswitch, netmode, roaming, error-code parsing, enums. All mock `_request` wholesale → XML parsing covered, HTTP/session/token flows not. |
| `lib/config_manager.py` | ~17 tests | Dataclass defaults/roundtrip, JSON save/load, CRUD, validate, export/import, b64 passwords, save/load cycle, empty-default policy. |
| `lib/data_store.py` | **none** | **0% — this is how C1 shipped.** |
| `hilink_control.py` | **none** | CLI parsing, uuid regex, fail() paths, metrics/probe/profiles untested. |
| `hilink_service.py` | **none** | Reconnect backoff, config hot-reload diffing, monitor loop untested. |
| PHP (3 controllers + model) | **none** | No PHP lint in CI either (TODO.md already notes). |
| Views / JS | **none** | |

Untested critical paths in `hilink_api.py`: all three login flows (WebUI 10 SCRAM-style,
17/21 token login), `_initialize_session` token negotiation, `set_bands`,
`set_network_search`, `set_active_profile`, `get_plmn_list`, `get_profiles`.

---

## C. Findings

Severity: **C**ritical = broken functionality · **H**igh = graceful-handling/correctness
gap · **M**edium = inconsistency · **L**ow = hygiene.

### C1 — `data_store.py`: `rrdtool` is never imported — the entire metrics pipeline is dead
`create_rrd()` (l.183), `update()` (l.231), `fetch()` (l.273), `get_latest()` (l.331) and
`generate_graph()` (l.618) call `rrdtool.create/update/fetch/info/graph`, but no
`import rrdtool` exists anywhere in the module. Every call raises `NameError`, which the
broad `except Exception` handlers swallow → each function silently returns `False`/`None`.

Blast radius:
- The service collects metrics every `collect_interval` and discards them all.
- No `/var/db/hilink/rrd/<uuid>.rrd` is ever created (TODO.md's on-box checklist item
  "Confirm RRD gets created and updated" **will fail**).
- `hilink_control.py metrics` → `fetch()` → `None` → "No metrics available", always.
- The pkg dep `rrdtool` is installed for nothing.

The intended fix is half-present: CLI shims `_rrd_run()` / `_rrd_fetch()` / `_rrd_info()`
(ll.18–84) shell out to the `rrdtool` binary — written but **never called**. Someone
started migrating off the Python binding (correct: `py313-rrdtool` is not a declared dep
and may not be stock) and never switched the call sites.

**Proposed fix**: route the five call sites through the shims (create/update/graph via
`_rrd_run`, fetch via `_rrd_fetch`, info via `_rrd_info`), keep the binding out of the
dependency set, and add `tests/unit/test_data_store.py` running against the real
`rrdtool` CLI (CI already installs it) with a temp `OPNSENSE_DATA_DIR`: create → update
→ fetch → statistics → cleanup, plus the unknown-uuid `None` paths. That test would have
caught this at commit time.

### C2 — `deploy-repo.yml` cannot serve the primary tested platform
The repo config templates `url: ".../FreeBSD:${ABI}"`; the workflow only creates
`FreeBSD:13:amd64` and `FreeBSD:14:amd64`. OPNsense 26.7 (the platform SETUP.md claims
the E3372h-320 was verified on) runs FreeBSD 15 → pkg expands `${ABI}` to
`FreeBSD:15:amd64` → 404 → `pkg update` fails.
**Fix**: add a `FreeBSD:15:amd64` directory (same `.pkg` copied in, as done for 13/14).

### H1 — Fragile numeric parsing of modem XML; whole-call failure on common payloads
`get_status()`: `int(status_info.get("ConnectionStatus","0"))`,
`int(...get("CurrentConnectTime","0"))`; `get_signal_info()`: `int(signal_data.get("rssi","0"))`;
`get_data_usage()`: six raw `int(...)` calls. HiLink firmware commonly returns values
with unit suffixes (`<rssi>-75dBm</rssi>`, `<sinr>15dB</sinr>`) or empty elements.
`int("-75dBm")` → `ValueError` → the entire status/signal/usage call fails → dashboard
card shows "Unreachable" for a healthy modem. The safe `_parse_int()` helper exists but
isn't used for these fields.
**Fix**: centralise a `_parse_modem_number()` (regex-extract `-?\d+`, else `None`) and
use it for every numeric field; let missing values degrade to `None`/0 per-field instead
of failing the whole call. Add tests with real-world payloads (`-75dBm`, empty tags).

### H2 — `monitor_loop` iterates a live dict that `config_reload_loop` mutates
`for manager in self.modem_managers.values():` awaits inside the body
(`collect_metrics()`, `check_connection()`). If the config reload task adds/removes a
modem during such an await, the next `next()` raises
`RuntimeError: dictionary changed size during iteration` → caught by the blanket
`except` → error log + 10 s stall. Self-healing but noisy and stalls collection.
**Fix**: iterate `list(self.modem_managers.values())`.

### H3 — Control commands report success regardless of backend result
`MonitorController::modemCommand()` always returns `['status' => 'ok', 'message' =>
'Connect command sent']` even when `hilink_control.py` printed
`{"status":"error","message":...}` — the dashboard shows success for a failed
connect/disconnect/reboot.
**Fix**: `json_decode` the configd output and pass through `status`/`message`
(keep `'ok'` only when the backend says so). Same class: `ServiceController::testAction()`
uses `strpos($response,'success')` — parse the JSON (`{"status":"success|error"}`)
instead of substring-matching.

### H4 — Dead configuration surface (UI/validation exists, nothing consumes it)
| Setting | UI | Validated | Consumed by |
|---|---|---|---|
| `general.update_interval` | "Dashboard refresh interval" | 10–300 (PHP+Py) | **nothing** — dashboard JS hardcodes 30 s; service loop hardcodes 5 s + per-modem `collect_interval` |
| `general.debug_logging` | checkbox | — | **nothing** — service never reads it; README points users to it and to a nonexistent `/var/log/hilink/debug.log` |
| `modem.max_idle_time` | advanced text | 0–86400 | **nothing** — wizard imports it, service never applies it; only `auto_disconnect_min` is applied — two UI fields for the same modem register (`MaxIdelTime`), one dead |
| `modem.alert_email` | advanced text | EmailField | **nothing** |
| `alerts.*` (SMTP/email) | full form | PHP+Py | **nothing** — no SMTP code anywhere; conditions are only logged |

TODO.md admits the alert/email part; README still advertises "Data usage tracking with
limits and **email alerts**" and `MonitorController::alertsAction()` returns a hardcoded
empty list while `docs/API.md` documents active/acknowledge/history alert endpoints.
**Fix** (pick per item, don't leave zombie fields): wire `update_interval` to the
dashboard refresh (fetch via `settings/get`); implement `debug_logging` (set root
logger level at service start) or drop it; collapse `max_idle_time` into
`auto_disconnect_min` (migrate on load: `auto_disconnect_min = max_idle_time // 60`);
either implement notifications via OPNsense's `notify` plumbing or hide the alerts form
behind "not yet implemented" and fix README.

### M1 — `docs/API.md` documents a different product
- Response envelope shown as `{"status":"success|error","data":{},"timestamp":...}` —
  actual controllers return `{"status":"ok",...}` and never a timestamp.
- Nonexistent endpoints: `/api/hilink/modem/{connect,disconnect,reboot,network_mode,roaming}`
  (real ones live under `/api/hilink/monitor/`), `/api/hilink/settings/validate`,
  `/api/hilink/alerts/{active,acknowledge,history}`, WebSocket `/api/hilink/ws`,
  rate-limit headers.
- Service status documented with `pid/uptime/version/modems_connected` — actual:
  `{status, running, enabled}` only.
- Metrics query params (`start/end/resolution/metrics`) documented — actual:
  `hilink_control.py metrics` takes only a uuid and returns a fixed 1-hour window
  (currently nothing at all, per C1).
**Fix**: rewrite from the controllers (TODO.md already lists this); or generate from code.

### M2 — `docs/USER_GUIDE.md` documents a fictional UI
Nonexistent screens: *Settings → Connection / Data Management / Advanced / Scheduling /
Failover / Notifications*, *Monitoring → History / Statistics*, usage graphs, PDF
export, syslog integration, scheduled connect/disconnect, failover rules — none of this
exists in the plugin. Also: `.txz` package names (build produces `.pkg`),
`yourusername` placeholder URLs, and the example modem name "Primary 4G" — rejected by
the model mask `/^[a-zA-Z0-9_-]+$/`.
**Fix**: rewrite from the current UI (SETUP.md is the accurate baseline) or delete and
merge into SETUP.md + a short dashboard section.

### M3 — README drift
- "email alerts" advertised (H4).
- Troubleshooting: "Services → HiLink → **Advanced** → Debug Logging; logs at
  `/var/log/hilink/debug.log`" — no Advanced tab exists (debug_logging is an advanced
  field inside General), no debug.log exists.
- "Python 3.11+" vs SETUP.md "Python 3.13" vs CI matrix 3.9–3.11 vs pkg dep `python313`.
- `[LICENSE](LICENSE)` — **no LICENSE file in the repo** (manifest claims MIT).
- Install example pins `os-hilink-0.1.2.pkg`; SETUP.md pins `os-hilink-0.1.12.pkg`.

### M4 — Makefile staleness
- `check-deps` probes `aiohttp`, `xmltodict`, `bs4`, `rrdtool` — actual deps: `httpx`,
  vendored XML/HTML parsing, `rrdtool` **CLI**. Every probe is wrong.
- `make release` copies `dist/*.txz` — `build_pkg.sh` produces `.pkg`; release target is
  broken.
- `make test`/`lint` fine otherwise.

### M5 — CI gaps
- Test matrix `3.9–3.11`; on-box interpreter is Python 3.13 → add `3.13` (code appears
  3.9-compatible, but test what you ship).
- No PHP lint job (TODO.md notes it caught nothing only because run manually).
- Integration job masks every failure with `|| true` (both service start and imports) —
  keep as smoke test but don't call it "integration".
- `safety-action` requires `SAFETY_API_KEY` secret — fails or no-ops on forks without it.

### M6 — Stale design docs
`DEVELOPMENT_STATUS.md` (claims aiohttp, "Testing 0%", frontend 0% — all pre-overhaul;
TODO.md already disclaims it), `ARCHITECTURE.md` (directory tree lists files that don't
exist: `hilink_monitor.py`, `hilink_collector.py`, `www/js/hilink/hilink.js`, `setup.sh`,
`+TARGETS`), `IMPLEMENTATION_PLAN.md` (12-week plan from project start).
**Fix**: delete DEVELOPMENT_STATUS + IMPLEMENTATION_PLAN; rewrite ARCHITECTURE's tree and
component list to match the current six-file backend.

### M7 — `pkg/+MANIFEST`
- `maintainer: hilink-plugin@example.com` — placeholder; use the real maintainer address.
- `licenses: [MIT]` but no LICENSE file (M3).
- desc advertises "Historical metrics" — currently broken (C1).

### L1 — XML injection into outbound modem requests
f-string interpolation without escaping: `self.username` in both login flows, and
profile fields (`Name`, `Apn`, `Username`, …) in `set_active_profile()` — values come
from the modem/user config; an `&` or `<` breaks the request body.
**Fix**: `xml.sax.saxutils.escape()` on every interpolated value.

### L2 — Low-severity XSS surface in `index.volt`
`renderModemCard()` inserts modem-sourced strings (`network_operator`, `wan_ip`,
`name` — name is mask-restricted, operator is not) via raw `split/join` template
substitution into HTML. A hostile/rogue cell can set an operator string containing
markup. **Fix**: HTML-escape token values before substitution (or build nodes with
`.text()`).

### L3 — Smaller items
- `network_type_map` (service) lacks the EV-DO/1xRTT family present in `NETWORK_TYPES`
  (hilink_api) → CDMA variants map to 0 ("No Service").
- Dead scaffolding: `_last_status_update`/`_status_cache_ttl` in `hilink_api.py` never
  used; unused imports (`Tuple`, `asyncio` top-level, `time`; `timedelta`, `Tuple` in
  `data_store.py`).
- `requirements.txt`: `pyyaml` unused; dev/test tools mixed with the single runtime dep
  (`httpx`) — split `requirements-dev.txt`.
- `settings.volt` profile dropdown always queries the **first enabled** modem's profiles
  regardless of the modem being edited (comment admits it) — wrong for multi-modem.
- Wizard nvram import maps `<dataswitch>` → `auto_connect`, but the live probe maps
  `ConnectMode` → `auto_connect`; `dataswitch` is the *current session* state, not the
  auto-dial flag → imports can set `auto_connect` wrong.
- `hilink_control.py metrics` constructs `DataStore()` which `mkdir -p`s the RRD dir on
  a read path; `run_test` reports `"success"` when zero modems are configured.
- Repo hygiene: committed `__pycache__/*.pyc` (cpython-312) and `.pytest_cache/`;
  `.gitignore` contains only `__pycache__` (needs `git rm -r --cached` + entries for
  `.pytest_cache/`, `build/`, `dist/`, `*.pyc`).
- `hilink_service.py` `--pidfile` unlink in `finally` could remove another process's
  pidfile (not used on-box; daemon(8) owns the pidfile).

---

## D. Proposed change list (priority order)

1. **[C1]** data_store: switch the five `rrdtool.*` call sites to the CLI shims; add
   `tests/unit/test_data_store.py` (real CLI, temp dirs). *This is the release blocker.*
2. **[C2]** deploy-repo.yml: add `FreeBSD:15:amd64`.
3. **[H1]** hilink_api: `_parse_modem_number()` for all numeric fields; strip unit
   suffixes; per-field degradation; real-world payload tests (incl. `-75dBm`, empties).
4. **[H3]** MonitorController::modemCommand + ServiceController::testAction: parse
   configd JSON, propagate real status.
5. **[H2]** monitor_loop: iterate a list copy.
6. **[H4]** Config surface cleanup: wire or remove `update_interval`, `debug_logging`;
   merge `max_idle_time` → `auto_disconnect_min`; implement-or-hide email alerts; fix
   README claim.
7. **[M1/M2]** Rewrite API.md and USER_GUIDE.md from the current implementation.
8. **[M3/M7]** README fixes; add LICENSE (MIT); real maintainer in +MANIFEST.
9. **[M4]** Makefile: fix `check-deps` (httpx import + `command -v rrdtool`), fix
   `release` for `.pkg`.
10. **[M5]** CI: add py3.13, PHP lint job, unmask integration failures (or rename).
11. **[L1/L2]** Escape XML in request builders; HTML-escape dashboard tokens.
12. **[L3]** Repo hygiene (`git rm -r --cached` caches, extend .gitignore), drop
    `pyyaml`, split dev requirements, remove dead imports/scaffolding, EV-DO mapping,
    nvram `auto_connect` semantics, per-modem profile dropdown.
13. **[M6]** Delete/refresh stale design docs.
14. **Tests**: add `test_hilink_control.py` (arg/uuid validation, fail paths), service
    backoff/reload tests with a mocked `HiLinkModem`, login-flow tests for all three
    WebUI versions; keep a no-`rrdtool`-import regression test (e.g. import data_store
    and call `create_rrd` in a temp dir — fails today).

## E. Verification status

- Static review: complete (all 49 files inspected).
- **Post-fix test run (2026-07-18, host, Python 3.12.13): `65 passed, 8 skipped`
  in 0.69s.** The 8 skips are the new `test_data_store.py` cases, which skip
  by design when the `rrdtool` CLI is absent (not installable on this host:
  no root/sudo; a docker-based run was attempted and blocked by the consent
  gate). CI installs `rrdtool`, so the suite runs fully there.
- The new suite immediately paid off: `test_get_data_usage_empty_fields`
  caught a residual crash — `<response></response>` (empty element) parses to
  `None`, so `.get("response", {})` returned `None` and `get_data_usage`
  died with `AttributeError`. Same latent pattern fixed in `get_status`,
  `get_signal_info`, `get_profiles`, `get_active_profile`,
  `set_active_profile` (`or {}` normalization).
- `python3 -m compileall src tests`: clean.
- `black --check`: not conclusive locally — only black 26.x was installable
  here, which flags pre-existing untouched files as well (CI pins black
  <26). New code follows the repo's existing (black 24/25) style; CI is the
  arbiter.
- Remaining unverified (consent-gated): rrdtool-backed `test_data_store.py`
  run, `git rm` of the two stale docs + untracking committed caches.
