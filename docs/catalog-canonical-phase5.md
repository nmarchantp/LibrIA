# Catálogo canónico — fase 5

Fecha: 2026-10-29. Implementación preparada, comparación reproducible y validación únicamente en PostgreSQL desechable. No se habilitó el catálogo nuevo, no se aplicaron migraciones a bases persistentes y no se ejecutó ningún procedimiento de fusión ni saneamiento.

## Resultado

`canonical.py` es la definición compartida de equivalencia confirmada. Una obra sin redirección activa conserva su UUID. Los candidatos, las coincidencias de título/autor y los identificadores de publicación no generan equivalencia entre UUID de obras. Se mantienen los registros físicos y sus claves históricas.

Se conserva el algoritmo anterior como `legacy_equivalent_work_ids()`. `equivalent_work_ids()` delega al servicio canónico solo con `CATALOG_CANONICAL_ENABLED=true`. La configuración sigue apagada y exige previamente el paquete de descubrimiento. La fusión administrativa continúa bloqueada por validación de configuración.

Los cuatro valores efectivos de configuración se comprobaron sin conectarse a una base persistente:

```text
catalog_discovery_enabled = false
catalog_editionless_enabled = false
catalog_canonical_enabled = false
catalog_admin_merge_enabled = false
```

## Reglas compartidas

| Concepto | Regla del modo preparado |
| --- | --- |
| Obra canónica | Destino terminal de una cadena de redirecciones activas y vinculadas a operaciones válidas. Sin cadena: UUID propio. |
| Referencia externa de lectura | Identificador exacto almacenado, con proveedor y tipo; se contrastan referencias y fuentes. Se rechazan contradicciones y se mantienen separados los espacios de nombres. No se consulta un proveedor ni se escriben metadatos para resolverla. |
| Pertenencia a biblioteca | Una pertenencia efectiva por usuario y raíz canónica entre entradas activas. Las entradas físicas se conservan. |
| Estado actual de biblioteca | Último intento por `created_at DESC, id DESC` entre las entradas activas de esa raíz. |
| Historial y relecturas | Cada `Reading.id` conserva su intento, obra física, edición elegida, progreso y eventos. La redirección no crea intentos nuevos. |
| Lectores únicos | Una persona por raíz canónica; los estados públicos usan el mismo último intento efectivo. |
| Reseña vigente | Una por `created_by_user_id` y raíz canónica, ordenada por actualización y UUID; en el ETL se reconstruye la revisión al cutoff y se ordena por instante registrado y UUID. |
| Visibilidad y puntuación | Seleccionar la reseña vigente **antes** de filtrar estado público y puntuación. Un borrador/ocultamiento más reciente impide recuperar automáticamente la reseña pública anterior. |
| Promedio público | Puntuaciones válidas de esas reseñas vigentes publicadas. Las reseñas sin puntuación aparecen en el listado, pero no aumentan el número de valoraciones. |
| Obras únicas frente a intentos | Distintos UUID canónicos para obras; distintos ID de intento para relecturas. El perfil conserva los intentos, pero `eligible_books_count`, umbral de acceso a IA y pertenencias cuentan obras canónicas únicas. |
| Edición opcional | Sigue siendo nula cuando el lector no la eligió. La equivalencia de obras no sustituye una edición ni relaja la FK de correspondencia física. |

La selección de reseñas se comparte en `books/consistency.py`. El listado por libro, promedio, mural y enlace público individual usan esa vigencia. Las reseñas anteriores permanecen en sus tablas y en el acceso privado del titular. Un enlace público a una reseña ya sustituida devuelve 404 en el modo nuevo; no borra la reseña ni sus revisiones.

La incorporación sin edición reutiliza la pertenencia canónica efectiva y devuelve el mismo último intento que presenta la biblioteca. Una selección que exigiría cambiar de pertenencia física/edición devuelve conflicto; no se reasigna silenciosamente. El historial de intentos incluye los UUID históricos de la misma raíz. Retirar una obra mediante la acción explícita del titular archiva sus pertenencias activas equivalentes, conservando intentos e historial.

## Consumidores integrados

- Biblioteca, incorporación, inicio de lectura, consulta de intentos y estadísticas por género.
- Fichas, agrupación de resultados internos, reseñas propias/públicas, mural y puntuaciones.
- Extracción y transformación diaria de obras, eventos, pertenencias y reseñas. Antes de normalizar se verifica la correspondencia física para no ocultar una relación inválida detrás de una raíz común.
- Evidencia personal al cutoff y perfiles nocturnos: lecturas y reseñas de UUID distintos se relacionan por la misma raíz, sin mezclar candidatos. Los campos bibliográficos de una edición elegida mantienen su procedencia física; los metadatos de obra usan el registro canónico.
- Proyecciones lectoras, contextos por libro, umbral de acceso a IA, catálogo de candidatos, contexto individual del worker, estados de recomendaciones y ADN lector.
- Publicaciones comunitarias y selección de periodos analíticos: no se sirve un agregado como vigente bajo una versión de identidad distinta.

Los contratos existentes conservan los UUID físicos necesarios para validar las FK. La identidad efectiva se expone en `catalog_volume.libria.canonicalWorkId` y en las proyecciones canónicas. No se cambiaron las selecciones de edición ni se modificaron UUID almacenados.

Las evidencias bibliográficas ambiguas se excluyen conservadoramente. Las referencias de publicaciones históricas que no puedan asociarse sin ambigüedad no reciben una asociación por título/autor. Las ramas heredadas permanecen disponibles con la configuración apagada.

## Versionado e invalidación

`identity_snapshot()` obtiene el mapa mediante la misma proyección SQL usada por la resolución individual. Rechaza ciclos, límites de profundidad y caminos contradictorios; las FK y el trigger existente impiden crear referencias inválidas y ciclos en la base. Los errores de lectura canónica se convierten en respuestas explícitas, sin seleccionar una raíz alternativa.

La versión tiene formato `confirmed-v1:<sha256>`, calculado sobre los caminos confirmados activos y sus operaciones. Agregar una obra independiente no cambia la versión de equivalencia ni invalida todos los perfiles sin necesidad. Las referencias candidatas tampoco la cambian.

La migración preparada `0058_canonical_versions` añade `identity_version` nullable a:

- `analytics.projection_runs`.
- `analytics.ejecuciones_etl`.
- `ia.reader_profile_versions`.
- `ia.analyses`.

El modelo ORM incorpora estos campos con carga diferida para mantener las consultas de compatibilidad. El esquema existente no se reemplaza. Los valores históricos permanecen nulos: no se atribuye retrospectivamente una versión que no se registró.

La migración también añade un trigger de redirecciones que marca lectores y catálogo como pendientes de proyección, en la misma transacción del cambio de relación. No modifica obras, lecturas ni reseñas y no crea trabajos de IA. El marcador revierte si la transacción falla.

Las proyecciones y perfiles registran la versión; los hashes de perfiles, contextos y ADN incorporan esa identidad. Las proyecciones lectoras y el resumen de ETL conservan información de los caminos/operaciones para investigar el significado del UUID. Cada perfil conserva la obra física de sus intentos como procedencia.

Además del marcador transaccional, las lecturas comparan la versión actual. Esto cubre relaciones programadas que pasan a estar activas sin otra escritura en ese instante. Una proyección lectora desactualizada se reconstruye sin invocar IA. Un perfil nocturno desactualizado espera un ETL compatible; no genera una recomendación automáticamente como efecto de resolver una identidad.

El caché comunitario anterior se conserva como salida histórica; si su versión no coincide se calcula una vista compatible sin reemplazar esa publicación histórica. Los periodos analíticos no mezclan cierres con versiones distintas: pueden quedar temporalmente sin datos hasta disponer de una extracción coherente autorizada.

La identidad de una extracción se evalúa al extraer; el cutoff limita los datos de lectura/reseña. Una relación confirmada posterior puede reinterpretar asociaciones en una **nueva** proyección versionada. No se reescriben las proyecciones ni hechos históricos para hacerlos coincidir.

## Comparación reproducible

Artefacto: `catalog-canonical-phase5-comparison.json`. Ejecuta consultas de PostgreSQL, endpoints reales de biblioteca/reseñas y funciones reales de ETL/perfiles, alternando únicamente el indicador dentro de las pruebas. Los ID aleatorios de fixtures se normalizan a A/B; no se modifican datos históricos para crear coincidencias. La firma reproducible es:

```text
1f00dc63ef64003b622a70ee4148a1ab26b92043fd673c35953f0b1dc1f567f8
```

Las obras sintéticas tienen igual título/autor, dos reseñas del mismo lector —A=5, B=1 más reciente— y dos intentos finalizados. Primero no existe relación confirmada; después se añade exclusivamente una relación sintética al grafo desechable, sin consolidar filas.

| Escenario y dimensión | Algoritmo/consumidor anterior | Identidad confirmada | Clasificación |
| --- | --- | --- | --- |
| Sin confirmación: grupo al consultar A | A+B | A | Cambio esperado: se elimina la equivalencia inferida. |
| Sin confirmación: reseñas públicas de A | 2 | 1 | Cambio esperado por separación de obras. La reseña B permanece accesible mediante B. |
| Sin confirmación: puntuación de A | 1 | 5 | Cambio esperado: la valoración de B deja de afectar a A. |
| Con redirección A→B: reseñas públicas | 2 | 1 | Inconsistencia corregida: el listado anterior mostraba dos reseñas aunque el promedio elegía una por lector. |
| Con redirección: puntuación y valoraciones vigentes | 1, un lector | 1, un lector | Sin diferencia: se conserva la selección de vigencia ya usada por el promedio. |
| Con redirección: reseñas del ETL | A y B | Solo la vigente, asociada a B | Inconsistencia corregida entre ETL y promedio público. Los originales siguen almacenados. |
| Con redirección: intentos elegibles del perfil | 1, asociado a A y su antigua puntuación 5 | 0: la puntuación vigente es 1 | Inconsistencia corregida: el perfil usa la misma valoración actual que el resto del sistema. |
| Sin confirmación: biblioteca | 2 | 2 | Sin diferencia: fase 3 ya usaba relaciones confirmadas para esta presentación. |
| Con redirección: biblioteca | 1 | 1 | Sin diferencia esperada; se confirma la coherencia transversal. |
| Ambos escenarios: lector finalizado en la ficha consultada | 1 | 1 | Sin diferencia: no se duplica a una persona. |
| Ambos escenarios: finalizaciones del ETL | 2 intentos | 2 intentos | Sin diferencia: se conservan las relecturas. |
| Sin confirmación: perfil y reseñas de ETL | Perfil A; reseñas A/B | Perfil A; reseñas A/B | Sin diferencia: no se mezclan señales de obras independientes. |

Pruebas adicionales comprueban borradores y ocultamientos, otro lector con puntuación propia, selección de edición conservada, referencias externas sin edición, separación de espacios de proveedor y cachés desactualizados. Un caso de puntuación vigente alta conserva dos intentos en `profile.books` con una sola raíz y contabiliza **una obra** elegible, sin repetir la evidencia de la reseña compartida.

Riesgos pendientes de la comparación: solo hay datos sintéticos. No se autorizó ni se consultó un dataset persistente anonimizado. Se requiere un clon autorizado y representativo antes de extrapolar estas diferencias al catálogo real.

## Pruebas y aislamiento

Comando desde `apps/backend`:

```text
.venv/Scripts/python.exe -B -m scripts.validate_catalog_phase5
```

Resultado final: **304 pruebas backend correctas, sin omisiones**, incluyendo las 286 de la suite anterior y 18 casos de fase 5. Las 83 regresiones de baseline también se ejecutan antes de migrar y están incluidas en el total; no se suman como casos distintos.

Cobertura de fase 5: independencia sin prueba confirmada; homónimos; redirecciones/UUID históricos; conservación de reseñas e intentos; selección común de vigencia y privacidad; bibliotecas efectivas; relecturas; edición nula; publicación real de hechos y perfiles canónicos; umbral de IA por obras únicas; contextos del worker; invalidación de proyecciones y salida comunitaria; rollback de relación/marcadores; rechazo de ciclos; ausencia de llamadas de IA durante resolución; referencias externas sin edición y namespaces separados.

PostgreSQL 17.11 en contenedor propio con tmpfs, puerto loopback y sin volúmenes persistentes. Se verificaron 71 tablas y 165 filas históricas sintéticas, columnas nuevas nulas, preservación de los valores originales, rollback completo ante fallo de DDL inyectado y upgrade repetido sin cambios. Las únicas dos relajaciones de CHECK corresponden a la fase 4, no a esta migración. El contenedor fue eliminado al terminar.

Las relaciones de fusión presentes en las pruebas son **fixtures del grafo**, sin ejecutar un servicio administrativo de consolidación, trasladar filas ni realizar operaciones en datos reales. Los UUID físicos de lecturas y las ediciones se comprueban después de resolver las relaciones.

Frontend: `node tests/library-selection.mjs`, `node tests/reading-optional-edition.mjs` y `npm.cmd run build` correctos. No se modificaron archivos fuente del frontend en fase 5. La compilación mantiene la advertencia de un bundle de 505.63 kB. No se ejecutó navegador automatizado ni se consultaron proveedores reales. La medición de contención heredada de fase 3 se guarda bajo el nombre de fase 5; no es una prueba de carga del nuevo conjunto de consumidores canónicos.

## Archivos de esta fase

Rutas relativas a `apps/backend/`. Se conservaron los cambios ajenos ya presentes en el workspace.

| Área | Archivos nuevos o modificados |
| --- | --- |
| Configuración y errores | `.env.example`, `app/core/config.py`, `app/main.py` |
| Identidad y reglas | `app/modules/books/canonical.py`, `service.py`, nuevo `consistency.py`, `resolution.py`, `library_view.py`, `discovery.py`, `community.py` |
| Biblioteca | `app/modules/library/router.py`, `commands.py` |
| Social | `app/modules/social/reviews_router.py`, `router.py` |
| Estadísticas personales | `app/modules/users/reading_statistics.py` |
| Analítica | `app/modules/analytics/etl.py`, `reader_evidence.py`, `recommendation_profiles.py`, `persistence.py`, `projections.py`, `models.py`, `eligibility.py`, `community.py`, `insights.py` |
| IA y contextos | Nuevo `app/modules/analytics/canonical_views.py`; `adaptive_ai.py`, `adaptive_router.py`, `transactional_sources.py`, `recommendation_sync.py`, `reader_dna.py`, `gemini_context.py`, `gemini_worker.py` |
| Migración | Nuevo `migrations/versions/0058_canonical_projection_versions.py`, revisión `0058_canonical_versions` |
| Validación | `scripts/validate_catalog_phase1.py`, nuevo `scripts/validate_catalog_phase5.py`, nuevo `tests/test_catalog_phase5.py` |
| Evidencia en `docs/` | Este informe, `catalog-canonical-phase5-results.json`, `catalog-canonical-phase5-comparison.json`, `catalog-canonical-phase5-benchmark.json`, `catalog-canonical-phase5-frontend-results.json` |

La cabecera preparada es `0058_canonical_versions`, con 58 revisiones lineales. Las migraciones aceptadas 0055–0057 conservan sus hashes. 0058 solo añade columnas y función/trigger; no contiene fusiones, reclasificación por metadatos ni reescritura de datos. Se conserva la estrategia de recuperación hacia delante y el downgrade se rechaza.

## Riesgos restantes y condiciones para fase 6

1. **Activación todavía no autorizada.** Mantener los cuatro indicadores apagados y no migrar una base persistente. Antes de desplegar: respaldos, permisos, ventana de DDL y clon autorizado con datos anonimizados.
2. **Carga real pendiente.** La resolución bulk y la selección de vigencia priorizan integridad; varias rutas recorren el grafo o conjuntos de reseñas. Medir tamaños y concurrencia representativos, planificar índices/consultas sin volver a inferencias por título/autor.
3. **Extracciones antiguas.** Una versión anterior no se considera vigente automáticamente. Preparar nuevas extracciones autorizadas y una política de publicación de periodos coherentes, especialmente para ventanas de 30 días. No reescribir los hechos históricos para esconder diferencias.
4. **Casos históricos ambiguos.** Publicaciones sin referencia exacta inequívoca, fuentes contradictorias y selecciones entre pertenencias físicas requieren revisión. Se mantienen excluidas o devuelven conflicto, sin deducir asociaciones por metadatos.
5. **Despliegue coordinado.** API, ETL y workers deben compartir versión/configuración. No alternar modos sobre cachés y perfiles ya publicados sin plan de recuperación; conservar lectores compatibles y suspender escrituras si aparece una incidencia. No eliminar UUID, reseñas ni intentos para facilitar un rollback.
6. **Fusión administrativa futura.** Fase 6 debe implementar simulación, elección explícita del destino y resolución de conflictos, incluyendo varias entradas, reseñas o intentos activos de una persona. Debe preservar originales y versiones, registrar efectos y redirecciones, confirmar permisos y permitir investigar/revertir incluso con actividad posterior.
7. **Validación previa adicional.** Revisar la comparación sobre el clon autorizado, ejecutar el recorrido completo en navegador, probar cambios concurrentes de identidad/publicación y verificar recuperación desde actividad posterior. Las garantías de una herramienta real de fusión no se deducen únicamente de estas fixtures de lectura del grafo.

No se inició la fase 6 ni se activó ningún procedimiento administrativo de fusión.
