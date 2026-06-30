# rentlora-booking-service

> Transactional core of the Rentlora platform — manages bookings, sends confirmation emails, and publishes lifecycle events to downstream consumers.

![Python](https://img.shields.io/badge/Python-3.12-3776AB?logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-0.115-009688?logo=fastapi&logoColor=white)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-RDS-336791?logo=postgresql&logoColor=white)
![SQS](https://img.shields.io/badge/AWS-SQS-FF9900?logo=amazonaws&logoColor=white)
![SES](https://img.shields.io/badge/AWS-SES-FF9900?logo=amazonaws&logoColor=white)

---

## Overview

`booking-service` owns the reservation lifecycle for Rentlora. Guests create bookings, hosts manage them, and the service reacts to each state change — sending transactional emails via Amazon SES and publishing events to an SQS queue for asynchronous downstream processing (audit logs, analytics, and push notifications). The service is backed by PostgreSQL for transactional integrity and uses Alembic for schema migrations.

---

## API Endpoints

### Bookings

| Method | Path | Description |
|---|---|---|
| `POST` | `/api/bookings` | Create a new booking |
| `GET` | `/api/bookings/mine` | List bookings for the authenticated guest |
| `GET` | `/api/bookings/host` | List bookings for the authenticated host |
| `PUT` | `/api/bookings/{id}/cancel` | Cancel a booking |
| `PUT` | `/api/bookings/{id}/complete` | Mark a booking as completed |

### Health

| Method | Path | Description |
|---|---|---|
| `GET` | `/healthz` | Liveness probe — returns `{"status":"ok"}` |
| `GET` | `/ready` | Readiness probe — checks DB connectivity |

All booking routes require a valid JWT, validated locally from the shared signing secret issued by `user-service`.

---

## AWS Resources

| Service | Purpose |
|---|---|
| **RDS (PostgreSQL)** | Source of truth for bookings table — availability holds, booking state, timestamps |
| **SQS — `booking-events`** | Publish `created` / `cancelled` booking lifecycle events for downstream consumers |
| **SES** | Send booking confirmation and status update emails to guests and hosts |
| **SNS** | Push notifications fan-out |
| **Secrets Manager** | DB password — fetched at startup via IRSA, never in code |
| **SSM Parameter Store** | DB config, SES sender email, SQS queue URL — per-environment non-sensitive config |
| **CloudWatch** | Custom booking count metrics for operational visibility |

---

## Event Flow

```
Guest creates booking
        │
        ▼
  POST /api/bookings
        │
        ├──▶ Write to PostgreSQL (bookings table)
        ├──▶ Send confirmation email (SES)
        └──▶ Publish booking:created event (SQS → booking-events queue)
                      │
                      ▼
              Downstream consumers
              (audit, analytics, notifications)
```

The SQS publish is non-blocking — if no queue URL is configured (local dev), the service logs the event and continues. The request path is never delayed by downstream consumers.

---

## Tech Stack

| Layer | Technology |
|---|---|
| Runtime | Python 3.12 |
| Framework | FastAPI 0.115 + Uvicorn |
| ORM | SQLAlchemy 2 (async) + asyncpg |
| Migrations | Alembic |
| Validation | Pydantic v2 |
| Auth | PyJWT (HS256) — validates tokens issued by user-service |
| Password Hashing | bcrypt |
| AWS SDK | boto3 |
| Logging | python-json-logger (structured JSON) |
| Container | Docker (multi-stage, non-root) |

---

## Database Schema

The service owns the `bookings` table and reads the `properties` and `users` tables (which are owned by `property-service` and `user-service` respectively, but shared via the same PostgreSQL instance).

Key columns on `bookings`: `id`, `property_id`, `guest_id`, `host_id`, `check_in`, `check_out`, `status`, `total_price`, `created_at`.

---

## Local Development

### Prerequisites

- Python 3.12+
- PostgreSQL (or use the project-level `docker-compose.yml` in the `rentlora` repo)
- (Optional) AWS credentials for SES email and SQS events

### Run Locally

```bash
# From the rentlora repo root (starts all services)
docker-compose up --build booking-service

# Or run standalone
cd rentlora-booking-service
pip install -r requirements.txt
uvicorn main:app --reload --port 8002
```

With `ENV=local` the service skips all AWS lookups, uses fallback defaults, and silently skips SES and SQS calls if not configured.

### Environment Variables

| Variable | Default | Description |
|---|---|---|
| `ENV` | `local` | Environment name (`local`, `dev`, `prod`) |
| `AWS_DEFAULT_REGION` | `us-east-1` | AWS region |
| `DATABASE_URL` | _(from SSM/fallback)_ | Async PostgreSQL connection string |

### Alembic Migrations

```bash
# Apply all pending migrations
alembic upgrade head

# Create a new migration
alembic revision --autogenerate -m "add_column_x"
```

---

## Deployment

This service is deployed on **Amazon EKS** as part of the Rentlora platform.

- **Container image**: built by GitHub Actions, scanned by Trivy, pushed to ECR
- **Helm chart**: `rentlora-helm/charts/booking-service`
- **GitOps**: Argo CD reconciles chart changes automatically
- **Port**: `8002`
- **Replicas**: 2 minimum (HPA max 6, target 70% CPU)
- **AWS credentials**: IRSA — the pod's ServiceAccount is annotated with the booking-service IAM role ARN

> **Note**: Amazon SES starts in sandbox mode and can only send to verified email addresses. Request SES production access via the AWS Console before real user emails will work.

---

## Health Probes

| Probe | Path | Notes |
|---|---|---|
| Liveness | `GET /healthz` | Fast, no DB call |
| Readiness | `GET /ready` | Checks DB connectivity; returns HTTP 503 if unreachable |

---

## Project Context

This service is part of the Rentlora microservices platform:

| Repository | Role |
|---|---|
| [`rentlora`](../rentlora) | Application source — all services + frontend |
| [`rentlora-infra`](../rentlora-infra) | Terraform — AWS infrastructure |
| [`rentlora-helm`](../rentlora-helm) | Helm charts + Argo CD GitOps |
