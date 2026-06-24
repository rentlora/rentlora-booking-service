"""CloudWatch Embedded Metric Format (EMF) helper.

Emits metrics by printing special JSON to stdout.  CloudWatch Logs
automatically parses EMF payloads into CloudWatch Metrics — no SDK
or CloudWatch Agent required.

Usage:
    emit_metric("Rentlora", "RequestCount", 1, dimensions={"Service": "booking-service"})
"""

import json
import sys
import time


def emit_metric(
    namespace: str,
    metric_name: str,
    value: float,
    unit: str = "Count",
    dimensions: dict[str, str] | None = None,
) -> None:
    """Emit a single CloudWatch metric via Embedded Metric Format.

    Args:
        namespace: CloudWatch namespace (e.g. "Rentlora").
        metric_name: Name of the metric (e.g. "RequestLatency").
        value: Numeric value to record.
        unit: CloudWatch unit — Count, Milliseconds, Bytes, etc.
        dimensions: Optional dimension key-value pairs.
    """
    dims = dimensions or {}
    emf_payload = {
        "_aws": {
            "Timestamp": int(time.time() * 1000),
            "CloudWatchMetrics": [
                {
                    "Namespace": namespace,
                    "Dimensions": [list(dims.keys())] if dims else [[]],
                    "Metrics": [{"Name": metric_name, "Unit": unit}],
                }
            ],
        },
        metric_name: value,
        **dims,
    }
    # EMF payloads must be a single line of JSON on stdout
    print(json.dumps(emf_payload, default=str), file=sys.stdout, flush=True)
