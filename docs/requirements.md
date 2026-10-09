# Requirements: user-architecture-model

## Project objective

Build a small backend API for users and their files that demonstrates
production-oriented Python development with FastAPI. Users register, authenticate,
inspect their profile, and manage their own files.

## Actors

- Visitor: registers an account or logs in with existing credentials.
- Authenticated user: retrieves their own profile and manages their own files.

## Business capabilities

- Account registration and credential verification.
- JWT access-token issuance and Bearer authentication.
- Private profile retrieval through `/me`.
- File upload, listing, metadata retrieval, and deletion with ownership isolation.

## Functional requirements

- R01: Register a user using name, email, and password.
- R02: Identify accounts uniquely by email and reject duplicate registration.
- R03: Login using email and password; successful login returns a JWT access token.
- R04: Authenticate protected operations using a valid Bearer access token.
- R05: Return the authenticated user's own profile through `/me`, without password data.
- R06: Accept an authenticated user's file upload and physically store it in AWS S3.
- R07: Persist file metadata in PostgreSQL, including ownership and enough information
  to identify the stored object and describe the uploaded file.
- R08: List only files owned by the authenticated user.
- R09: Retrieve metadata for a single file owned by the authenticated user.
- R10: Delete an owned file, removing its stored content and metadata on success.
- R11: Prevent every user from accessing or deleting another user's files.
- R12: Report unsuccessful operations without falsely reporting successful persistence
  or deletion when a required external operation fails.

## High-level security requirements

- Never store passwords in plain text or return passwords or password hashes.
- Reject invalid credentials and invalid, expired, or missing access tokens.
- Enforce authentication and file ownership on all file operations.
- Do not disclose another user's file existence through ownership failure responses.
- Keep credentials, signing secrets, and AWS secrets out of source control and API responses.
- Keep file contents private; uploading must not grant public access.

## Constraints

- Python 3.12+, FastAPI, Pydantic v2.
- PostgreSQL, SQLAlchemy 2.x async, and Alembic for persistence and migrations.
- JWT access tokens with an eventual PyJWT implementation.
- AWS S3 with boto3 for physical file storage.
- pytest, pytest-asyncio, and httpx for testing; Docker and Docker Compose for local setup.
- Follow `AGENTS.md` engineering and workflow guidance; detailed design belongs to later stages.

## Assumptions

- Email is the login identifier and is compared without case sensitivity.
- Registration does not automatically authenticate the new user; login issues the token.
- Each uploaded file belongs to exactly one user; sharing is not supported.
- File listing can initially return all of a user's files; pagination is deferred.
- Concrete validation limits, HTTP contracts, and failure behavior are set in the specification.
- An operator supplies an S3 bucket, database access, and runtime secrets.

## Out of scope

- Refresh tokens, logout/revocation, password reset, email verification, and MFA.
- Editing/deleting accounts, administration, roles, and user discovery.
- File download, public links, sharing, folders, versioning, and metadata editing.
- Malware scanning, billing, quotas, production deployment, and automatic orphan reconciliation.
