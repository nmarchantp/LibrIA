# Catálogo canónico — fase 4

Fecha: 2026-10-28. Fase implementada y verificada en PostgreSQL desechable. **Sin activación pública, sin migraciones ni escrituras en bases persistentes.** No se realizaron fusiones, saneamientos ni cambios de UUID históricos.

## Resultado funcional

Las lecturas conservan `work_id` obligatorio y admiten `edition_id=NULL`. Agregar una obra no selecciona su primera edición, aunque existan ediciones disponibles. Las publicaciones seleccionadas explícitamente conservan su edición exacta. El total de páginas bibliográfico no se copia al intento en el flujo nuevo.

Una lectura puede comenzar, registrar páginas observadas, corregirlas, finalizar o abandonarse con total desconocido. En ese caso `total_pages` y `progress_percent` permanecen nulos: finalizar establece el estado y la fecha, sin inventar un total ni un porcentaje. Si al finalizar no se proporciona una página final, se conserva la última registrada. Una página final explícita no puede retroceder.

El lector puede declarar un total positivo en el intento. Esto modifica únicamente `lecturas.total_pages`; no modifica `ediciones.page_count`. Los eventos anteriores conservan el total que tenían cuando se registraron. Un intento cerrado no admite cambios posteriores de páginas mediante el nuevo comando.

Seleccionar posteriormente una edición es una operación explícita: conserva el ID del intento, progreso, páginas declaradas, fechas, cuaderno y eventos; no cambia una edición previamente seleccionada. Hay auditoría antes/después, propiedad del lector y protección frente a concurrencia. Repetir la misma selección no duplica la auditoría.

## Activación y compatibilidad

Los valores predeterminados siguen siendo:

```dotenv
CATALOG_DISCOVERY_ENABLED=false
CATALOG_EDITIONLESS_ENABLED=false
CATALOG_CANONICAL_ENABLED=false
CATALOG_ADMIN_MERGE_ENABLED=false
```

El segundo indicador solo puede configurarse junto con el primero. Su combinación se utilizó únicamente en pruebas aisladas. No se modificó `.env`. La configuración todavía rechaza agrupación canónica global y fusión administrativa.

Los auxiliares de lectura de datos se prepararon para nulos; las incorporaciones y comandos nuevos permanecen protegidos por configuración. El camino público antiguo se conserva cuando los indicadores están apagados. La compatibilidad con datos sin edición no implica autorización para activar el despliegue.

## Contratos API

| Ruta | Contrato preparado |
| --- | --- |
| `POST /api/readings/library` | Obra interna mediante `book_ref=UUID`, sin `edition_id`, incorpora sin edición. La selección interna explícita lleva `edition_id`; la externa lleva referencia tipada y `edition_selected=true`. |
| Misma ruta con referencia externa | `edition_selected=false` permite incorporar solo la obra usando evidencia consultada por servidor. No crea una edición ni una fuente de publicación nueva que el lector no seleccionó. Registra referencia, procedencia y recibo. |
| `POST /api/readings/events` | `page_count` opcional/nulo. `progress` y `correction` requieren `current_page`; los eventos posteriores al inicio conservan `reading_id`. Si se envía un total debe coincidir con el intento; declararlo/cambiarlo usa la ruta específica. |
| `PATCH /api/readings/{reading_id}/total-pages` | Total positivo declarado para ese intento; no menor que la página actual. Los intentos cerrados devuelven 409. |
| `PATCH /api/readings/{reading_id}/edition` | Nueva ruta, cuerpo `{ "edition_id": "UUID" }`. Solo titular; solo transición desde nulo o repetición de la selección actual. Edición ajena: 422; sustitución de edición elegida: 409; indicador apagado: 404. |
| `GET /api/readings/me` | Incluye lecturas sin edición. `edition_id`, `total_pages` y `progress_percent` pueden ser nulos. Añade `edition_optional` para adaptar la interfaz. |
| `GET /api/readings/{reading_id}/history` | Conserva eventos de ese intento, incluidos sus totales nulos originales. |
| `GET /api/readings/library/{work_id}/attempts` | Nueva ruta privada para descubrir todos los intentos propios de la obra, también los anteriores a una relectura. Protegida por el indicador de fase 4. |
| Fichas, reseñas y mural | Las fichas de obra no eligen edición por defecto. Las reseñas siguen asociadas a `work_id` con edición opcional. Los avances sin total muestran la página, sin porcentaje inventado. |

Ejemplo de incorporación de obra existente:

```json
{
  "book_ref": "UUID-de-la-obra",
  "book_title": "Texto de presentación",
  "edition_id": null,
  "edition_selected": false
}
```

Se conserva `Idempotency-Key` de fase 3. `book_title` y `page_count` de la incorporación no son evidencia bibliográfica ni actualizan el catálogo. Las referencias antiguas a publicaciones conservan su interpretación de compatibilidad; para expresar una incorporación externa sin edición se usa la referencia tipada con `edition_selected=false`.

La selección posterior solo admite ediciones de la **misma obra física** del intento, de acuerdo con la FK compuesta. No reasigna el intento a otro UUID ni utiliza similitud de título y autor. Las transiciones entre obras históricas relacionadas siguen requiriendo el procedimiento futuro correspondiente.

## Migración preparada

`0057_reading_optional_progress`, sucesora de `0056_catalog_nullable_edition`. El grafo tiene 57 revisiones y una única cabecera. 0055 y 0056 no se modificaron; sus hashes coinciden con la evidencia anterior.

Cambios de esquema, sin DML de reclasificación ni modificación de filas:

- Mantiene `lecturas.work_id NOT NULL` y las FK de obra/biblioteca y obra/edición. La edición ya era nullable desde 0056.
- Sustituye únicamente `ck_lecturas_started` y `ck_lecturas_finished` por versiones compatibles con total desconocido. Conserva estados válidos, fechas coherentes, páginas no negativas y correspondencia con el total cuando este se conoce.
- Hace nullable `eventos_lectura.total_pages` y `analytics.hechos_lectura.total_pages`. Mantiene las validaciones de intervalos para totales conocidos. La edición de los hechos analíticos ya era nullable desde 0056.
- Añade `uq_lecturas_id_work` para referenciar de forma compuesta el intento y su obra.
- Añade `app.selecciones_edicion_lectura`: UUID, instante, actor, intento, obra, edición y snapshots antes/después. FK restrictivas, correspondencia compuesta con intento/obra y edición/obra, unicidad por intento e índice `(actor_user_id,created_at)`.
- Trigger que impide UPDATE/DELETE de la auditoría. No se borran tablas, claves históricas ni relaciones.

DDL transaccional con `lock_timeout=5s`. El downgrade se rechaza expresamente: no debe reimponerse NOT NULL ni eliminarse historial nuevo. La FK compuesta de edición sigue comprobándose cuando `edition_id` no es nulo.

## Archivos modificados

Rutas relativas a `apps/backend/`, salvo donde se indica lo contrario. Se preservaron cambios ajenos que ya existían en el workspace.

| Área | Archivos |
| --- | --- |
| Configuración | `.env.example`, `app/core/config.py` |
| Biblioteca y comandos | `app/modules/library/{models,schemas,router}.py`; nuevo `commands.py` |
| Resolución y presentación | `app/modules/books/{resolution,facade,library_view,discovery,router}.py` |
| Mural | `app/modules/social/router.py` |
| ETL e IA | `app/modules/analytics/{etl,recommendation_profiles,gemini_worker}.py` |
| Migración | Nuevo `migrations/versions/0057_reading_optional_progress.py` |
| Validadores | `scripts/validate_catalog_phase1.py`; nuevo `scripts/validate_catalog_phase4.py` |
| Pruebas backend | `tests/test_catalog_phase{0,1,3}.py`; nuevo `tests/test_catalog_phase4.py` |
| Frontend (`apps/web/`) | `src/context/LibraryContext.jsx`, `src/services/{booksService,librarySelection}.js`, nuevo `src/services/readingState.js`, `src/pages/{BookDetailPage,LibraryBookPage,ReadingPage,LibraryPage}.jsx` |
| Pruebas frontend | Nuevo `apps/web/tests/reading-optional-edition.mjs` |
| Documentación | Este informe, `catalog-canonical-phase4-results.json`, `catalog-canonical-phase4-benchmark.json`, `catalog-canonical-phase4-frontend-results.json` |

## Estadísticas, ETL y recomendaciones

Se retiraron los joins obligatorios con edición de la extracción de eventos, el perfil nocturno, el contexto individual de IA y el mural. Los consumidores no sustituyen la edición nula por otra del catálogo.

El ETL valida la correspondencia de edición solo cuando hay edición; conserva el total registrado en cada evento en lugar de exigir que todos los eventos coincidan con el total actual del intento. La versión de transformación es `daily-v5-editionless`, compatible con el límite existente de 20 caracteres.

La métrica de páginas agrega diferencias de páginas observadas/declaradas, incluidas correcciones. Un cierre con total desconocido no extrapola páginas. La prueba integral registra 31 páginas, finaliza sin total y comprueba 31 páginas en L10 y una finalización en L05. La biblioteca y las estadísticas por género cuentan la obra actual una vez; las relecturas siguen siendo intentos diferentes, no obras adicionales. L05 cuenta finalizaciones de intentos, de acuerdo con su definición existente.

Las reseñas sin edición generan puntuación de obra y evidencia personal. El perfil nocturno conserva las reglas de elegibilidad existentes —lectura finalizada y reseña suficiente— sin exigir edición. Los campos bibliográficos no disponibles permanecen nulos. Se comprueba también que una edición seleccionada después de un cutoff no aparezca retroactivamente en el perfil de ese cutoff.

Se verificaron extracción, transformación, publicación real de hechos y persistencia de `ia.reader_profile_versions` en la transacción desechable. No se ejecutaron llamadas reales de IA ni se arrancaron workers. La selección bibliográfica de candidatos de recomendación sigue siendo una política aparte; esta fase adapta la evidencia del lector, sin cambiar las reglas de candidatos ni la agrupación global del catálogo.

## Pruebas ejecutadas

Desde `apps/backend`:

```text
.venv/Scripts/python.exe -B -m scripts.validate_catalog_phase4
```

**286 pruebas correctas, sin fallos ni omisiones**, en PostgreSQL 17.11 desechable. Incluyen las regresiones anteriores y módulos adicionales de ETL diario, perfiles nocturnos, géneros y reflexiones. Las 83 pruebas de baseline también se ejecutaron antes de migrar; están incluidas en las 286 y no deben sumarse como casos distintos.

Se comprobaron incorporación con/sin edición, ISBN y referencias de fases anteriores, ciclo completo sin total, total declarado del intento, selección posterior, recarga, reseña/puntuación de obra, historial de relecturas y privacidad, correspondencia de FK, auditoría inmutable, selección concurrente con progreso, rollback de incorporación/eventos/selección y compatibilidad histórica. La prueba antigua que esperaba exclusión por falta de edición se reemplazó por el contrato aprobado; los demás casos comparativos de identidad se conservaron.

El validador creó exclusivamente su propio contenedor tmpfs, sin volúmenes persistentes y con puerto loopback. Comparó 71 tablas y 165 filas históricas sintéticas antes/después, verificó rollback ante fallo de DDL inyectado, preservación de las restricciones salvo las dos relajaciones declaradas y upgrade repetido sin cambios. El contenedor se eliminó al finalizar. Los tests nocturnos anteriormente optativos se habilitaron únicamente dentro de este harness.

Desde `apps/web`:

- `node tests/library-selection.mjs`: correcto; compatibilidad de selecciones de fase 3.
- `node tests/reading-optional-edition.mjs`: correcto; selección opcional/explícita, recarga, total desconocido, total declarado, selección posterior y compatibilidad antigua.
- ESLint dirigido a los ocho archivos fuente de frontend afectados: correcto.
- `npm.cmd run build`: correcto, 1713 módulos; advertencia de bundle de 505.63 kB.

No se ejecutó automatización de navegador en esta fase. Las pruebas frontend cubren las funciones de selección y estado; las de backend recorren las rutas HTTP reales con PostgreSQL. Queda pendiente verificar las interacciones completas en navegador y los proveedores reales antes de habilitar.

La medición concurrente repetida desde fase 3 se conserva en el artefacto específico de fase 4: medianas 54.40/73.50/158.19ms para concurrencia 1/2/4. Es una regresión sintética de incorporaciones con edición y proveedores simulados; no mide capacidad productiva ni sustituye la prueba de concurrencia de selección/progreso.

## Riesgos y recuperación

1. Ninguna migración persistente está autorizada. Para un despliegue posterior hay que revisar versión real, respaldo, permisos de la nueva tabla/función y ventana de bloqueo de DDL/índice único sobre lecturas. Repetir la validación sobre un clon autorizado representativo del volumen real.
2. Desplegar API, frontend, ETL y workers compatibles antes de activar. Todos deben compartir la configuración; no mezclar versiones antiguas que descarten lecturas sin edición. Los clientes que supongan porcentajes o totales no nulos necesitan actualización.
3. Tras existir lecturas nulas reales, apagar los indicadores o volver al binario antiguo puede ocultarlas en ramas heredadas. La recuperación segura conserva los lectores compatibles y suspende comandos de escritura mediante mantenimiento. No fabricar ediciones, cambiar UUID, borrar intentos ni reimponer NOT NULL para facilitar un rollback.
4. Los casos inválidos devuelven errores y rollback; ante error operativo se reintenta con la misma clave idempotente en incorporaciones. La selección repetida es segura; los eventos cerrados rechazan repeticiones incompatibles. Los comandos usan transacción externa, actor antes de intento y la política de timeout/reintento de fase 3.
5. La auditoría registra la selección explícita, pero esta entrega no permite sustituir una edición ya elegida, deshacer selecciones ni fusionar obras. Una corrección de identidad necesita un procedimiento posterior revisado y auditable.
6. Siguen pendientes las diferencias de agrupación lógica entre reseñas, puntuaciones y analítica identificadas en fases anteriores. La compatibilidad con nulos está probada; no equivale a haber completado la unificación canónica transversal de fase 5. Revisar comparativas antes de cualquier cambio en esa semántica.

## Condiciones para iniciar fase 5

- Aceptar la entrega de fase 4 y mantener desactivadas las capacidades hasta autorizar su despliegue.
- Ejecutar las comparativas de identidad sobre un snapshot autorizado: reseñas vigentes, puntuaciones, estadísticas, bibliotecas, asociaciones de lectura y evidencia de recomendaciones, incluidos los casos nulos. No reemplazar agrupaciones lógicas sin revisar las diferencias.
- Diseñar el uso compartido del servicio canónico en los consumidores restantes y la deduplicación de valoraciones vigentes sin perder relecturas ni versiones históricas.
- Completar pruebas de navegador, revisión de contratos de clientes, proveedores reales y carga de DDL en clon antes de habilitar las fases 3/4.
- Mantener las fusiones apagadas hasta contar con simulación, resolución explícita de conflictos, confirmación administrativa, auditoría, UUID históricos y recuperación incluso con actividad posterior.

Esta entrega no activa ni ejecuta ninguna de esas operaciones de fase 5.
