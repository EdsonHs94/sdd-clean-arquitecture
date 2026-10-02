# Create Implementation Tasks

Read:

- `AGENTS.md`
- `docs/spec.md`
- `docs/plan.md`

Create:

`docs/tasks.md`

Do not implement application code.

Break the plan into small, independently verifiable tasks.

## Suggested sequence

1. Python project configuration
2. domain user entity
3. user repository port
4. password hasher port
5. token service port
6. register user use case
7. login user use case
8. SQLAlchemy user persistence
9. authentication API
10. `/me`
11. file domain entity
12. file repository port
13. file storage port
14. upload file use case
15. list files use case
16. retrieve file use case
17. delete file use case
18. SQLAlchemy file persistence
19. S3 adapter
20. file API endpoints
21. Alembic migrations
22. infrastructure integration tests
23. API tests
24. architecture review
25. security review

## Every task must contain

- task ID
- objective
- relevant acceptance criteria
- expected files or modules
- dependencies on previous tasks
- tests to write first
- expected result
- completion criteria

For implementation tasks include:

### RED

Which failing tests must be created first.

### GREEN

Minimum implementation required to satisfy the tests.

### REFACTOR

Potential cleanup after tests pass.

Keep tasks small.

Do not implement any task.
