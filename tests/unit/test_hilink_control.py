"""
Unit tests for the hilink_control CLI (the configd entry points).
"""

import json
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../src/opnsense/scripts/hilink'))

import hilink_control

VALID_UUID = "550e8400-e29b-41d4-a716-446655440000"


def _run_main_expect_exit(monkeypatch, argv):
    monkeypatch.setattr(sys, "argv", argv)
    with pytest.raises(SystemExit) as exc:
        hilink_control.main()
    return exc.value.code


class TestUuidValidation:
    """The uuid is a security boundary: it reaches configd as a parameter."""

    def test_missing_uuid(self, monkeypatch, capsys):
        code = _run_main_expect_exit(monkeypatch, ["hilink_control.py", "status"])
        assert code == 1
        out = json.loads(capsys.readouterr().out)
        assert out["status"] == "error"
        assert "UUID required" in out["message"]

    def test_uuid_with_shell_metacharacters(self, monkeypatch, capsys):
        code = _run_main_expect_exit(
            monkeypatch, ["hilink_control.py", "status", "abc; rm -rf /"]
        )
        assert code == 1
        out = json.loads(capsys.readouterr().out)
        assert out["status"] == "error"
        assert "Invalid modem UUID" in out["message"]

    def test_uuid_too_long(self, monkeypatch, capsys):
        code = _run_main_expect_exit(
            monkeypatch, ["hilink_control.py", "status", "a" * 65]
        )
        assert code == 1
        out = json.loads(capsys.readouterr().out)
        assert "Invalid modem UUID" in out["message"]


class TestMetricsCommand:
    def test_no_metrics_available(self, monkeypatch, capsys):
        monkeypatch.setattr(
            hilink_control.DataStore, "fetch", lambda self, uuid: None
        )
        code = _run_main_expect_exit(
            monkeypatch, ["hilink_control.py", "metrics", VALID_UUID]
        )
        assert code == 1
        out = json.loads(capsys.readouterr().out)
        assert out["status"] == "error"
        assert "No metrics" in out["message"]

    def test_metrics_returned_as_json(self, monkeypatch, capsys):
        payload = {"timestamps": [1], "metrics": {"signal_strength": [-65]}}
        monkeypatch.setattr(
            hilink_control.DataStore, "fetch", lambda self, uuid: payload
        )
        monkeypatch.setattr(sys, "argv", ["hilink_control.py", "metrics", VALID_UUID])
        hilink_control.main()
        out = json.loads(capsys.readouterr().out)
        assert out == payload


class TestConfigFailures:
    def test_config_load_failure(self, monkeypatch, capsys):
        monkeypatch.setattr(
            hilink_control.ConfigManager, "load", lambda self: False
        )
        code = _run_main_expect_exit(
            monkeypatch, ["hilink_control.py", "status", VALID_UUID]
        )
        assert code == 1
        out = json.loads(capsys.readouterr().out)
        assert "Failed to load configuration" in out["message"]

    def test_unknown_modem(self, monkeypatch, capsys):
        monkeypatch.setattr(
            hilink_control.ConfigManager, "load", lambda self: True
        )
        monkeypatch.setattr(
            hilink_control.ConfigManager, "get_modem", lambda self, uuid: None
        )
        code = _run_main_expect_exit(
            monkeypatch, ["hilink_control.py", "status", VALID_UUID]
        )
        assert code == 1
        out = json.loads(capsys.readouterr().out)
        assert "not found" in out["message"]


class TestTestCommand:
    def test_success_payload(self, monkeypatch, capsys):
        async def fake_run_test(config_path):
            return {"status": "success", "modems": {}}

        monkeypatch.setattr(hilink_control, "run_test", fake_run_test)
        monkeypatch.setattr(sys, "argv", ["hilink_control.py", "test"])
        hilink_control.main()
        out = json.loads(capsys.readouterr().out)
        assert out["status"] == "success"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
