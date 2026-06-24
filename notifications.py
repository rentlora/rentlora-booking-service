import logging
import os

import boto3
from config import get_settings

logger = logging.getLogger("booking-service.notifications")
settings = get_settings()

def get_ses_client():
    if os.getenv("ENV") != "production":
        return None
    return boto3.client('ses', region_name=settings.aws_default_region)

def get_sns_client():
    if os.getenv("ENV") != "production":
        return None
    return boto3.client('sns', region_name=settings.aws_default_region)

def send_booking_email(user_email: str, user_name: str, property_title: str, check_in, check_out, total_price):
    ses = get_ses_client()
    if not ses:
        logger.info(f"[DEV MODE] Would send email to {user_email} for booking {property_title}")
        return

    try:
        html_body = f"""
        <html>
        <body>
            <h2>Booking Confirmed!</h2>
            <p>Hi {user_name},</p>
            <p>Your booking for <strong>{property_title}</strong> is confirmed.</p>
            <ul>
                <li><strong>Check-in:</strong> {check_in}</li>
                <li><strong>Check-out:</strong> {check_out}</li>
                <li><strong>Total Price:</strong> ${total_price}</li>
            </ul>
            <p>Thank you for choosing Rentlora!</p>
        </body>
        </html>
        """
        ses.send_email(
            Source=settings.ses_sender_email,
            Destination={'ToAddresses': [user_email]},
            Message={
                'Subject': {'Data': f"Booking Confirmed: {property_title}"},
                'Body': {'Html': {'Data': html_body}}
            }
        )
        logger.info(f"Successfully sent confirmation email to {user_email}")
    except Exception as e:
        logger.error(f"Failed to send email to {user_email}: {str(e)}")

def send_host_sms_alert(host_phone: str, property_title: str, check_in):
    sns = get_sns_client()
    if not sns:
        logger.info(f"[DEV MODE] Would send SMS to host {host_phone}: {property_title} was booked!")
        return

    if not host_phone:
        return

    try:
        message = f"Rentlora Alert: Your property '{property_title}' was just booked for {check_in}!"
        sns.publish(
            PhoneNumber=host_phone,
            Message=message
        )
        logger.info(f"Successfully sent SMS alert to host at {host_phone}")
    except Exception as e:
        logger.error(f"Failed to send SMS to {host_phone}: {str(e)}")
