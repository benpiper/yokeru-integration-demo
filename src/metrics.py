"""Prometheus metrics — exposed via the FastAPI /metrics endpoint."""

from prometheus_client import CollectorRegistry, Counter, Gauge

REGISTRY = CollectorRegistry()

calls_attempted_total = Counter(
    "yokeru_calls_attempted_total",
    "Welfare check attempts handed to the dispatch layer.",
    labelnames=("adapter",),
    registry=REGISTRY,
)
calls_delivered_total = Counter(
    "yokeru_calls_delivered_total",
    "Welfare checks acknowledged by the Yokeru API.",
    labelnames=("adapter",),
    registry=REGISTRY,
)
calls_failed_total = Counter(
    "yokeru_calls_failed_total",
    "Welfare checks that failed permanently or transiently.",
    labelnames=("adapter", "kind"),
    registry=REGISTRY,
)
http_retries_total = Counter(
    "yokeru_http_retries_total",
    "Number of times an outbound HTTP request was retried.",
    labelnames=("target",),
    registry=REGISTRY,
)
webhooks_received_total = Counter(
    "yokeru_webhooks_received_total",
    "Webhook events accepted (label 'kind' = new|duplicate|invalid_signature).",
    labelnames=("kind",),
    registry=REGISTRY,
)
breaker_state = Gauge(
    "yokeru_breaker_state",
    "Circuit breaker state: 0=closed, 1=half_open, 2=open.",
    labelnames=("name",),
    registry=REGISTRY,
)
