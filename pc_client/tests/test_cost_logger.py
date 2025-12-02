"""Tests for cost_logger module."""

import pytest
import tempfile
import os
from unittest.mock import patch, MagicMock

from pc_client.telemetry.cost_logger import (
    estimate_cost,
    log_api_cost,
    get_daily_summary,
    COST_RATES,
)


class TestEstimateCost:
    """Tests for estimate_cost function."""

    def test_estimate_cost_gemini_known_model(self):
        """Test cost estimation for known Gemini model."""
        cost = estimate_cost("gemini", "gemini-2.0-flash", 1000, 500)
        # input: 1000 tokens * 0.075 / 1M = 0.000075
        # output: 500 tokens * 0.30 / 1M = 0.00015
        # total: 0.000225
        assert cost == pytest.approx(0.000225, rel=1e-4)

    def test_estimate_cost_gemini_default_model(self):
        """Test cost estimation for unknown Gemini model uses default."""
        cost = estimate_cost("gemini", "unknown-model", 1000000, 1000000)
        # Uses default rates: input 0.10, output 0.30
        # 1M * 0.10 / 1M + 1M * 0.30 / 1M = 0.40
        assert cost == pytest.approx(0.40, rel=1e-4)

    def test_estimate_cost_chatgpt_known_model(self):
        """Test cost estimation for known ChatGPT model."""
        cost = estimate_cost("chatgpt", "gpt-4o-mini", 1000, 500)
        # input: 1000 * 0.15 / 1M = 0.00015
        # output: 500 * 0.60 / 1M = 0.0003
        # total: 0.00045
        assert cost == pytest.approx(0.00045, rel=1e-4)

    def test_estimate_cost_chatgpt_reasoning_model(self):
        """Test cost estimation for ChatGPT reasoning model."""
        cost = estimate_cost("chatgpt", "o1-preview", 1000, 1000)
        # input: 1000 * 15.0 / 1M = 0.015
        # output: 1000 * 60.0 / 1M = 0.06
        # total: 0.075
        assert cost == pytest.approx(0.075, rel=1e-4)

    def test_estimate_cost_unknown_provider(self):
        """Test cost estimation for unknown provider returns zero."""
        cost = estimate_cost("unknown", "model", 1000, 1000)
        assert cost == 0.0

    def test_estimate_cost_zero_tokens(self):
        """Test cost estimation with zero tokens."""
        cost = estimate_cost("gemini", "gemini-2.0-flash", 0, 0)
        assert cost == 0.0


class TestLogApiCost:
    """Tests for log_api_cost function."""

    @patch("pc_client.telemetry.cost_logger._get_cost_logger")
    def test_log_api_cost_success(self, mock_get_logger):
        """Test logging successful API cost."""
        mock_logger = MagicMock()
        mock_get_logger.return_value = mock_logger

        log_api_cost(
            provider="gemini",
            model="gemini-2.0-flash",
            prompt_tokens=100,
            completion_tokens=50,
            latency_ms=150.0,
            task_id="test-123",
            success=True,
        )

        mock_logger.info.assert_called_once()
        log_line = mock_logger.info.call_args[0][0]
        assert "gemini" in log_line
        assert "gemini-2.0-flash" in log_line
        assert "in:100" in log_line
        assert "out:50" in log_line
        assert "OK" in log_line
        assert "task:test-123" in log_line

    @patch("pc_client.telemetry.cost_logger._get_cost_logger")
    def test_log_api_cost_error(self, mock_get_logger):
        """Test logging failed API cost."""
        mock_logger = MagicMock()
        mock_get_logger.return_value = mock_logger

        log_api_cost(
            provider="chatgpt",
            model="gpt-4o-mini",
            prompt_tokens=100,
            completion_tokens=0,
            latency_ms=50.0,
            success=False,
            error="Rate limit exceeded",
        )

        mock_logger.info.assert_called_once()
        log_line = mock_logger.info.call_args[0][0]
        assert "chatgpt" in log_line
        assert "ERROR" in log_line
        assert "error:Rate limit exceeded" in log_line


class TestGetDailySummary:
    """Tests for get_daily_summary function."""

    def test_get_daily_summary_no_file(self):
        """Test summary when log file doesn't exist."""
        with patch("pc_client.telemetry.cost_logger.Path") as mock_path:
            mock_path.return_value.exists.return_value = False
            summary = get_daily_summary()
            assert summary["total_cost"] == 0.0
            assert summary["total_tokens"] == 0
            assert summary["providers"] == {}

    def test_get_daily_summary_empty_file(self):
        """Test summary with empty log file."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.log', delete=False) as f:
            f.write("")
            temp_path = f.name

        try:
            with patch("pc_client.telemetry.cost_logger.Path") as mock_path:
                mock_file = MagicMock()
                mock_file.exists.return_value = True
                mock_path.return_value = mock_file

                summary = get_daily_summary()
                assert summary["total_cost"] == 0.0
        finally:
            os.unlink(temp_path)


class TestCostRates:
    """Tests for cost rates configuration."""

    def test_cost_rates_structure(self):
        """Test that cost rates have proper structure."""
        assert "gemini" in COST_RATES
        assert "chatgpt" in COST_RATES

        for provider, models in COST_RATES.items():
            assert "default" in models, f"{provider} missing default rates"
            for model, rates in models.items():
                assert "input" in rates, f"{provider}/{model} missing input rate"
                assert "output" in rates, f"{provider}/{model} missing output rate"
                assert rates["input"] >= 0
                assert rates["output"] >= 0
