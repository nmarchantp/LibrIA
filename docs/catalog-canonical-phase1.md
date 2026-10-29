# Catálogo canónico — Fase 1: preparación de almacenamiento

Fecha: 2026-10-28. Implementación limitada a esquema aditivo y compatibilidad de tipos.
No se aplicó ninguna migración a desarrollo, producción ni a la instancia local de pruebas
existente. No se implementa ni activa resolución canónica, incorporación nueva, lectura sin
edición o fusión administrativa. Se mantienen las reglas funcionales anteriores.

## Conciliación de Alembic

Antes del cambio: 54 revisiones, una base `0001_auth_users`, un head
`0054_gemini_ledger_dna`, sin ramas ni dependencias ausentes. La longitud máxima de los
identificadores existentes es 32, compatible con `alembic_version.version_num`.
No fue necesario editar, renumerar, unir, hacer stamp ni ejecutar migraciones históricas
en ninguna base existente.

Cadena nueva:

```text
0052_ai_usage_calls
  -> 0053_versioned_reading_analysis
  -> 0054_gemini_ledger_dna             (baseline anterior)
  -> 0055_catalog_foundation           (cinco tablas vacías)
  -> 0056_catalog_nullable_edition     (nuevo único head)
```

`catalog-canonical-phase1-results.json` conserva los nombres, revisiones y SHA-256 de las
54 migraciones previas y las dos nuevas. Las 54 existentes se ejecutaron desde cero
exclusivamente en PostgreSQL desechable. No se consultó el estado actual de Alembic de
bases persistentes; su revisión deberá comprobarse antes de autorizar un despliegue.
La referencia a una base local en 0052 pertenece a la auditoría anterior, no a una nueva
inspección ni actualización de esa instancia.

## Cambios realizados

| Archivo | Cambio |
| --- | --- |
| `migrations/versions/0055_catalog_canonical_foundation.py` | Estructuras, índices, restricciones y triggers solo en tablas nuevas. No contiene backfill ni consolidación. |
| `migrations/versions/0056_catalog_nullable_edition.py` | Relaja exclusivamente `edition_id` en `app.lecturas` y `analytics.hechos_lectura`. No cambia valores ni claves foráneas. |
| `app/modules/books/catalog_models.py` | Modelos ORM de las cinco tablas nuevas. |
| `migrations/env.py` | Registro de esos modelos en metadatos Alembic. |
| `app/modules/library/models.py` | `Reading.edition_id` nullable en ORM. |
| `app/modules/library/schemas.py` | Respuestas `ReadingState` y `ReadingEventResponse` capaces de representar `edition_id=null`. |
| `app/core/config.py`, `.env.example` | Tres capacidades apagadas; activar cualquiera se rechaza al validar configuración. `.env` no se modifica. |
| `scripts/validate_catalog_phase1.py` | Entorno desechable propio, conciliación, snapshots, fallo DDL deliberado, migraciones y suites. No admite una URL de destino del operador. |
| `tests/test_catalog_phase1.py` | Pruebas de esquema, compatibilidad, preservación, restricciones, rollback y concurrencia. |
| `tests/test_catalog_phase0.py` | Un caso se actualiza: nullable del ORM ahora caracteriza preparación de fase 1. El baseline histórico de fase 0 permanece documentado. |

No se modifican búsqueda, fichas, funciones de agrupación/importación, reseñas, promedios,
ETL, recomendaciones, rutas administrativas ni interfaz. Por tanto, los problemas funcionales
de la auditoría siguen pendientes de sus fases; no deben interpretarse como corregidos.

## Estructuras y garantías de almacenamiento

### `app.operaciones_catalogo`

Registro inmutable por operación completada: UUID, actor FK, tipo, clave de solicitud,
hash SHA-256 del contenido, obra origen opcional, destino obligatorio, motivo, evidencia,
contexto, instante y operación compensada en caso de reversión.

- Tipos: `library_add`, `admin_import`, `merge`, `reversal`.
- Único `(actor_user_id, operation_type, request_key)`.
- Hash debe contener 64 caracteres hexadecimales minúsculos.
- Una fusión exige origen y destino distintos; otras operaciones no usan origen.
- Una reversión exige referencia a la operación previa.
- `identity_version` es una identidad bigint única asignada por PostgreSQL.
- Índices por destino/fecha y por origen no nulo.
- Claves compuestas auxiliares permiten comprobar actor, destino y par origen/destino.
- Trigger rechaza UPDATE y DELETE: correcciones mediante operaciones compensatorias.

La secuencia asigna identificadores, no prueba orden de commit; puede contener huecos.
No se utiliza todavía como versión global de snapshots. El futuro servicio deberá coordinar
la asignación y el corte bajo el bloqueo de identidad antes de publicar versiones canónicas.

### `app.referencias_obras`

Referencia externa de obra interna, proveedor, tipo, identificador externo, estado,
evidencia JSON, verificador/fecha y operación de procedencia.

- Google admite `volume`; Open Library admite `work` y `edition`.
- Estados: `provisional`, `confirmed`, `contradictory`, `rejected`.
- Una confirmación requiere evidencia no vacía, verificador y fecha.
- Índice único parcial por proveedor/tipo/identificador para enlaces provisionales o
  confirmados. También se reserva la referencia provisional: evita duplicados sin autor.
- Candidaturas contradictorias/rechazadas pueden coexistir; no constituyen enlaces activos.
- FK compuesta comprueba que la operación apunta a la misma obra.
- Índices por obra y operación.

El esquema verifica presencia y coherencia relacional, no la verdad de la evidencia. No hay
normalizador, checksum ISBN ni política de confianza nuevos en esta fase. Las referencias
no se extraen automáticamente de `identity_key`, fuentes ni coincidencias de títulos.
Las futuras revisiones de evidencia deberán conservar antes/después en el servicio auditable;
no se implementa todavía ese ciclo de vida.

### `app.incorporaciones_catalogo`

Procedencia de una incorporación: operación única, actor, origen `library`/`admin_import`,
obra, edición opcional, indicador de selección explícita, biblioteca opcional, referencia
opcional y referencia solicitada en JSON.

- FK compuesta a operación/actor y operación/destino.
- Edición, biblioteca y referencia deben pertenecer a la misma obra física.
- `edition_selected` equivale a que `edition_id` no sea NULL.
- Origen biblioteca requiere entrada; importación administrativa no la utiliza.
- Trigger verifica propietario de biblioteca y correspondencia del origen con el tipo
  de operación. Las autorizaciones administrativas pertenecen al futuro servicio/API.
- Índices por obra/fecha y actor/fecha.
- UPDATE y DELETE rechazados para preservar procedencia.

### `app.redirecciones_obras`

Historial de vínculos origen/destino con operación de fusión, vigencia y operación de retiro.

- Ambos UUID siguen apuntando a `app.obras`; no se eliminan ni reasignan registros históricos.
- FK compuesta exige el par exacto de la operación auditada.
- Una sola redirección activa por origen; índice parcial por destino activo.
- El trigger impide ciclos, borrar filas, reescribir identidades o reactivar filas retiradas.
- Retirar requiere una operación de reversión que compense la fusión original.
- Una nueva decisión puede coexistir con una redirección retirada, sin borrar esa fila.
- Bloqueo transaccional de grafo `pg_advisory_xact_lock(73155,1)`.
- Escrituras del grafo requieren `READ COMMITTED`; se rechazan otros aislamientos para
  impedir validaciones con snapshots repetibles obsoletos. El futuro servicio tomará el
  mismo bloqueo antes de resolver y escribir, no solo al insertar la redirección.

Esto valida estructura del grafo, no autoriza fusiones. No existe endpoint para poblarlo.

### `app.efectos_operacion_catalogo`

Diario inmutable de efectos: operación, ordinal único, tabla/UUID afectado, antes/después
JSON e instante. Exige al menos una imagen; ambas deben ser objetos JSON si existen.
Índice por tabla/UUID permite investigar una entidad. No se usa FK polimórfica para que
las imágenes históricas sobrevivan a cambios futuros de representación.

Todas las FK nuevas son restrictivas; no hay eliminación en cascada. Se revocan permisos
PUBLIC sobre las cinco tablas. No se crean roles ni se amplían permisos existentes.
Los triggers de inmutabilidad protegen UPDATE/DELETE, no sustituyen separación de roles,
control de TRUNCATE, privilegios de propietario/superusuario ni almacenamiento externo de
auditoría; esos permisos deben revisarse antes de habilitar escritores en fases posteriores.

## Edición nullable sin activación

`0056` elimina solo NOT NULL en dos columnas. UUID, índices, FK compuestas, restricciones
de estado/páginas y valores existentes se conservan. Una edición no nula incorrecta sigue
siendo rechazada por PostgreSQL. Una lectura pendiente NULL no crea edición ni páginas.

La API actual sigue resolviendo una edición como antes. No se añade ruta ni rama que
genere lecturas NULL. Feed, ETL e IA todavía no soportan todas esas lecturas: no se insertarán
manualmente en una base persistente ni se habilitarán hasta adaptar sus consumidores.

Configuración incorporada:

```dotenv
CATALOG_CANONICAL_ENABLED=false
CATALOG_EDITIONLESS_ENABLED=false
CATALOG_ADMIN_MERGE_ENABLED=false
```

En esta versión, `true` provoca error de configuración; no basta cambiar una variable para
activar funcionalidad incompleta. Los procesos existentes conservan sus rutas funcionales.

## Validación reproducible y aislamiento

Ejecutado desde `apps/backend`:

```powershell
.\.venv\Scripts\python.exe -B -m scripts.validate_catalog_phase1
```

El validador únicamente crea un contenedor cuyo nombre y etiqueta contienen un UUID propio:

- Imagen local `postgres:17-alpine`, sin descargas implícitas (`--pull=never`).
- PGDATA en tmpfs de 256 MiB, sin volúmenes persistentes ni montajes del workspace.
- Puerto aleatorio publicado únicamente en `127.0.0.1`.
- Usuario/base de nombre exclusivo y contraseña aleatoria no incluida en el informe.
- Marca aleatoria de propiedad en el comentario de la base.
- No inicia API, scheduler ni worker; el proceso de pruebas utiliza credenciales desechables.
- Comprueba destino/propiedad antes de ejecutar las pruebas de escritura.
- Finalmente verifica la etiqueta, detiene solo su contenedor `--rm` y comprueba que no queda.
- No utiliza ni actualiza `.env`; las variables de conexión solo existen en los hijos de prueba.

### Resultados

Informe estructurado: `docs/catalog-canonical-phase1-results.json`.

| Comprobación | Resultado |
| --- | --- |
| Cadena histórica desde base hasta 0054 | Correcta, 54 revisiones |
| Regresiones sobre 0054 | 83 pruebas correctas |
| Datos previos capturados | 71 tablas, 165 filas, incluidos datos sintéticos y semillas de migraciones históricas |
| Fallo deliberado después del DDL 0055/0056 | Rollback completo; nuevas tablas ausentes y NOT NULL restaurado |
| Upgrade Alembic 0054 → 0056 | Correcto |
| Filas previas | Idénticas mediante comparación de JSON de todas las tablas previas |
| Restricciones previas | Conservadas, comparando nombre y definición |
| Tablas nuevas tras migrar | Cinco, vacías |
| Suites después de migrar | 133 pruebas correctas: 20 de fase 0, 30 de fase 1 y 83 regresiones |
| Repetición de upgrade head | Sin cambio de datos |
| Aislamiento/limpieza | Contenedor desechable eliminado; ninguna base persistente accedida |

Las regresiones incluyen `test_catalog_mirror`, `test_open_library`, `test_book_community`,
`test_reviews` y `test_bibliographic_identity`. Algunas pruebas bibliográficas usan SQLite en
memoria por su diseño anterior; las nuevas pruebas de esquema/concurrencia y las suites que
usan el engine de aplicación se dirigen al PostgreSQL desechable.

Se comprueban referencias duplicadas, evidencia de confirmación, selección explícita,
propietario/origen de incorporación, historia inmutable, FK históricas, retiro compensatorio,
rollback de operación+referencia, carreras de clave idempotente y referencia, y dos
redirecciones opuestas simultáneas. La carrera tiene un ganador y un rechazo; no es todavía
la respuesta idempotente de un futuro comando HTTP.

El ensayo DDL deliberado utiliza las funciones `upgrade()` exactas dentro de una transacción
SQLAlchemy/Alembic Operations, inyecta división por cero y comprueba rollback. El upgrade
normal y su repetición sí recorren el entorno Alembic real. No se ensaya downgrade destructivo.

La suite existente emite una advertencia de deprecación Starlette/httpx y logs de fallos de
proveedor simulados; no producen fallos ni se cambian dependencias como parte de esta fase.

## Recuperación y condiciones para un despliegue futuro

Los upgrades son DDL transaccional de PostgreSQL. Ambas revisiones usan `lock_timeout=5s`:
si no obtienen bloqueos, fallan y se revierte la transacción. No llevan DML sobre tablas previas.
Las claves restrictivas y los triggers nuevos solo afectan tablas nuevas, inicialmente vacías.

`downgrade()` se bloquea explícitamente para no borrar evidencia ni forzar NOT NULL sobre
historia futura. Si falla el upgrade, corregir la causa y reintentar tras comprobar revisión.
Después de un commit, preferir corrección aditiva hacia delante, sin borrar tablas ni datos.
Desactivar capacidades no requiere retirar el esquema. Restaurar un respaldo completo es
último recurso y debe considerar actividad posterior, nunca borrar selectivamente historia.

Antes de desplegar sobre una base persistente:

1. Obtener autorización posterior explícita. Esta preparación no autoriza ese despliegue.
2. Comprobar revisión real, esquema y deriva de la base destino con acceso autorizado.
   Si está antes de 0054, las migraciones anteriores tienen sus propios cambios de datos:
   requieren evaluación independiente; no están autorizados por este parche aditivo.
3. Verificar hashes de revisiones revisadas, permisos, respaldo/restauración ensayados y
   capacidad de obtener bloqueos en ventana controlada. El ensayo sintético no mide carga real.
4. Revisar el SQL 0054:0056 y ejecutar únicamente Alembic autorizado. No usar
   `scripts.migrate_and_seed`, arranque de stack ni scripts de setup como sustituto: pueden
   ejecutar semillas/importaciones fuera del alcance. No ejecutar `stamp` para eludir revisiones.
5. Mantener las tres capacidades en false; no permitir escritores de tablas canónicas nuevos.
6. Coordinar despliegue: `schema-check --check-heads` de compose bloqueará un binario con
   head 0056 sobre una base en 0054. No arrancar el stack automáticamente antes de autorizar
   y aplicar esquema. Volver a un binario viejo también puede fallar su control de head.
7. Verificar postdespliegue: revisión, nulabilidad, FK originales y cinco tablas vacías;
   no hay backfill, activación ni fusión como parte de esta fase.

Antes de activar capacidades en fases posteriores se exige servicio único canónico,
consumidores NULL completos, comparativas sobre snapshot anonimizado, selección vigente
de reseñas, permisos administrativos, simulación/conflictos y trazabilidad de actividad
posterior a fusiones. Las cinco tablas preparadas no demuestran por sí solas esas garantías.

Riesgos restantes: reglas heredadas de agrupación siguen vigentes; servicio de incorporación
atómica e idempotente aún no existe; autoridad bibliográfica y normalización de referencias
necesitan política y pruebas; la secuencia no es un reloj de commits; no se ha medido bloqueo
en producción; no hay recuperación funcional con actividad posterior ni cambio de ETL/IA.
No habilitar fusiones hasta cerrar esas condiciones.
