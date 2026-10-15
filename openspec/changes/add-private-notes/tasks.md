# Tasks

Estos checkboxes describen trabajo futuro; crear el plan no inicia apply. La referencia de aceptación es `specs/private-notes/spec.md` y los contratos/propiedad de archivos están en `design.md`. Solo el Lead actualiza este checklist después de revisar evidencia.

Todo desarrollador, incluido el Lead cuando escribe comportamiento, usa Superpowers TDD: registrar RED por el comportamiento esperado, implementar GREEN y verificar tras REFACTOR. Para configuración/contratos sin comportamiento basta verificación directa, sin pruebas artificiales. No modificar las tareas SDD históricas.

Dependencias y paralelismo:

```text
1.1 --> 1.2 --> 1.3 --> 1.4 --> 1.5
                                  |
                                  v
                           2.1 --> 2.2
                                  |
                   +--------------+--------------+
                   v                             v
              3.1 --> 3.2                   4.1 --> 4.2
                        |                             |
                        v                             v
                       3.3                           4.3
                        |                             |
                        v                             v
                       3.4                           4.4
                        +--------------+--------------+
                                       v
                                5.1 --> 5.2 --> 5.3
                                                 |
                                                 v
                                          6.1 --> 6.2
```

## 1. Lead: base contractual secuencial

- [x] 1.1 Antes de implementar, confirmar revisión de estos artefactos y petición explícita de apply; registrar estado Git y baseline de pruebas/lint con `uv run --locked pytest -m 'not integration'`, `uv run --locked ruff check .` y `uv run --locked ruff format --check .`. Verificación: resultados registrados y cambios preexistentes identificados, sin atribuir pruebas no ejecutadas a la baseline.
- [x] 1.2 [Depende de 1.1] Implementar `Note`, `InvalidNoteData` y validadores en dominio mediante TDD. Verificación: tests de UUID/fechas UTC, títulos 0/1/200/201 después de trim, contenido 0/10 000/10 001 con espacios/saltos conservados y representación sin propietario/contenido; regresión de dominio e import boundaries.
- [x] 1.3 [Depende de 1.2] Estabilizar `NoteResult`, `NotePatch`, `NoteNotFound` y `NoteRepository` con las firmas de design; probar validación del cambio vacío, omisión interna y proyección segura. Entregar matriz de contrato: propiedad, orden, ausencia, PATCH por campos, commit y fallo sin mutación. Verificación: pruebas del comportamiento interno y matriz disponible para ambos workers, sin tipos de framework/vendor en contratos.
- [x] 1.4 [Depende de 1.3] Registrar `NoteNotFound` e `InvalidNoteData` en los handlers existentes con TDD. Verificación: tests directos/HTTP de error `404` y `422`, formatos sanitizados y ausencia de regresión en errores de usuarios/archivos. Archivos compartidos de errores quedan estabilizados antes del paralelo.
- [ ] 1.5 [Depende de 1.4] Revisar diff de la base contractual y registrar una revisión Git común transferible para los workers durante apply. Verificación: tests afectados, Ruff e import boundaries pasan; se conocen firmas, revisión base y propiedad de archivos; no se registran tareas posteriores como completadas.

## 2. Lead: preparar sesiones visibles y worktrees

- [ ] 2.1 [Depende de 1.5] Usar la skill oficial Herdr y comprobar `HERDR_ENV=1`, ayuda y estado del CLI/servidor; preparar ramas/worktrees separados para `notes-api` y `notes-persistence` desde la misma revisión 1.5. Verificación: rutas absolutas distintas, misma base Git y árboles sin cambios ajenos; si Herdr no está disponible, comunicar el bloqueo sin reemplazarlo por subagentes ocultos. No crear workspaces/tabs extra; seguir la skill de worktrees y validar ubicación/ignorado antes de crear dentro del repo.
- [ ] 2.2 [Depende de 2.1] Identificar el Lead como `notes-lead` cuando el CLI permita nombrar el agente existente y abrir sesiones Codex visibles `notes-api` y `notes-persistence` en panes adecuados, conservando foco; enviar a cada una alcance, archivos permitidos, cwd de su worktree, contratos, dependencias y obligación de TDD con Superpowers. Verificación: IDs y nombres leídos de Herdr, cwd correcto y recepción observada de ambas asignaciones; no duplicar prompts tras un timeout sin inspeccionar el estado.

## 3. Worker notes-api: aplicación y HTTP

Este grupo puede ejecutarse en paralelo con el grupo 4. No modifica dominio/puertos/errores comunes, modelos ORM, migraciones ni bootstrap. Los tests y fixtures de notas serán archivos propios; cualquier cambio a fixtures compartidas se solicita al Lead.

- [ ] 3.1 [Depende de 2.2] Añadir `FakeNoteRepository` y tests de contrato en archivos nuevos `tests/unit/application/test_note_repository_contract.py` y soporte existente de fakes. Verificación: RED/GREEN/REFACTOR para aislamiento, títulos repetidos, orden, PATCH que conserva omitidos, ausencia, fallo sin mutación y eliminación única; usar la matriz de 1.3.
- [ ] 3.2 [Depende de 3.1] Implementar los cinco casos de uso con inyección por constructor y callables de reloj/UUID donde corresponda. Verificación: tests unitarios para creación, listado, lectura, edición de uno/ambos campos, valor repetido, validación sin escritura, inexistencia/propiedad, fechas y outages; invalidación parcial conserva todo el estado y no se invoca almacenamiento de archivos.
- [ ] 3.3 [Depende de 3.2] Añadir schemas, router y dependencias HTTP de notas sin construir adaptadores; probarlos con router incluido en una app de prueba y overrides específicos. Verificación: cinco operaciones y códigos de la spec, matriz de tokens del contrato existente, `401` antes de UUID, entrada estricta, rechazo de `null`/`{}`/campos desconocidos, igualdad de `404` ajeno/inexistente, campos públicos exactos y `503`/`500` sanitizados. No registrar todavía el router en bootstrap.
- [ ] 3.4 [Depende de 3.3] Revisar el diff y entregar la revisión del worker al Lead con listado de archivos, evidencia TDD, comandos/resultados y bloqueos. Verificación: pruebas unitarias/API afectadas, Ruff e import boundaries pasan; firmas coinciden con la base y el diff respeta la propiedad acordada. Documentar en la entrega cómo retirar la inclusión manual del router de pruebas durante 5.1.

## 4. Worker notes-persistence: PostgreSQL y Alembic

Este grupo puede ejecutarse en paralelo con el grupo 3, sin esperar fake, casos de uso o HTTP. Es el único propietario del módulo de modelos y de la migración nueva. Usa esquemas únicos por prueba y PostgreSQL desechable configurado explícitamente mediante `TEST_DATABASE_URL`.

- [ ] 4.1 [Depende de 2.2] Añadir `NoteModel` y revisión `0002_private_notes.py`, actualizando expectativas existentes de tablas y agregando pruebas de restricciones/índice. Verificación: RED ante esquema ausente y GREEN en PostgreSQL; upgrade vacío y desde `0001` con usuarios/archivos de muestra conserva sus datos; downgrade solo a `0001` elimina notas y conserva los datos previos; re-upgrade y paridad ORM pasan.
- [ ] 4.2 [Depende de 4.1] Implementar `SqlAlchemyNoteRepository` y pruebas de persistencia contra la matriz de 1.3. Verificación: lectura/listado por propietario, inserción y borrado confirmados desde otra sesión, orden fecha/UUID, títulos duplicados, fallos de escritura con rollback y traducción sanitizada de errores; ausencia devuelve `None`/`False` como está contratado.
- [ ] 4.3 [Depende de 4.2] Implementar y probar UPDATE parcial con predicados de nota/propietario, asignaciones limitadas a campos presentes, RETURNING y commit antes de devolver el resultado al consumidor. Verificación: sesiones independientes conservan título/contenido concurrentes, serialización controlada comprueba última escritura del mismo campo, borrado que gana produce ausencia sin recreación y dos deletes eliminan una única fila; rollback de PATCH conserva campos y fechas. Coordinar carreras con eventos/bloqueos observables, sin sleeps como prueba de orden.
- [ ] 4.4 [Depende de 4.3] Revisar y entregar la revisión del worker con archivos, evidencia TDD, comandos PostgreSQL y explicación de upgrade/downgrade. Verificación: suite de persistencia/migración afectada, Ruff e import boundaries pasan; una sola cabeza Alembic y ninguna edición de `0001`.

## 5. Lead: integración y aceptación transversal

- [ ] 5.1 [Depende de 3.4 y 4.4] Integrar ambas entregas en la rama del Lead, resolver conflictos y conectar fábrica de repositorio/router en `bootstrap.py`. Ajustar fixtures de notas para usar la composición real sin inclusión duplicada y documentar rutas, límites, concurrencia y migración en README. Verificación: arranque/cierre y DI pasan; OpenAPI contiene cada operación de notas una vez; no se modifican firmas comunes sin comunicarlo ni se alteran contratos existentes.
- [ ] 5.2 [Depende de 5.1] Añadir aceptación transversal con dos usuarios y adaptadores reales: crear, listar, consultar, editar, borrar, denegar acceso ajeno y comprobar errores/rollback. Verificación: recorrido HTTP con PostgreSQL confirma persistencia entre peticiones, concurrencia acordada y ninguna llamada a almacenamiento de archivos por operaciones de notas; revalidar fixtures que usan el ciclo de vida S3 existente.
- [ ] 5.3 [Depende de 5.2] Ejecutar regresión completa con PostgreSQL y S3 local configurados mediante `TEST_DATABASE_URL` y `TEST_S3_ENDPOINT_URL`, además de `uv run --locked pytest tests/architecture -q`, `uv run --locked ruff check .`, `uv run --locked ruff format --check .` y `git diff --check`. Verificación: resultados reales de `uv run --locked pytest -q`, revisión del diff y mapa de cada requisito/escenario a evidencia; reportar servicios no disponibles o skips sin afirmar aceptación completa.

## 6. Reviewer independiente y cierre del Lead

- [ ] 6.1 [Depende de 5.3] Abrir una sesión Codex visible y nombrada `notes-reviewer` mediante Herdr sobre un checkout separado de la revisión integrada. Entregar propuesta/spec/design, diff y evidencia; solicitar revisión independiente de propiedad, PATCH/concurrencia, transacciones, migración, seguridad, TDD y dependencias entre capas, sin escribir código. Verificación: informe con archivos/líneas, severidad y validación contra criterios, o declaración explícita de ausencia de hallazgos; no sustituir revisión por un resumen del Lead.
- [ ] 6.2 [Depende de 6.1] Si hay hallazgos, asignarlos al propietario correspondiente, exigir pruebas de regresión cuando apliquen, integrar correcciones y repetir solo checks afectados y aceptación necesaria; volver a revisión para cerrar hallazgos. Verificación: informe final, evidencia actualizada y checklist completado únicamente con trabajo verificado; ninguna implementación pendiente ni desviación sin documentar. Si no hubo hallazgos, registrar esa evidencia sin inventar correcciones.

## Workflow follow-up

- Entregar el cambio implementado para revisión del usuario; no desplegar, publicar, fusionar a la rama principal ni archivar automáticamente.
- Conservar las sesiones/worktrees hasta la entrega; cerrar o limpiar únicamente los recursos creados para el trabajo cuando corresponda y sin perder cambios no integrados.

## Execution evidence

- Baseline 1.1: rama `feature/openspec-demo`; únicos archivos preexistentes sin seguimiento: artefactos de este cambio. Suite sin servicios: 645 passed, 33 deselected; Ruff lint y formato correctos (109 archivos). Apply solicitado explícitamente y artefactos revisados.
- Instrucción del usuario durante apply: desarrollar ahora sin Docker y probar servicios externos después. Se prepararán las pruebas PostgreSQL/S3, pero los checks de integración y las tareas que los requieren no se marcarán completos hasta ejecutarlos. No iniciar Docker en esta etapa.
- 1.2: RED: 29 fallos por dominio de notas ausente. GREEN/refactor: 149 pruebas de dominio y arquitectura correctas; Ruff lint/formato correctos.
- 1.3: RED: 6 fallos por DTO ausentes. GREEN: 77 casos de notas/DTO/arquitectura correctos; puerto async estabilizado según design y matriz contractual definida allí para fake y SQL.
- 1.4: RED: 2 respuestas 500 donde se esperaban 404/422; GREEN: ambos errores HTTP correctos. Ruff y diff sin errores.
