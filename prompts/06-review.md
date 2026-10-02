# Final Architecture Review

Read:

- `AGENTS.md`
- `docs/requirements.md`
- `docs/spec.md`
- `docs/plan.md`
- `docs/tasks.md`
- the complete implementation

Do not modify code initially.

Perform a complete review.

## Specification compliance

Verify every acceptance criterion from `docs/spec.md`.

Identify:

- implemented requirements
- missing requirements
- behavior that differs from specification

## Architecture

Verify:

- correct dependency direction
- domain independence
- application independence from infrastructure
- ports and adapters separation
- FastAPI only at the presentation boundary where practical

## SOLID

Evaluate practical application of:

- SRP
- OCP
- LSP
- ISP
- DIP

Do not recommend abstraction merely for theoretical purity.

## Testability

Verify that:

- use cases can run without PostgreSQL
- use cases can run without S3
- use cases can run without FastAPI
- PyJWT can be replaced in tests
- persistence can be replaced with fakes
- external integrations can be mocked

## TDD quality

Review whether tests focus on observable behavior instead of implementation details.

Identify excessive mocking.

Identify missing failure cases.

## Security

Review:

- password handling
- JWT validation
- token expiration
- user isolation
- cross-user resource access
- S3 object ownership
- sensitive configuration handling

## Infrastructure

Review:

- SQLAlchemy session boundaries
- transaction handling
- repository implementations
- Alembic migrations
- S3 adapter behavior

## Maintainability

Look for:

- duplicated logic
- large classes
- hidden coupling
- framework leakage
- unnecessary abstractions
- unclear names

## Overengineering

Explicitly identify abstractions that provide no meaningful value.

## Output

Produce findings grouped by:

- specification
- architecture
- SOLID
- testability
- TDD
- security
- infrastructure
- maintainability
- overengineering

For each finding include:

- severity
- affected files
- explanation
- recommended correction

Do not apply the changes unless explicitly requested.
