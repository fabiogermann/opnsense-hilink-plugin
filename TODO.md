# Follow-up Notes

Status notes after the 2026-07 overhaul that fixed compatibility with recent
OPNsense releases (24.7/25.x, post-Phalcon MVC, Python 3.11). Where this file
contradicts `DEVELOPMENT_STATUS.md`, this file wins — that document predates
the overhaul and overstates completeness.

## Must do before a release

- [ ] **Test on a real OPNsense box.** Everything that could be verified
      off-box has been (unit tests, PHP 8.2 lint, XML validation, service
      start/stop under `daemon(8)`, `hilink_control.py` against a mocked
      modem HTTP API). Not yet exercised: volt rendering, menu/ACL
      registration, bootgrid dialogs, configd action dispatch. Checklist:
  - [ ] Install package, confirm *Services ▸ HiLink* appears in the menu
  - [ ] Settings page: add/edit/toggle/delete a modem, Save & Apply
  - [ ] Confirm `configctl hilink start|stop|restart|status` behave
  - [ ] Dashboard: modem card renders, connect/disconnect/reboot work
  - [ ] Confirm `/var/db/hilink/rrd/<uuid>.rrd` gets created and updated
- [ ] **Verify FreeBSD package names in `pkg/+MANIFEST`.** `py311-rrdtool`,
      `py311-beautifulsoup`, `py311-aiohttp` etc. must exist in the OPNsense
      package repo for the target release; adjust names/versions to what
      `pkg search` on the box reports. Python version suffix will need
      bumping when OPNsense moves past 3.11.
- [ ] **Test against real hardware.** The WebUI 10 SCRAM-style login and the
      WebUI 17/21 flows follow known-working implementations
      (huawei-lte-api) but have not been run against a physical E3372/E8372.
      Note: the seemingly reversed HMAC argument order in `_login_webui_10`
      is intentional — it matches Huawei's nonstandard implementation.

## Known limitations / not implemented

- **Email alerts are configuration-only.** The model, forms and validation
  exist, but the Python service contains no SMTP sending code. Low-signal
  and data-limit conditions are only logged (data limit also disconnects).
- **`max_idle_time` and `alert_email` are stored but never enforced/used**
  by the service.
- **No charts.** The dashboard's chart section was removed because the
  referenced JS never existed and OPNsense does not bundle a charting
  library. RRD data is collected and `/api/hilink/monitor/metrics` serves
  it; re-adding charts means bundling a chart lib locally (CSP forbids CDN).
- **Config export/import API has no UI.** `/api/hilink/settings/export` and
  `/import` work but nothing in the views calls them.
- **Monitor status is fetched live per request** (PHP → configd →
  `hilink_control.py` → modem HTTP), so the dashboard status call costs
  roughly 1–3 s per modem. If that becomes annoying, serve cached state from
  the running daemon (e.g. a small unix-socket status endpoint) instead.
- **Monthly usage comes from the modem's own month counter** — there is no
  local billing-day handling; if the modem's clock/month stats reset oddly,
  the data-limit enforcement inherits that.
- **Scheduled connect/disconnect, failover, multi-modem dashboards** listed
  in the README as "advanced/future" remain future.

## Architectural notes (for whoever touches this next)

- **The Python service reads `/conf/config.xml` directly** (mount point
  `//OPNsense/hilink`, modem uuid is an XML *attribute*). There is
  deliberately no configd template; "Save & Apply" simply restarts the
  service. Env overrides for tests: `OPNSENSE_SYSTEM_CONFIG`,
  `OPNSENSE_CONFIG_DIR`, `HILINK_CONFIG_DIR`, `HILINK_LOG_DIR`,
  `OPNSENSE_DATA_DIR`.
- **The configd `status` action prints exactly `running`/`stopped`** and the
  custom `ServiceController::statusAction()` matches on that. Do not swap in
  the base-class `statusAction()` without changing the action output to the
  `... is running` phrasing it expects.
- **Daemonization is `daemon(8)`'s job** (see `actions_hilink.conf`);
  `hilink_service.py` always runs in the foreground and `--foreground` is a
  compat no-op. Don't reintroduce `python-daemon` — it is not packaged for
  OPNsense.
- **Passwords**: modem/SMTP passwords live in plaintext in `config.xml`
  (standard OPNsense `PasswordField` behaviour). The `b64:` prefix scheme in
  `config_manager.py` only applies to plugin-managed JSON/XML files and is
  obfuscation, not encryption.
- **uuid validation is a security boundary**: request-supplied
  `modem_uuid` is regex-checked and resolved against the model before being
  passed to configd (`configdpRun`). Keep that if adding endpoints.

## Nice to have

- [ ] Migrate the repo to the official `opnsense/plugins` build framework
      (`plugin.mk`, `pkg-descr`) instead of the custom Makefile/+MANIFEST —
      that is the supported path to proper `.pkg` builds and would allow
      upstreaming. The GitHub Pages pkg-repo workflow
      (`deploy-repo.yml`) is untested end to end.
- [ ] Wire the enforced-but-silent alert conditions to actual notifications
      (OPNsense has `notify` plumbing; or implement the SMTP sender).
- [ ] Add PHP linting to CI (`php -l` via a container) — it caught nothing
      this time only because it was run manually.
- [ ] Surface `hilink test` (Settings → "Test configuration") in the UI;
      the API endpoint exists.
- [ ] Update `docs/API.md` to match the reworked endpoints (settings
      get/set now return the standard `{"hilink": ...}` model shape;
      signal/data are derived from `getstatus`).
