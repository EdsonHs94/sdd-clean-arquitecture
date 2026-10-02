# User Architecture Model

This repository is a learning project focused on production-oriented Python backend architecture.

## Engineering goals

Prioritize:

- maintainability
- testability
- low coupling
- clear responsibility boundaries
- explicit dependencies
- simple solutions over unnecessary abstraction

## Architecture

Use a pragmatic Clean / Hexagonal Architecture.

Primary layers:

- domain
- application
- infrastructure
- presentation

Dependencies point inward.

Domain and application layers must not depend directly on:

- FastAPI
- SQLAlchemy
- PostgreSQL
- boto3
- AWS
- PyJWT

Infrastructure implements ports defined by inner layers.

## Design principles

Apply SOLID when it improves the design.

Especially favor:

- Single Responsibility
- Dependency Inversion
- Interface Segregation

Avoid abstractions without a concrete reason.

## Dependency injection

Use constructor injection inside application code.

Use FastAPI `Depends` mainly at the presentation/composition boundary.

## Ports

Use Python `Protocol` or ABC when application logic depends on external capabilities.

Expected examples include:

- UserRepository
- FileRepository
- FileStorage
- PasswordHasher
- TokenService

## Use cases

Represent business operations as explicit use cases.

Avoid large generic service classes.

## Testing

Use TDD for business behavior:

1. RED: write a failing test.
2. GREEN: implement the minimum required behavior.
3. REFACTOR: improve the implementation without changing behavior.

Use:

- fakes for repositories and stateful dependencies where useful
- mocks for interaction-oriented external systems
- integration tests for infrastructure
- API tests for HTTP behavior

## Documentation

Treat `docs/` as the project source of truth.

Relevant documentation:

- `docs/requirements.md`: initial business requirements
- `docs/spec.md`: behavioral specification
- `docs/plan.md`: technical implementation plan
- `docs/tasks.md`: ordered implementation work

Do not silently diverge from these documents.

If implementation requires changing an agreed requirement, update the relevant documentation first.

## Workflow

For significant work:

requirement → specification → plan → tasks → tests → implementation → review

Read only the documentation relevant to the current task.

## Validation

After implementation:

- run relevant tests
- verify acceptance criteria
- verify dependency boundaries
- report any deviation from the specification
