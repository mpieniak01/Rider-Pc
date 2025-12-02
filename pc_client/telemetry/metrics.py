"""Prometheus metrics for monitoring providers and task queue."""

from prometheus_client import Counter, Histogram, Gauge

# Task processing metrics
tasks_processed_total = Counter(
    'provider_tasks_processed_total',
    'Total number of tasks processed by providers',
    ['provider', 'task_type', 'status'],
)

task_duration_seconds = Histogram(
    'provider_task_duration_seconds',
    'Task processing duration in seconds',
    ['provider', 'task_type'],
    buckets=[0.01, 0.05, 0.1, 0.5, 1.0, 2.0, 5.0, 10.0, 30.0],
)

# Queue metrics
task_queue_size = Gauge('task_queue_size', 'Current size of the task queue', ['queue_name'])

task_queue_full_count = Counter('task_queue_full_total', 'Total number of times queue was full')

# Circuit breaker metrics
circuit_breaker_state = Gauge(
    'circuit_breaker_state', 'Circuit breaker state (0=closed, 1=half_open, 2=open)', ['provider']
)

circuit_breaker_failures = Counter('circuit_breaker_failures_total', 'Total circuit breaker failures', ['provider'])

# Provider metrics
provider_initialized = Gauge(
    'provider_initialized', 'Provider initialization state (0=not initialized, 1=initialized)', ['provider']
)

# Cache metrics
cache_hits_total = Counter('cache_hits_total', 'Total cache hits', ['cache_type'])

cache_misses_total = Counter('cache_misses_total', 'Total cache misses', ['cache_type'])

# External LLM provider metrics
llm_requests_total = Counter(
    'llm_requests_total',
    'Total number of LLM API requests',
    ['provider', 'model', 'status'],
)

llm_tokens_used_total = Counter(
    'llm_tokens_used_total',
    'Total tokens used by LLM providers',
    ['provider', 'model', 'token_type'],
)

llm_latency_seconds = Histogram(
    'llm_latency_seconds',
    'LLM API request latency in seconds',
    ['provider', 'model'],
    buckets=[0.1, 0.5, 1.0, 2.0, 5.0, 10.0, 30.0, 60.0],
)

llm_errors_total = Counter(
    'llm_errors_total',
    'Total number of LLM API errors',
    ['provider', 'model', 'error_type'],
)
