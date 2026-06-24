"""Structured JSON logging configuration for Rentlora microservices.

Outputs logs in JSON format compatible with CloudWatch Logs Insights.
Each log entry includes: timestamp, level, service name, message, and
any extra fields (request_id, method, path, status, duration_ms).
"""

import logging
import sys

from pythonjsonlogger import jsonlogger


class _RentloraFormatter(jsonlogger.JsonFormatter):
    """Custom JSON formatter that injects a fixed service name into every record."""

    def __init__(self, service_name: str, *args, **kwargs):
        super().__init__(
            *args,
            fmt="%(asctime)s %(levelname)s %(name)s %(message)s",
            rename_fields={"asctime": "timestamp", "levelname": "level"},
            **kwargs,
        )
        self._service_name = service_name

    def add_fields(self, log_record, record, message_dict):
        super().add_fields(log_record, record, message_dict)
        log_record["service"] = self._service_name


def setup_logging(service_name: str, level: int = logging.INFO) -> None:
    """Replace the root logger with a single JSON-to-stdout handler.

    Args:
        service_name: Identifier embedded in every log line (e.g. "booking-service").
        level: Minimum log level (default INFO).
    """
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(_RentloraFormatter(service_name))
    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(level)
