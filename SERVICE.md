# booking-service

Owns **authentication, users, and bookings** — the transactional core.

## What it does
- **Auth (JWT)** — `POST /api/auth/register|login|refresh|logout`
- **Users** — `GET/PUT /api/users/me`
- **Bookings** — create, list mine, list host's, cancel, complete (`/api/bookings/...`)
- Sends **booking confirmation emails** + notifications
- Liveness/readiness: `/healthz`, `/ready`

## AWS resources & why

| Resource | Used for | Why / benefit |
|---|---|---|
| **RDS (PostgreSQL)** | users, bookings tables | Transactional data — booking state, availability holds, user accounts. |
| **Secrets Manager** | DB password **+ JWT signing secret** | Both are sensitive; read at startup via IRSA, never in code. |
| **SQS — `booking-events` (SendMessage)** | publish booking lifecycle events | Decouples downstream reactions (notifications, analytics) from the request path. |
| **SES** (`ses:SendEmail`) | booking confirmation / status emails | Managed email; no SMTP server to run. |
| **SNS** (`sns:Publish`) | push notifications | Fan-out notifications (e.g. SMS/topic subscribers). |
| **SSM Parameter Store** | db config, SES sender email, queue URL | Per-env non-sensitive config. |
| **CloudWatch** (custom metrics) | booking counts | Business + ops metrics. |

## Note on responsibility boundary
This service owns **auth for the whole app** (login/JWT/users) *and* bookings. That's two
concerns in one service. Fine at this scale, but see improvements.

## Improvements
- **Split auth into its own service** (or a shared auth lib) — right now every other service
  validates JWTs that booking-service issues; a dedicated `auth-service` would clarify the boundary.
- **Rate-limit login/register** (brute-force protection) — e.g. at the gateway or in-app.
- **SES production access** — SES starts in sandbox (only verified recipients); request prod
  access before real emails work. (This is a console step, not Terraform.)
- **Idempotency keys** on `POST /bookings` to avoid double-booking on retries.
- Dead-letter queue on `booking-events`.

## Unnecessary / cleanup
- **SNS** is wired but verify it's actually used (notifications.py) — if there are no SMS/topic
  subscribers, the `sns:Publish` grant + client are dead weight and can be removed.
