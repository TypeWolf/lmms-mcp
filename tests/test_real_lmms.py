"""Opt-in integration checks against an explicitly selected real application.

Set LMMS_TEST_EXECUTABLE to an executable/launcher already prepared in the test
environment. Tests never download, extract, or install an application/plugin.
"""

import json
import os

import pytest

from lmms_mcp import lmms_app, server


@pytest.fixture
def real_lmms(monkeypatch):
    configured = os.environ.get("LMMS_TEST_EXECUTABLE")
    if not configured:
        pytest.skip("Set LMMS_TEST_EXECUTABLE for real application checks")
    monkeypatch.setenv("LMMS_EXECUTABLE", configured)
    # An explicit but invalid test installation must fail rather than skip.
    assert lmms_app.find_lmms_exe() is not None
    return configured


def test_real_lmms_version(real_lmms):
    version = lmms_app.get_lmms_version()
    assert version is not None
    expected = os.environ.get("LMMS_TEST_EXPECTED_VERSION")
    if expected:
        assert version == expected


def test_real_lmms_inventory(real_lmms):
    assert lmms_app.get_plugins_dir() is not None
    installed = lmms_app.get_installed_plugins()
    assert {"tripleoscillator", "delay"} <= installed


def test_real_lmms_info(real_lmms):
    info = json.loads(server.get_lmms_info())
    assert info["found"] is True
    assert info["version"] is not None
    assert info["plugin_inventory_status"] == "available"
    assert "tripleoscillator" in info["instruments_verified_available"]
    assert "delay" in info["effects_verified_available"]
