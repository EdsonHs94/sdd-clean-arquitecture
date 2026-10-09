# Technical implementation plan

## Architecture and dependency direction

Use four layers with an outer composition root. Domain holds plain Python entities,
validation, and invariant errors. Application orchestrates individual operations and
defines capability ports. Infrastructure implements persistence, storage, hashing,
and token ports. Presentation translates HTTP input/output and invokes use cases.

Dependencies: application → domain; infrastructure → application/domain;
presentation → application/domain. `app/bootstrap.py` wires concrete adapters into
use cases and builds FastAPI. Domain/application never import FastAPI, Pydantic,
SQLAlchemy, PostgreSQL clients, boto3, AWS SDK types, or PyJWT. Presentation routers
do not construct adapters or implement business decisions. Infrastructure never
imports presentation. Use constructor injection; reserve `Depends` for HTTP and
composition. Check imports with an automated AST-based boundary test.

## Domain

- `User`: UUID id, normalized email, name, password_hash, UTC created_at.
- `File`: UUID id, user_id, original_name, storage_key, content_type, size, UTC created_at.
- Pure validation functions implement name/email normalization, password length,
  filename restrictions, and size limits. Centralize these rules for all entry points.
  Evaluate syntax with an email-validation library without network/deliverability checks;
  normalize explicitly so library normalization cannot change the specification.
- Domain errors: `InvalidUserData`, `InvalidFileData`, `FileTooLarge`.
  Application errors: `EmailAlreadyRegistered`, `InvalidCredentials`,
  `NotAuthenticated`, `FileNotFound`, `DependencyUnavailable`.
- Use standard UUID, datetime, str, and int; no custom ID/email value objects or
  entity inheritance are justified. Hide password hashes in entity representations.

## Application use cases

Each use case has an explicit input/result and async `execute` method where I/O is
required. Input/results are plain dataclasses or primitives, never framework models.
Authenticated file inputs take a user ID supplied by the composition boundary.

| Use case | Dependencies | Responsibility |
| --- | --- | --- |
| RegisterUser | UserRepository, PasswordHasher | Validate/normalize, reject duplicate, hash, create account; handle uniqueness race. |
| LoginUser | UserRepository, PasswordHasher, TokenService | Verify credentials and issue token; same error for unknown email/wrong password. |
| AuthenticateUser | UserRepository, TokenService | Validate token and resolve existing user; distinguish unavailable dependency from invalid authentication. |
| GetCurrentUser | none | Project authenticated User into safe profile result; reuse resolved user. |
| UploadFile | FileRepository, FileStorage | Validate upload, assign UUID/key/owner, store bytes, save metadata, compensate failed persistence. |
| ListUserFiles | FileRepository | List owned files in specified order. |
| GetUserFile | FileRepository | Retrieve with owner-scoped lookup; missing/foreign maps to one error. |
| DeleteUserFile | FileRepository, FileStorage | Resolve owned file, delete object, then delete metadata; preserve retry behavior. |

Use standard UUID generation and UTC timestamps; supply small clock/ID callables
to use cases requiring deterministic tests rather than introduce a generic service.
Upload accepts at most 10 MiB of bytes after bounded presentation reading and repeats
size checks for non-HTTP callers. Compensation catches only expected dependency
errors; record cleanup failure through a module logger without sensitive values.

## Ports (application-owned Protocols)

- UserRepository: async `get_by_email(email)`, `get_by_id(id)`, `add(user)`.
  Add commits atomically, returns only after success, raises duplicate-email or
  dependency error; database uniqueness is authoritative.
- FileRepository: async `add(file)`, `list_by_owner(user_id)`,
  `get_owned(file_id, user_id)`, `delete_owned(file_id, user_id)`.
  Mutations commit before returning. Failed writes roll back. Delete reports
  whether a row was removed; an absent row after a concurrent delete can map to 404.
- FileStorage: async `upload(key, bytes, content_type)`, `delete(key)`;
  delete is idempotent for absent objects. No read/public-URL operation is needed.
- PasswordHasher: async `hash(password)`, `verify(password, hash)`.
- TokenService: async `issue(user_id)` returning token and expiry duration;
  `verify(token)` returning UUID subject. Invalid token and dependency errors are distinct.

Adapters translate vendor exceptions to these application errors; vendor objects
do not escape ports. Narrow operation interfaces avoid generic CRUD or a global
service container. No general UnitOfWork is needed: each use case has one committed
database mutation, with explicit cross-system compensation rather than a shared transaction.

## Infrastructure adapters

### Database

Use SQLAlchemy 2.x async with PostgreSQL and asyncpg. Request-scoped AsyncSession,
explicit commit/rollback per repository mutation, no auto-commit after HTTP response.
Use separate ORM models mapped into domain entities. No lazy ORM entities leave adapters.
Translate a normalized-email unique-constraint violation into EmailAlreadyRegistered;
other database failures become DependencyUnavailable. Query files with both id and
user_id; never fetch globally then expose ownership. SQL ordering matches the spec.

Models and Alembic migrations:

- users: UUID primary key, email varchar(254) not null unique, name varchar(100),
  password_hash text, created_at timezone-aware timestamp; required fields non-null.
- files: UUID primary key, user_id non-null FK to users.id (restrict delete),
  original_name varchar(255), storage_key text unique, content_type text, size bigint
  with 0..10485760 check, created_at timezone-aware timestamp; all non-null.
- Composite index (user_id, created_at, id) supports owner listing.
- Generate normalized emails before write. No account deletion route or cascade is needed.
- Alembic uses the configured database URL and ORM metadata; never runs automatically
  on each API worker startup. Verify upgrade/downgrade on disposable databases.

### Storage

S3 adapter uses boto3 with a configured private bucket and opaque `files/<uuid>`
keys unrelated to filenames. Do not set public ACLs. Run synchronous SDK operations
in worker threads, using bounded SDK timeouts/retries. Region, bucket, and optional
local endpoint are configuration. Obtain credentials through the normal AWS provider
chain; do not embed them. Tests use mocks for interaction/failure cases and an S3
compatible local service for integration; actual AWS permissions remain operator setup.

### Security

Use Argon2id through argon2-cffi for salted hashes; run CPU work in worker threads.
Verify wrong-password and malformed-hash behavior; malformed stored hash is an
internal dependency failure, not a plaintext fallback. Use a dummy hash verification
for unknown accounts to reduce a trivial credential timing difference.

PyJWT adapter uses HS256 with an explicit single-algorithm allowlist, a random
signing secret of at least 32 bytes, required `sub`, `exp`, `iat`, `iss`, `aud`,
and strict claim types. Lifetime is 3600 seconds with no expiry leeway. Default
issuer `user-architecture-model`, audience `user-architecture-model-api`.
Invalid signatures/claims map to NotAuthenticated. Test exact expiry with controlled
time; disable no verification in production. Tokens include no private profile data.

## Presentation and composition

- Routers: users (`POST /users`, `GET /me`), auth (`POST /auth/login`),
  files (`POST /files`, `GET /files`, `GET/DELETE /files/{file_id}`).
- Pydantic v2 schemas perform strict string-shape checks and forbid extra JSON fields;
  domain validation remains authoritative. Safe response schemas explicitly allow
  only fields listed in the spec. Map original_name → filename and size → size_bytes.
- Bearer extraction dependency calls AuthenticateUser. Apply authentication before
  resource validation/lookup; test invalid UUID plus missing authentication returns 401.
- Read multipart uploads in bounded chunks, abort above limit, close upload handles;
  do not trust Content-Length. Configure bounded multipart parsing/spooling and test
  chunked oversized requests, since endpoint reads alone do not bound initial parsing.
- Route handlers convert input, invoke one use case, and return schema/status.
- Central error mapping: invalid data 422; duplicate email 409; credentials/auth 401
  with Bearer challenge; file absent 404; size excess 413; dependency failures 503;
  unexpected errors 500. Sanitize validation responses to omit input/context secrets.
- Dependency overrides allow API tests with fakes. App factory and lifespan manage
  database engine cleanup and shared SDK client; settings validation happens at startup.

## Configuration and local development

Use pyproject.toml with Python >=3.12 and runtime/dev dependency groups; select and
lock compatible versions during implementation. Settings belong to outer layers,
using pydantic-settings. Required: DATABASE_URL, JWT_SECRET, S3_BUCKET.
Optional/default: JWT_ISSUER, JWT_AUDIENCE, AWS_REGION, S3_ENDPOINT_URL.
Use environment variables/provider-chain credentials; safe `.env.example` placeholders.

Dockerfile and Docker Compose provide API, PostgreSQL, and a local S3-compatible
service with a private test bucket initializer. Local credentials are explicitly
dummy values. Production AWS bucket provisioning is external. README documents
setup, migration, tests, credentials, endpoint examples, and partial failure recovery.

## Proposed project structure (to be created during implementation)

```text
app/
  domain/{entities.py,validation.py,errors.py}
  application/{ports.py,dto.py,errors.py,use_cases/}
  infrastructure/
    persistence/{models.py,session.py,user_repository.py,file_repository.py}
    storage/s3.py
    security/{passwords.py,tokens.py}
    settings.py
  presentation/{schemas.py,dependencies.py,error_handlers.py,routers/}
  bootstrap.py
tests/
  unit/{domain/,application/,fakes.py}
  integration/{persistence/,storage/,security/}
  api/
  architecture/
alembic/versions/
alembic.ini
pyproject.toml
Dockerfile
compose.yaml
.env.example
docs/{requirements.md,spec.md,plan.md,tasks.md}
```

## Testing and TDD

For every business use case: RED writes the relevant acceptance tests and confirms
failure for missing behavior; GREEN adds the smallest implementation; REFACTOR
improves boundaries/names while retaining passing tests. Do this within each task,
not by writing all implementation before tests. Do not count import/environment
failure as evidence of a behavioral test failing.

- Domain unit tests: validation boundaries, normalization, safe representations.
- Application unit tests: stateful fake user/file repositories and storage for
  lifecycle/ownership; fake token/hasher for deterministic orchestration. Fakes model
  uniqueness, commit failure, ordering, ownership, and absent-object deletion.
- Mocks: interaction-oriented SDK calls, upload compensation attempts, prohibited
  storage access on foreign IDs, and injected external failures.
- Infrastructure integration: real disposable PostgreSQL for unique-email races,
  rollback, owner-scoped queries, and migrations; local S3 for byte roundtrip,
  deletion, and private-access configuration; actual Argon2/PyJWT for crypto behavior.
- API tests: httpx ASGI transport, fake dependencies, all status/body/header contracts,
  two-user isolation, upload boundaries, secret-safe validation, and exception mapping.
- End-to-end integration: local PostgreSQL/S3 through composed API, register/login,
  `/me`, upload/list/retrieve/delete, with a second user's access denied.
- Architecture tests: parse all production imports, enforce layer dependency rules
  including relative imports and forbidden vendor imports in inner layers.
- Isolate resources per test; integration markers require explicit services and never
  contact production. Ordinary unit/API suite requires no AWS account or database.

Map all AC01–AC17 into task tests; final review verifies coverage, not only green tests.

## Decisions, trade-offs, and rejected alternatives

- Repository-owned commits simplify one-write use cases. Reject a generic UnitOfWork
  until a concrete multi-write atomic transaction needs it.
- Bounded in-memory upload payload is acceptable for a 10 MiB learning API; streaming
  end-to-end and larger files would require revisiting the spec and resource budgets.
- Synchronous boto3/Argon2 use workers to keep async handlers responsive; no custom
  asynchronous S3 SDK is required by the target stack.
- Reject a generic user/file service, framework types in application, ORM domain
  entities, global dependency lookup, CQRS, events, and distributed transactions.
- S3/PostgreSQL cannot be atomically committed together here. Compensation and retry
  meet the specification; orphan cleanup is manual and operationally documented.
- Enforce secrets exclusion, private storage, algorithm/claim verification, bounded
  uploads, safe logs, and ownership before storage mutations.

## Unresolved questions

No design question blocks task breakdown. Exact compatible dependency versions and
multipart resource-control mechanics must be verified during their implementation
tasks. Actual AWS credentials/bucket, production secret delivery, and deployment
are operator concerns outside this workflow. No deviations from requirements/spec.
