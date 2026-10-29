# Catálogo canónico: fase 3

Fecha: 2026-10-28. Implementación preparada y verificada, **sin activar**. No se ejecutaron migraciones ni escrituras en bases persistentes. No se implementaron fusiones ni lecturas sin edición.

## Resultado y alcance

`CATALOG_DISCOVERY_ENABLED=false` es el valor predeterminado. Al habilitarlo, se cambia conjuntamente descubrimiento, incorporación, presentación de biblioteca y protección de escritores antiguos. Los demás indicadores de catálogo canónico, fusión y lecturas sin edición siguen desactivados. No hay que habilitarlos para probar este paquete.

| Operación | Flujo antiguo conservado con indicador apagado | Paquete nuevo verificado |
| --- | --- | --- |
| Buscar o abrir una ficha externa | Puede importar mediante servicios heredados | Solo consulta; búsqueda puede escribir `consultas_catalogo` |
| Agregar resultado externo | Depende de persistencia previa y resolutores heredados | Referencia tipada → evidencia del servidor → resolución transaccional |
| Reutilizar publicación histórica | Varios caminos de resolución | Fuente exacta inequívoca, sin reescribir metadatos históricos |
| Datos enviados por cliente | Metadatos presentes en payload histórico | Título y páginas no constituyen evidencia de identidad |
| Importar administrativamente | Scripts escriben directamente | Permiso administrador, motivo, clave idempotente y servicio central |
| Agrupación al presentar catálogo nuevo | Equivalencia lógica heredada | Relaciones canónicas confirmadas; no coincidencia automática por título/autor |

El comportamiento antiguo continúa activo mientras el indicador esté apagado. Esta entrega no significa que las búsquedas de una instalación existente hayan cambiado ya.

## Rutas y servicios

- Búsqueda y fichas de `books/router.py` delegan en `discovery.search()` y `discovery.detail()` en el modo nuevo. Las referencias externas y los UUID existentes continúan aceptándose. Una ficha externa no necesita importación previa.
- `POST /api/readings/library` usa `facade.public_addition()` y `resolution.incorporate_book()`. La selección de edición es explícita; no se escoge otra edición. Se conservan los conflictos como errores 409. No se habilita incorporación sin edición.
- `GET /api/readings/me`, la ficha y el inicio de lectura reconocen la incorporación ya persistida. Iniciar una lectura desconocida no constituye una ruta alternativa de importación.
- `POST /api/admin/catalog/imports`: referencia tipada, motivo e `Idempotency-Key`; permiso real de administrador comprobado también en el servicio. Registra importación y procedencia, sin agregar el libro a una biblioteca personal.
- `resolution.import_book()` comparte `_external_resolution()` y bloqueos con la incorporación de biblioteca. Ningún auxiliar confirma transacciones. La fachada controla el commit y el rollback.
- Para una publicación nueva, se consulta el detalle al proveedor desde el servidor antes de tomar bloqueos. El cliente envía identificadores, nunca evidencia bibliográfica confiable. Los ISBN se validan y normalizan como identificadores de publicación; las contradicciones no autorizan reutilización insegura.
- Las fuentes históricas exactas e inequívocas pueden reutilizar su edición sin proveedor disponible. Se registra esa evidencia como referencia a la publicación almacenada, sin convertir metadatos antiguos incompletos en afirmaciones bibliográficas nuevas.

### Caché y escritores

La caché tiene espacio de nombres `discovery-v1`, contiene resultados externos y se vuelve a presentar contra el catálogo actual. Se descartan los identificadores internos que lleguen dentro de un payload externo. TTL: 86400 segundos para éxito, 600 para vacío y 30 para resultado parcial; enfriamiento de actualización de 10 segundos. Un resultado en caché no constituye una obra ni autoriza una identidad.

`store_volume`, los escritores de `open_library_catalog` y la consolidación heredada revisada se rechazan en modo nuevo. No se eliminan sus ramas antiguas. `run_catalog_ingest` y los cargadores de populares de España, Chile y Argentina delegan al CLI autorizado `scripts/import_catalog.py`. Este exige administrador, motivo y prefijo idempotente; cada publicación se incorpora mediante la misma fachada. Una búsqueda de importación CLI es una selección administrativa explícita de un lote, no una búsqueda pública.

`seed_default_admin` reutiliza publicaciones existentes mediante referencia exacta o `--catalog-map` de ediciones, y no fabrica catálogo en este modo. Los metadatos sintéticos de `seed_analytics_demo` y escenarios derivados requieren el marcador y comentario de la base desechable propiedad del validador. No son un mecanismo de importación a bases persistentes. Las migraciones y fixtures del validador permanecen separados de los escritores de aplicación.

## Concurrencia y fallos

- Orden de adquisición: bloqueo global transaccional de catálogo `(73155,1)`, bloqueo del actor para biblioteca, referencia de publicación y después ISBN cuando existe. El mismo resolutor conserva la serialización global; no se retiraron garantías para mejorar la medición.
- PostgreSQL `READ COMMITTED`; `lock_timeout=2000ms`, `statement_timeout=10000ms` por sentencia y por intento, configurables. No son un límite global de duración de toda la petición.
- Hasta tres intentos, únicamente para `55P03`, `40P01`, `40001`, con esperas de 50 y 100ms. Cada intento usa una transacción nueva; agotamiento devuelve 503 y `Retry-After: 1`. Errores bibliográficos, permisos y conflictos no se reintentan como fallos transitorios.
- Clave idempotente por actor y contenido semántico. El frontend conserva la clave para reintentar una misma selección. Clientes antiguos tienen una clave determinista derivada de referencia y selección. Reutilizar una clave con otra operación es conflicto.
- Peticiones de proveedor fuera de la transacción de catálogo; Google limita su llamada a 15 segundos y el contexto compartido limita el presupuesto de proveedor a 45 segundos, incluidos reintentos y esperas. Open Library respeta el tiempo restante. Si Google falla y se inicia un presupuesto nuevo para fallback, la búsqueda puede consumir hasta aproximadamente 60 segundos de proveedor, más procesamiento local; no se promete un límite total de 45 segundos para ese camino.
- El fallo del proveedor precede a las escrituras. El fallo dentro del comando revierte la incorporación completa. El caché usa su propia escritura de descubrimiento y no mantiene bloqueos de catálogo durante llamadas remotas.

## Archivos de esta fase

Rutas relativas al repositorio; se conservan los cambios ajenos que ya existían en el workspace.

| Área | Archivos nuevos o modificados en esta fase |
| --- | --- |
| Configuración y montaje | `apps/backend/.env.example`, `app/core/config.py`, `app/main.py` |
| Servicios centrales | `app/modules/books/{facade,discovery,policy,library_view,admin_router}.py` nuevos; `resolution.py`, `evidence.py` ampliados |
| Integración y proveedores | `app/modules/books/{router,google_books,open_library,open_library_catalog,service}.py` |
| Biblioteca | `app/modules/library/{router,schemas}.py` |
| Escritores administrativos y fixtures | `scripts/import_catalog.py` nuevo; `run_catalog_ingest.py`, `load_popular_{spanish,chile,argentina}_books.py`, `seed_default_admin.py`, `seed_analytics_demo.py` |
| Frontend | `apps/web/src/services/librarySelection.js` nuevo; `services/booksService.js`, `context/LibraryContext.jsx`, `pages/BookDetailPage.jsx` |
| Verificación | `apps/backend/tests/test_catalog_phase3.py`, `scripts/validate_catalog_phase3.py`, `apps/web/tests/library-selection.mjs` nuevos |
| Evidencia | Este informe, `catalog-canonical-phase3-results.json`, `catalog-canonical-phase3-benchmark.json` |

En la tabla, `app/` y `scripts/` sin prefijo corresponden a `apps/backend/`. No hay migraciones nuevas en fase 3. La cabecera sigue siendo `0056_catalog_nullable_edition`, con 56 revisiones; los hashes de 0055 y 0056 figuran en el resultado. No se modificó el archivo real `.env`.

## Pruebas ejecutadas

Comando: `apps/backend/.venv/Scripts/python.exe -B -m scripts.validate_catalog_phase3`, desde `apps/backend`.

**219 pruebas correctas** en PostgreSQL 17.11 desechable, además de una ejecución previa de las 83 regresiones de baseline. Esas 83 también forman parte de las 219; no deben sumarse como casos distintos. Incluye fases anteriores, resiliencia de proveedores y pruebas de integración HTTP de esta fase.

El validador creó su propio contenedor con almacenamiento tmpfs, puerto solo loopback y sin volúmenes persistentes. Comprobó 71 tablas y 165 filas sintéticas históricas, rollback de DDL inyectado, conservación de filas y restricciones, upgrade repetido sin efecto y eliminación final del contenedor. No acepta una URL de una base persistente como destino de validación.

Cobertura comprobada:

- Búsqueda Google y Open Library y apertura de fichas: conteos de las cinco tablas definitivas sin cambios.
- Recorrido HTTP búsqueda → ficha → incorporación → recarga de biblioteca → inicio de lectura.
- Reutilización por UUID, referencia externa histórica y repetición idempotente sin proveedor.
- Incorporación simultánea por dos usuarios sin duplicar la referencia; bloqueo real agotado devuelve 503 y no deja escrituras.
- Referencias de proveedores distintos con mismo título/autor permanecen separadas sin prueba de identidad.
- ISBN contradictorio devuelve conflicto y rollback; casos adicionales de normalización y falta de ISBN incluidos desde fase 2.
- Detalle consultado por servidor, fallo remoto sin incorporación parcial y ausencia de transacción de petición durante llamadas remotas.
- Caché separado del catálogo, actualización de presentación tras incorporación y payload externo con identidad interna falsa ignorada.
- Permisos/procedencia de importación administrativa, guardas de escritores antiguos, delegación de scripts y guardas de fixtures.
- Reintento transitorio sin volver a consultar al proveedor, relaciones históricas y redirecciones cubiertas por regresiones anteriores.

Frontend: `node tests/library-selection.mjs` correcto; `npm.cmd run build` correcto; ESLint dirigido a los cuatro archivos fuente de esta fase correcto. La compilación advierte de un bundle de unos 502kB. No se ejecutó automatización de navegador ni consultas reales a proveedores: las pruebas HTTP usan respuestas controladas. La delegación CLI se prueba y la incorporación administrativa se prueba por HTTP; falta una prueba operativa de cada lote CLI real con proveedores.

### Medición básica

Ocho comandos por nivel, PostgreSQL desechable, proveedores simulados sin latencia; incluye camino HTTP y conserva el bloqueo global.

| Concurrencia | Comandos/s | Mediana ms | Máximo ms |
| --- | ---: | ---: | ---: |
| 1 | 18.52 | 52.86 | 59.89 |
| 2 | 25.15 | 73.74 | 100.24 |
| 4 | 23.63 | 151.19 | 200.10 |

Es una prueba pequeña local, no una estimación de capacidad productiva. La saturación observada confirma la limitación del bloqueo global. Se necesitan pruebas de carga representativas antes de dimensionar la activación.

## Riesgos, habilitación y recuperación

1. Indicador apagado: las ramas heredadas siguen operando. Habilitar solo con autorización posterior, esquema compatible comprobado, respaldo y ventana de despliegue coordinada. Esta fase no aplica migraciones a instalaciones persistentes.
2. Todos los procesos API, cron e importadores deben usar la misma versión y configuración. Detener escritores antiguos antes del cambio; evitar instancias con modos mezclados. Revisar permisos de PostgreSQL para no permitir a tareas antiguas eludir el servicio mediante SQL directo.
3. Revisar credenciales, límites y respuestas reales de ambos proveedores; ejecutar recorrido de navegador en entorno aislado con la configuración de despliegue. Supervisar timeouts, 409, 503, caché y latencia de incorporación.
4. Las agrupaciones confirmadas usadas por la presentación nueva pueden cambiar puntuaciones frente al agrupamiento lógico antiguo. Las reseñas, ETL y recomendaciones heredadas todavía necesitan la unificación transversal de sus fases respectivas. Revisar comparativas sobre un snapshot autorizado antes de habilitar este cambio de presentación; no se garantiza paridad analítica global en esta fase.
5. Conservar los UUID físicos históricos y las evidencias permite investigar incorporaciones. No hay fusión que revertir. Ante errores, detener incorporaciones y aislar los registros afectados para revisión; no borrarlos ni reasignarlos automáticamente. Desactivar el indicador por sí solo reactiva escritores antiguos: el rollback operativo debe mantener pausados importadores y escrituras hasta decidir el modo seguro.
6. El bloqueo global sigue siendo un cuello de botella conocido. Evaluar cargas reales sin eliminar integridad. Reintentar solicitudes con su misma clave y nunca tratar un timeout como prueba de que hubo commit.

## Condiciones para comenzar fase 4

Aprobar esta entrega y el alcance de compatibilidad pendiente. Inventariar y adaptar todos los consumidores de `edition_id` nulo: biblioteca, lecturas, fichas, API/frontend, estadísticas, ETL y perfiles/recomendaciones. Caracterizar comparativamente agrupaciones y asociaciones antes de reemplazar la lógica heredada. Definir transiciones explícitas para seleccionar/cambiar edición y preservar el historial.

Las pruebas de fase 4 deben demostrar que una lectura sin edición no fabrica páginas, ISBN ni datos de publicación y que las lecturas existentes conservan su edición elegida. Mantener la capacidad apagada hasta completar esas pruebas. La fusión administrativa sigue fuera de este alcance y requiere su propia simulación, conflictos, auditoría y recuperación antes de cualquier activación.
