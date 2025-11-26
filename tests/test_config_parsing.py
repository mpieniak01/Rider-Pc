"""Tests for configuration parsing, specifically MONITORED_SERVICES."""

import os

import pytest


class TestParseMonitoredServices:
    """Tests for _parse_monitored_services function."""

    def test_empty_environment_variable(self, monkeypatch):
        """Parser returns empty list when env var is not set."""
        monkeypatch.delenv("MONITORED_SERVICES", raising=False)

        from pc_client.config.settings import _parse_monitored_services

        result = _parse_monitored_services()
        assert result == []

    def test_empty_string(self, monkeypatch):
        """Parser returns empty list when env var is empty string."""
        monkeypatch.setenv("MONITORED_SERVICES", "")

        from pc_client.config.settings import _parse_monitored_services

        result = _parse_monitored_services()
        assert result == []

    def test_single_service(self, monkeypatch):
        """Parser handles single service correctly."""
        monkeypatch.setenv("MONITORED_SERVICES", "rider-pc.service")

        from pc_client.config.settings import _parse_monitored_services

        result = _parse_monitored_services()
        assert result == ["rider-pc.service"]

    def test_multiple_services(self, monkeypatch):
        """Parser handles multiple services correctly."""
        monkeypatch.setenv("MONITORED_SERVICES", "rider-pc.service,rider-voice.service,rider-vision.service")

        from pc_client.config.settings import _parse_monitored_services

        result = _parse_monitored_services()
        assert result == ["rider-pc.service", "rider-voice.service", "rider-vision.service"]

    def test_whitespace_around_services(self, monkeypatch):
        """Parser handles whitespace around service names (e.g., 'svc1, svc2 , svc3')."""
        monkeypatch.setenv("MONITORED_SERVICES", "svc1.service, svc2.service , svc3.service")

        from pc_client.config.settings import _parse_monitored_services

        result = _parse_monitored_services()
        assert result == ["svc1.service", "svc2.service", "svc3.service"]

    def test_empty_entries_ignored(self, monkeypatch):
        """Parser ignores empty entries (e.g., 'svc1,,svc2')."""
        monkeypatch.setenv("MONITORED_SERVICES", "svc1.service,,svc2.service")

        from pc_client.config.settings import _parse_monitored_services

        result = _parse_monitored_services()
        assert result == ["svc1.service", "svc2.service"]

    def test_multiple_empty_entries(self, monkeypatch):
        """Parser handles multiple consecutive empty entries."""
        monkeypatch.setenv("MONITORED_SERVICES", "svc1.service,,,svc2.service,,")

        from pc_client.config.settings import _parse_monitored_services

        result = _parse_monitored_services()
        assert result == ["svc1.service", "svc2.service"]

    def test_whitespace_only_entries(self, monkeypatch):
        """Parser ignores whitespace-only entries."""
        monkeypatch.setenv("MONITORED_SERVICES", "svc1.service,   ,svc2.service")

        from pc_client.config.settings import _parse_monitored_services

        result = _parse_monitored_services()
        assert result == ["svc1.service", "svc2.service"]

    def test_only_commas(self, monkeypatch):
        """Parser returns empty list when input is only commas."""
        monkeypatch.setenv("MONITORED_SERVICES", ",,,")

        from pc_client.config.settings import _parse_monitored_services

        result = _parse_monitored_services()
        assert result == []

    def test_only_whitespace(self, monkeypatch):
        """Parser returns empty list when input is only whitespace."""
        monkeypatch.setenv("MONITORED_SERVICES", "   ")

        from pc_client.config.settings import _parse_monitored_services

        result = _parse_monitored_services()
        assert result == []

    def test_target_units_accepted(self, monkeypatch):
        """Parser accepts .target units."""
        monkeypatch.setenv("MONITORED_SERVICES", "rider-minimal.target,rider-dev.target")

        from pc_client.config.settings import _parse_monitored_services

        result = _parse_monitored_services()
        assert result == ["rider-minimal.target", "rider-dev.target"]

    def test_mixed_service_and_target(self, monkeypatch):
        """Parser handles mixed .service and .target units."""
        monkeypatch.setenv("MONITORED_SERVICES", "rider-pc.service,rider-minimal.target")

        from pc_client.config.settings import _parse_monitored_services

        result = _parse_monitored_services()
        assert result == ["rider-pc.service", "rider-minimal.target"]
