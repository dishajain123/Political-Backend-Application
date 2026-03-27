# Political Communication Platform Backend

A FastAPI-based backend for a role-aware political communication and operations platform. The system supports voter engagement, leader workflows, corporator oversight, and OPS analytics, with modules for announcements, polls, complaints, appointments, events, campaigns,donations, chat, notifications, and voter profile verification. MongoDB is the primary datastore, and JWT-based auth is enforced via dependency-based access control with role and permission rules.

## Tech Stack
- FastAPI + Uvicorn
- MongoDB with Motor (async) and PyMongo
- Pydantic v2 and `pydantic-settings`
- JWT auth via `python-jose`
- Password hashing via `passlib[bcrypt]`
- AWS Bedrock via `boto3` for translation in chat flows
- ReportLab (PDF receipts) and PyMuPDF (PDF previews)
- httpx/aiohttp for outbound HTTP calls

## Project Structure
```
.
├── app/
│   ├── app_init.py
│   ├── main.py
│   ├── api/
│   │   ├── dependencies.py
│   │   └── routes/
│   │       ├── analytics.py
│   │       ├── announcements.py
│   │       ├── appointments.py
│   │       ├── auth.py
│   │       ├── campaigns.py
│   │       ├── chat.py
│   │       ├── complaints.py
│   │       ├── events.py
│   │       ├── feedback.py
│   │       ├── help_numbers.py
│   │       ├── notifications.py
│   │       ├── polls.py
│   │       ├── users.py
│   │       └── voter_profile.py
│   ├── core/
│   │   ├── access_control_patterns.py
│   │   ├── app_factory.py
│   │   ├── config.py
│   │   ├── permissions.py
│   │   ├── roles.py
│   │   ├── routes.py
│   │   ├── security.py
│   │   └── startup.py
│   ├── db/
│   │   ├── indexes.py
│   │   └── mongodb.py
│   ├── middleware/
│   │   ├── auth_middleware.py
│   │   └── logging_middleware.py
│   ├── models/
│   │   ├── announcement_model.py
│   │   ├── appointment_model.py
│   │   ├── campaign_model.py
│   │   ├── chat_model.py
│   │   ├── complaint_model.py
│   │   ├── donation_model.py
│   │   ├── event_model.py
│   │   ├── feedback_model.py
│   │   ├── help_number_model.py
│   │   ├── notification_model.py
│   │   ├── poll_model.py
│   │   └── user_model.py
│   ├── schemas/
│   │   ├── announcement_schema.py
│   │   ├── appointment_schema.py
│   │   ├── auth_schema.py
│   │   ├── campaign_schema.py
│   │   ├── chat_schema.py
│   │   ├── complaint_schema.py
│   │   ├── donation_schema.py
│   │   ├── event_schema.py
│   │   ├── feedback_schema.py
│   │   ├── help_number_schema.py
│   │   ├── notification_schema.py
│   │   ├── ops_analytics_schema.py
│   │   ├── poll_schema.py
│   │   ├── user_schema.py
│   │   └── voter_lookup_schema.py
│   ├── services/
│   │   ├── analytics_service.py
│   │   ├── announcement_service.py
│   │   ├── appointment_service.py
│   │   ├── auth_service.py
│   │   ├── campaign_service.py
│   │   ├── chat_service.py
│   │   ├── complaint_service.py
│   │   ├── event_service.py
│   │   ├── feedback_service.py
│   │   ├── help_number_service.py
│   │   ├── notification_service.py
│   │   ├── ops_analytics_service.py
│   │   ├── poll_service.py
│   │   ├── translation_service.py
│   │   ├── user_service.py
│   │   ├── voter_lookup_service.py
│   │   ├── analytics/
│   │   └── chat/
│   ├── scripts/
│   │   └── seed_data.py
│   ├── utils/
│   │   ├── eci_session_manager.py
│   │   ├── enums.py
│   │   ├── geo.py
│   │   ├── helpers.py
│   │   ├── pagination.py
│   │   ├── receipt_generator.py
│   │   └── sentiment.py
│   └── static/              # created at runtime (uploads/receipts)
├── .env
├── .env.example
├── requirements.txt
└── README.md
```

## Architecture Overview
- **Entry point**: `app/main.py` imports the FastAPI app from `app/app_init.py`. You can run `python -m app.main` or `uvicorn app.main:app`.
- **Compatibility wrapper**: `app/app_init.py` ensures the project root is on `sys.path` (Windows/uvicorn reload) and calls the app factory.
- **App factory**: `app/core/app_factory.py` builds the `FastAPI` app, mounts `/static`, registers middleware, and includes routers. Docs are served at `/api/docs` and `/api/redoc`.
- **Router registration**: `app/core/routes.py` registers all API routers under `API_V1_PREFIX` and mounts auth routes again without prefix for legacy compatibility.
- **Middleware flow**: CORS is registered first, followed by `AuthMiddleware` (token parsing, user context) and `LoggingMiddleware` (request/response metrics).
- **Dependency/auth flow**: `app/api/dependencies.py` validates access tokens, fetches users from MongoDB, and enforces roles/permissions via `require_role`, `require_roles`, `require_ops`, and `require_permission`.
- **Service layer**: Each route delegates to a service under `app/services`. The service layer handles MongoDB access, validation, and business rules.
- **Schema/model layer**: Pydantic schemas live in `app/schemas` and Mongo-style models/enums live in `app/models`.
- **DB connection flow**: `app/db/mongodb.py` manages a singleton Motor client; `get_database()` returns the active DB.
- **Startup/lifespan flow**: `app/core/startup.py` connects to MongoDB, creates indexes, creates chat indexes, seeds help numbers, and closes the DB on shutdown.
- **Config/env flow**: `app/core/config.py` loads settings from `.env` via `pydantic-settings` and exposes a singleton `settings`.

## Feature/Module Overview
- **Auth**: Voter/leader registration, login, refresh, password reset, and profile identity checks.
- **Users**: Profile CRUD, leader territory assignments, and user analytics access controls.
- **Complaints**: Complaint creation and tracking, leader/OPS handling, optional file/image uploads.
- **Appointments**: Appointment requests, approval/reschedule flows.
- **Events**: Event scheduling, participation tracking, and leader assignments.
- **Announcements**: Create and distribute announcements with engagement metrics.
- **Polls**: Poll creation, participation, and results visibility.
- **Feedback**: Feedback submission with sentiment tagging and analytics.
- **Notifications**: In-app notification creation and read tracking.
- **Chat**: Direct and broadcast messaging with optional media attachments and translation support.
- **Campaigns & Donations**: Ward campaigns, donation submission, OCR-based verification, fraud checks, and receipt generation.
- **Help Numbers**: Public-facing emergency/help numbers with startup seeding.
- **Analytics**: Aggregated dashboards, OPS intelligence endpoints, and role-scoped metrics.
- **Voter Profile**: ECI-backed voter lookup/verification and stored voter profile data.

## Authentication & Authorization
- JWT access and refresh tokens are created in `app/core/security.py` with a `type` claim (`access` or `refresh`).
- `AuthMiddleware` parses tokens and enriches `request.state`, but does not enforce access by itself.
- Access enforcement happens via dependencies in `app/api/dependencies.py` and service-layer access patterns in `app/core/access_control_patterns.py`.
- Role hierarchy applies only to political roles (VOTER < LEADER < CORPORATOR). OPS is separate and enforced via permissions.
- Fine-grained permissions live in `app/core/permissions.py`.
- Legacy compatibility: auth routes are available both at `/api/v1/auth/*` and `/auth/*`.

## Environment Configuration
Settings are loaded from `.env` at the repo root. Required variables:
- `SECRET_KEY` (JWT signing key)
- `MONGODB_URL`

Common optional variables (see `.env.example`):
- `APP_NAME`, `API_V1_PREFIX`, `DEBUG`
- `MONGODB_DB_NAME`
- `ACCESS_TOKEN_EXPIRE_MINUTES`, `REFRESH_TOKEN_EXPIRE_DAYS`, `PWD_BCRYPT_ROUNDS`
- `MAX_UPLOAD_SIZE_MB`, `ALLOWED_IMAGE_TYPES`
- `ENABLE_PUSH_NOTIFICATIONS`, `ENABLE_EMAIL_NOTIFICATIONS`
- `SENTIMENT_ANALYSIS_ENABLED`
- `RATE_LIMIT_PER_MINUTE`
- `GPT_MODEL`, `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `AWS_DEFAULT_REGION`

Note: `ALLOWED_ORIGINS` is defined in settings but CORS is currently hardcoded to allow all origins in `app/core/app_factory.py`.

## Setup & Run
1. Create a virtual environment.
2. Install dependencies.
3. Copy `.env.example` to `.env` and set required values.
4. Run the server.

```bash
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Alternative:
```bash
python -m app.main
```

## API Overview
- Base prefix is `API_V1_PREFIX` (default `/api/v1`).
- Auth routes are additionally exposed without the prefix for legacy compatibility.
- OpenAPI docs: `/api/docs` and `/api/redoc`.
- Health check: `/health`.

## Startup Behavior
On application startup (`app/core/startup.py`):
- Connects to MongoDB.
- Creates indexes for users, complaints, appointments, events, polls, campaigns, donations, notifications, and more.
- Creates chat-specific indexes for chats/messages.
- Seeds help numbers via `HelpNumberService`.
On shutdown, the MongoDB connection is closed.

## Uploads & Static Assets
- `/static` is mounted from `app/static` and is used for complaints, donations, and generated receipts.
- Complaint uploads are stored under `app/static/complaints`.
- Donation screenshots are stored under `app/static/donations`.
- Receipt PDFs are stored under `app/static/receipts`.
- Chat media uploads are stored in an absolute directory `/uploads/chat` and served via `/api/v1/chat/files/{filename}`.

## Tests
No automated tests are currently included in the repository.

## Repository Hygiene / Notes
- Do not commit `.env` with secrets.
- Virtual environment folders should not be committed.
- OCR for donation screenshots is optional and relies on `pytesseract` and `Pillow` if installed.
- DOC/DOCX previews in chat require LibreOffice to be available on the system.

## Known Limitations / Current Status
- Rate limiting is defined in settings but not enforced in middleware.
- CORS settings in `.env` are not currently wired; `app_factory` allows all origins.
- Chat uploads use an absolute path (`/uploads/chat`), which requires explicit server filesystem setup.

## Developer Handoff Notes
This repository already follows a clear separation of concerns (routes → services → db), has explicit RBAC/permission utilities, and a deterministic startup lifecycle. The README is intended to reflect the current codebase as-is, without inventing modules or endpoints. For onboarding, start with `app/main.py`, `app/core/app_factory.py`, and `app/core/routes.py` to understand the runtime flow, then review the module-specific services under `app/services`.
