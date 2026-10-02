# Create Technical Plan

Read:

- `AGENTS.md`
- `docs/requirements.md`
- `docs/spec.md`

Do not implement code.

Create:

`docs/plan.md`

Design a pragmatic production-oriented architecture for the specification.

## Architecture

Use Clean / Hexagonal Architecture concepts.

Define responsibilities for:

- domain
- application
- infrastructure
- presentation

Explain dependency direction.

## Domain

Identify required:

- entities
- domain exceptions
- value objects only where they provide clear value

Avoid unnecessary abstractions.

## Application

Identify use cases.

At minimum evaluate:

- RegisterUser
- LoginUser
- GetCurrentUser
- UploadFile
- ListUserFiles
- GetUserFile
- DeleteUserFile

## Ports

Identify abstractions required by application logic.

Evaluate:

- UserRepository
- FileRepository
- FileStorage
- PasswordHasher
- TokenService

Application use cases must depend on abstractions instead of infrastructure implementations.

## Infrastructure

Plan adapters for:

- SQLAlchemy
- PostgreSQL
- S3 with boto3
- password hashing
- JWT with PyJWT

## Presentation

Plan:

- FastAPI routers
- request schemas
- response schemas
- authentication dependencies
- application exception to HTTP error mapping

Business logic must not live inside route handlers.

## Persistence

Plan the required persistence models and relationships.

Expected concepts:

User:
- id
- email
- name
- password_hash
- created_at

File:
- id
- user_id
- original_name
- storage_key
- content_type
- size
- created_at

## Testing strategy

Define:

- domain tests
- use-case unit tests
- fake repositories
- mocks
- infrastructure integration tests
- API tests

Explain which dependencies should use mocks and which are better represented as fakes.

## TDD

Explain how each use case will be developed using:

RED
GREEN
REFACTOR

## Project structure

Propose the expected directory layout.

## Decisions

Document:

- architectural decisions
- trade-offs
- rejected alternatives
- security considerations
- unresolved questions

Do not implement code.
