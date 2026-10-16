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
- [x] 1.5 [Depende de 1.4] Revisar diff de la base contractual y registrar una revisión Git común transferible para los workers durante apply. Verificación: tests afectados, Ruff e import boundaries pasan; se conocen firmas, revisión base y propiedad de archivos; no se registran tareas posteriores como completadas.

## 2. Lead: preparar sesiones visibles y worktrees

- [x] 2.1 [Depende de 1.5] Usar la skill oficial Herdr y comprobar `HERDR_ENV=1`, ayuda y estado del CLI/servidor; preparar ramas/worktrees separados para `notes-api` y `notes-persistence` desde la misma revisión 1.5. Verificación: rutas absolutas distintas, misma base Git y árboles sin cambios ajenos; si Herdr no está disponible, comunicar el bloqueo sin reemplazarlo por subagentes ocultos. No crear workspaces/tabs extra; seguir la skill de worktrees y validar ubicación/ignorado antes de crear dentro del repo.
- [x] 2.2 [Depende de 2.1] Identificar el Lead como `notes-lead` cuando el CLI permita nombrar el agente existente y abrir sesiones Codex visibles `notes-api` y `notes-persistence` en panes adecuados, conservando foco; enviar a cada una alcance, archivos permitidos, cwd de su worktree, contratos, dependencias y obligación de TDD con Superpowers. Verificación: IDs y nombres leídos de Herdr, cwd correcto y recepción observada de ambas asignaciones; no duplicar prompts tras un timeout sin inspeccionar el estado.

## 3. Worker notes-api: aplicación y HTTP

Este grupo puede ejecutarse en paralelo con el grupo 4. No modifica dominio/puertos/errores comunes, modelos ORM, migraciones ni bootstrap. Los tests y fixtures de notas serán archivos propios; cualquier cambio a fixtures compartidas se solicita al Lead.

- [x] 3.1 [Depende de 2.2] Añadir `FakeNoteRepository` y tests de contrato en archivos nuevos `tests/unit/application/test_note_repository_contract.py` y soporte existente de fakes. Verificación: RED/GREEN/REFACTOR para aislamiento, títulos repetidos, orden, PATCH que conserva omitidos, ausencia, fallo sin mutación y eliminación única; usar la matriz de 1.3.
- [x] 3.2 [Depende de 3.1] Implementar los cinco casos de uso con inyección por constructor y callables de reloj/UUID donde corresponda. Verificación: tests unitarios para creación, listado, lectura, edición de uno/ambos campos, valor repetido, validación sin escritura, inexistencia/propiedad, fechas y outages; invalidación parcial conserva todo el estado y no se invoca almacenamiento de archivos.
- [x] 3.3 [Depende de 3.2] Añadir schemas, router y dependencias HTTP de notas sin construir adaptadores; probarlos con router incluido en una app de prueba y overrides específicos. Verificación: cinco operaciones y códigos de la spec, matriz de tokens del contrato existente, `401` antes de UUID, entrada estricta, rechazo de `null`/`{}`/campos desconocidos, igualdad de `404` ajeno/inexistente, campos públicos exactos y `503`/`500` sanitizados. No registrar todavía el router en bootstrap.
- [x] 3.4 [Depende de 3.3] Revisar el diff y entregar la revisión del worker al Lead con listado de archivos, evidencia TDD, comandos/resultados y bloqueos. Verificación: pruebas unitarias/API afectadas, Ruff e import boundaries pasan; firmas coinciden con la base y el diff respeta la propiedad acordada. Documentar en la entrega cómo retirar la inclusión manual del router de pruebas durante 5.1.

## 4. Worker notes-persistence: PostgreSQL y Alembic

Este grupo puede ejecutarse en paralelo con el grupo 3, sin esperar fake, casos de uso o HTTP. Es el único propietario del módulo de modelos y de la migración nueva. Usa esquemas únicos por prueba y PostgreSQL desechable configurado explícitamente mediante `TEST_DATABASE_URL`.

- [ ] 4.1 [Depende de 2.2] Añadir `NoteModel` y revisión `0002_private_notes.py`, actualizando expectativas existentes de tablas y agregando pruebas de restricciones/índice. Verificación: RED ante esquema ausente y GREEN en PostgreSQL; upgrade vacío y desde `0001` con usuarios/archivos de muestra conserva sus datos; downgrade solo a `0001` elimina notas y conserva los datos previos; re-upgrade y paridad ORM pasan.
- [ ] 4.2 [Depende de 4.1] Implementar `SqlAlchemyNoteRepository` y pruebas de persistencia contra la matriz de 1.3. Verificación: lectura/listado por propietario, inserción y borrado confirmados desde otra sesión, orden fecha/UUID, títulos duplicados, fallos de escritura con rollback y traducción sanitizada de errores; ausencia devuelve `None`/`False` como está contratado.
- [ ] 4.3 [Depende de 4.2] Implementar y probar UPDATE parcial con predicados de nota/propietario, asignaciones limitadas a campos presentes, RETURNING y commit antes de devolver el resultado al consumidor. Verificación: sesiones independientes conservan título/contenido concurrentes, serialización controlada comprueba última escritura del mismo campo, borrado que gana produce ausencia sin recreación y dos deletes eliminan una única fila; rollback de PATCH conserva campos y fechas. Coordinar carreras con eventos/bloqueos observables, sin sleeps como prueba de orden.
- [ ] 4.4 [Depende de 4.3] Revisar y entregar la revisión del worker con archivos, evidencia TDD, comandos PostgreSQL y explicación de upgrade/downgrade. Verificación: suite de persistencia/migración afectada, Ruff e import boundaries pasan; una sola cabeza Alembic y ninguna edición de `0001`.

## 5. Lead: integración y aceptación transversal

- [x] 5.1 [Depende de 3.4 y 4.4] Integrar ambas entregas en la rama del Lead, resolver conflictos y conectar fábrica de repositorio/router en `bootstrap.py`. Ajustar fixtures de notas para usar la composición real sin inclusión duplicada y documentar rutas, límites, concurrencia y migración en README. Verificación: arranque/cierre y DI pasan; OpenAPI contiene cada operación de notas una vez; no se modifican firmas comunes sin comunicarlo ni se alteran contratos existentes.
- [ ] 5.2 [Depende de 5.1] Añadir aceptación transversal con dos usuarios y adaptadores reales: crear, listar, consultar, editar, borrar, denegar acceso ajeno y comprobar errores/rollback. Verificación: recorrido HTTP con PostgreSQL confirma persistencia entre peticiones, concurrencia acordada y ninguna llamada a almacenamiento de archivos por operaciones de notas; revalidar fixtures que usan el ciclo de vida S3 existente.
- [ ] 5.3 [Depende de 5.2] Ejecutar regresión completa con PostgreSQL y S3 local configurados mediante `TEST_DATABASE_URL` y `TEST_S3_ENDPOINT_URL`, además de `uv run --locked pytest tests/architecture -q`, `uv run --locked ruff check .`, `uv run --locked ruff format --check .` y `git diff --check`. Verificación: resultados reales de `uv run --locked pytest -q`, revisión del diff y mapa de cada requisito/escenario a evidencia; reportar servicios no disponibles o skips sin afirmar aceptación completa.

## 6. Reviewer independiente y cierre del Lead

- [x] 6.1 [Depende de 5.3] Abrir una sesión Codex visible y nombrada `notes-reviewer` mediante Herdr sobre un checkout separado de la revisión integrada. Entregar propuesta/spec/design, diff y evidencia; solicitar revisión independiente de propiedad, PATCH/concurrencia, transacciones, migración, seguridad, TDD y dependencias entre capas, sin escribir código. Verificación: informe con archivos/líneas, severidad y validación contra criterios, o declaración explícita de ausencia de hallazgos; no sustituir revisión por un resumen del Lead.
- [ ] 6.2 [Depende de 6.1] Si hay hallazgos, asignarlos al propietario correspondiente, exigir pruebas de regresión cuando apliquen, integrar correcciones y repetir solo checks afectados y aceptación necesaria; volver a revisión para cerrar hallazgos. Verificación: informe final, evidencia actualizada y checklist completado únicamente con trabajo verificado; ninguna implementación pendiente ni desviación sin documentar. Si no hubo hallazgos, registrar esa evidencia sin inventar correcciones.

## 7. Lead: corrección de texto aprobada tras revisión

- [x] 7.1 [Depende de 6.1 y autorización recibida] Aplicar la exclusión de NUL y sustitutos aislados con Superpowers TDD después de actualizar proposal/spec/design. Verificación: RED de dominio y POST/PATCH con escapes JSON reales, GREEN sin operaciones de escritura ni cambios de campos/fechas ante rechazo; conservar emojis directos y pares JSON válidos; suite completa sin servicios, arquitectura, Ruff, formato y OpenSpec strict correctos. Documentar la regla en README; Docker sigue aplazado.
- [ ] 7.2 [Depende de 7.1] Entregar la revisión corregida a la sesión independiente `notes-reviewer` mediante Herdr, con checkout actualizado y sin escrituras del reviewer. Verificación: informe que cierre el P2 o describa hallazgos pendientes; registrar evidencia y conservar explícitamente pendientes las pruebas con PostgreSQL/S3 y el cierre global 6.2.

## Workflow follow-up

- Entregar el cambio implementado para revisión del usuario; no desplegar, publicar, fusionar a la rama principal ni archivar automáticamente.
- Conservar las sesiones/worktrees hasta la entrega; cerrar o limpiar únicamente los recursos creados para el trabajo cuando corresponda y sin perder cambios no integrados.

## Execution evidence

- Baseline 1.1: rama `feature/openspec-demo`; únicos archivos preexistentes sin seguimiento: artefactos de este cambio. Suite sin servicios: 645 passed, 33 deselected; Ruff lint y formato correctos (109 archivos). Apply solicitado explícitamente y artefactos revisados.
- Instrucción del usuario durante apply: desarrollar ahora sin Docker y probar servicios externos después. Se prepararán las pruebas PostgreSQL/S3, pero los checks de integración y las tareas que los requieren no se marcarán completos hasta ejecutarlos. No iniciar Docker en esta etapa.
- Las dependencias hacia pruebas con servicios se mantienen pendientes para aceptación; por la instrucción anterior se permite preparar e integrar código entregado antes de cerrar esas verificaciones. No se modifica el comportamiento especificado ni se presenta la aceptación completa antes de probarlo.
- El Lead añade `.worktrees` a `.dockerignore` para que los checkouts y entornos de los workers no entren en futuros contextos de imagen; configuración local de aislamiento, sin ejecutar Docker.
- 1.2: RED: 29 fallos por dominio de notas ausente. GREEN/refactor: 149 pruebas de dominio y arquitectura correctas; Ruff lint/formato correctos.
- 1.3: RED: 6 fallos por DTO ausentes. GREEN: 77 casos de notas/DTO/arquitectura correctos; puerto async estabilizado según design y matriz contractual definida allí para fake y SQL.
- 1.4: RED: 2 respuestas 500 donde se esperaban 404/422; GREEN: ambos errores HTTP correctos. Ruff y diff sin errores.
- 1.5: Base común guardada en d2476b6; 682 pruebas sin servicios correctas, Ruff lint/formato y diff correctos; solo contratos, errores y planificación. Workers parten de esa revisión.
- 2.1: Herdr 0.9.5 compatible y HERDR_ENV=1; dos ramas/worktrees independientes y limpios desde d2476b6, directorio .worktrees ignorado. Se usa Git para evitar que el helper de Herdr cree workspaces adicionales.
- 2.2: Sesiones Codex visibles notes-api en w7:p6 y notes-persistence en w7:p7, worktrees correctos y recepción/trabajo observados; Lead notes-lead en w7:p1 conserva foco.
- 3.1: Entrega API 84913a0: 9 tests de contrato fake correctos; revisión local confirma propiedad, PATCH parcial y errores. Verificados nuevamente con suite integrada de 335 casos.
- 3.2: Entrega API 84913a0: 30 tests de casos de uso correctos y RED registrado; contratos congelados respetados; verificados con suite integrada.
- 3.3: Entrega API 84913a0: 290 tests HTTP correctos con matriz JWT y validación estricta; composición real integrada sin registrar el router dos veces. Suite focal integrada: 335 passed.
- 3.4: Entrega 84913a0 revisada e integrada como cb0873a; ámbito de archivos respetado, árbol del worker limpio; evidencia RED/GREEN/REFACTOR y comprobaciones sin servicios entregadas.
- Persistencia entregada en `dd758bd`, integrada como `1b45186`: RED de 3 casos de migración y 22 de adaptador; 25 checks nuevos sin servicios y 42 de arquitectura verificados de nuevo por el Lead (67 passed). Checks reales de 4.1–4.4 pendientes por instrucción del usuario.
- Aceptación 5.2 preparada en `tests/integration/test_notes_lifecycle.py`: cuatro casos de ciclo de vida, aislamiento, concurrencia y rollback. Recopilación conjunta con persistencia: 57 tests; no se ejecutaron con servicios.

### Acceptance evidence map

| Requisitos de private-notes | Evidencia sin servicios | Evidencia con servicios pendiente |
| --- | --- | --- |
| Autenticación y propiedad | `tests/api/test_notes.py`: matriz JWT, precedencia, outages y equivalencia ajeno/inexistente | `test_notes_lifecycle.py`: dos usuarios; `persistence/test_notes.py`: filtros reales |
| Título, contenido y JSON estricto | `test_note.py`, `test_note_dto.py`, `test_notes.py` de aplicación/API: límites, normalización, duplicados, null, omisión, desconocidos y estructura | `persistence/test_notes.py`: restricciones y Unicode |
| Creación, representación y fechas | `test_notes.py` de aplicación/API: ciclo, proyección, reloj fijo y repetición de valor | `test_notes_lifecycle.py`: representación y persistencia entre peticiones |
| Listado y consulta | `test_notes.py` de aplicación/API: orden empatado, vacío, propiedad y UUID | `persistence/test_notes.py`: orden y visibilidad desde otra sesión |
| PATCH y concurrencia | `test_note_repository_contract.py`, `test_notes.py` de aplicación/API: campos omitidos, no preread, cambios inválidos y carreras con fake | `persistence/test_notes.py`: locks reales, campos distintos, mismo campo y delete/PATCH |
| Eliminación y fallos | Contratos, API y `test_note_repository.py`: ausencia, rollback y sanitización | `test_notes_lifecycle.py` y `persistence/test_notes.py`: rollback real y carrera de deletes |
| Compatibilidad | Regresión sin servicios, import boundaries y fixture que rechaza llamadas a FileStorage en notas | Regresión histórica con PostgreSQL/S3 y comprobación de migración preservando usuarios/archivos |

- Integración del Lead: suite completa sin servicios `1042 passed, 64 deselected` (selección explícita `-m 'not integration'`); Ruff lint/formato (128 archivos), diff y OpenSpec strict correctos. Las 64 pruebas con servicios siguen sin ejecutar. Revisión independiente del código se hará ahora; aceptación con servicios y cierre global se mantienen pendientes.
- Revisión independiente completada antes de la aceptación con servicios por la secuencia de validación indicada por el usuario. P2 abierto en `app/domain/validation.py`: título/contenido aceptan NUL y sustitutos Unicode aislados. El reviewer reprodujo `201` con NUL usando fake y `500` con un sustituto aislado; el Lead confirmó aceptación en ambos validadores y `UnicodeEncodeError` al serializar este último. PostgreSQL no admite NUL en columnas de texto. Se propone excluir esos caracteres con `422`, actualizar primero los artefactos y añadir regresión POST/PATCH; pendiente decisión del usuario, sin cambiar silenciosamente la especificación.
- Decisión posterior del usuario: autoriza excluir NUL y sustitutos aislados con `422`, actualizar los artefactos y corregir mediante TDD, manteniendo Docker aplazado. Las tareas 7.1–7.2 registran el ajuste y su revisión; el P2 anterior es evidencia histórica, no una decisión todavía pendiente.
- 5.1: Entregas API y persistencia integradas; 6 pruebas de composición y 329 casos de API/aplicación correctos (335 total). Bootstrap registra fábrica/router; OpenAPI contiene las cinco operaciones y fixture sin registro duplicado. README y exclusión de worktrees documentadas.
- 6.1: Reviewer independiente notes-reviewer en w7:p8, checkout detached 28306a6, revisó a534311..28306a6 sin escrituras. Hallazgo P2: validadores aceptan NUL y surrogates aislados, causando errores de servidor. Corrección requiere precisar el contrato; aceptación con servicios sigue pendiente.
- 7.1: RED: 30 fallos y 4 controles Unicode válidos correctos. GREEN: 34 regresiones de dominio/POST/PATCH correctas; suite sin servicios 1076 passed, 64 deselected. Arquitectura 42 passed; Ruff lint/formato, diff y OpenSpec strict correctos. Contrato y README actualizados antes de cerrar el ajuste; ningún servicio iniciado.
