from pathlib import Path

import pytest

from tests.architecture.checker import import_violations


@pytest.mark.parametrize(
    "vendor",
    [
        "fastapi",
        "fastapi.routing",
        "pydantic",
        "sqlalchemy",
        "asyncpg",
        "psycopg",
        "psycopg2",
        "boto3",
        "botocore",
        "jwt",
        "argon2",
    ],
)
@pytest.mark.parametrize("layer", ["domain", "application"])
def test_inner_layers_reject_vendor_imports(vendor, layer):
    assert import_violations(f"import {vendor}", f"app.{layer}.example")


@pytest.mark.parametrize(
    ("module", "source"),
    [
        ("app.domain.entities", "from app.application import ports"),
        ("app.application.ports", "from app.infrastructure.storage import s3"),
        ("app.application.ports", "from ..infrastructure import settings"),
        ("app.domain.entities", "from .. import application"),
        ("app.domain.entities", "from app import bootstrap"),
        ("app.infrastructure.storage.s3", "from ...presentation import schemas"),
        ("app.presentation.routers.files", "from ...infrastructure import settings"),
        ("app.application", "from .. import infrastructure"),
        ("app.application.ports", "from sqlalchemy.orm import Session as Hidden"),
        ("app.domain.entities", "if False:\n    import boto3"),
    ],
)
def test_absolute_relative_and_aliased_outward_imports_are_rejected(module, source):
    assert import_violations(source, module, is_package=module == "app.application")


@pytest.mark.parametrize(
    ("module", "source", "is_package"),
    [
        ("app.domain.entities", "from .errors import InvalidFileData", False),
        ("app.domain.validation", "from email_validator import validate_email", False),
        ("app.application.ports", "from ..domain.entities import File", False),
        ("app.infrastructure.persistence.models", "from sqlalchemy.orm import Mapped", False),
        (
            "app.presentation.routers.files",
            "from ...application.ports import FileRepository",
            False,
        ),
        ("app.bootstrap", "from app.infrastructure.storage.s3 import S3FileStorage", False),
        ("app.bootstrap", "from app.presentation.routers import files", False),
        ("app.application", "from . import ports", True),
    ],
)
def test_inward_imports_and_composition_are_allowed(module, source, is_package):
    assert import_violations(source, module, is_package=is_package) == []


def test_checker_detects_temporary_fixture_violation(tmp_path):
    path = tmp_path / "entities.py"
    path.write_text("from ..infrastructure.storage.s3 import S3FileStorage\n")
    violations = import_violations(path.read_text(), "app.domain.entities")
    assert violations
    assert any("infrastructure" in violation for violation in violations)


def test_all_production_modules_respect_boundaries():
    root = Path(__file__).resolve().parents[2]
    failures = []
    for path in sorted((root / "app").rglob("*.py")):
        parts = path.relative_to(root).with_suffix("").parts
        is_package = parts[-1] == "__init__"
        module = ".".join(parts[:-1] if is_package else parts)
        failures.extend(
            f"{path.relative_to(root)}: {violation}"
            for violation in import_violations(path.read_text(), module, is_package=is_package)
        )
    assert failures == []
