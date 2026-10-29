# Catálogo canónico — Fase 0

Fecha: 2026-10-28. Alcance autorizado: contratos, invariantes, caracterización y preparación técnica.

No se cambia código de aplicación, esquema, migraciones, datos de catálogo ni configuración.
No se conectan bases de datos ni proveedores. Los únicos artefactos nuevos son este documento,
las pruebas, su soporte sintético y el informe comparativo JSON. No se inicia la fase 1.
El repositorio contiene cambios previos ajenos a esta fase; no se revierten ni modifican.

## 1. Contrato de identidad compartida (propuesto, no implementado)

Habrá un solo servicio de identidad en `app/modules/books/canonical.py`, con una representación
SQL reutilizable por los procesos por lotes. No habrá un segundo algoritmo de equivalencia en ETL o IA.
La implementación SQL y la API Python del mismo servicio deberán tener pruebas de paridad.

Operaciones conceptuales:

| Operación | Entrada | Salida y garantías |
| --- | --- | --- |
| `resolve_canonical_work` | UUID histórico, versión de identidad opcional | UUID canónico, UUID solicitado, camino y versión; no escribe. Desconocido: error explícito, no crea. |
| `canonical_members` | UUID y versión | Miembros por relaciones confirmadas. Nunca inferir por título/autor. |
| `resolve_for_addition` | Referencia tipada, edición explícita opcional, actor, clave idempotente | Obra, edición nullable, evidencia y resultado; participa en la transacción del comando. |
| `current_reviews` | Obra canónica, versión/corte | Selecciones vigentes antes de aplicar visibilidad; común a listado, puntuación y analítica. |
| `canonical_projection` | Conexión/snapshot y corte | Relación SQL de UUID original a canónico para ETL, sin red ni commits internos. |

Referencias tipadas: `internal_work`, `google_volume`, `open_library_work`, `open_library_edition`.
Una referencia externa de descubrimiento no implica que el usuario eligiera su edición.
El frontend debe enviar esa selección de forma explícita. Una selección inválida se rechaza;
nunca se sustituye por la primera edición.

Una operación de incorporación devolverá `requested_reference`, `original_work_id`,
`canonical_work_id`, `edition_id` nullable, `library_entry_id`, `reading_id`,
`incorporation_id`, `identity_version`, `reused` y `verification_status`.
La forma HTTP definitiva se implementará conservando compatibilidad con los clientes actuales.

Estados de evidencia propuestos: `provisional`, `confirmed`, `contradictory`, `rejected`.
Un ISBN válido identifica publicación/edición, no demuestra por sí mismo la identidad de una obra.
Un identificador de obra externo requiere procedencia y verificación de la relación edición–obra.
Título y autor solo producen candidatos. Un dato del cliente no se acepta como verificación.

## 2. Invariantes y evidencia de cumplimiento

| ID | Invariante exigido | Situación actual / verificación pendiente |
| --- | --- | --- |
| C01 | Buscar o abrir ficha no crea obras, ediciones, autores o incorporaciones | Hoy Google busca e importa; ficha externa importa. Caracterización estática. La caché sí podrá escribirse. |
| C02 | Incorporar solo por biblioteca o importación administrativa autorizada | Futuro servicio; auditar también scripts de ingestión y semillas. |
| C03 | Ninguna fusión por título/autor | El servicio actual sí agrupa lógicamente; comparación ejecutable registra impactos. |
| C04 | UUID y relaciones históricas sobreviven a fusiones | Futuras redirecciones y auditoría; no usar la consolidación física actual. |
| C05 | Una selección canónica vigente de reseña por perfil personal y obra | Futura selección explícita; originales y revisiones intactos. |
| C06 | Visibilidad después de seleccionar vigencia | El SQL actual de puntuación lo cumple; listado actual no comparte deduplicación. |
| C07 | Lectura sin edición conserva `edition_id=NULL` | Modelo actual lo impide; no fabricar edición, ISBN, referencia, idioma ni páginas. |
| C08 | Una edición explícita se conserva | La ruta actual puede sustituirla al reutilizar bibliotecas equivalentes. Pendiente integración. |
| C09 | Idempotencia por referencia y selección idénticas | Claves y bloqueos existentes son parciales; pendiente PostgreSQL concurrente. |
| C10 | Incorporación atómica | Obra/referencia/edición/biblioteca/lectura/procedencia/idempotencia en un commit del comando. Pendiente pruebas de fallos. |
| C11 | Lecturas e historial nunca se pierden o se suman como lectores extra | Oráculo sintético prueba selección por lector y preservación de entradas; no prueba fusión real. |
| C12 | Todos los consumidores usan identidad y vigencia iguales | Hoy ETL/IA usan UUID físicos y joins obligatorios de edición. |
| C13 | Permiso administrativo real y confirmación explícita | Reutilizar `AccountPermission`; alinear `AdminGate` con backend. |
| C14 | Recuperación con actividad posterior investigable | Contrato de trazabilidad de la sección 4; no demostrado operacionalmente. |

Lectura sin edición: pendiente puede tener total desconocido. Al registrar avance por páginas se
solicita un total del intento al lector; no se deduce de una edición no elegida. No se inventará
un total para terminar una lectura. El contrato inicial conserva el requisito de total explícito
para eventos que lo necesitan; una futura lectura terminada sin páginas requeriría otra decisión.

Idempotencia: mismo actor, referencia normalizada y selección devuelve el mismo resultado.
Clave repetida con otro contenido produce 409. Actores distintos comparten obra y edición
cuando corresponda, pero tienen pertenencias independientes. Una referencia desconocida sin
autor también debe ser idempotente. Errores de proveedor no dejan incorporaciones parciales.
Cambiar de edición o restaurar una biblioteca archivada es una operación explícita diferenciada.

## 3. Comparación previa al cambio

`tests/catalog_phase0_support.py` invoca la función actual `equivalent_work_ids()` sobre un
doble de sesión que solo acepta sus SELECT conocidos. No ejecuta SQL.
El lado propuesto es un oráculo exclusivo de pruebas con relaciones confirmadas ficticias;
no constituye el futuro servicio. Métricas y asociaciones se calculan en memoria según la
semántica auditada, no ejecutando los endpoints ni el ETL de producción.

`docs/catalog-canonical-phase0-comparison.json` contiene ambas salidas y campos afectados:
miembros, reseñas visibles, promedio exacto, cantidad de valoraciones, estadísticas de lectura,
usuarios con biblioteca activa y asociaciones lectura–reseña.
Estas asociaciones no equivalen a la elegibilidad final de IA, que aplica más filtros.

| Escenario sintético | Resultado comparativo |
| --- | --- |
| Solo título/autor | Actual agrupa A+B: promedio 3, dos puntuaciones. Contrato separa A: promedio 5, una puntuación; cambian lectores, reseñas y asociaciones. |
| Traducción confirmada | Actual separa títulos distintos; contrato une y recupera asociación lectura A–reseña B. |
| Puente bilingüe transitivo | Actual agrupa A+B+C; contrato conserva A sin vínculos confirmados. |
| Última reseña oculta | Promedio ausente en ambos; listado actual muestra reseña pública vieja y el contrato no la presenta como vigente. |
| Mismo lector en ambas obras | Una puntuación y último estado de lectura; contrato muestra una sola reseña vigente. Lecturas archivadas no aportan lectores. |
| Autor desconocido | No aparece evidencia positiva ni agrupación por título. |

No se creó una línea base nueva de datos reales ni se infieren confirmaciones de los datos
inspeccionados en la auditoría anterior. Antes del reemplazo funcional se exige una comparación
en snapshot anonimizado y versionado, con resultados de SQL/endpoints/ETL reales y revisión
de todas las diferencias. Nunca confirmar automáticamente los grupos heredados para evitar cambios.

## 4. Fusión y recuperación: requisitos de implementación

No se invocará `consolidate_equivalent_works(reviewed=True)` en fase 0 ni se reutilizará su
borrado físico. Origen y destino serán explícitos; ambos UUID permanecerán consultables.

La simulación incluirá miembros completos de ambas identidades, versiones, bibliotecas,
lecturas, reseñas, valores públicos antes/después, decisiones de vigencia y conflictos de fuentes.
Cada conflicto exige decisión identificada; la vigencia por fecha solo es una sugerencia.
El oráculo de esta fase usa la más reciente para comparar, no autoriza esa política en la fusión.
Confirmación caducada o datos cambiados: 409 y nueva simulación. Prohibidos ciclos y destinos ambiguos.

La operación guardará actor autorizado, motivo, evidencia, clave idempotente, simulación,
decisiones, versión anterior/posterior y efectos antes/después. No sobrescribir procedencia.
Las relaciones originales de ediciones, bibliotecas, lecturas, reseñas y revisiones permanecen.
Si se edita un metadato del destino, su valor previo y origen se registran.

Toda escritura posterior relacionada con una obra fusionada deberá registrar como mínimo:
UUID/referencia solicitada, UUID físico usado, canónico resuelto, versión de identidad,
actor, instante, acción, entidad afectada y evidencia de la selección de edición cuando exista.
La cobertura incluye API, scripts, importaciones, eventos, cambios de biblioteca y reseñas.
Actividad sin esta trazabilidad bloquea habilitar fusiones: redirecciones y fotos previas no bastan.

Una reversión será compensatoria y auditada. Sin actividad posterior puede restaurar estados
previos; con actividad posterior debe simular la separación y asignar explícitamente los nuevos
registros ambiguos, preservando su historial. Nunca borrar contenido del lector para hacer rollback.
No se promete deshacer automáticamente cualquier fusión. Los ETL antiguos conservan corte y
versión de identidad; la corrección publica nuevas proyecciones, sin reescribir snapshots históricos.

## 5. Inventario concreto de preparación

| Área | Archivos / funciones afectadas en fases posteriores |
| --- | --- |
| Descubrimiento | `books/router.py`: `search_books`, `get_book`, `store_volume`, `work_payload`, `local_works`; `open_library_catalog.py`: `present`, `ensure_edition`, `store_selected`, `find_existing`. |
| Identidad | `books/identity.py`, `books/service.py`: `equivalent_work_ids`, `verified_work_for_import`, candidatos y consolidación; modelos y nuevas referencias. |
| Biblioteca | `library/models.py`, `schemas.py`, `router.py`: `resolve_book`, `add_to_library`, `my_readings`, eventos y archivo canónico. |
| Comunidad | `books/community.py`: `public_rating`, `reading_statistics`; `social/reviews_router.py`: validación, creación, edición, listados; `social/router.py`: feed y respuestas. |
| Analítica | `analytics/etl.py`: `extract`, validación y carga; `projections.py`: `refresh_catalog`, proyecciones por lector; `reader_evidence.py`, `recommendation_profiles.py`, `eligibility.py`, `book_transport.py`, comunidad y descubrimiento de pares. |
| IA | Revisar persistencia, contexto, perfiles, hashes/versiones y trabajos de recomendaciones; evitar unir reseñas solo por UUID físico o descartar lecturas por joins de edición. |
| Administración | Nuevo servicio/router de catálogo; `users/roles_router.py:get_admin`, `AccountPermission`, registro en `app/main.py`; conservar autenticación de sesión actual. |
| Ingestión | `scripts/run_catalog_ingest.py`, `load_popular_*_books.py`, semillas: documentar autorización y contexto de incorporación. |
| Frontend | `booksService.js`, `LibraryContext.jsx`, `BooksPage`, `BookDetailPage`, `BookExperience`, `LibraryBookPage`, `ReadingPage`, `BookReviews`, `AdminGate`, `App`, `Layout`. |

La fase 1 será aditiva. Hacer nullable `lecturas.edition_id` exige revisar también esquemas de
respuesta, joins de feed, ETL, campos analíticos y comparaciones `edition_updated_at < cutoff`.
No habilitar escrituras NULL hasta desplegar lectores compatibles. No poblar relaciones
confirmadas con `identity_key`; conservarlo como dato heredado, no prueba de identidad.

## 6. Pruebas ejecutadas y límites

Desde `apps/backend`:

```powershell
.\.venv\Scripts\python.exe -B -m unittest tests.test_catalog_phase0 -v
```

Resultado final: **20 pruebas correctas**, sin skips ni expected failures. Suite con bloqueos
explícitos de `Engine.connect`, `socket.connect` y `socket.create_connection` durante los casos.
No se ejecutan suites existentes con `flush`, `commit`, SQLite temporal o PostgreSQL.
No se importa `app.main`, ni se inicia API/worker. Registrar modelos y construir consultas no
abre conexiones. La opción `-B` evita generar bytecode.

Cobertura: algoritmo real de agrupación sobre doble de sesión; normalización real; metadatos
de nulabilidad; compilación del SQL real de puntuación; inspecciones AST de rutas y joins;
seis comparaciones sintéticas y casos adicionales de privacidad, autor distinto, puntuación
ausente, preservación de datos opcionales, determinismo y rechazo de ciclos en el oráculo.

Las comprobaciones AST son alarmas de caracterización del código actual, no pruebas funcionales.
Durante el cambio deberán sustituirse por tests del comportamiento autorizado. Los tests del
oráculo no demuestran que exista el servicio, el esquema futuro o la herramienta de fusión.

No comprobado todavía: checksum/reutilización de ISBN en todos los importadores, transacciones
y concurrencia real, permisos de futuros endpoints, roundtrip completo sin edición, migraciones,
paridad SQL/Python canónica, rendimiento, reversión y actividad posterior a una fusión.

Generación reproducible del informe, sin acceso a DB/red, desde `apps/backend`:

```powershell
.\.venv\Scripts\python.exe -B -c "import json; from pathlib import Path; from tests.catalog_phase0_support import report; Path('../../docs/catalog-canonical-phase0-comparison.json').write_text(json.dumps(report(), ensure_ascii=False, indent=2) + '\n', encoding='utf-8')"
```

## 7. Riesgos y puertas de avance

Riesgos detectados: cambios de puntuaciones al retirar agrupaciones heredadas; referencias de
traducción no aprovechadas; listado público y puntuación con vigencias diferentes; lecturas sin
edición excluidas por joins; validación de edición equivalente incompatible con FK física;
selección de edición sobrescrita; bloqueo/idempotencia no uniformes; permisos UI/backend
divergentes; catálogo analítico limitado a Google; falta de versión histórica de identidad.

Antes de comenzar fase 1:

1. Aprobación explícita de fase 1; esta autorización solo cubre fase 0.
2. Revisar contratos C01–C14 y las diferencias sintéticas; acordar que ninguna divergencia
   heredada se resolverá por fusión automática.
3. Fijar el head Alembic real y conciliar cambios existentes. La auditoría anterior detectó
   una base local en 0052 y archivos posteriores; no asumir que local, pruebas y producción coinciden.
4. Preparar PostgreSQL desechable y datos sintéticos para futuras pruebas con escritura;
   credenciales distintas y comprobación del destino. Nada de pruebas de integración en producción.
5. Revisar SQL de migraciones aditivas y estrategia de despliegue lector-antes-de-escritor.
6. Definir respaldo/restauración y un ensayo verificable antes de aplicar esquema a datos reales.

Antes de sustituir agrupación o habilitar fusiones (puertas posteriores, no confundir con M1):

- Comparativa sobre snapshot anonimizado con diferencias aprobadas de miembros, vigencia,
  puntuaciones, lectores, biblioteca, asociaciones y elegibilidad de recomendaciones.
- Pruebas de concurrencia multi-conexión, reintentos, fallos intermedios y no persistencia GET.
- Roundtrip sin edición en API/UI/feed/ETL/IA sin fabricar metadatos.
- Paridad del servicio compartido y su proyección SQL; versión consistente por snapshot.
- Auditoría de escrituras posteriores, simulación, permisos, conflictos y recuperación ensayada.
- Posibilidad de desactivar funcionalidades nuevas sin desplegar un binario incompatible con NULL
  o redirecciones. No degradar esquema eliminando información nueva para volver atrás.
