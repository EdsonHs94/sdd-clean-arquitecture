# Ordered implementation tasks

TASK-001–TASK-032 are **complete**.
Execute exactly one selected TASK_ID per implementation invocation unless the user
explicitly authorizes a sequential batch. Dependencies list prerequisites, not
permission to batch tasks. Acceptance IDs refer to `docs/spec.md`.

For every implementation task, demonstrate RED before GREEN and rerun tests after
REFACTOR. Completion also requires relevant tests passing, diff inspection, inward
dependency checks, no secret exposure, and no undocumented specification deviation.
Configuration/contract tasks use focused verification rather than artificial business
tests. Integration tests introduced with adapters run against isolated fixtures;
the later integration task adds cross-adapter coverage rather than postponing tests.

## TASK-001 — Python project configuration

- Objective: Establish Python 3.12+ packaging, dependency lock, and test/lint tools.
- Acceptance criteria: Plan tooling prerequisite for AC01–AC17.
- Expected files: `pyproject.toml`, dependency lock, `app/__init__.py`, `tests/conftest.py`.
- Dependencies: none.
- RED / tests first: Verify Python constraint, package installation, pytest async
  configuration, integration marker registration, and lint invocation against missing configuration.
- GREEN: Add minimal package/tool configuration and compatible runtime/dev dependencies.
- REFACTOR: Remove redundant tool settings; document commands where necessary.
- Expected result: Reproducible environment; unit tests can run without external services.
- Completion criteria: Install/resolve succeeds, lock exists, tool checks work, no business code added.

## TASK-002 — User entity and input rules

- Objective: Represent users and centralize registration/login validation.
- Acceptance criteria: AC01, AC02, AC05, AC17 (domain portions).
- Expected files: `app/domain/{entities.py,validation.py,errors.py}`, `tests/unit/domain/test_user.py`.
- Dependencies: TASK-001.
- RED / tests first: Name 0/1/100/101, password 7/8/128/129, whitespace preservation,
  trimmed/case-normalized email, valid/invalid syntax, email length, UTC fields, safe repr.
- GREEN: Plain User entity, pure normalization/validation, typed domain errors.
- REFACTOR: Consolidate shared validation without custom value-object hierarchy.
- Expected result: Testable rules with no framework or persistence imports.
- Completion criteria: Boundary cases pass; password/hash absent from representations.

## TASK-003 — User repository port and fake

- Objective: Define account persistence capability and its failure contract.
- Acceptance criteria: AC01, AC03, AC06, AC16 (supporting contract).
- Expected files: `app/application/{ports.py,errors.py}`, `tests/unit/application/fakes.py`, `tests/unit/application/test_user_repository_contract.py`.
- Dependencies: TASK-002.
- RED / tests first: Fake add/get-by-email/get-by-id, uniqueness and simulated failed write
  without mutation; verify consumers can receive a fake without vendor dependencies.
- GREEN: UserRepository Protocol, duplicate/dependency errors, stateful fake.
- REFACTOR: Keep method set limited to planned operations.
- Expected result: Explicit commit/uniqueness semantics usable by use cases.
- Completion criteria: Fake contract checks pass; port imports only inner-layer types.

## TASK-004 — Password hasher port

- Objective: Define async hash/verify without choosing an adapter in application.
- Acceptance criteria: AC01, AC05, AC17 (supporting contract).
- Expected files: `app/application/ports.py`, `tests/unit/application/fakes.py`.
- Dependencies: TASK-003.
- RED / tests first: Fake roundtrip and wrong-password behavior, injected failure;
  ensure raw credentials do not appear in fake representations/diagnostics.
- GREEN: PasswordHasher Protocol and deterministic test fake.
- REFACTOR: Keep fake explicitly test-only and never wire it into production.
- Expected result: Credential operations injectable via a narrow contract.
- Completion criteria: Contract checks pass without a crypto dependency in inner layers.

## TASK-005 — Token service port

- Objective: Define issuance/verification and distinguish invalid token from outage.
- Acceptance criteria: AC04, AC06, AC16 (supporting contract).
- Expected files: `app/application/{ports.py,dto.py,errors.py}`, `tests/unit/application/fakes.py`.
- Dependencies: TASK-004.
- RED / tests first: Fake issue result, subject resolution, invalid token, dependency
  failure, deterministic expiration; no vendor types in results.
- GREEN: TokenService Protocol, plain token result, authentication error and fake.
- REFACTOR: Reuse standard UUID/time types rather than add token object hierarchy.
- Expected result: Injectable token capability for login/authentication.
- Completion criteria: Contract checks pass; lifetime result can express 3600 seconds.

## TASK-006 — RegisterUser

- Objective: Register validated unique accounts with protected passwords.
- Acceptance criteria: AC01, AC02, AC03, AC16, AC17.
- Expected files: `app/application/use_cases/register_user.py`, `app/application/dto.py`, `tests/unit/application/test_register_user.py`.
- Dependencies: TASK-005.
- RED / tests first: Valid/invalid registration, normalized duplicates, duplicate-on-add
  race, hashing failure, persistence failure, safe profile output; failed operations create no account.
- GREEN: Constructor-injected orchestration, validation, hashing, committed add and profile result.
- REFACTOR: Remove duplicate normalization and vendor-specific exception handling.
- Expected result: Correct account creation independently of HTTP/database.
- Completion criteria: All cases pass with fakes; no token or raw password in persisted user/result.

## TASK-007 — LoginUser

- Objective: Verify credentials and return an access-token result.
- Acceptance criteria: AC04, AC05, AC16, AC17.
- Expected files: `app/application/use_cases/login_user.py`, `tests/unit/application/test_login_user.py`.
- Dependencies: TASK-006.
- RED / tests first: Correct login, case/whitespace email, wrong password, unknown email,
  invalid inputs, verify/token/repository outages; no token issued on invalid credentials.
- GREEN: Inject repository/hasher/token service; same credential error for absent user
  and mismatch. Arrange dummy verification for absent users through the hasher contract.
- REFACTOR: Avoid duplicated credential rules and crypto details in orchestration.
- Expected result: Safe token result and deterministic credential failures.
- Completion criteria: Unit suite passes; 3600-second result and safe error/log behavior verified.

## TASK-008 — AuthenticateUser and GetCurrentUser

- Objective: Resolve token subjects to existing users and project their safe profile.
- Acceptance criteria: AC06, AC07, AC16, AC17.
- Expected files: `app/application/use_cases/{authenticate_user.py,get_current_user.py}`, `tests/unit/application/test_authenticate_user.py`, `tests/unit/application/test_current_user.py`.
- Dependencies: TASK-007.
- RED / tests first: Valid user, invalid token/subject, expired fake token, absent user,
  repository outage, and two distinct profiles without hashes.
- GREEN: Separate token resolution from pure current-profile projection.
- REFACTOR: Reuse safe DTO mapping without adding a generic user service.
- Expected result: HTTP-independent authentication and current-profile behavior.
- Completion criteria: Invalid authentication remains distinct from dependency failure.

## TASK-009 — Argon2 password adapter

- Objective: Implement production password hashing outside inner layers.
- Acceptance criteria: AC01, AC05, AC17.
- Expected files: `app/infrastructure/security/passwords.py`, `tests/integration/security/test_passwords.py`.
- Dependencies: TASK-004, TASK-007.
- RED / tests first: Real Argon2 roundtrip, unique salts, wrong password, 128-character
  input, malformed hash, unknown-user dummy verification and safe diagnostics.
- GREEN: Argon2id hash/verify in worker threads; translate expected failures.
- REFACTOR: Centralize adapter error conversion; no plaintext fallback.
- Expected result: Salted protected passwords with nonblocking async interface.
- Completion criteria: Crypto tests pass without database/AWS; raw credentials never logged.

## TASK-010 — JWT adapter

- Objective: Issue and verify the specified access tokens with PyJWT.
- Acceptance criteria: AC04, AC06, AC17.
- Expected files: `app/infrastructure/security/tokens.py`, `tests/integration/security/test_tokens.py`.
- Dependencies: TASK-005, TASK-008.
- RED / tests first: Claims/lifetime, exact expiry, tampering, wrong key/algorithm,
  issuer/audience mismatch, missing claims, wrong claim types and invalid UUID subject.
- GREEN: HS256 allowlist, required claims, configured secret/issuer/audience,
  3600-second lifetime, strict verification and error translation.
- REFACTOR: Inject/control time for tests without weakening production verification.
- Expected result: Real tokens obey the spec and expose no passwords/profile secrets.
- Completion criteria: Positive and negative crypto cases pass; unsupported algorithms rejected.

## TASK-011 — SQLAlchemy user persistence

- Objective: Implement committed account persistence with PostgreSQL uniqueness.
- Acceptance criteria: AC01, AC03, AC06, AC16.
- Expected files: `app/infrastructure/persistence/{models.py,session.py,user_repository.py}`, `tests/integration/persistence/test_users.py`.
- Dependencies: TASK-003, TASK-006, TASK-008.
- RED / tests first: Real PostgreSQL roundtrip, normalized email uniqueness, concurrent
  duplicate writes, commit rollback, safe entity mapping and session cleanup.
- GREEN: Async models/repository/session setup; unique constraint and explicit commits.
- REFACTOR: Keep ORM mapping inside adapter; distinguish duplicate constraint from other failures.
- Expected result: UserRepository implementation satisfying the fake-tested contract.
- Completion criteria: Isolated integration tests pass; failures roll back and no ORM escapes.
  Tests may create temporary ORM schema until TASK-027 adds migration verification.

## TASK-012 — Settings and HTTP composition

- Objective: Build app factory, safe settings, injected dependencies, and error mapping.
- Acceptance criteria: AC06, AC16, AC17 (HTTP foundation).
- Expected files: `app/infrastructure/settings.py`, `app/bootstrap.py`, `app/presentation/{dependencies.py,error_handlers.py}`, `.env.example`, `tests/api/test_app.py`.
- Dependencies: TASK-008, TASK-009, TASK-010, TASK-011.
- RED / tests first: Missing/weak settings, dependency overrides, lifespan cleanup,
  sanitized 422/503/500, auth challenges, case-insensitive Bearer and invalid schemes.
- GREEN: Outer wiring with request sessions, authentication dependency, central error
  handlers, safe validation errors, and placeholders in .env.example.
- REFACTOR: Separate construction from handlers; no global service locator.
- Expected result: Testable HTTP boundary and validated runtime configuration.
- Completion criteria: API foundation tests pass without external services; .env.example is not ignored.

## TASK-013 — Registration and login API

- Objective: Expose public account creation and login contracts.
- Acceptance criteria: AC01–AC05, AC16, AC17.
- Expected files: `app/presentation/routers/{users.py,auth.py}`, `app/presentation/schemas.py`, `tests/api/test_auth.py`.
- Dependencies: TASK-012.
- RED / tests first: Status/body contracts, invalid field types, extra fields, normalization,
  duplicate email, invalid credentials/challenge, dependency failures, password-safe validation.
- GREEN: Strict schemas and thin routes invoking RegisterUser/LoginUser.
- REFACTOR: Consolidate response projections; keep rules in domain/application.
- Expected result: 201 profile and 200 token contracts; consistent failures.
- Completion criteria: API tests pass; response fields match spec exactly and disclose no hashes.

## TASK-014 — Current user API

- Objective: Expose protected `GET /me`.
- Acceptance criteria: AC06, AC07, AC16, AC17.
- Expected files: `app/presentation/routers/users.py`, `tests/api/test_me.py`.
- Dependencies: TASK-013.
- RED / tests first: Two-user profile isolation, missing/malformed/expired/unknown-user
  authentication, dependency failure and no password fields.
- GREEN: Authentication dependency plus GetCurrentUser projection and safe response.
- REFACTOR: Reuse resolved authenticated user instead of an unnecessary second lookup.
- Expected result: Caller receives only their own profile.
- Completion criteria: API cases pass including challenge header and sanitized error bodies.

## TASK-015 — File entity and validation

- Objective: Represent owned metadata and enforce upload invariants.
- Acceptance criteria: AC08, AC09, AC17 (domain portions).
- Expected files: `app/domain/{entities.py,validation.py,errors.py}`, `tests/unit/domain/test_file.py`.
- Dependencies: TASK-014.
- RED / tests first: UUID/ownership fields, filename lengths and slash/backslash/control
  rejection, sizes 0/limit/limit+1, negative size, content-type default, UTC timestamp.
- GREEN: File entity and pure validation; separate storage key from original filename.
- REFACTOR: Share constants and typed errors without framework coupling.
- Expected result: File rules independently testable.
- Completion criteria: All boundaries pass and private locator is excluded from safe output.

## TASK-016 — File repository port and fake

- Objective: Define owner-scoped metadata persistence and committed mutations.
- Acceptance criteria: AC08, AC11–AC16 (supporting contract).
- Expected files: `app/application/ports.py`, `tests/unit/application/fakes.py`, `tests/unit/application/test_file_repository_contract.py`.
- Dependencies: TASK-015.
- RED / tests first: Add/list/get/delete, missing vs foreign, ordering with tied times,
  failed commits retaining state, and concurrent absent-row deletion result.
- GREEN: FileRepository Protocol and ownership-enforcing stateful fake.
- REFACTOR: Keep owner scoping explicit in method signatures.
- Expected result: Reliable fake and narrow persistence contract.
- Completion criteria: Contract checks pass; no unrestricted single-file access method introduced.

## TASK-017 — File storage port and fake

- Objective: Define private upload/idempotent-delete capabilities.
- Acceptance criteria: AC08, AC10, AC13–AC15 (supporting contract).
- Expected files: `app/application/ports.py`, `tests/unit/application/fakes.py`.
- Dependencies: TASK-016.
- RED / tests first: Stored bytes/content type by opaque key, repeated filenames with
  distinct keys, absent-object delete, injected upload/delete failures and call recording.
- GREEN: FileStorage Protocol and fake object store.
- REFACTOR: Keep read assertions test-only; no download/public URL production port.
- Expected result: Testable storage lifecycle and failure injection.
- Completion criteria: Fake contract passes without AWS libraries in application.

## TASK-018 — UploadFile

- Objective: Save private file content and metadata with upload compensation.
- Acceptance criteria: AC08–AC10, AC17.
- Expected files: `app/application/use_cases/upload_file.py`, `app/application/dto.py`, `tests/unit/application/test_upload_file.py`.
- Dependencies: TASK-017.
- RED / tests first: Authenticated ownership, distinct opaque keys, size boundaries,
  invalid filename, storage failure/no metadata, metadata failure/cleanup, cleanup
  failure/diagnostic and safe result fields.
- GREEN: Validate, create id/key/time, upload then committed add; compensate persistence failure.
- REFACTOR: Preserve original failure during cleanup; avoid sensitive diagnostic data.
- Expected result: Success only after both writes; explicit permitted orphan failure state.
- Completion criteria: State/interaction assertions pass including compensation ordering.

## TASK-019 — ListUserFiles

- Objective: Return ordered metadata only for the caller.
- Acceptance criteria: AC11, AC16, AC17.
- Expected files: `app/application/use_cases/list_user_files.py`, `tests/unit/application/test_list_files.py`.
- Dependencies: TASK-018.
- RED / tests first: Two-user isolation, empty list, tied-time ID ordering, repository failure,
  safe metadata without storage locator.
- GREEN: Owner-scoped list invocation and safe DTO mapping.
- REFACTOR: Reuse safe file projection without generic CRUD service.
- Expected result: Stable owned-file listing.
- Completion criteria: Unit tests pass; caller cannot choose another owner through business input.

## TASK-020 — GetUserFile

- Objective: Retrieve owned file metadata with indistinguishable absent/foreign failures.
- Acceptance criteria: AC12, AC16, AC17.
- Expected files: `app/application/use_cases/get_user_file.py`, `tests/unit/application/test_get_file.py`.
- Dependencies: TASK-019.
- RED / tests first: Owned success, missing/foreign failure, repository outage, safe metadata;
  assert use case has no storage dependency/read.
- GREEN: Owner-scoped lookup and FileNotFound mapping.
- REFACTOR: Share profile projection only where useful.
- Expected result: Retrieval enforces ownership before returning any metadata.
- Completion criteria: All cases pass and no private locator escapes.

## TASK-021 — DeleteUserFile

- Objective: Delete content before metadata and permit retry after partial failure.
- Acceptance criteria: AC13–AC15, AC17.
- Expected files: `app/application/use_cases/delete_user_file.py`, `tests/unit/application/test_delete_file.py`.
- Dependencies: TASK-020.
- RED / tests first: Owned success/order, foreign/missing no storage calls, repeat not found,
  storage failure retains metadata, metadata failure and retry with absent content,
  concurrent delete outcome without touching unrelated keys.
- GREEN: Owned lookup, idempotent storage delete, committed owner-scoped metadata delete.
- REFACTOR: Simplify failure handling without falsely reporting successful deletion.
- Expected result: Both resources removed on success; partial state is retryable.
- Completion criteria: State and prohibited-interaction tests pass for all failure branches.

## TASK-022 — SQLAlchemy file persistence

- Objective: Implement file metadata storage with database ownership filters.
- Acceptance criteria: AC08, AC11–AC16.
- Expected files: `app/infrastructure/persistence/{models.py,file_repository.py}`, `tests/integration/persistence/test_files.py`.
- Dependencies: TASK-011, TASK-016, TASK-021.
- RED / tests first: Real database roundtrip, FK/size/key constraints, ordering, owner-scoped
  retrieval/delete, commit rollback and concurrent delete behavior.
- GREEN: File model, index, repository, explicit commits and domain mapping.
- REFACTOR: Centralize repeated mapping/error conversion within persistence.
- Expected result: FileRepository adapter matches fake semantics.
- Completion criteria: PostgreSQL tests pass; foreign owner queries never return or delete rows.

## TASK-023 — S3 adapter

- Objective: Implement private physical storage via boto3.
- Acceptance criteria: AC08, AC10, AC13–AC15, AC17.
- Expected files: `app/infrastructure/storage/s3.py`, `tests/integration/storage/test_s3.py`, `tests/unit/infrastructure/test_s3_calls.py`.
- Dependencies: TASK-017, TASK-018, TASK-021.
- RED / tests first: Mock exact SDK bucket/key/body/content-type calls, no public ACL,
  absent-object delete, timeout/client failures translated; local S3 byte roundtrip/deletion.
- GREEN: Worker-thread boto3 adapter with bounded SDK timeout/retry configuration.
- REFACTOR: Keep SDK specifics inside adapter; no key derived from client filenames.
- Expected result: FileStorage implementation with private objects and consistent errors.
- Completion criteria: Mock and local-service checks pass; no production AWS calls in tests.

## TASK-024 — Upload HTTP endpoint and resource limits

- Objective: Expose authenticated multipart upload with bounded resource consumption.
- Acceptance criteria: AC06, AC08–AC10, AC16, AC17.
- Expected files: `app/presentation/routers/files.py`, `app/presentation/schemas.py`, `app/bootstrap.py`, `tests/api/test_upload.py`.
- Dependencies: TASK-012, TASK-018, TASK-022, TASK-023.
- RED / tests first: Missing file/invalid filename, empty/limit/limit+1 bytes, chunked
  request without Content-Length, default content type, unauthorized upload, spoofed
  owner field, dependency/cleanup failures, and file-handle cleanup.
- GREEN: Verify selected framework parser limits, bound parsing/spooling/read behavior,
  authenticate caller, invoke UploadFile, return 201 schema; reject owner override.
- REFACTOR: Keep transport limits at boundary and repeat business size check in use case.
- Expected result: Upload contracts hold even for streamed oversized requests.
- Completion criteria: API tests pass; document measured parser/resource limits and no secret echo.

## TASK-025 — File list and metadata HTTP endpoints

- Objective: Expose protected listing and single-file metadata retrieval.
- Acceptance criteria: AC06, AC11, AC12, AC16, AC17.
- Expected files: `app/presentation/routers/files.py`, `tests/api/test_file_reads.py`.
- Dependencies: TASK-024, TASK-019, TASK-020.
- RED / tests first: Two-user isolation, ordered/empty list, owned metadata, absent/foreign
  identical 404, malformed UUID 422, unauthenticated malformed UUID 401, repository outage.
- GREEN: Thin owner-derived routes with safe response schemas and auth-first validation.
- REFACTOR: Share DTO conversion while keeping handlers free of ownership decisions.
- Expected result: No storage URLs or other users' file metadata exposed.
- Completion criteria: Exact HTTP contracts and no-storage-read assertions pass.

## TASK-026 — File deletion HTTP endpoint

- Objective: Expose protected retryable file deletion.
- Acceptance criteria: AC06, AC13–AC17.
- Expected files: `app/presentation/routers/files.py`, `tests/api/test_file_delete.py`.
- Dependencies: TASK-025, TASK-021.
- RED / tests first: Empty 204, repeat 404, foreign/missing identical 404 with no storage
  calls, malformed UUID/auth precedence, both dependency failure states and successful retry.
- GREEN: Invoke DeleteUserFile with verified identity and return mapped responses.
- REFACTOR: Reuse central exception handlers rather than route-specific error branches.
- Expected result: Safe HTTP deletion matching application failure semantics.
- Completion criteria: All API cases pass; no success response with metadata left behind.

## TASK-027 — Alembic migrations

- Objective: Version the PostgreSQL schema for clean setup and rollback.
- Acceptance criteria: AC01, AC03, AC08, AC11 (persistence foundation).
- Expected files: `alembic.ini`, `alembic/env.py`, `alembic/versions/*`, `tests/integration/persistence/test_migrations.py`.
- Dependencies: TASK-022, TASK-026.
- RED / tests first: Blank database upgrade, schema constraints/indexes, downgrade/upgrade,
  and repository suite against migrated schema.
- GREEN: Alembic environment and explicit users/files migration using configured database URL.
- REFACTOR: Remove hardcoded URLs and ensure model metadata matches migration.
- Expected result: Repeatable schema initialization without API startup migration side effects.
- Completion criteria: Disposable migration cycle and repository tests pass with migrated schema.

## TASK-028 — Docker and local service configuration

- Objective: Supply reproducible local API/PostgreSQL/S3 services.
- Acceptance criteria: Plan runtime prerequisite for AC01–AC17.
- Expected files: `Dockerfile`, `compose.yaml`, `.dockerignore`, `.env.example`, `README.md`.
- Dependencies: TASK-027.
- RED / tests first: Validate Compose configuration/build, isolated service health, private
  bucket initialization and documented migration command; verify no real secrets in image context.
- GREEN: Add service setup with explicitly dummy local credentials, health checks,
  API app factory entrypoint, and setup/migration/test instructions.
- REFACTOR: Keep local values separate from production provider-chain configuration.
- Expected result: A clean checkout can run the local stack using documented commands.
- Completion criteria: Build/start/migrate smoke check succeeds; no remote AWS dependency.

## TASK-029 — Cross-adapter integration and end-to-end tests

- Objective: Verify actual infrastructure cooperation and partial failure recovery.
- Acceptance criteria: AC01, AC03, AC04, AC06–AC08, AC10–AC16.
- Expected files: `tests/integration/test_lifecycle.py`, `tests/integration/conftest.py`, `README.md`.
- Dependencies: TASK-028.
- RED / tests first: Real database/S3 register/login/profile/upload/list/get/delete lifecycle,
  second-user denial, duplicate race, injected persistence-after-storage failure,
  cleanup failure and deletion retry after metadata failure.
- GREEN: Add isolated fixtures/failure injection; fix only demonstrated adapter integration gaps.
- REFACTOR: Reuse fixtures, avoid suite-wide shared users/buckets and production endpoints.
- Expected result: End-to-end behavior matches single-adapter and use-case contracts.
- Completion criteria: Integration suite passes on local services; failures produce specified states.

## TASK-030 — API acceptance coverage audit

- Objective: Close demonstrable HTTP contract gaps across all acceptance criteria.
- Acceptance criteria: AC01–AC17.
- Expected files: `tests/api/*`, `docs/tasks.md` (test-evidence references).
- Dependencies: TASK-029.
- RED / tests first: Audit each AC and add missing scenarios, especially all token variants
  on every protected route, strict JSON shapes, auth precedence, size boundaries, sanitized errors.
- GREEN: Fix demonstrated gaps with minimal changes; retain existing endpoint tests.
- REFACTOR: Parameterize repeated cases without hiding route-specific expectations.
- Expected result: Every AC has identifiable API/unit/integration evidence.
- Completion criteria: Unit/API and infrastructure suites pass; coverage matrix has no missing AC.

## TASK-031 — Architecture review

- Objective: Verify dependency direction, responsibility boundaries, and injection.
- Acceptance criteria: AGENTS.md and plan boundaries; supports AC01–AC17.
- Expected files: `tests/architecture/test_boundaries.py`, `docs/tasks.md` (review evidence).
- Dependencies: TASK-030.
- RED / tests first: Import-boundary checker tests include forbidden vendor imports,
  absolute/relative outward imports, and valid composition; checker fails on temporary fixtures.
- GREEN: Implement AST import checks; fix only demonstrated boundary violations.
- REFACTOR: Remove unnecessary abstractions or duplicated wiring while preserving behavior.
- Expected result: Domain/application remain independent; routers contain transport logic only.
- Completion criteria: Boundary test passes on all production modules; manually inspect
  constructor injection, ORM containment, and route responsibilities; rerun affected tests.

## TASK-032 — Security review and final documentation

- Objective: Verify ownership, credentials, tokens, storage privacy, and operational guidance.
- Acceptance criteria: AC01–AC17, especially AC06, AC10, AC14, AC15, AC17.
- Expected files: `tests/api/test_security.py`, `tests/integration/security/*`, `README.md`, `docs/tasks.md`.
- Dependencies: TASK-031.
- RED / tests first: Add any missing adversarial two-user cases, spoofed owners/keys,
  algorithm/claim attacks, captured-log/validation secret leakage, public-object checks,
  and oversized chunked input. Avoid duplicating existing coverage without a gap.
- GREEN: Fix evidenced issues; document secret setup, test commands, upload/deletion
  partial states and manual orphan cleanup. Do not change agreed behavior silently.
- REFACTOR: Consolidate redaction and policy checks at the appropriate boundary.
- Expected result: Security contracts have evidence and operational limitations are clear.
- Completion criteria: Relevant suites and final full checks pass; all AC evidence reviewed,
  no secrets tracked; report any deviation and unresolved operational limitation.

## Acceptance traceability

| Acceptance criteria | Principal tasks |
| --- | --- |
| AC01 | TASK-002, TASK-006, TASK-009, TASK-011, TASK-013 |
| AC02 | TASK-002, TASK-006, TASK-013 |
| AC03 | TASK-003, TASK-006, TASK-011, TASK-013, TASK-029 |
| AC04 | TASK-005, TASK-007, TASK-010, TASK-013 |
| AC05 | TASK-007, TASK-009, TASK-013 |
| AC06 | TASK-008, TASK-010, TASK-012, TASK-014, TASK-024–TASK-026, TASK-030 |
| AC07 | TASK-008, TASK-014, TASK-029 |
| AC08 | TASK-015, TASK-018, TASK-022–TASK-024, TASK-029 |
| AC09 | TASK-015, TASK-018, TASK-024 |
| AC10 | TASK-018, TASK-023, TASK-024, TASK-029 |
| AC11 | TASK-016, TASK-019, TASK-022, TASK-025 |
| AC12 | TASK-020, TASK-022, TASK-025 |
| AC13 | TASK-021–TASK-023, TASK-026, TASK-029 |
| AC14 | TASK-021, TASK-022, TASK-026, TASK-032 |
| AC15 | TASK-021–TASK-023, TASK-026, TASK-029 |
| AC16 | TASK-006–TASK-008, TASK-011–TASK-014, TASK-019–TASK-022, TASK-024–TASK-026, TASK-029 |
| AC17 | TASK-002, TASK-006–TASK-010, TASK-012–TASK-015, TASK-018–TASK-021, TASK-023–TASK-026, TASK-032 |

## Assumptions and unresolved issues

- Suggested prompt ordering is adapted to introduce real security adapters before
  HTTP wiring and to keep adapter tests alongside implementation. No product scope changes.
- Dependency compatibility is verified in TASK-001; multipart controls in TASK-024.
- Local integration services are configured in TASK-028; earlier adapter tests can
  use operator-provided disposable local endpoints and temporary schemas.
- No blocking issue remains for task execution. Production AWS/secret provisioning
  and manual orphan reconciliation remain documented operator responsibilities.

## Execution evidence — first batch

- TASK-001: Missing configuration check failed as expected. Python 3.12.15 installed;
  uv.lock resolved and locked offline sync passed. Two temporary configuration smoke
  tests passed (installation, runtime, pytest async mode and marker). Ruff check and
  format checks passed. Temporary tests are outside the repository.
- TASK-002: 36 behavior tests failed on explicit unimplemented scaffolds, then all
  passed after implementation and refactor. Tests: `tests/unit/domain/test_user.py`.
  Strict email syntax, no deliverability checks; immutable User hides hash in repr
  and normalizes aware creation timestamps to UTC. No specification changes.
- TASK-003: Eight fake repository tests failed before behavior implementation, then
  passed; full suite after refactor: 44 passed. Tests:
  `tests/unit/application/test_user_repository_contract.py`. Application owns a
  narrow async Protocol; fake commits immediately, enforces uniqueness without an
  await between check/write, and supports failures with no state mutation.
- TASK-004: Nine hasher contract tests failed before fake behavior implementation,
  then passed; full suite after refactor: 53 passed. Tests:
  `tests/unit/application/test_password_hasher_contract.py`. Async PasswordHasher
  Protocol has no crypto imports; deterministic unsalted SHA-256 exists only in
  the test fake, with explicit documentation that it is unsuitable for production.
- TASK-005: Twelve token contract tests failed before fake behavior implementation,
  then passed; full suite after refactor: 65 passed, none skipped. Tests:
  `tests/unit/application/test_token_service_contract.py`. TokenResult is a plain
  immutable dataclass with hidden token representation; async TokenService returns
  UUID subjects. Fake tokens are opaque test values, with clock-controlled exclusive
  expiration at 3600 seconds and separate authentication/dependency errors.
- Final first-batch validation: Ruff lint/format and git diff whitespace checks pass.
  Production import inspection confirms domain has no application/infrastructure/
  presentation imports, application imports only domain/application/stdlib, and no
  forbidden vendor or test imports exist in either inner layer. No use cases,
  infrastructure adapters, HTTP routes, or file behavior have been implemented.
- Deviations: none from the plan or specification. Package/tool setup uses uv and
  Hatchling; domain email validation uses the planned standalone library, not Pydantic.
  Requirements, specification, and plan were not changed in this batch.
- Review before TASK-006: input rules and safe representations, async port signatures,
  fake failure flags, and locked dependencies. Hasher/token fakes are deliberately
  non-production; real Argon2 and PyJWT adapters remain TASK-009 and TASK-010.

## Execution evidence — second batch

- TASK-006: Twelve RegisterUser tests failed on unimplemented behavior, then passed.
  Full suite after cleanup: 77 passed. Constructor-injected repository/hasher with
  optional clock/UUID callables; validates before I/O, handles duplicate-on-add
  race via the port, persists only a hash, and returns an immutable safe UserProfile.
  Tests: `tests/unit/application/test_register_user.py`. Ruff and whitespace checks
  passed. No requirement/specification/plan deviation.
- TASK-007: Fourteen LoginUser tests failed on unimplemented behavior, then passed.
  Full suite after cleanup: 91 passed. Normalizes credentials, verifies stored or
  precomputed dummy hash exactly once, never authenticates an absent account even
  when dummy verification matches, and issues a token only on valid credentials.
  Tests: `tests/unit/application/test_login_user.py`. Dummy hash is an explicit
  constructor input; future composition must generate it with the real hasher once
  at startup. Dependency failures propagate distinctly. Ruff/format/whitespace
  checks passed; no deviation from the plan or specification.
- TASK-008: Thirteen authentication tests and two profile tests failed before
  implementation, then passed. Full suite after cleanup: 106 passed. Invalid or
  expired tokens and non-UUID subjects cause no user lookup; a valid subject must
  resolve to an existing user. Outages remain distinct from invalid authentication.
  GetCurrentUser synchronously projects the already resolved user via UserProfile,
  requiring no extra repository call. Tests: `test_authenticate_user.py` and
  `test_current_user.py` under `tests/unit/application/`. Ruff and whitespace
  checks passed. No plan/specification deviation.
- TASK-009: Fourteen Argon2 adapter tests failed on missing behavior, then passed.
  Corrected test instrumentation to patch read-only vendor methods at class level;
  assertions were preserved and behavioral RED was rerun. Full suite after cleanup:
  120 passed. Real Argon2id uses library salt generation and worker-thread hashing/
  verification; mismatch returns false, malformed hashes/vendor errors become
  sanitized DependencyUnavailable without visible vendor traceback context. Tests:
  `tests/integration/security/test_passwords.py`, including real dummy verification
  through LoginUser. No external database/AWS service required. Ruff/format/whitespace
  passed; no plan/specification deviation.
- TASK-010: Forty-nine JWT adapter tests failed before implementation, then passed.
  Hostile-token fixtures sign raw JSON because the installed PyJWT encoder rejects
  non-string issuers before they reach the decoder; assertions were preserved.
  Full suite after cleanup: 169 passed, none skipped. HS256 allowlist, required
  sub/exp/iat/iss/aud, strict integer dates and UUID subject, exact issuer/audience,
  and zero expiry leeway. Production PyJWT verification is never disabled; tests
  control its clock only inside isolated fixtures. Operational signing/key errors
  are sanitized dependency failures. Tests: `tests/integration/security/test_tokens.py`,
  including real Argon2/JWT cooperation through account use cases with a fake repository.
- Final second-batch validation: 104 new tests; total 169 passing. Ruff lint/format,
  whitespace, and production-import boundary inspection pass. No database, HTTP,
  storage, migration, or later-task implementation added. TASK-011 onward remains
  pending. No changes to requirements, specification, plan, or locked dependencies.
- Review before continuing: safe UserProfile DTO, LoginUser's required precomputed
  dummy hash (generate once with the real hasher in future composition), and JWT
  secret/issuer/audience configuration. Supply a random secret of at least 32 bytes;
  no default production secret exists. Crypto adapters run without external services;
  SQLAlchemy persistence and HTTP contracts remain unimplemented by design.

## Execution evidence — third batch

- TASK-011: Ten initial behavioral tests failed, then passed against disposable
  PostgreSQL 16. Two added connection-outage cases failed and were fixed without
  weakening assertions. Final full suite: 181 passed. Tests use unique schemas and
  never skip missing database setup. ORM mappings stay in infrastructure; mutations
  commit before returning, roll back on failure, and recognize only the named email
  unique constraint as EmailAlreadyRegistered. Session closure rolls back unfinished
  work and releases connections. SQLAlchemy and connection outages are sanitized.
  Tests: `tests/integration/persistence/test_users.py` (12 cases). No plan/spec change.
- TASK-012: Twenty-five settings/HTTP foundation cases failed on unimplemented
  settings/app behavior, then passed. After refactor, service-free suite: 194 passed;
  12 PostgreSQL cases excluded from that command and previously passed in TASK-011.
  Uses httpx ASGI transport with explicit lifespan rather than deprecated TestClient.
  Secret-safe settings, overrideable repository/token dependencies, one startup dummy
  hash, database shutdown, Bearer extraction, and sanitized error mapping verified.
  `.env` is ignored and `.env.example` is available for tracking. Current composition
  wires user/security adapters only; storage wiring remains with later file tasks.
  Ruff/format/whitespace pass; no plan/specification deviation.
- TASK-013: Twenty-nine API tests failed with 404 before routes existed, then passed.
  Service-free suite after cleanup: 223 passed. Strict request schemas reject extra
  fields/coercion; SecretStr prevents password representations from exposing input.
  Thin registration/login routes call the existing use cases and allowlist response
  fields. Status/body/header contracts, invalid input, duplicate normalized email,
  hashing protection, and dependency outages verified with fakes. Tests:
  `tests/api/test_auth.py`. Ruff and whitespace passed; no plan/specification deviation.
- TASK-014: Eleven `/me` tests failed with 404 before route implementation, then
  passed. Service-free suite after cleanup: 234 passed. Two-user isolation,
  missing/malformed/expired/unknown-user tokens, authentication outages, challenge
  headers and a single repository lookup verified. Reuses GetCurrentUser and the
  safe response schema. Tests: `tests/api/test_me.py`; Ruff/format/whitespace pass.
  No plan/specification deviation.
- TASK-015: Forty-two file-domain cases failed on missing behavior, then passed.
  Service-free suite after cleanup: 276 passed. Immutable File validates IDs,
  timezone-aware creation time, filename length/separators/control characters,
  nonnegative integer sizes and the inclusive 10 MiB limit. Defaults absent content
  type and hides storage key/owner from representation. Public file DTOs remain
  with the later application/HTTP tasks. Tests: `tests/unit/domain/test_file.py`.
  Existing user behavior remains unchanged. No plan/specification deviation.
- Final third-batch validation: 119 new tests; full suite 288 passed, none skipped,
  including all 12 real PostgreSQL cases. Ruff lint/format, whitespace, import
  boundaries, and route-scope checks pass. Only registration, login and `/me` routes
  exist; no file ports, file repository/storage adapters, or later use cases added.
  The disposable PostgreSQL container was stopped and removed after validation.
  Requirements, specification, plan, and locked dependencies were not modified.
- Review before continuing: PostgreSQL named email constraint and commit/rollback
  semantics, `.env.example`, explicit TEST_DATABASE_URL instructions in README,
  secret-safe request/error schemas, and file validation rules. Persistence tests
  use temporary ORM schemas until TASK-027 provides migrations. No blocking issue
  remains; TASK-016 onward is pending.

## Execution evidence — fourth batch

- TASK-015: Already complete; verified all 42 file-domain tests again.
- TASK-016: Added owner-scoped FileRepository Protocol, stateful fake, and five
  contract tests. RED: five expected NotImplementedError failures. GREEN/refactor:
  281 service-free tests passed, 12 external PostgreSQL tests deselected.
  Failed writes retain state; tied timestamps sort by UUID; concurrent deletion
  removes one row. No unrestricted lookup, plan deviation, or unresolved issue.

- TASK-017: Added private FileStorage Protocol, stateful fake, and four storage
  contract tests. RED: four expected NotImplementedError failures. GREEN: four
  passed; refactor/regression: 285 service-free tests passed, 12 PostgreSQL tests
  deselected. Fake read access remains test-only; no AWS dependency, plan
  deviation, or unresolved issue.

- TASK-018: Created UploadFile and its 14 behavioral cases; added immutable
  FileMetadata projection. RED: 14 expected NotImplementedError failures. GREEN:
  14 passed; refactor/regression: 299 service-free tests passed, 12 PostgreSQL
  tests deselected; Ruff passed. Constructor-injected ports, UUID-based keys,
  domain validation before I/O, storage-before-metadata, and compensation preserve
  the original dependency error. Cleanup diagnostics contain only the safe file ID.
  Assumption: authenticated UUID is supplied by the composition boundary, as planned.
  No requirement/specification change, plan deviation, or unresolved issue.

- TASK-019: Created ListUserFiles and four behavioral tests covering owner
  isolation, empty results, timestamp/UUID ordering, safe projection, and outages.
  RED: four expected NotImplementedError failures. GREEN: four passed.
  Refactor moved the shared file fixture into test support; 303 service-free tests
  passed, 12 PostgreSQL tests deselected, and nine affected tests passed again
  after removing an unused import. Ruff passed. Only the authenticated UUID from
  composition is accepted; there is no separate client-selected owner input.
  No plan deviation or unresolved issue.

- TASK-020: Created GetUserFile and four behavioral tests; added FileNotFound.
  RED: four expected failures from unimplemented retrieval. GREEN: four passed.
  Refactor tightened exception assertions and reused FileMetadata; final regression:
  307 service-free tests passed, 12 external PostgreSQL tests deselected (not rerun
  in this application-only batch). No failing tests were skipped.
  Ruff lint/format and whitespace checks passed. Manual AST inspection verified
  inward dependencies and absence of vendor/framework imports in inner layers.
  Retrieval has no storage dependency; missing and foreign files share one error.
  No plan deviation or unresolved issue. TASK-021 and later were not implemented.

## Execution evidence — fifth batch

- TASK-021: Created DeleteUserFile and six behavioral tests. RED: six expected
  failures from unimplemented deletion. GREEN: six passed; refactor/regression:
  313 service-free tests passed, 12 PostgreSQL tests deselected; Ruff passed.
  Owned lookup precedes storage deletion, which precedes committed metadata removal.
  Failed persistence permits retry with absent content; concurrent deletion cannot
  report success for an absent row or touch unrelated storage. No plan deviation
  or unresolved issue.

- TASK-022: Added FileModel and SqlAlchemyFileRepository with ten new PostgreSQL
  cases. RED reached the disposable database: unimplemented repository and missing
  file table failed. GREEN: all 22 persistence tests passed; refactor/full regression:
  335 tests passed, none skipped. The model enforces FK, unique key, size bounds,
  non-null fields, and an owner/time/ID index. SQL predicates enforce ownership;
  mutations commit explicitly and roll back on failures. Ruff/format/whitespace
  checks passed. Disposable PostgreSQL 16 used; no migrations (TASK-027) created.
  No plan deviation or unresolved issue.

- TASK-023: Added worker-thread boto3 storage adapter, bounded client factory,
  eleven SDK interaction/failure cases, and one local S3 lifecycle test.
  RED: eleven SDK tests and the local roundtrip failed on missing behavior.
  GREEN/refactor/full regression: 347 tests passed, none skipped.
  Network attempts use 3-second connect/5-second read timeouts and three total
  attempts. SDK failures become sanitized dependency errors; no public ACL is sent.
  MinIO registries denied image access; installed locked Moto 5.2.3 as a dev-only
  local S3 service instead, consistent with the planned S3-compatible test service.
  Verified exact bytes/content type, anonymous 403, and repeated deletion over HTTP.
  Updated README service instructions; no production AWS calls or plan deviation.

- TASK-024: Added POST /files, allowlisted metadata schema, boundary parser/resource
  controls, use-case dependencies, centralized file validation/size errors, and
  shared S3 client lifespan cleanup. Added 26 upload API cases and one startup
  failure cleanup case; extended the existing lifecycle assertion for S3 closure.
  RED: original 21 API cases failed on the route scaffold. GREEN: 21 passed;
  added resource/auth/lifecycle verification and refactored boundary helpers.
  Full regression: 374 passed, none skipped; affected API checks: 52 passed.
  Ruff passed. Measured 64-KiB writes, 1-MiB spool threshold, and <=10-MiB disk
  payload on rejection; authenticated multipart parsing, zero/limit chunked input,
  incomplete parts, owner spoofing, and handle cleanup verified. README records
  header/boundary/envelope limits and per-request memory assumptions.
  Requirements/spec unchanged; resource mechanics resolve the plan's open detail.
  No plan deviation or unresolved issue.

- TASK-025: Added GET /files and GET /files/{file_id}, two repository-only
  use-case dependencies, and centralized FileNotFound-to-404 mapping.
  Added sixteen API cases. RED: fourteen expected failures, two existing generic
  unexpected-error checks passed. GREEN: sixteen passed; refactor/service-free
  regression: 367 passed, 23 external-service tests deselected. Final full suite
  with PostgreSQL and local S3: 390 passed, none skipped. Ruff lint/format,
  whitespace checks, and manual import-boundary inspection passed.
  Read responses share the allowlisted schema; owner selectors cannot override
  authentication, missing/foreign errors match, malformed UUID plus no auth is
  401, and metadata retrieval/listing invoke no storage operations.
  No plan deviation, requirement/spec change, or unresolved issue.
  Stopped at TASK-025: no DELETE HTTP route, migrations, Compose, or future task work.

## Execution evidence — sixth batch

- TASK-026: Added DELETE /files/{file_id}, constructor-injected use-case wiring,
  and eleven API cases. RED: ten missing-route-behavior failures, one generic
  unexpected-error case passed. GREEN: eleven passed; refactor/regression:
  378 service-free tests passed, 23 external-service tests deselected. Ruff passed.
  Central error mapping reused; auth precedes UUID validation, foreign/missing
  files never touch storage, successful deletion leaves neither resource, and
  partial failure is retryable. No plan deviation or unresolved issue.

- TASK-027: Added Alembic environment/configuration, initial users/files revision,
  revision template, four migration checks, and migrated-schema repository fixtures.
  RED: three missing-schema/parity assertions failed; template syntax test exposed
  and verified correction of an escaping defect. GREEN/refactor: 26 migration and
  repository cases passed on disposable PostgreSQL; 378 service-free cases passed.
  Offline upgrade SQL verified. Constraints, index, downgrade/re-upgrade, metadata
  parity, and revision generation all pass. README documents explicit environment-
  configured migration commands; API startup does not migrate. Ruff/whitespace
  checks passed. No plan deviation or unresolved issue.

- TASK-028: Added multi-stage non-root Dockerfile, Compose PostgreSQL/Moto/API
  stack, local private bucket initializer, context exclusions, optional host ports,
  and README setup/migration/test commands. RED: missing Compose config rejected.
  GREEN: config/build/start/migrate smoke passed in isolated architecture-sdd-smoke
  project; database/S3/API healthy, initialization services exited zero.
  Verified public-access block flags, anonymous object 403, Bearer challenge,
  non-root API user, and absence of .env/.aws/Git/test files from runtime image.
  Refactor/checks: lint/format/whitespace passed; full service-backed suite:
  405 passed, none skipped. Compose credentials are dummy local values; no remote
  AWS calls. Moto is the planned local S3-compatible emulator. No plan deviation
  or unresolved issue.

- TASK-029: Added six cross-adapter lifecycle/failure cases and shared isolated
  migrated-schema/S3/application fixtures. Removed the old directory-local
  persistence fixture and extracted migration support for reuse.
  Existing production behavior passed all six tests on the first tests-first run.
  RED negative control: process-local disabled storage cleanup caused the expected
  orphan assertion failure; no production file was changed. GREEN/refactor:
  unmodified real adapters plus shared fixtures passed the full 411-test suite,
  none skipped. Argon2/JWT/PostgreSQL/boto3 cooperate, concurrent normalized-email
  registration has one winner, foreign access leaves both resources untouched,
  compensation/orphan diagnostics match spec, and deletion retry succeeds after
  a real rolled-back commit failure. README records fixture isolation and commands.
  No adapter gap, production behavior change, plan deviation, or unresolved issue.


## TASK-030 acceptance evidence

Each AC has the following executable HTTP and supporting adapter/use-case evidence.
The JWT matrix covers all five protected routes with real verification, valid tokens
at issue/one second before expiry, rejection at the expiry instant, signature/payload
tampering, unsupported algorithms, missing/invalid claims, unknown users, and no
file repository/storage calls on rejection. These are acceptance checks; the
separate architecture/security reviews in TASK-031/TASK-032 remain pending.

| AC | Executable test references |
| --- | --- |
| AC01 | `tests/api/test_auth.py::test_registration_returns_normalized_safe_profile_and_hashed_password`<br>`tests/integration/test_lifecycle.py::test_real_adapters_lifecycle_and_second_user_denial` |
| AC02 | `tests/api/test_auth.py::test_invalid_registration_returns_safe_422_without_persistence`<br>`tests/api/test_acceptance.py::test_non_object_json_is_422_and_does_not_echo_input`<br>`tests/api/test_acceptance.py::test_email_length_boundary_at_http_boundary` |
| AC03 | `tests/api/test_auth.py::test_duplicate_normalized_email_returns_409`<br>`tests/integration/test_lifecycle.py::test_real_database_duplicate_registration_race` |
| AC04 | `tests/api/test_auth.py::test_login_issues_bearer_token_for_normalized_credentials`<br>`tests/integration/security/test_tokens.py::test_issued_token_has_only_required_claims_and_verifiable_subject` |
| AC05 | `tests/api/test_auth.py::test_invalid_credentials_return_identical_401_with_challenge`<br>`tests/api/test_auth.py::test_invalid_login_input_is_422_and_sanitized` |
| AC06 | `tests/api/test_acceptance.py::test_all_token_variants_on_every_protected_route`<br>`tests/api/test_acceptance.py::test_real_valid_jwt_is_accepted_on_each_route` |
| AC07 | `tests/api/test_me.py::test_me_returns_only_authenticated_profile`<br>`tests/integration/test_lifecycle.py::test_real_adapters_lifecycle_and_second_user_denial` |
| AC08 | `tests/api/test_upload.py::test_size_boundaries_safe_owned_metadata_and_closed_handles`<br>`tests/integration/storage/test_s3.py::test_private_byte_roundtrip_content_type_and_idempotent_delete`<br>`tests/integration/test_lifecycle.py::test_real_adapters_lifecycle_and_second_user_denial` |
| AC09 | `tests/api/test_upload.py::test_invalid_filename_has_no_side_effects`<br>`tests/api/test_upload.py::test_oversized_file_rejected_during_parsing`<br>`tests/api/test_upload.py::test_chunked_valid_upload_without_content_length` |
| AC10 | `tests/api/test_upload.py::test_dependency_failures_are_sanitized_and_close_handles`<br>`tests/integration/test_lifecycle.py::test_upload_persistence_failure_compensates_or_records_orphan`<br>`tests/integration/test_lifecycle.py::test_real_storage_failure_creates_no_metadata` |
| AC11 | `tests/api/test_file_reads.py::test_two_user_listing_isolation_order_and_empty`<br>`tests/integration/persistence/test_files.py::test_committed_roundtrip_owner_filters_and_order` |
| AC12 | `tests/api/test_file_reads.py::test_owned_metadata_allowlist_no_private_fields_or_storage_access`<br>`tests/api/test_file_reads.py::test_foreign_and_missing_responses_are_identical`<br>`tests/api/test_file_reads.py::test_malformed_uuid_validated_only_after_authentication` |
| AC13 | `tests/api/test_file_delete.py::test_empty_204_and_repeat_404`<br>`tests/integration/test_lifecycle.py::test_real_adapters_lifecycle_and_second_user_denial` |
| AC14 | `tests/api/test_file_delete.py::test_foreign_missing_identical_without_storage_calls`<br>`tests/unit/application/test_delete_file.py::test_foreign_and_missing_do_not_touch_storage` |
| AC15 | `tests/api/test_file_delete.py::test_failure_preserves_metadata_and_retry_succeeds`<br>`tests/integration/test_lifecycle.py::test_real_deletion_retry_after_metadata_commit_failure` |
| AC16 | `tests/api/test_acceptance.py::test_authentication_outage_precedes_file_operations`<br>`tests/api/test_auth.py::test_registration_outages_are_sanitized_503`<br>`tests/api/test_auth.py::test_login_outages_are_sanitized_503`<br>`tests/api/test_file_reads.py::test_read_outages_are_sanitized` |
| AC17 | `tests/api/test_acceptance.py::test_all_token_variants_on_every_protected_route`<br>`tests/api/test_auth.py::test_invalid_registration_returns_safe_422_without_persistence`<br>`tests/api/test_file_reads.py::test_owned_metadata_allowlist_no_private_fields_or_storage_access`<br>`tests/integration/test_lifecycle.py::test_upload_persistence_failure_compensates_or_records_orphan` |


- TASK-030: Added 215 HTTP acceptance cases in test_acceptance.py and verified
  AC01–AC17 references above against real test functions. Expanded real JWT
  variants across every protected route, exact expiry and pre-expiry behavior,
  strict/non-object JSON, field boundaries, and auth dependency outage precedence.
  Invalid issuer test vectors use low-level JWS signing because the high-level
  encoder rejects their types; all HTTP assertions retained.
  RED negative control: process-local token verification bypass produced the
  expected expired-token HTTP 200-versus-401 failure; production source unchanged.
  GREEN/refactor: all 215 acceptance cases passed; final full suite: 626 passed,
  none skipped, with local PostgreSQL/S3. Lint/format/whitespace and manual per-task
  dependency checks passed. No production contract gap required a behavior change.
  No specification/requirements change, plan deviation, or unresolved blocker.
  TASK-031 and TASK-032 remain pending; this batch stops after TASK-030.

## Execution evidence — final batch

- TASK-031: Added test-only AST import checker and 42 boundary cases. RED:
  all 42 failed on unimplemented checking. GREEN/refactor: 42 passed; service-free
  regression: 635 passed, 33 external-service cases deselected; Ruff passed.
  The checker resolves package-relative imports, aliases, and from-package imports,
  catches inward-layer vendor/outward imports even in conditional code, permits
  composition, and rejects a temporary illegal fixture. All production imports pass.
  Manual review confirmed constructor-injected ports, ORM-only infrastructure,
  owner-derived thin routes, narrow adapters, and no unnecessary abstractions.
  No boundary fix, plan deviation, or unresolved issue.

- TASK-032: Added 10 adversarial/security cases covering client-supplied owners,
  private storage locators, foreign UUID filenames, missing-file spoofing, secret
  JSON field names, and the ASGI exception/logging boundary. Existing JWT attack,
  anonymous-object denial, chunked/oversized upload, compensation, and ownership
  suites cover the remaining review items without duplicate tests.
  RED: two validation tests exposed passwords in unknown-field error locations;
  a strict ASGI test exposed raw unexpected exception propagation to server logs.
  GREEN/refactor: omit unknown field names from sanitized error locations and
  contain unhandled HTTP exceptions in presentation middleware; preserve typed
  handlers, generic 500 responses, safe failures after headers, and visible startup
  failures. All 10 new security cases pass. During verification an assertion was
  accidentally placed in the startup test (NameError); placement was corrected
  without weakening it, and both focused and full suites were rerun successfully.
  Final full suite: 678 passed, none skipped, using disposable PostgreSQL and Moto.
  Ruff lint/format and whitespace checks pass. All 43 executable references for
  AC01–AC17 were reviewed and resolved; production import boundaries pass.
  Inspected tracked/stageable files: no real credentials or private-key material;
  configuration examples and local/test secrets are dummy values.
  README now covers secret setup, API behavior, partial states, manual orphan
  cleanup, and deployment limitations. No requirements/specification/plan change
  or architectural deviation: redaction stays at the presentation boundary.
  Production AWS IAM/private-bucket configuration, secret delivery, concurrency
  limits, and operator orphan cleanup remain deployment responsibilities; local
  emulation does not prove live AWS policy. No implementation blocker remains.
  Stopped after TASK-032; all ordered implementation tasks are complete.
