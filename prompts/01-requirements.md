# Define Requirements

Read `AGENTS.md`.

Do not design the architecture yet.

Create:

`docs/requirements.md`

for the `user-architecture-model` project.

## Product goal

Build a small backend API that demonstrates production-oriented Python architecture using FastAPI.

The application manages users and files.

## Required features

Users must be able to:

- register using name, email and password
- login using email and password
- receive a JWT access token
- authenticate using Bearer authentication
- retrieve their own profile through `/me`
- upload files
- list their own files
- retrieve metadata for one of their files
- delete one of their files

Files are physically stored in AWS S3.

File metadata is stored in PostgreSQL.

Users must never access files owned by another user.

## Authentication

Use JWT access tokens.

The infrastructure implementation will eventually use PyJWT.

Passwords must never be stored in plain text.

## Technical context

The target stack is:

- Python 3.12+
- FastAPI
- PostgreSQL
- SQLAlchemy 2.x async
- Alembic
- Pydantic v2
- PyJWT
- boto3
- pytest
- pytest-asyncio
- httpx
- Docker
- Docker Compose

## Important

This document should describe WHAT the system needs to accomplish.

Do not define:

- directory structures
- classes
- repository implementations
- architecture details
- SQLAlchemy models
- FastAPI implementation details

Those decisions belong to later SDD stages.

## Output

`docs/requirements.md` must contain:

- project objective
- actors
- business capabilities
- functional requirements
- high-level security requirements
- constraints
- assumptions
- out-of-scope behavior

Do not implement code.
