# Design

## Context

Ver `proposal.md` para la motivación y `specs/private-notes/spec.md` para el comportamiento aprobado. El backend tiene entidades dataclass inmutables, puertos en `app/application/ports.py`, casos de uso por operación, repositorios async con commit propio y composición en `app/bootstrap.py`. La autenticación se resuelve en presentación y entrega un `User` verificado.

Las pruebas usan fakes para aplicación/HTTP, PostgreSQL con esquemas únicos por prueba y migraciones reales para persistencia. `tests/integration/persistence/test_migrations.py` enumera las tablas actuales, por lo que necesitará adaptación. La revisión existente es `0001_users_and_files`; Alembic importa `Base.metadata` desde el módulo central de modelos.

## Goals / Non-Goals

**Goals:**
- Extender las cuatro capas respetando las dependencias existentes y mantener los detalles de transporte y base de datos fuera de las capas internas.
- Estabilizar los contratos antes de dividir la implementación entre aplicación/HTTP y persistencia.
- Dar a cada worker un conjunto de archivos propio, verificaciones independientes y un punto claro de integración.

**Non-Goals:**
- No introducir repositorio CRUD genérico, contenedor de servicios, UnitOfWork, eventos, bloqueo optimista ni refactorización de los recursos existentes.
- No cambiar el ciclo de vida actual de S3 en el arranque de la aplicación; las operaciones de notas no usarán ese adaptador.
- Crear estos artefactos no abre sesiones, crea worktrees ni autoriza comenzar la implementación automáticamente.

## Decisions

### 1. Dominio y contratos comunes antes del paralelo

El Lead añadirá `Note` a `app/domain/entities.py`, reglas de notas a `validation.py` e `InvalidNoteData` a `errors.py`. La entidad tendrá `id`, `user_id`, `title`, `body`, `created_at` y `updated_at`, validará UUID y fechas conscientes de zona horaria y normalizará fechas a UTC. Seguirá el patrón inmutable existente; el propietario y contenido no deben aparecer en su representación de diagnóstico.

Se usarán `NoteResult` y `NotePatch` en `app/application/dto.py`, `NoteNotFound` en errores de aplicación y un `NoteRepository` en puertos. `NoteResult` contiene exclusivamente los cinco campos públicos. `NotePatch` contiene `title: str | None` y `body: str | None`; `None` significa omitido internamente. Se rechaza un cambio sin campos. HTTP rechaza `null` antes de traducirlo a esta representación, de modo que nunca se confunda con omisión.

Detalle de implementación de límites: contar caracteres con la longitud de strings de Python, sin normalización Unicode; aplicar `str.strip()` solo al título. El contenido se conserva exactamente. No se añade unicidad del título. Son concreciones técnicas de las reglas acordadas.

Tras la revisión P2, el usuario aprobó excluir NUL (`U+0000`) y sustitutos Unicode aislados (`U+D800`–`U+DFFF`). Los validadores puros de título y contenido rechazarán esos valores mediante `InvalidNoteData`, sin importar PostgreSQL ni tipos de infraestructura. Una comprobación compartida de texto evita diferencias entre ambos campos. Entidad y `NotePatch` reutilizan esos validadores; la presentación mantiene su traducción existente a `422` sanitizado. No se requiere otra migración ni cambios al puerto.

La causa era la diferencia entre un string de Python aceptado por longitud y texto serializable/persistible: NUL llega a PostgreSQL y los sustitutos aislados fallan al codificar UTF-8. No se corrige cambiando un `503` o `500` a posteriori; se rechaza la entrada antes de escribir. Los pares de sustitutos válidos en JSON se decodifican como un único carácter Unicode y siguen admitidos. Las pruebas enviarán escapes JSON como bytes ASCII para reproducir sustitutos aislados sin que el cliente de pruebas falle primero.

| Operación async de NoteRepository | Resultado y semántica |
| --- | --- |
| `add(note: Note)` | `None`; confirma la inserción antes de retornar |
| `list_by_owner(user_id: UUID)` | `list[Note]`; orden por fecha de creación e ID |
| `get_owned(note_id: UUID, user_id: UUID)` | `Note` o `None`; nunca búsqueda pública global |
| `update_owned(note_id: UUID, user_id: UUID, changes: NotePatch, updated_at: datetime)` | `Note` actualizada o `None`; cambia exclusivamente campos presentes y fecha de actualización; confirma antes de retornar |
| `delete_owned(note_id: UUID, user_id: UUID)` | `bool`; confirma y devuelve si eliminó una fila |

Todas las operaciones traducen fallos operacionales a `DependencyUnavailable`; las escrituras fallidas revierten la transacción. Actualizar o eliminar una nota inexistente o ajena devuelve ausencia, no un error que revele propiedad. Cambios inválidos se rechazan antes de invocar escrituras.

Alternativas descartadas: agregar capacidades de notas a `FileRepository` mezclaría responsabilidades; guardar una entidad completa para PATCH perdería cambios concurrentes; usar tipos Pydantic en el puerto rompería las dependencias.

### 2. Casos de uso y frontera HTTP

Crear `CreateNote`, `ListUserNotes`, `GetUserNote`, `UpdateUserNote` y `DeleteUserNote` en archivos propios bajo `app/application/use_cases/`. Inyectar `NoteRepository` por constructor y reloj/UUID mediante callables pequeños donde corresponda, siguiendo `RegisterUser`. Creación usa una sola lectura del reloj para ambas fechas. Edición valida y normaliza el cambio, obtiene la fecha y llama directamente a `update_owned`; no necesita leer previamente la nota ni reemplazarla completa. La ausencia produce `NoteNotFound`.

El router nuevo `app/presentation/routers/notes.py` usa `get_authenticated_user`, schemas Pydantic estrictos y dependencias de notas en `presentation/dependencies.py`. El UUID de propietario nunca viene del cuerpo. Los schemas de notas estarán en el módulo existente `presentation/schemas.py`, con respuesta explícita y validación de presencia/null para PATCH. El Lead registra los errores nuevos en `presentation/error_handlers.py`, conservando sanitización y formatos existentes.

`get_note_repository` obtiene la fábrica desde `app.state` con una sesión de la base de datos; el Lead registra `SqlAlchemyNoteRepository` y el router en `bootstrap.py` durante integración. No se construyen adaptadores en los routers. Las operaciones quedan detalladas en la spec y no requieren cambios en settings ni paquetes.

### 3. Actualización parcial atómica

El adaptador ejecutará una actualización SQL con predicados por `id` y `user_id`, asignaciones solo para campos enviados y `updated_at`, y `RETURNING` de la fila resultante. Confirmará la transacción antes de devolver la entidad. Así PostgreSQL serializa escrituras sobre una misma fila sin sobrescribir campos omitidos. El fake debe tener la misma semántica observable.

Si dos escrituras envían el mismo campo, prevalece la última aplicada a la fila; no se promete orden por llegada de peticiones o por respuesta HTTP. Una eliminación que gana antes del UPDATE produce ausencia. Si el UPDATE gana y luego se elimina la fila, el PATCH puede haber respondido con éxito y una consulta posterior obtener `404`.

`updated_at` procede del reloj inyectado de aplicación; no funciona como versión ni garantiza crecimiento estricto u orden total entre peticiones concurrentes. Se vuelve a asignar incluso en ediciones que repiten valores; la precisión del reloj puede producir timestamps iguales. No se impone `updated_at >= created_at` como restricción de base de datos frente a ajustes de reloj.

Alternativas: el bloqueo optimista exigiría un contrato de versiones/ETags que quedó fuera del alcance; un ciclo leer-modificar-guardar exigiría bloqueo y trabajo adicional para conseguir la misma semántica.

### 4. Persistencia y migración

Añadir `NoteModel` al módulo existente `app/infrastructure/persistence/models.py` para que Alembic vea la tabla sin otro mecanismo de registro. Crear `note_repository.py` junto a los adaptadores actuales y el archivo `0002_private_notes.py` con revisión `0002` y `down_revision = "0001"`, identificador comprobado en la revisión inicial.

Tabla `notes`: UUID PK, `user_id` FK a `users.id` con `ON DELETE RESTRICT`, título no nulo de hasta 200 caracteres, contenido `Text` no nulo, fechas timezone-aware no nulas e índice `(user_id, created_at, id)`. Restricciones de longitud para título 1–200 y contenido hasta 10 000 como defensa adicional. La normalización del título pertenece al dominio. No hay relación con archivos ni operación sobre S3.

Los tests del adaptador deben comprobar commits observables desde otra sesión, rollback, propiedad, orden, actualizaciones parciales y concurrencia usando sesiones separadas. La semántica del fake y del adaptador se compara contra la misma matriz de contrato, aunque sus fixtures sean distintas.

### 5. Coordinación futura con Herdr

La implementación comenzará únicamente por una petición posterior de apply. El Lead usará la skill oficial local `herdr`, comprobará `HERDR_ENV=1` y descubrirá la sintaxis del CLI instalado. Si no está dentro de Herdr, detendrá la orquestación y comunicará el bloqueo; no sustituirá las sesiones visibles por subagentes ocultos.

Sesiones Codex nombradas: `notes-lead`, `notes-api`, `notes-persistence` y `notes-reviewer`. El Lead se identifica en su pane existente si el CLI lo permite sin reiniciar la sesión; los workers y reviewer usan panes visibles de la misma pestaña, con foco preservado. Inspeccionar geometría antes de dividir y usar IDs devueltos por Herdr. No responder automáticamente a diálogos de aprobación de otros agentes.

El Lead prepara los contratos y errores HTTP comunes primero. Después, los dos workers de escritura parten de la misma revisión contractual, cada uno con rama y Git Worktree propio, y reciben instrucciones explícitas con su cwd absoluto. El reviewer trabaja sobre el resultado integrado desde un checkout separado, sin escribir código. No se comparten working directories entre escritores ni se crean workspaces/tabs adicionales por defecto.

| Responsable | Archivos propios |
| --- | --- |
| Lead, base común | `app/domain/{entities,validation,errors}.py`, `app/application/{ports,dto,errors}.py`, tests nuevos de dominio/contrato del cambio y registro de errores en `presentation/error_handlers.py` |
| `notes-api` | Cinco archivos nuevos de casos de uso, `presentation/routers/notes.py`, adiciones a `presentation/{schemas,dependencies}.py`, `tests/unit/application/fakes.py`, tests nuevos unitarios/HTTP y fixtures específicas de notas |
| `notes-persistence` | `infrastructure/persistence/models.py`, nuevo `note_repository.py`, única revisión nueva y tests de persistencia/migración |
| Lead, integración | `bootstrap.py`, fixtures compartidas si son necesarias, test de recorrido completo, README y progreso de `tasks.md` |
| `notes-reviewer` | Lectura del diff integrado, contratos, evidencia y pruebas; entrega hallazgos sin modificar producto |

El worker API puede probar el router con una aplicación de prueba que lo incluya explícitamente, reutilizando autenticación, handlers y overrides existentes, antes de que bootstrap lo registre. Esa composición debe limitarse a las fixtures de notas y ajustarse al integrar para evitar registrar rutas dos veces. El worker de persistencia puede probar el adaptador directamente, sin esperar casos de uso ni HTTP.

Solo el Lead actualiza el checklist compartido. Cada worker reporta rutas cambiadas, revisión entregada, evidencia RED/GREEN/REFACTOR, comandos y resultados, desviaciones y bloqueos. Los cambios de contrato vuelven al Lead; ningún worker modifica unilateralmente la base común. Si el reviewer encuentra fallos, se asignan al propietario del área y se vuelven a verificar antes de cerrar.

## Risks / Trade-offs

- Archivos centrales compartidos -> propiedad exclusiva por fase, base común estabilizada y puntos de entrega explícitos; los worktrees no resuelven conflictos semánticos.
- Discrepancias fake/SQL -> matriz común para propiedad, PATCH, orden, ausencia y fallo sin mutación; concurrencia real en PostgreSQL.
- Listado sin paginación que incluye contenido -> limitación aceptada de esta versión; no añadir paginación silenciosamente.
- Fechas usadas como supuesto orden de concurrencia -> documentar que `updated_at` no es una versión; comprobar campos y orden efectivo de escrituras.
- Pruebas históricas que enumeran tablas -> actualizar expectativas y comprobar que la revisión nueva no altera datos de usuarios/archivos.
- Divergencia durante trabajo paralelo -> una sola migración y revisión de contratos antes de integrar; ambos workers parten de la misma base.
- Tiempo de coordinación mayor que la implementación individual -> aceptado por el objetivo educativo; mantener solo dos workers y un reviewer posterior.

## Migration Plan

1. Verificar la cadena Alembic y aplicar la nueva revisión sobre la base existente antes de arrancar la versión con notas; no migrar automáticamente al iniciar FastAPI.
2. Probar upgrade desde base vacía y desde `0001` con usuarios/archivos existentes, además de paridad con ORM e índices/restricciones.
3. Integrar aplicación y adaptador, ejecutar recorrido real y regresión; no usar credenciales AWS reales para las pruebas.
4. Para rollback de esquema, detener la versión que usa notas y bajar solo a la revisión anterior. Se pierde el contenido de notas al eliminar la tabla; usuarios y archivos deben permanecer intactos. Un rollback solo de aplicación puede dejar la tabla aditiva sin uso.
5. No desplegar, publicar ni archivar automáticamente al terminar la implementación.
