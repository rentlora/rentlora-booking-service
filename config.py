import os
from functools import lru_cache

import boto3
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "booking-service"
    app_version: str = "1.0.0"
    database_url: str = ""
    jwt_secret: str = ""
    aws_default_region: str = "us-east-1"
    # SQS queue for booking lifecycle events. Empty -> events are logged only.
    booking_events_queue_url: str = ""
    # Verified SES sender. Configured via Parameter Store in dev/prod.
    ses_sender_email: str = "no-reply@rentlora.com"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


def fetch_aws_config():
    """Pull config from Secrets Manager + Parameter Store in dev/prod.

    Sensitive values (db password, jwt) come from Secrets Manager; non-sensitive
    values (db host/user/name, queue URL, sender email) come from Parameter
    Store, each with a fallback. Credentials are resolved via the pod's IRSA
    role — no static keys, no .env.
    """
    env = os.getenv("ENV", "local")
    if env not in ["dev", "prod"]:
        return {}

    region = os.getenv("AWS_DEFAULT_REGION", "us-east-1")
    ssm = boto3.client("ssm", region_name=region)
    secrets = boto3.client("secretsmanager", region_name=region)

    def _param(name, default):
        try:
            return ssm.get_parameter(Name=name)["Parameter"]["Value"]
        except Exception:
            return default

    db_pass = secrets.get_secret_value(SecretId=f"/rentlora/{env}/db-password")["SecretString"]
    jwt_sec = secrets.get_secret_value(SecretId=f"/rentlora/{env}/jwt-secret")["SecretString"]

    db_endpoint = ssm.get_parameter(Name=f"/rentlora/{env}/db-endpoint")["Parameter"]["Value"]
    db_user = _param(f"/rentlora/{env}/db-user", "postgres")
    db_name = _param(f"/rentlora/{env}/db-name", "rentlora")

    database_url = f"postgresql+asyncpg://{db_user}:{db_pass}@{db_endpoint}/{db_name}"

    return {
        "database_url": database_url,
        "jwt_secret": jwt_sec,
        "aws_default_region": region,
        "booking_events_queue_url": _param(f"/rentlora/{env}/booking-events-queue-url", ""),
        "ses_sender_email": _param(f"/rentlora/{env}/ses-sender-email", "no-reply@rentlora.com"),
    }


@lru_cache
def get_settings() -> Settings:
    aws_values = fetch_aws_config()
    return Settings(**aws_values)
