# private-notes Specification

## Purpose

Permitir que cada usuario gestione apuntes privados de texto mediante una API REST, con validación explícita, persistencia confirmada y aislamiento entre propietarios.

## Requirements

### Requirement: Autenticación de todas las operaciones
El sistema SHALL exigir autenticación válida en todas las rutas de notas, reutilizando el contrato Bearer existente. SHALL autenticar antes de consultar o modificar notas y antes de validar el UUID de ruta.

#### Scenario: Usuario sin autenticación o con token inválido
- **WHEN** se invoca cualquier operación de notas sin token o con un token rechazado por el contrato de autenticación existente
- **THEN** responde `401`, `{"detail":"Not authenticated"}` y `WWW-Authenticate: Bearer`, sin operaciones sobre notas

#### Scenario: UUID inválido y ausencia de autenticación
- **WHEN** se consulta, edita o elimina `/notes/no-es-uuid` sin autenticación válida
- **THEN** responde `401` antes de informar un UUID inválido

#### Scenario: Dependencia de autenticación no disponible
- **WHEN** falla una dependencia al resolver al usuario autenticado
- **THEN** responde `503` sin consultar ni modificar notas

### Requirement: Propiedad privada e identidad generada por el servidor
El sistema SHALL derivar el propietario únicamente del usuario autenticado y generar el UUID y las fechas de cada nota. SHALL responder `404` con `{"detail":"Note not found"}` para identificadores inexistentes y notas ajenas, sin revelar ni modificar estas últimas.

#### Scenario: Lectura o mutación de nota ajena
- **WHEN** un usuario consulta, edita o elimina una nota de otro usuario
- **THEN** obtiene el mismo código y cuerpo que para un UUID inexistente, y la nota ajena permanece intacta

#### Scenario: Intento de elegir propietario o identidad
- **WHEN** un cuerpo de creación o edición incluye `user_id`, `owner_id`, `id`, `created_at` o `updated_at`
- **THEN** responde `422` sin crear ni modificar notas

### Requirement: Validación del título
El sistema SHALL exigir un título de tipo string con Unicode admitido, quitar sus espacios exteriores y aceptar entre 1 y 200 caracteres después de esa normalización. SHALL permitir títulos repetidos para un mismo propietario. Un título inválido SHALL producir `422` sin mutación.

#### Scenario: Normalización y límites inclusivos
- **WHEN** se crea o edita una nota con un título que, después de quitar espacios exteriores, contiene entre 1 y 200 caracteres
- **THEN** se acepta y devuelve el título normalizado

#### Scenario: Título vacío o demasiado largo
- **WHEN** el título normalizado está vacío o contiene 201 caracteres
- **THEN** responde `422` y no modifica el estado persistido

#### Scenario: Títulos duplicados
- **WHEN** un usuario crea dos notas con el mismo título o cambia un título por otro ya utilizado
- **THEN** ambas notas pueden conservar ese título y se distinguen por sus UUID

### Requirement: Validación del contenido
El sistema SHALL exigir un contenido `body` de tipo string con Unicode admitido y aceptar de 0 a 10 000 caracteres, conservando exactamente espacios y saltos de línea. El contenido es texto plano. Un contenido inválido SHALL producir `422` sin mutación.

#### Scenario: Contenido vacío o en el límite
- **WHEN** se crea o edita una nota con `body` igual a `""` o con exactamente 10 000 caracteres
- **THEN** se acepta y devuelve el contenido sin transformación

#### Scenario: Conservación de espacios y saltos de línea
- **WHEN** el contenido válido tiene espacios exteriores y saltos de línea
- **THEN** la lectura posterior devuelve exactamente ese contenido

#### Scenario: Contenido excesivo
- **WHEN** el contenido contiene 10 001 caracteres
- **THEN** responde `422` y conserva el estado anterior

### Requirement: Texto Unicode admitido
El sistema SHALL rechazar con `422` NUL (`U+0000`) y sustitutos Unicode aislados (`U+D800`–`U+DFFF`) en título o contenido, antes de persistir. SHALL conservar el Unicode válido sin reemplazos ni eliminación silenciosa de caracteres, incluidos emojis representados por pares de sustitutos válidos en JSON.

#### Scenario: Texto no admitido al crear o editar
- **WHEN** un POST o PATCH envía título o contenido con NUL o un sustituto Unicode aislado
- **THEN** responde `422` sanitizado sin invocar escrituras ni cambiar campos o fechas de notas existentes, aunque el otro campo enviado sea válido

#### Scenario: Emoji válido en JSON
- **WHEN** un POST o PATCH envía un emoji como carácter Unicode o como par de sustitutos válido en JSON dentro de los límites acordados
- **THEN** acepta la operación y devuelve el emoji intacto en título y contenido

### Requirement: Cuerpos JSON estrictos
El sistema SHALL aceptar únicamente objetos JSON con `title` y `body` como campos posibles. SHALL rechazar campos desconocidos, valores `null` y valores no string para estos campos. Los errores de validación SHALL seguir el formato sanitizado existente de `422` con entradas `loc`, `msg` y `type`.

#### Scenario: Creación incompleta
- **WHEN** `POST /notes` omite `title` o `body`
- **THEN** responde `422` y no crea una nota

#### Scenario: Tipo o estructura inválidos
- **WHEN** el cuerpo es una lista, un escalar, JSON inválido, contiene un campo desconocido o incluye `null`, un número, booleano, objeto o lista como título o contenido
- **THEN** responde `422` sin mutación ni reproducción de los valores de entrada en los errores

### Requirement: Creación de notas
El sistema SHALL aceptar `POST /notes` con `title` y `body` válidos y responder `201` con la nota únicamente después de confirmar su persistencia. Cada creación SHALL producir un UUID nuevo.

#### Scenario: Creación y lectura posterior
- **WHEN** un usuario crea una nota válida
- **THEN** recibe `201` y puede consultarla y encontrarla en su listado desde una petición posterior

#### Scenario: Creaciones repetidas
- **WHEN** un usuario envía dos creaciones válidas con el mismo título y contenido
- **THEN** se crean dos notas con UUID distintos

### Requirement: Representación pública y fechas
El sistema SHALL devolver únicamente `id`, `title`, `body`, `created_at` y `updated_at` por nota. El identificador SHALL ser UUID y las fechas UTC ISO 8601. Al crear, ambas fechas SHALL ser iguales; editar SHALL conservar `created_at` y asignar `updated_at` desde el reloj del servidor en cada edición exitosa.

#### Scenario: Representación segura
- **WHEN** se crea, consulta, lista o edita una nota
- **THEN** cada representación incluye exactamente los cinco campos públicos y ninguna identidad de propietario ni información de credenciales

#### Scenario: Fechas de creación y edición sin cambios de valor
- **WHEN** una nota se crea y posteriormente recibe un PATCH válido que repite un valor existente
- **THEN** las fechas iniciales son iguales, `created_at` no cambia y `updated_at` se vuelve a asignar para esa edición

### Requirement: Listado de notas propias
El sistema SHALL responder a `GET /notes` con `200` y un array de todas las notas del usuario autenticado, ordenado por `created_at` ascendente y después por `id` ascendente, sin paginación ni selector de propietario.

#### Scenario: Dos usuarios y fechas empatadas
- **WHEN** un usuario lista notas y existen notas suyas con fechas iguales y notas de otro usuario
- **THEN** recibe únicamente las suyas, ordenadas por fecha y UUID, incluyendo contenido y fechas

#### Scenario: Usuario sin notas
- **WHEN** un usuario sin notas invoca `GET /notes`
- **THEN** recibe `200` con `[]`

### Requirement: Consulta individual
El sistema SHALL responder a `GET /notes/{note_id}` con `200` y la nota propia correspondiente. Con autenticación válida, un identificador de ruta que no sea UUID SHALL producir `422` en consulta, edición y eliminación.

#### Scenario: Consulta de nota propia
- **WHEN** un usuario consulta el UUID de una nota suya
- **THEN** recibe `200` con el contenido persistido y la representación pública

#### Scenario: UUID malformado con autenticación válida
- **WHEN** un usuario autenticado consulta, edita o elimina una nota con un UUID malformado
- **THEN** recibe `422` sin mutación de notas

### Requirement: Edición parcial
El sistema SHALL aceptar `PATCH /notes/{note_id}` con uno o ambos campos editables y responder `200` con la nota actualizada después de confirmar la persistencia. SHALL conservar los campos omitidos y rechazar `{}` con `422`. Si cualquier campo enviado es inválido, SHALL rechazar toda la edición.

#### Scenario: Edición de un solo campo
- **WHEN** se envía únicamente un título válido o únicamente un contenido válido
- **THEN** cambia solo ese campo y `updated_at`, conservando el campo omitido, UUID y `created_at`

#### Scenario: Edición de ambos campos
- **WHEN** se envían un título y un contenido válidos
- **THEN** ambos cambios quedan confirmados juntos y se devuelve la nota actualizada

#### Scenario: PATCH vacío o parcialmente inválido
- **WHEN** se envía `{}` o se envía un campo válido junto a otro inválido
- **THEN** responde `422` sin cambiar campos ni timestamps

### Requirement: Concurrencia de ediciones
El sistema SHALL conservar cambios concurrentes sobre campos distintos y aplicar la última escritura efectiva sobre un mismo campo, sin versiones ni ETags. Si la eliminación se confirma antes de que una edición pueda actualizar la nota, esta SHALL responder `404` sin recrearla.

#### Scenario: Ediciones simultáneas de campos distintos
- **WHEN** dos peticiones concurrentes de una misma nota cambian únicamente el título y únicamente el contenido, respectivamente, y ambas tienen éxito
- **THEN** la lectura posterior conserva ambos cambios

#### Scenario: Ediciones simultáneas del mismo campo
- **WHEN** dos peticiones concurrentes cambian el título y ambas tienen éxito
- **THEN** el título final corresponde a la última escritura efectiva, sin combinar valores ni exigir una versión

#### Scenario: Eliminación antes de la actualización
- **WHEN** una nota es eliminada antes de que un PATCH pueda efectuar su actualización
- **THEN** el PATCH responde `404` y no vuelve a crear la nota

### Requirement: Eliminación de notas
El sistema SHALL responder a `DELETE /notes/{note_id}` con `204` sin cuerpo únicamente después de confirmar la eliminación de una nota propia. Una petición posterior sobre ese UUID SHALL responder `404`.

#### Scenario: Eliminación y repetición
- **WHEN** un usuario elimina una nota suya y repite la eliminación
- **THEN** la primera respuesta es `204` sin cuerpo, la segunda es `404` y la nota desaparece de consulta y listado

#### Scenario: Eliminaciones concurrentes
- **WHEN** dos peticiones intentan eliminar simultáneamente una nota propia
- **THEN** una elimina la nota y obtiene `204`; la otra obtiene `404`

### Requirement: Fallos y confirmación de persistencia
El sistema SHALL responder `503` con `{"detail":"Service unavailable"}` ante fallos operacionales de dependencias, y `500` con `{"detail":"Internal server error"}` ante fallos inesperados. SHALL confirmar las mutaciones antes de responder éxito y revertir escrituras fallidas; las respuestas no SHALL exponer detalles internos.

#### Scenario: Fallo de escritura antes de confirmar
- **WHEN** la persistencia de una creación, edición o eliminación falla y la transacción se revierte
- **THEN** responde `503`, sin creación parcial, cambios parciales ni pérdida de la nota previa

#### Scenario: Fallo de lectura o inesperado
- **WHEN** falla una dependencia de lectura o se produce un error inesperado en una operación de notas
- **THEN** devuelve respectivamente el `503` o `500` sanitizado y no revela SQL, credenciales ni excepciones internas

### Requirement: Compatibilidad de capacidades existentes
La incorporación de notas SHALL preservar los contratos existentes de registro, login, perfil y archivos. Las operaciones sobre notas no SHALL leer ni modificar contenido de archivos ni depender de una operación de almacenamiento de objetos.

#### Scenario: Regresión de recursos existentes
- **WHEN** se ejecutan los escenarios existentes de usuarios, autenticación y archivos con el feature de notas integrado
- **THEN** mantienen sus contratos actuales

#### Scenario: Notas sin acceso a almacenamiento de archivos
- **WHEN** un usuario ejecuta cualquiera de las cinco operaciones de notas
- **THEN** no se invocan operaciones de almacenamiento de archivos
