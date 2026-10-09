"""Test-only AST import policy; no runtime imports or vendor packages are loaded."""

import ast
from importlib.util import resolve_name

ALLOWED = {
    "domain": {"domain"},
    "application": {"domain", "application"},
    "infrastructure": {"domain", "application", "infrastructure"},
    "presentation": {"domain", "application", "presentation"},
}
INNER_FORBIDDEN = {
    "fastapi",
    "starlette",
    "pydantic",
    "pydantic_settings",
    "sqlalchemy",
    "asyncpg",
    "psycopg",
    "psycopg2",
    "boto3",
    "botocore",
    "jwt",
    "argon2",
}


def import_violations(source: str, module: str, *, is_package: bool = False) -> list[str]:
    layer = module.split(".")[1] if "." in module else ""
    package = module if is_package else module.rpartition(".")[0]
    violations = []
    for node in ast.walk(ast.parse(source)):
        imports = []
        if isinstance(node, ast.Import):
            imports = [alias.name for alias in node.names]
        elif isinstance(node, ast.ImportFrom):
            base = node.module or ""
            if node.level:
                try:
                    base = resolve_name("." * node.level + base, package)
                except ImportError:
                    violations.append(f"line {node.lineno}: invalid relative import")
                    continue
            imports = [base] + [f"{base}.{alias.name}" for alias in node.names]
        for imported in imports:
            parts = imported.split(".")
            forbidden_vendor = layer in {"domain", "application"} and parts[0] in INNER_FORBIDDEN
            outward = (
                layer in ALLOWED
                and parts[0] == "app"
                and len(parts) > 1
                and parts[1] not in ALLOWED[layer]
            )
            if forbidden_vendor or outward:
                violations.append(f"line {node.lineno}: {layer} cannot import {imported}")
    return violations
