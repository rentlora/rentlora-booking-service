"""SQS messaging for booking-service.

Publishes booking lifecycle events (created, cancelled, completed) to the
`booking-events` queue for downstream consumers (analytics, audit,
notifications v2). This is additive — existing SES/SNS notifications are
unchanged. AWS calls use the pod's IRSA identity (no static credentials).
"""
import json
import logging
import time
from functools import lru_cache

import boto3
from config import get_settings

logger = logging.getLogger("booking-service.messaging")
settings = get_settings()


@lru_cache
def _sqs_client():
    return boto3.client("sqs", region_name=settings.aws_default_region)


def publish_booking_event(event_type: str, booking_id: int, **attrs) -> bool:
    """Publish a booking lifecycle event to the booking-events SQS queue.

    Returns True if sent, False if the queue is not configured or the send
    failed. Supports both FIFO and standard queues.
    """
    queue_url = settings.booking_events_queue_url
    if not queue_url:
        logger.info(f"[NO-QUEUE] booking event '{event_type}' for booking {booking_id} (queue not configured)")
        return False

    payload = {"event_type": event_type, "booking_id": booking_id, **attrs}
    try:
        kwargs = {
            "QueueUrl": queue_url,
            "MessageBody": json.dumps(payload, default=str),
        }
        if queue_url.endswith(".fifo"):
            kwargs["MessageGroupId"] = "bookings"
            kwargs["MessageDeduplicationId"] = f"{booking_id}-{event_type}-{int(time.time() * 1000)}"
        _sqs_client().send_message(**kwargs)
        logger.info(f"Published booking event '{event_type}' for booking {booking_id}")
        return True
    except Exception as e:
        logger.error(f"Failed to publish booking event '{event_type}' for {booking_id}: {e}")
        return False
