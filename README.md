# EVE Healthcare Backend

Backend service for diagnostic test bookings with simulated payments, built as the
**EVE Healthcare SDE Intern Backend Engineering Assignment**.

Users sign up and log in with JWT authentication, browse diagnostic centres and the
tests each centre offers (with centre-specific pricing), book a test at a chosen
centre and appointment time, pay through a deterministic simulated payment service,
and the system accepts payment-provider webhooks with idempotent processing — so
repeated webhook deliveries never create duplicate payments/bookings or corrupt
booking state.

## 1. Overview

This is a backend-only API service. It solves the problem of letting patients
discover diagnostic centres, compare centre-specific test prices, reserve an
appointment slot as a booking, and complete a (simulated) payment — while keeping
booking and payment state consistent under retries, duplicate webhook deliveries,
and concurrent requests.

Key design decisions:

- **Layered architecture** — routers handle HTTP only; business rules and state
  transitions live in a service layer; SQLAlchemy models define persistence.
- **Price snapshotting** — a booking copies the catalogue price at creation time,
  so later price changes never rewrite history.
- **Ownership by JWT identity** — the API never accepts a client-supplied
  `user_id`; cross-user access returns `404` to avoid leaking resource existence.
- **Idempotent webhooks** — the provider's `event_id` is persisted with a unique
  constraint, so replays and racing duplicates are safe.

## 2. Features

- JWT authentication (signup, login, Bearer-protected endpoints)
- Password hashing with bcrypt; hashes are never stored in plaintext or returned
- Diagnostic centre catalogue (name + location)
- Diagnostic test catalogue (name + description)
- Centre-specific test pricing via a `centre_tests` association
- Authenticated booking creation with appointment datetime and price snapshot
- Booking lifecycle: `PENDING` / `CONFIRMED` / `FAILED` / `CANCELLED`
- Booking cancellation with state-transition enforcement
- Simulated payments (`SUCCESS` / `FAILED`, deterministic, no real gateway)
- Payment failure handling (booking moves to `FAILED`)
- Idempotent payment webhook (`event_id` persistence + unique constraint +
  race handling + terminal-state guards)
- Ownership-based authorization on bookings and payments
- PostgreSQL persistence with SQLAlchemy 2.x and Alembic migrations
- Pydantic request/response validation with explicit API contracts
- Swagger/OpenAPI docs with Bearer auth support
- Automated pytest suite (54 tests, SQLite-isolated — no database needed)
- Docker + Docker Compose for the API and database
- Idempotent seed script for catalogue data
- Windows `run.bat` quick-start script (uses the existing `.venv`)

## 3. Tech Stack

| Technology | Purpose | Version |
|---|---|---|
| Python | Language | 3.13 |
| FastAPI | Web framework / routing / OpenAPI | 0.116.1 |
| Uvicorn | ASGI server | 0.35.0 |
| PostgreSQL | Primary database | 16 (Docker image `postgres:16`) |
| SQLAlchemy | ORM | 2.0.43 |
| Alembic | Database migrations | 1.16.5 |
| psycopg2-binary | PostgreSQL driver | 2.9.10 |
| Pydantic | Request/response validation | 2.11.7 |
| pydantic-settings | Environment-based configuration | 2.10.1 |
| PyJWT | JWT issue/verify | 2.10.1 |
| bcrypt | Password hashing | 4.3.0 |
| email-validator | Email validation for auth schemas | 2.3.0 |
| python-multipart | Form/multipart support | 0.0.20 |
| httpx | TestClient transport for tests | 0.28.1 |
| pytest | Test runner | 8.4.1 |
| Docker / Docker Compose | Containerized API + database | — |

## 4. Architecture

Request flow:

```text
Client
  ↓
FastAPI Router (app/api/*)
  ↓
Pydantic Schemas (app/schemas/*) — validation + response contracts
  ↓
Service Layer (app/services/*) — business logic + state transitions
  ↓
SQLAlchemy ORM (app/models/*)
  ↓
PostgreSQL
```

```mermaid
flowchart TD
    Client --> API[FastAPI Routers<br/>app/api]
    API --> Auth[Authentication<br/>get_current_user + JWT]
    API --> Schemas[Pydantic Schemas<br/>app/schemas]
    API --> Services[Service Layer<br/>app/services]
    Services --> DB[SQLAlchemy Models<br/>app/models]
    DB --> PostgreSQL[(PostgreSQL)]
```

Layer responsibilities:

- **API / router layer** (`app/api/`, `app/main.py`) — HTTP concerns only:
  routes, status codes, auth dependencies, and translating domain errors
  (`BookingError` / `PaymentError`) into HTTP responses. No business rules here.
- **Schema / validation layer** (`app/schemas/`) — Pydantic request/response
  contracts. Raw ORM objects are never returned; `UserResponse`, for example,
  exposes only `id`, `name`, `email`, `created_at`.
- **Service / business-logic layer** (`app/services/`) — the actual rules:
  email normalization, booking creation and cancellation rules, payment guards,
  atomic payment+booking updates, and webhook idempotency.
- **Database / model layer** (`app/models/`, `app/core/database.py`) —
  SQLAlchemy entities, relationships, constraints, plus the engine, session
  factory, and per-request `get_db()` session handling.
- **Authentication / security layer** (`app/core/security.py`,
  `app/dependencies.py`, `app/core/config.py`) — bcrypt password hashing, JWT
  creation/verification, environment-driven settings, and the reusable
  `get_current_user()` Bearer dependency used by every protected endpoint.

## 5. Database Design

Tables:

- `users` — `id` (UUID PK), `name`, `email` (unique + indexed),
  `hashed_password`, timestamps. Owns many bookings.
- `diagnostic_centres` — `id` (UUID PK), `name`, `location`.
- `diagnostic_tests` — `id` (UUID PK), `name` (unique + indexed), `description`.
- `centre_tests` — `id` (UUID PK), `centre_id` FK, `test_id` FK,
  `price` (`NUMERIC(10,2)`). Unique `(centre_id, test_id)`. This association
  exists because the same test costs different amounts at different centres
  (e.g. CBC is 500.00 at Apollo vs 450.00 at Dr Lal PathLabs).
- `bookings` — `id` (UUID PK), `user_id` FK, `centre_id` FK, `test_id` FK,
  `amount` (`NUMERIC(10,2)` — price snapshot taken at booking time),
  `appointment_at` (timestamptz), `status` enum
  (`PENDING`/`CONFIRMED`/`FAILED`/`CANCELLED`), timestamps. Has at most one
  payment.
- `payments` — `id` (UUID PK), `booking_id` FK (unique — at most one payment per
  booking), `amount` (`NUMERIC(10,2)`), `status` enum (`SUCCESS`/`FAILED`),
  `provider_ref` (unique — the webhook lookup key, e.g. `pay_<hex>`).
- `webhook_events` — `id` (UUID PK), `event_id` (unique — the idempotency key),
  `payload` (JSON).

```mermaid
erDiagram
    users ||--o{ bookings : owns
    diagnostic_centres ||--o{ centre_tests : offers
    diagnostic_tests ||--o{ centre_tests : listed_in
    bookings ||--o| payments : paid_by
    centre_tests {
        uuid centre_id_FK
        uuid test_id_FK
        numeric price
    }
    bookings {
        uuid user_id_FK
        uuid centre_id_FK
        uuid test_id_FK
        numeric amount_snapshot
        timestamptz appointment_at
        enum status
    }
    payments {
        uuid booking_id_FK_UK
        numeric amount
        enum status
        string provider_ref_UK
    }
    webhook_events {
        string event_id_UK
        json payload
    }
```

Pricing design:

```text
centre_tests.price → current catalogue price (may change over time)
bookings.amount    → historical snapshot copied at booking creation
```

Money uses `NUMERIC(10,2)` / `Decimal` end to end and is serialized as exact
decimal strings in JSON (no floats).

Important constraints and indexes:

- Unique: `users.email`, `(centre_tests.centre_id, centre_tests.test_id)`,
  `payments.booking_id`, `payments.provider_ref`, `webhook_events.event_id`,
  `diagnostic_tests.name`.
- Foreign keys: `CASCADE` on user → bookings and booking → payment;
  `RESTRICT` on bookings → centres/tests (catalogue rows referenced by bookings
  cannot be deleted); `CASCADE` on centre/test → centre_tests.
- Indexes on foreign keys, `bookings.status`, `payments.status`, and lookup
  keys (`email`, `provider_ref`, `event_id`).
- UUID primary keys (`sa.Uuid`) and named enums (`booking_status`,
  `payment_status`) work on both PostgreSQL and the SQLite test database.

Migrations (Alembic, head: `0003_booking_fk_indexes`):

| Revision | Description |
|---|---|
| `0001_initial` | Users, centres, tests, centre_tests, bookings, payments, webhook_events |
| `0002_booking_appointment` | Added `bookings.appointment_at` (backfilled, then `NOT NULL`) + unique `payments.provider_ref` |
| `0003_booking_fk_indexes` | Indexes on `bookings.centre_id` / `bookings.test_id` to match the models |

## 6. Booking Lifecycle

```text
PENDING
  ├── payment SUCCESS → CONFIRMED
  ├── payment FAILED  → FAILED
  └── cancellation    → CANCELLED

CONFIRMED
  └── cancellation → CANCELLED
```

- `FAILED` and `CANCELLED` are terminal: cancelling them returns `409 Conflict`.
- Only `PENDING` bookings can be paid. Paying a `CONFIRMED`, `FAILED`, or
  `CANCELLED` booking — or a booking that already has a payment row — returns
  `409 Conflict`.
- Creating a second payment for the same booking returns `409 Conflict`.
- Cross-user view/cancel/pay returns `404` (not `403`) to avoid leaking whether
  another user's booking exists.

## 7. Payment Flow

There is intentionally no real payment gateway. `POST /api/payments/` simulates
a payment deterministically via `simulate_status` (`SUCCESS` or `FAILED`):

```text
Client
  ↓ POST /api/payments/ { booking_id, simulate_status }
Validate ownership (JWT) + booking is PENDING + no existing payment
  ↓
Read amount from bookings.amount (never from the client)
  ↓
Create payment with generated provider_ref (pay_<hex>)
  ↓
SUCCESS → payment = SUCCESS, booking = CONFIRMED
FAILED  → payment = FAILED,  booking = FAILED
```

The payment insert and the booking status update are committed in a single
transaction, so they can never diverge (e.g. `payment = SUCCESS` with
`booking` still `PENDING`).

## 8. Webhook Idempotency

`POST /api/payments/webhook` represents the payment provider notifying the
server. Payload:

```json
{ "event_id": "evt_123", "payment_id": "pay_abc", "status": "SUCCESS" }
```

- `event_id` — the provider's unique event identifier (required; unique at the
  DB level in `webhook_events`). This is the idempotency key.
- `payment_id` — the payment's `provider_ref` returned at payment creation.
- `status` — `SUCCESS` or `FAILED` (validated by Pydantic).

Processing order: validate payload → if `event_id` is already recorded, ignore
→ look up the payment by `provider_ref` (unknown → `404`, nothing created) →
apply the payment/booking update and record the event in one transaction.
A unique-constraint violation on `event_id` (concurrent duplicate delivery) is
caught and treated as a duplicate, so the losing delivery rolls back only its
own uncommitted changes.

```text
First delivery:  event_id = evt_001 → processed (payment/booking updated)
Second delivery: event_id = evt_001 → duplicate ignored, zero side effects
Third delivery:  event_id = evt_001 → duplicate ignored, zero side effects
```

Two documented terminal-state rules protect booking integrity:

- `SUCCESS` is terminal — a later conflicting `FAILED` event (new `event_id`)
  is recorded but never downgrades an already-successful payment/booking
  (stale-event protection).
- `CANCELLED` is terminal — webhooks never resurrect a cancelled booking; the
  event is recorded and the state is left untouched.

## 9. Authentication & Authorization

```text
Signup → bcrypt hash → Login → JWT (sub = user id, exp) → Bearer token
  → get_current_user() → protected endpoints
```

- Signup trims the name, normalizes email (trim + lowercase), rejects
  duplicates with `409` (including a DB-race guard that maps an
  `IntegrityError` to `409`), and never stores or returns plaintext passwords
  or hashes.
- Login verifies credentials and returns `401` on failure. JWT secret,
  algorithm, and expiry come from environment configuration
  (`JWT_SECRET_KEY` / `JWT_ALGORITHM` / `ACCESS_TOKEN_EXPIRE_MINUTES`).
- Protected endpoints use `HTTPBearer` (`get_current_user()`); missing,
  malformed, expired, or unknown-user tokens return `401` with a
  `WWW-Authenticate: Bearer` header.
- Booking ownership always comes from the JWT identity — the API accepts no
  client-supplied `user_id`. Viewing, cancelling, or paying another user's
  booking returns `404`.
- The webhook endpoint is intentionally unauthenticated (provider-to-server
  callback); trust comes from payload validation plus `event_id` uniqueness.

## 10. API Endpoints

| Method | Endpoint | Auth | Description |
|---|---|---|---|
| GET | `/health` | No | Health check → `{"status": "ok"}` |
| POST | `/api/auth/signup` | No | Register user (201; 409 on duplicate email) |
| POST | `/api/auth/login` | No | Login, returns Bearer JWT |
| GET | `/api/auth/me` | Yes | Current authenticated user |
| GET | `/api/centres` | No | List diagnostic centres |
| GET | `/api/centres/{centre_id}` | No | Get one centre (404 if unknown/malformed id) |
| GET | `/api/centres/{centre_id}/tests` | No | Centre with its tests + centre-specific prices |
| GET | `/api/tests` | No | List diagnostic tests |
| GET | `/api/tests/{test_id}` | No | Get one test (404 if unknown/malformed id) |
| POST | `/api/bookings` | Yes | Create booking (201, starts `PENDING`) |
| GET | `/api/bookings` | Yes | List own bookings (newest first) |
| GET | `/api/bookings/{booking_id}` | Yes | Get own booking (404 if missing/not owned) |
| POST | `/api/bookings/{booking_id}/cancel` | Yes | Cancel own `PENDING`/`CONFIRMED` booking |
| POST | `/api/payments/` | Yes | Simulated payment (201; 409 on duplicate/ineligible) |
| POST | `/api/payments/webhook` | No | Provider callback (idempotent; see §8) |

Status-code conventions: `201` created, `200` success, `400` invalid business
data (e.g. test not offered by centre), `401` missing/invalid auth,
`404` missing or not-owned resources (including malformed UUIDs),
`409` state conflicts/duplicates, `422` schema validation errors. Error
responses carry a `detail` message and never expose stack traces.

Interactive docs: `GET /docs` (Swagger UI, with Bearer authorize support),
`GET /redoc`, `GET /openapi.json`.

## 11. Example API Flow

```bash
# 1. Signup
curl -X POST localhost:8000/api/auth/signup \
  -H 'Content-Type: application/json' \
  -d '{"name":"Asha","email":"asha@example.com","password":"password123"}'
# → 201 {"id":"...","name":"Asha","email":"asha@example.com","created_at":"..."}

# 2. Login
curl -X POST localhost:8000/api/auth/login \
  -H 'Content-Type: application/json' \
  -d '{"email":"asha@example.com","password":"password123"}'
# → 200 {"access_token":"...","token_type":"bearer"}
TOKEN=<access_token>

# 3. Browse centres
curl localhost:8000/api/centres
# → [{"id":"...","name":"Apollo Diagnostics","location":"Bangalore",...}, ...]

# 4. Centre with its tests and centre-specific prices
curl localhost:8000/api/centres/<centre_id>/tests
# → {"id":"...","name":"Apollo Diagnostics","location":"Bangalore",
#    "tests":[{"id":"...","name":"CBC","price":"500.00"}, ...]}

# 5. Browse the test catalogue
curl localhost:8000/api/tests

# 6. Create booking (amount comes from the catalogue, not the client)
curl -X POST localhost:8000/api/bookings \
  -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' \
  -d '{"centre_id":"<centre_id>","test_id":"<cbc_id>",
       "appointment_at":"2026-10-02T10:00:00"}'
# → 201 {"id":"<booking_id>","status":"PENDING","amount":"500.00",...}

# 7. Simulate a successful payment
curl -X POST localhost:8000/api/payments/ \
  -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' \
  -d '{"booking_id":"<booking_id>","simulate_status":"SUCCESS"}'
# → 201 {"status":"SUCCESS","provider_ref":"pay_...","amount":"500.00",...}

# 8. Booking is now CONFIRMED
curl localhost:8000/api/bookings/<booking_id> \
  -H "Authorization: Bearer $TOKEN"
# → {... "status":"CONFIRMED" ...}

# 9. Provider webhook (first delivery processes the event)
curl -X POST localhost:8000/api/payments/webhook \
  -H 'Content-Type: application/json' \
  -d '{"event_id":"evt_001","payment_id":"pay_...","status":"SUCCESS"}'
# → 200 {"event_id":"evt_001","processed":true,"detail":"Event processed"}

# 10. Replaying the same event is a safe no-op
curl -X POST localhost:8000/api/payments/webhook \
  -H 'Content-Type: application/json' \
  -d '{"event_id":"evt_001","payment_id":"pay_...","status":"SUCCESS"}'
# → 200 {"event_id":"evt_001","processed":false,"detail":"Duplicate event ignored"}
```

Failed payment: same flow with `"simulate_status":"FAILED"` → payment
`FAILED`, booking `FAILED`. Cancellation:
`POST /api/bookings/<id>/cancel` → `CANCELLED` (from `PENDING` or `CONFIRMED`);
paying a cancelled booking returns `409`.

## 12. Local Development

```bash
git clone <repo-url>
cd EVE-HealthCare-Assignment

python -m venv .venv
.venv\Scripts\activate        # Windows
# source .venv/bin/activate   # macOS/Linux

pip install -r requirements.txt

copy .env.example .env        # Windows (then edit secrets)
# cp .env.example .env        # macOS/Linux

# Start PostgreSQL (or use Docker Compose, see §13), then:
python -m alembic upgrade head
python -m app.seed
uvicorn app.main:app --reload
```

Windows quick start: double-click `run.bat` in the project root. It uses the
existing `.venv` without reinstalling dependencies and starts
`python -m uvicorn app.main:app --reload`. It prints a clear error and pauses
if `.venv\Scripts\python.exe` or `app\main.py` is missing.

Then:

- Swagger UI: http://localhost:8000/docs (use Authorize with a login token)
- Health: http://localhost:8000/health

Migrations:

```bash
python -m alembic upgrade head                  # apply all (current head: 0003_booking_fk_indexes)
python -m alembic revision --autogenerate -m "x"  # new migration
python -m alembic downgrade -1                  # roll back one
```

Seed (`python -m app.seed`) is idempotent: 2 centres (Apollo Diagnostics /
Bangalore, Dr Lal PathLabs / Delhi), 4 tests (CBC, Thyroid Profile,
Lipid Profile, Blood Sugar (Fasting)), and 6 centre-specific prices.
Re-running it creates nothing new (it also syncs prices if they changed).

## 13. Docker

```bash
docker compose build
docker compose up
```

Services:

| Service | Image / Build | Ports | Behavior |
|---|---|---|---|
| `db` | `postgres:16` | `5432:5432` | Persistent volume `pgdata`, restarts always |
| `api` | Built from `Dockerfile` (`python:3.13-slim`) | `8000:8000` | Runs `alembic upgrade head && python -m app.seed && uvicorn app.main:app --host 0.0.0.0 --port 8000`; restarts on failure |

Port note: the compose file maps host `5432` to the database. If another local
PostgreSQL already occupies `5432`, either stop it or point the app at a
database on another host port via `DATABASE_URL`. (Local development here used
a standalone PostgreSQL on port `5433` with
`DATABASE_URL=postgresql+psycopg2://eve:eve@localhost:5433/eve_healthcare`.)

## 14. Environment Variables

Defined in `.env.example` (placeholders only — never commit real secrets; `.env`
is gitignored):

| Variable | Description | Example |
|---|---|---|
| `DATABASE_URL` | SQLAlchemy database URL | `postgresql+psycopg2://eve:eve@localhost:5432/eve_healthcare` |
| `JWT_SECRET_KEY` | Secret for signing JWTs | `change-me-to-a-long-random-secret` |
| `JWT_ALGORITHM` | JWT algorithm | `HS256` |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | Token lifetime in minutes | `60` |

## 15. Running Tests

```bash
python -m pytest -v
```

Verified result: **54 passed, 0 failed** (12 auth · 17 bookings · 8
centres/tests · 9 payments · 8 webhooks).

Tests run against an isolated in-memory SQLite database via a `get_db`
dependency override in `tests/conftest.py`, so no PostgreSQL is needed.
PostgreSQL behavior (migrations applying cleanly to head, enums, UUIDs,
constraints, seed idempotency, catalogue counts) was additionally verified
against a live PostgreSQL 16 instance.

Coverage highlights:

- **Auth** — signup success/duplicate (incl. case-insensitive)/validation,
  login success/wrong-password/unknown-email, missing/invalid/expired token,
  wrong auth scheme, concurrent-duplicate signup race → `409`.
- **Centres/tests** — list/get/invalid for both, centre-tests endpoint with
  centre-specific prices, invalid centre ids.
- **Bookings** — creation (`PENDING`, DB-derived amount, appointment kept),
  invalid centre/test, test-not-offered (`400`), unauthenticated rejection,
  list-only-own, get-own vs other-user (`404`), cancel pending/confirmed,
  cancel failed/already-cancelled (`409`), cancel another user's (`404`).
- **Price snapshot** — old booking keeps its amount after a catalogue price
  change; a new booking uses the new price.
- **Payments** — success → `CONFIRMED`, failure → `FAILED`, amount from
  booking, nonexistent/unauthorized/cancelled/confirmed/duplicate → 4xx,
  exactly one payment row on duplicates.
- **Webhooks** — success upgrade, terminal-`SUCCESS` conflict ignored, unknown
  payment (`404`), invalid payload (`422`), same event 3× → one
  event/payment/booking with correct state, cancelled booking never
  resurrected, threaded concurrent-duplicate race → exactly one effect.

## 16. Error Handling & Edge Cases

Handled and tested:

- Duplicate signup, including case-insensitive and concurrent-race duplicates
  (`409`, never `500` or a hash leak)
- Missing/invalid/expired tokens (`401` + `WWW-Authenticate: Bearer`)
- Malformed or unknown UUIDs for centres, tests, and bookings (`404`)
- Test not offered by the selected centre (`400`)
- Cross-user view/cancel/pay (`404`, no existence leak)
- Invalid state transitions (`409`): cancelling `FAILED`/`CANCELLED`, paying
  non-`PENDING` or already-paid bookings, duplicate payments
- Failed payments (booking → `FAILED`, cannot be resurrected by re-paying)
- Duplicate/unknown/conflicting webhook events; webhook arriving after
  cancellation; empty/malformed webhook payloads (`422`)
- Concurrent duplicate webhook delivery (unique constraint + race guard —
  exactly one event row, one payment, correct booking state)
- Validation errors (`422`) for bad emails, short passwords, missing fields,
  malformed datetimes, and invalid enum values

## 17. Assumptions

- Payments are simulated; no real provider (Stripe/Razorpay/etc.) is used —
  `simulate_status` deterministically selects `SUCCESS`/`FAILED`.
- The webhook endpoint is unauthenticated by design (provider-to-server
  callback); trust comes from payload validation and `event_id` uniqueness.
- `appointment_at` is a plain timestamp — no slot inventory, availability
  checks, past-date validation, or scheduling engine.
- Webhook `SUCCESS` is terminal: a later conflicting `FAILED` event is
  recorded but never downgrades a success (stale-event protection).
- `CANCELLED` bookings are terminal against webhook state changes.
- List endpoints return full collections (no pagination — datasets are small).
- Catalogue data is seeded; booking prices are snapshots of seed-managed
  catalogue prices.

## 18. Future Improvements

Not implemented; listed as next steps only:

- Appointment slot availability/inventory and past-date validation
- Provider signature verification for real webhooks
- Idempotency keys on client payment requests (safe retries)
- Pagination for large centre/test/booking datasets
- Rate limiting and structured observability (logging/metrics/tracing)
- Asynchronous webhook processing (queue/worker) if volume requires it
- Redis/Celery or microservices only if scale genuinely demands them

## 19. Project Structure

```text
.
├── app/
│   ├── main.py              # FastAPI entrypoint (app.main:app), /health
│   ├── dependencies.py      # get_current_user() Bearer dependency
│   ├── seed.py              # Idempotent catalogue seed (python -m app.seed)
│   ├── api/                 # Routers: auth, centres, tests, bookings, payments
│   ├── schemas/             # Pydantic request/response contracts
│   ├── services/            # Business logic: auth, centre, booking, payment
│   ├── models/              # SQLAlchemy entities + enums
│   └── core/                # config, database (engine/session), security (JWT/bcrypt)
├── alembic/
│   └── versions/            # 0001_initial → 0002_booking_appointment → 0003_booking_fk_indexes
├── tests/                   # pytest suite (conftest, helpers, 5 test modules)
├── Dockerfile               # python:3.13-slim API image
├── docker-compose.yml       # db (postgres:16) + api services
├── requirements.txt         # Pinned dependencies
├── pytest.ini               # testpaths = tests
├── alembic.ini              # Alembic configuration
├── .env.example             # Placeholder environment variables
└── run.bat                  # Windows quick start (existing .venv, no reinstall)
```
