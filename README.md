# user-architecture-model

A learning project exploring production-oriented Python backend design with
FastAPI, pragmatic Clean / Hexagonal Architecture, SOLID, TDD, and Spec-Driven
Development.

The project source of truth is `docs/`. Workflow prompts live in `prompts/`,
architecture guidance in `AGENTS.md`, application code in `app/`, and tests in
`tests/`.

Work proceeds through requirements, specification, plan, and ordered tasks before
individual implementation tasks begin.

Development requires Python 3.12+ and uv. Install the locked environment with
`uv sync --locked`. Run tests without external services with
`uv run --locked pytest -m 'not integration'`, lint with
`uv run --locked ruff check .`, and check formatting with
`uv run --locked ruff format --check .`.

PostgreSQL tests require an explicit `TEST_DATABASE_URL` pointing to a disposable
database using the `postgresql+asyncpg://` scheme. With that variable set, run
`uv run --locked pytest tests/integration/persistence` for persistence checks. Persistence fixtures create and remove
a unique schema per test; the test database user needs schema creation permission.
Missing integration configuration fails explicitly instead of skipping tests.


S3 tests require `TEST_S3_ENDPOINT_URL` pointing to a disposable loopback service.
For example, start `uv run --locked moto_server -H 127.0.0.1 -p 59000` in a separate
terminal and set `TEST_S3_ENDPOINT_URL=http://127.0.0.1:59000`.
The tests use explicit dummy credentials and unique temporary private buckets,
verify an anonymous read is denied, and remove test objects/buckets afterward.
With both test service variables set, run `uv run --locked pytest` for the full suite.
Moto is a local S3 emulator; it does not validate production AWS IAM policies.


The upload boundary authenticates before multipart parsing and permits exactly one
`file` part, with no owner field. On the locked Starlette parser, `max_part_size`
limits ordinary fields rather than file bytes, so a boundary subclass checks file
bytes before spooling. The file cap is 10,485,760 bytes, including chunked requests
without Content-Length. Parsing and payload reads use 65,536-byte chunks; files
spool to disk above 1 MiB. Tests instrument writes and confirm no parser write
exceeds 64 KiB and an oversized file never writes more than the file cap.
Multipart headers are capped at 16 KiB and boundaries at 200 bytes; the entire
request has a file-cap-plus-64-KiB envelope, limiting multipart overhead.
Unknown fields, multiple files, malformed or incomplete multipart, and excessive
part headers return sanitized 422; excess file/request bytes return 413.
Every temporary handle closes on success, validation failure, or dependency failure.
The bounded payload uses up to 10 MiB plus a temporary copy when converting to
bytes; these are per-request bounds, not a global concurrent-request memory limit.


Apply the versioned schema explicitly before serving the API:
`DATABASE_URL=postgresql+asyncpg://... uv run --locked alembic upgrade head`.
Alembic reads DATABASE_URL from the environment; it needs no JWT or S3 configuration.
The API never applies migrations at startup. For a disposable database, verify
rollback with `uv run --locked alembic downgrade base`, then upgrade again.
Persistence integration fixtures now migrate each unique test schema rather than
creating tables from ORM metadata; migration tests also verify schema/model parity.

For the disposable local stack, run:

```sh
docker compose up --build -d
docker compose ps
docker compose run --rm migrate
```

Compose builds the Python 3.12 API and a separate Moto S3 image from the locked
environment, starts PostgreSQL, initializes a private local bucket, and applies
Alembic in a one-shot migration service before starting the API.
The documented migration command can also be run independently; API workers never
migrate their own database. The API runs as an unprivileged user.
API: http://127.0.0.1:8000; PostgreSQL: 127.0.0.1:55432; local S3: 127.0.0.1:59000.
Override API_PORT, POSTGRES_PORT, or S3_PORT if a host port is occupied.
All Compose credentials and the signing secret are explicitly dummy local values.
Production configuration continues to use environment settings and the ordinary
AWS credentials provider chain. The build context excludes .env files, .aws,
Git metadata, private key files, test code, and local virtual environments.

With Compose services healthy, run all checks from the host:

```sh
export TEST_DATABASE_URL=postgresql+asyncpg://sdd:sdd-local-only@127.0.0.1:55432/sdd
export TEST_S3_ENDPOINT_URL=http://127.0.0.1:59000
uv run --locked pytest
```

Stop the stack with `docker compose down`. Moto's local objects are in memory;
PostgreSQL uses a named volume. For a fresh disposable environment, use
`docker compose down --volumes` and start again so both stores reset together.
These local services emulate development behavior; AWS IAM and bucket provisioning
remain operator responsibilities.

Cross-adapter checks run with
`uv run --locked pytest tests/integration/test_lifecycle.py` and both test service
variables above. Each case migrates a unique PostgreSQL schema and creates a unique
private local bucket. The composed ASGI app uses real repositories, Argon2, JWT,
and boto3; only test schema selection and deliberate failure injection are replaced.
Tests cover two-user isolation, concurrent registration, upload compensation and
orphan diagnostics, and retry after storage-first deletion loses its metadata commit.
Fixtures remove all schemas, buckets, and objects after each case.

## Secrets and deployment configuration

For host execution, copy `.env.example` to `.env`, restrict its permissions
(`chmod 600 .env`), and replace every placeholder. Required settings are
`DATABASE_URL` (postgresql+asyncpg), `JWT_SECRET` (at least 32 UTF-8 bytes), and
`S3_BUCKET`. Generate the signing secret locally with Python's
`secrets.token_urlsafe(32)` and store it in your private environment or secret
manager. Never commit credentials or print tokens in application logs.
Optional settings are `JWT_ISSUER`, `JWT_AUDIENCE`, `AWS_REGION`, and
`S3_ENDPOINT_URL`; an empty endpoint uses AWS's normal endpoint selection.
Compose supplies its own dummy credentials; `.env` values do not turn the local
Compose stack into a production deployment.

Run the configured host API with
`uv run --locked uvicorn app.bootstrap:create_app --factory`.
The API loads `.env`; Alembic requires `DATABASE_URL` explicitly exported in its
process environment. Production operators must provision a private bucket,
public-access blocks, TLS, and credentials through the normal AWS provider chain.
Restrict application object permissions to the configured bucket (PutObject and
DeleteObject); administrative inspection/cleanup needs separate appropriate access.
The local emulator verifies application privacy behavior, not live AWS policies.

## API contract

| Request | Success | Body |
| --- | --- | --- |
| POST /users | 201 | JSON name, email, password |
| POST /auth/login | 200 | JSON email, password; returns access_token and token_type |
| GET /me | 200 | Authenticated user profile |
| POST /files | 201 | Exactly one multipart file part named file |
| GET /files | 200 | Owned file metadata list |
| GET /files/{id} | 200 | Owned file metadata |
| DELETE /files/{id} | 204 | Empty response |

All routes except registration/login require `Authorization: Bearer <access_token>`.
File ownership comes from that token; clients cannot select an owner, object key,
or bucket. File routes expose metadata, with no object download URL or storage
locator. Foreign and missing IDs both return 404. Tokens expire after 3600 seconds.
Invalid input returns sanitized 422, duplicates 409, authentication failures 401
with a Bearer challenge, excess upload bytes 413, dependency failures 503, and
unexpected failures generic 500. Unknown JSON field names are omitted from error
locations because those names can themselves contain secrets. Unhandled HTTP
exception details are contained before they can reach server exception logging;
failures after response headers expose only a generic exception. Startup failures
remain visible to the operator. Deployment logging must also avoid request bodies,
Authorization headers, credentials, and private storage locators.

## Partial failures and manual cleanup

Database and S3 changes have no shared transaction or automatic reconciliation.

| Failure | Retained state and recovery |
| --- | --- |
| Upload storage failure | No metadata is committed; request returns 503. |
| Upload metadata commit failure | Metadata rolls back; object cleanup is attempted; request returns 503. |
| Upload compensation also fails | An orphan object may remain; diagnostic contains only the file UUID. |
| Delete storage failure | Metadata remains; request returns 503; retry the owned deletion. |
| Delete metadata commit failure after object removal | Metadata remains while content is absent; retry removes the metadata because storage deletion is idempotent. |

For an orphan diagnostic, wait until the failed request and any in-flight operations
have settled. In a private administrative session, check the configured database
for a committed `files` row with that UUID. If none exists, inspect the exact
`files/<uuid>` key in the configured bucket and remove that one orphan with your
administrative S3 tooling. If a row exists, investigate it before deleting any
object; use the authenticated deletion flow where applicable. Do not perform
blanket bucket deletion or publish database credentials/object locators in shared
logs. A storage timeout can leave an uncertain remote outcome, so confirm actual
object state during investigation rather than assuming an exception means absence.
There is no background orphan collector in this project.

Upload limits above apply per request. Production concurrency, reverse-proxy
limits, temporary disk capacity, secret delivery, and live AWS access policies
remain deployment responsibilities. Parser bounds depend on the locked framework
version; retain the upload regression suite when upgrading it.

Architecture and security review evidence is recorded in `docs/tasks.md`.
