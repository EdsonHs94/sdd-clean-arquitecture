# Bootstrap Project

Initialize this directory as the repository for the project:

`user-architecture-model`

Do not implement business functionality.

## Goals

Prepare the repository for a Spec-Driven Development workflow.

## Tasks

1. Initialize Git if this directory is not already a Git repository.

```bash
git init
```

2. Create a Python `.gitignore`.

It must ignore at least:

- `.venv/`
- `venv/`
- `__pycache__/`
- `*.pyc`
- `.pytest_cache/`
- `.coverage`
- `htmlcov/`
- `.mypy_cache/`
- `.ruff_cache/`
- `.env`
- `.env.*`
- IDE files
- OS temporary files

Do not ignore:

`.env.example`

3. Verify these directories exist:

```text
docs/
prompts/
app/
tests/
```

4. Preserve the existing:

```text
AGENTS.md
prompts/
```

5. Create a minimal `README.md`.

It should describe this project as an exercise in:

- Python
- FastAPI
- Clean / Hexagonal Architecture
- SOLID
- TDD
- Spec-Driven Development

6. Create empty documentation placeholders if they do not already exist:

```text
docs/requirements.md
docs/spec.md
docs/plan.md
docs/tasks.md
```

7. Inspect:

```bash
git status
```

Verify that no secret or generated file is being tracked.

8. Create the initial commit:

```text
chore: initialize user architecture model project
```

Do not configure a Git remote.

Do not implement application code.

## Completion criteria

Report:

- files created
- directories created
- git repository status
- commit created
- anything requiring manual configuration
