# Implement One Task Using TDD

Implement task:

`<TASK_ID>`

from:

`docs/tasks.md`

## Context

Read:

- `AGENTS.md`
- the relevant sections of `docs/spec.md`
- the relevant sections of `docs/plan.md`
- task `<TASK_ID>` in `docs/tasks.md`

Inspect the existing code related to this task.

Do not implement future tasks.

## TDD workflow

Follow RED → GREEN → REFACTOR.

### RED

Create the tests required by this task before implementing the behavior.

Run the relevant tests.

Verify they fail for the expected reason.

Do not weaken assertions simply to make tests pass.

### GREEN

Implement the minimum production code necessary to satisfy the tests.

Respect the architecture described in `docs/plan.md`.

Run the relevant tests again.

### REFACTOR

Once the tests pass:

- improve naming if necessary
- remove duplication
- simplify implementation
- preserve dependency boundaries

Run tests again after refactoring.

## Architecture constraints

Verify that:

- domain does not depend on infrastructure
- application does not import FastAPI, SQLAlchemy, boto3 or PyJWT
- use cases depend on ports/interfaces
- infrastructure implements those ports
- FastAPI remains at the presentation boundary

## Documentation

If implementation exposes a genuine flaw or missing requirement in the current specification:

do not silently change behavior.

Report the conflict and update documentation only when appropriate.

## Completion

When finished report:

- task implemented
- tests created
- test results
- files changed
- architecture decisions
- deviations from plan
- unresolved concerns
