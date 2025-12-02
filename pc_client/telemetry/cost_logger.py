"""Cost logger for external AI providers.

This module provides logging for API costs associated with external
AI providers (Gemini, ChatGPT). Costs are logged to a dedicated file
for billing analysis and monitoring.
"""

import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

# Cost rates per 1M tokens (approximate, may vary by model)
# These are reference values and should be updated based on current pricing
COST_RATES = {
    "gemini": {
        "gemini-2.0-flash": {"input": 0.075, "output": 0.30},
        "gemini-2.5-flash-lite": {"input": 0.05, "output": 0.20},
        "default": {"input": 0.10, "output": 0.30},
    },
    "chatgpt": {
        "gpt-4o-mini": {"input": 0.15, "output": 0.60},
        "gpt-4o": {"input": 5.0, "output": 15.0},
        "gpt-4-turbo": {"input": 10.0, "output": 30.0},
        "o1-preview": {"input": 15.0, "output": 60.0},
        "o1-mini": {"input": 3.0, "output": 12.0},
        "default": {"input": 0.50, "output": 1.50},
    },
}


def _get_cost_logger() -> logging.Logger:
    """Get or create the cost logger with file handler."""
    logger = logging.getLogger("providers.costs")

    # Only set up handler if not already configured
    if not logger.handlers:
        logger.setLevel(logging.INFO)

        # Ensure logs directory exists
        logs_dir = Path("logs")
        logs_dir.mkdir(exist_ok=True)

        # Create file handler for cost logging
        handler = logging.FileHandler(logs_dir / "providers-costs.log")
        handler.setLevel(logging.INFO)

        # Format: timestamp | provider | model | tokens_in | tokens_out | cost | task_id
        formatter = logging.Formatter("%(asctime)s | %(message)s")
        handler.setFormatter(formatter)

        logger.addHandler(handler)

        # Prevent propagation to root logger
        logger.propagate = False

    return logger


def estimate_cost(
    provider: str,
    model: str,
    prompt_tokens: int,
    completion_tokens: int,
) -> float:
    """Estimate cost for an API call based on token usage.

    Args:
        provider: Provider name ("gemini" or "chatgpt")
        model: Model name
        prompt_tokens: Number of input tokens
        completion_tokens: Number of output tokens

    Returns:
        Estimated cost in USD
    """
    provider_rates = COST_RATES.get(provider, {})
    model_rates = provider_rates.get(model, provider_rates.get("default", {"input": 0.0, "output": 0.0}))

    input_cost = (prompt_tokens / 1_000_000) * model_rates["input"]
    output_cost = (completion_tokens / 1_000_000) * model_rates["output"]

    return round(input_cost + output_cost, 6)


def log_api_cost(
    provider: str,
    model: str,
    prompt_tokens: int,
    completion_tokens: int,
    latency_ms: float = 0.0,
    task_id: Optional[str] = None,
    success: bool = True,
    error: Optional[str] = None,
    meta: Optional[Dict[str, Any]] = None,
) -> None:
    """Log API call cost to providers-costs.log.

    Args:
        provider: Provider name ("gemini" or "chatgpt")
        model: Model name
        prompt_tokens: Number of input tokens
        completion_tokens: Number of output tokens
        latency_ms: API call latency in milliseconds
        task_id: Optional task identifier
        success: Whether the call was successful
        error: Error message if not successful
        meta: Additional metadata
    """
    logger = _get_cost_logger()

    cost = estimate_cost(provider, model, prompt_tokens, completion_tokens)
    total_tokens = prompt_tokens + completion_tokens
    status = "OK" if success else "ERROR"

    # Format: provider | model | in_tokens | out_tokens | total | cost_usd | latency_ms | status | task_id
    log_line = (
        f"{provider} | {model} | "
        f"in:{prompt_tokens} | out:{completion_tokens} | total:{total_tokens} | "
        f"${cost:.6f} | {latency_ms:.0f}ms | {status}"
    )

    if task_id:
        log_line += f" | task:{task_id}"

    if error:
        log_line += f" | error:{error[:100]}"

    logger.info(log_line)


def get_daily_summary(date: Optional[datetime] = None) -> Dict[str, Any]:
    """Get cost summary for a specific date.

    Args:
        date: Date to get summary for (default: today)

    Returns:
        Dictionary with cost statistics per provider
    """
    if date is None:
        date = datetime.now()

    date_str = date.strftime("%Y-%m-%d")
    log_file = Path("logs/providers-costs.log")

    if not log_file.exists():
        return {"date": date_str, "providers": {}, "total_cost": 0.0, "total_tokens": 0}

    summary: Dict[str, Any] = {
        "date": date_str,
        "providers": {},
        "total_cost": 0.0,
        "total_tokens": 0,
        "total_requests": 0,
    }

    try:
        with open(log_file, "r") as f:
            for line in f:
                if date_str not in line:
                    continue

                parts = line.split(" | ")
                if len(parts) < 7:
                    continue

                # Parse log line
                provider = parts[1].strip() if len(parts) > 1 else "unknown"
                model = parts[2].strip() if len(parts) > 2 else "unknown"

                # Extract token counts
                tokens_in = 0
                tokens_out = 0
                cost = 0.0

                for part in parts:
                    if part.startswith("in:"):
                        try:
                            tokens_in = int(part.split(":")[1])
                        except (ValueError, IndexError):
                            # Malformed log line - skip this value silently
                            pass
                    elif part.startswith("out:"):
                        try:
                            tokens_out = int(part.split(":")[1])
                        except (ValueError, IndexError):
                            # Malformed log line - skip this value silently
                            pass
                    elif part.startswith("$"):
                        try:
                            cost = float(part[1:])
                        except (ValueError, IndexError):
                            # Malformed cost value - skip this value silently
                            pass

                # Update summary
                if provider not in summary["providers"]:
                    summary["providers"][provider] = {
                        "models": {},
                        "total_cost": 0.0,
                        "total_tokens": 0,
                        "requests": 0,
                    }

                prov_summary = summary["providers"][provider]
                prov_summary["total_cost"] += cost
                prov_summary["total_tokens"] += tokens_in + tokens_out
                prov_summary["requests"] += 1

                if model not in prov_summary["models"]:
                    prov_summary["models"][model] = {"cost": 0.0, "tokens": 0, "requests": 0}

                prov_summary["models"][model]["cost"] += cost
                prov_summary["models"][model]["tokens"] += tokens_in + tokens_out
                prov_summary["models"][model]["requests"] += 1

                summary["total_cost"] += cost
                summary["total_tokens"] += tokens_in + tokens_out
                summary["total_requests"] += 1

    except Exception as e:
        summary["error"] = str(e)

    return summary
