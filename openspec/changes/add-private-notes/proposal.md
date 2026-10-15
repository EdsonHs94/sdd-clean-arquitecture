# Proposal

## Why

Los usuarios necesitan guardar apuntes privados de texto junto a las capacidades existentes de cuentas y archivos. Este recurso permite practicar un ciclo SDD completo y una implementación con dos sesiones Codex coordinadas por Herdr, con contratos explícitos, TDD y revisión independiente.

## What Changes

- Incorporar notas privadas: crear, listar, consultar, editar parcialmente y eliminar mediante `/notes` y `/notes/{note_id}`.
- Validar título de 1–200 caracteres después de quitar espacios exteriores y contenido de hasta 10 000 caracteres, incluido contenido vacío; permitir títulos repetidos.
- Exponer UUID, título, contenido y fechas UTC; obtener el propietario exclusivamente de la autenticación existente.
- Conservar cambios concurrentes sobre campos distintos y aplicar la última escritura sobre cada campo enviado, sin versiones ni ETags.
- Añadir persistencia PostgreSQL, migración Alembic y pruebas de comportamiento, aislamiento y concurrencia.
- Planificar contratos previos al paralelo, dos workers con worktrees independientes y un reviewer independiente. Esta propuesta no inicia esas sesiones.
- Fuera de alcance: paginación, búsqueda, etiquetas, relaciones con archivos, colaboración, Markdown/HTML renderizado, historial y nuevos servicios externos.

## Capabilities

### New Capabilities

- `private-notes`: gestión REST de notas privadas por usuario, validación, aislamiento, actualización parcial y persistencia confirmada.

### Modified Capabilities

Ninguna. No existen capacidades registradas en `openspec/specs/`; los contratos actuales de usuarios, autenticación y archivos descritos en `docs/` se preservan.

## Impact

- Nuevos componentes en dominio, aplicación, infraestructura y presentación; integración en `app/bootstrap.py`.
- Nueva tabla `notes` relacionada con `users`, índice para listado por propietario y una nueva revisión Alembic; adaptación de pruebas que enumeran tablas.
- Reutilización de autenticación, errores sanitizados, inyección por constructor y límites arquitectónicos existentes. No requiere modificar S3 ni añadir dependencias de producto.
- Los artefactos de este cambio son la referencia para el feature; no se reescriben las tareas históricas de `docs/tasks.md`.
- La ejecución futura usará la skill oficial de Herdr, sesiones Codex visibles y nombradas, worktrees por worker de escritura y TDD con Superpowers.
