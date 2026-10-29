# Fase 7 — fusiones administrativas habilitadas en desarrollo

Rama `Nicole`, sin ramas adicionales. Implementado el recorrido **comparar → simular → resolver conflictos → fusionar → verificar → revertir**, probado en el navegador contra la API y PostgreSQL reales del proyecto.

La base local `libria` estaba en 0054 y tenía 483 obras. Se respaldó antes de aplicar 0055–0060. La migración conservó los valores existentes de las 71 tablas históricas. Se habilitaron las fases 3–7 únicamente en la configuración local de desarrollo. No se modificó un entorno externo y no se fusionaron obras preexistentes: todas las fusiones reales usaron las dos obras creadas expresamente para esta prueba.

## Diseño implementado

### Identidad y conflictos

`merge_execution.execute_merge()` usa la identidad compartida de `canonical.py`. La fusión agrega una operación administrativa, una redirección entre raíces canónicas y las selecciones explícitas de reseñas. **No mueve ni elimina obras, ediciones, ISBN, referencias, bibliotecas, lecturas, eventos, páginas, reseñas o revisiones.** Las claves foráneas de obra/edición siguen describiendo sus relaciones físicas originales.

Las entradas de biblioteca originales permanecen. Los consumidores canónicos muestran una pertenencia efectiva y conservan todos los intentos. Las reseñas originales también permanecen. La nueva tabla `app.selecciones_resena_canonica` registra cuál debe ser vigente por perfil; la selección se aplica antes de filtrar visibilidad y valorar. Una reseña oculta o borrador seleccionada no se publica ni permite que reaparezca otra pública como sustitución.

Las propuestas usan la regla explícita «última actualización y UUID», incluyendo los estados privados. No se aplican automáticamente. Si existe un conflicto, el servidor exige exactamente una elección válida para ese perfil y rechaza selecciones ajenas. Ni títulos/autores similares ni un ISBN de publicación ejecutan una unión.

La elección de destino también decide los metadatos canónicos de esta versión del MVP. El administrador debe aceptar `metadata_policy=preserve_destination` y `library_policy=preserve_all`. Los valores de la otra obra y su procedencia permanecen en su UUID. No se implementó un editor para mezclar campos de ambas obras ni se modificaron las ediciones históricas.

Las selecciones activas se comparten entre reseñas públicas, valoraciones, feed, extracción ETL, evidencia lectora y perfiles de recomendaciones. El selector compartido no usa una reseña alternativa si la elegida no está disponible dentro de un corte histórico. La identidad incorpora las reversiones para que un retorno a la misma forma del grafo no vuelva válidas cachés de una etapa anterior.

### Transacción, concurrencia e idempotencia

La fachada HTTP termina la lectura de autenticación y abre una transacción propia. El servicio exige `READ COMMITTED`, toma primero el bloqueo exclusivo `(73155,1)` y vuelve a comprobar el permiso administrativo efectivo. Después recupera la simulación, comprueba versión/caducidad, recalcula su huella, resuelve raíces y valida decisiones.

Los escritores de dominio participan mediante triggers `BEFORE STATEMENT` que toman el mismo bloqueo en modo compartido. Los SELECT ORM con bloqueo de filas también entran primero en esa barrera, desde `core/database.py`. La incorporación sigue usando el bloqueo exclusivo existente. El escritor de redirecciones conserva su comprobación de ciclos y bloqueo exclusivo de PostgreSQL. Las operaciones históricas de auditoría no promocionan un bloqueo compartido a exclusivo, evitando el interbloqueo detectado durante las pruebas.

El orden del ejecutor es barrera global → permiso y estado actual → comprobación de huella y decisiones → operación/selecciones/redirección → efectos auditables e invalidación → commit del llamador. Los auxiliares solo hacen flush. Cualquier error revierte la transacción completa.

La unicidad por administrador, tipo de operación y `Idempotency-Key`, junto con el hash de la solicitud, permite repetir exactamente una confirmación y recibir la misma operación. Reutilizar la clave para otro contenido devuelve 409. Las confirmaciones simultáneas con la misma clave se probaron desde conexiones independientes.

Se conservan los timeouts y reintentos acotados de la fachada de incorporación. La simulación mantiene 15 minutos de validez. Una respuesta previa de `/validate` nunca sustituye la revalidación dentro de la transacción de ejecución.

### Huella acotada

Las simulaciones nuevas tienen versión 2; la versión 1 sigue conservada como auditoría, pero no puede ejecutarse. `merge_scope.py` calcula SHA-256 únicamente sobre las obras conectadas a origen/destino y sus relaciones relevantes: autores, variantes, publicaciones, fuentes, referencias, entradas, lecturas, progreso, eventos, selección de edición, reseñas, revisiones, perfiles vinculados, publicaciones, incorporaciones, selecciones administrativas y redirecciones.

La exploración del componente canónico parte de los UUID y de las aristas de redirección, sin iniciar un recorrido de todas las obras. Los hashes de filas se calculan en PostgreSQL; no se devuelve su contenido privado. Los estados derivados de analítica/IA no se usan como evidencia de identidad ni forman parte de esta huella. Sus invalidaciones continúan usando los mecanismos existentes y la versión canónica.

La actividad sobre una obra independiente ya no caduca la simulación. Cambiar una edición, un autor vinculado, una lectura o una reseña afectada sí la invalida. La prueba de carrera confirma que el ejecutor espera a un escritor independiente y rechaza la confirmación cuando ese escritor termina con cambios.

La invalidación de 0058 sigue siendo global porque los consumidores actuales comparten una versión global de identidad. Ese coste se conserva deliberadamente; reducirlo requiere versionar también las dependencias de las proyecciones, no solo acotar la huella.

## Reversión

`preview_reversal()` compara el estado relevante actual con los hashes guardados después de la fusión. Muestra registros creados, modificados o eliminados posteriormente y la procedencia de incorporaciones. Resalta solicitudes de una obra histórica que acabaron almacenadas en otra obra física del grupo.

Sin actividad posterior, la reversión retira la redirección mediante una operación compensatoria. Las selecciones de esa operación dejan de tener efecto y vuelven a regir las selecciones anteriores que sigan activas. No se borran operaciones, selecciones, reseñas ni revisiones.

Con actividad posterior, el MVP exige aceptar **cada registro** que se conservará con su atribución física actual. Esto es una elección administrativa explícita, no una redistribución automática. Se probaron lecturas posteriores y una incorporación cuyo UUID solicitado difería de la obra física conservada.

**Límite de recuperación:** la herramienta no reasigna arbitrariamente registros posteriores a otra obra. Si el administrador necesita esa redistribución, debe conservar la unión hasta que exista una operación específica de atribución. Otra fusión dependiente, cambios en selecciones/redirecciones o una eliminación de registros bloquean la separación con su motivo; deben resolverse primero. Las obras originales nunca se eliminan como parte de este mecanismo.

## Migración 0060

Dependencia lineal de `0059_merge_previews`; 60 revisiones y una única cabecera.

- Amplía el CHECK de versión de simulaciones para conservar v1 y aceptar v2.
- Agrega `app.selecciones_resena_canonica`, UUID propio y unicidad por operación/perfil.
- Claves foráneas restrictivas a operación, obra, perfil y reseña; correspondencia compuesta operación/destino y reseña/perfil.
- Agrega unicidad `(id,author_profile_id)` en reseñas para soportar esa correspondencia, sin sustituir su clave ni unicidad anteriores.
- Índices de selección por obra, lecturas por obra y reseñas por obra.
- Inmutabilidad de selecciones y barrera compartida para los escritores de dominio existentes.
- No contiene saneamiento, fusiones, reasignaciones, eliminación ni relleno de datos históricos. Su downgrade rechaza destruir la auditoría; recuperación mediante migraciones posteriores revisadas.

El respaldo previo está en `backups/catalog-phase7-20261029T131700Z.dump`, ignorado por Git, con SHA-256 `25dcb5976c03dfc9cbf2b9d93759f21d81972233d69b0a310236ca7d48124c7b`. Se comprobó su formato con `pg_restore --list`; no se ejecutó una restauración completa de ese archivo. La reversión real de las fusiones sí se probó mediante la herramienta, conservando sus registros posteriores.

## Endpoints y pantalla

Continúan los endpoints de búsqueda interna, comparación y simulación de fase 6. Se agregan:

| Método y ruta bajo `/api/admin/catalog` | Uso |
| --- | --- |
| `POST /merge-previews/{id}/execute` | Confirmación `FUSIONAR`, motivo, políticas y selecciones de reseñas |
| `GET /history` | Últimas 50 operaciones de fusión/reversión, con estado activo |
| `POST /merges/{operation_id}/reversal-preview` | Simulación de separación, procedencia y bloqueos |
| `POST /reversal-previews/{id}/execute` | Confirmación `REVERTIR`, motivo y atribuciones posteriores aceptadas |

Las ejecuciones requieren `Idempotency-Key`. El backend comprueba permisos en ruta y servicio. `/roles/access` expone la capacidad efectiva `catalog_merge`; ocultar el botón no es el control de seguridad.

`/admin/catalog` permite seleccionar origen/destino, comparar, simular, revisar propuestas, elegir reseñas vigentes, aceptar las políticas, introducir motivo y confirmación, ejecutar y consultar el resultado/historial. La separación muestra procedencia, registros posteriores, decisiones y motivos de bloqueo. Las confirmaciones repetidas conservan su clave si la solicitud no cambió.

La biblioteca se recarga ante un cambio de identidad en la sesión administrativa. Las fichas UUID históricas navegan a la URL canónica; las ediciones seleccionadas explícitamente conservan su presentación. Los demás usuarios reciben la identidad actual al volver a consultar o recargar; no se agregó difusión en tiempo real entre sesiones.

## Archivos de esta fase

- `app/modules/books/merge_execution.py`: ejecución, idempotencia, separación y auditoría.
- `app/modules/books/merge_scope.py`: estado relevante, linaje físico y huella.
- `app/modules/books/merge_preview.py`: v2, grafo acotado y propuestas de reseña.
- `app/modules/books/canonical.py`: resolución de componente y versión sensible a reversiones.
- `app/modules/books/consistency.py`, `app/modules/analytics/reader_evidence.py`: selección vigente común para API, ETL y recomendaciones.
- `app/modules/books/admin_router.py`, `app/modules/users/roles_router.py`: contratos, capacidades e historial.
- `app/core/database.py`, `app/core/config.py`: orden de bloqueos y habilitación controlada de desarrollo/test.
- `migrations/versions/0060_admin_merges.py`.
- `scripts/validate_catalog_phase7.py`, ajuste del entorno aislado en `validate_catalog_phase1.py`, adaptación del contrato de versión en `tests/test_catalog_phase6.py`, nuevas pruebas `tests/test_catalog_phase7.py`.
- `scripts/prepare_catalog_phase7_dev.py`, `seed_catalog_phase7_demo.py`, `verify_catalog_phase7_dev.py`: migración respaldada, fixtures mediante el resolver y postflight de solo lectura, restringidos a la base local del proyecto.
- Frontend: `AdminCatalogPage.jsx`, `LibraryContext.jsx`, `BookDetailPage.jsx`, `tests/catalog-merge-development.mjs`.
- Configuración local ignorada `.env`: cinco capacidades activadas. Los valores por defecto del código siguen apagados; no se habilitan fusiones fuera de development/test.
- `.gitignore`: excluye también perfiles temporales `.tmp/` del navegador.

## Pruebas y recorrido real

**344 pruebas backend correctas, sin omisiones**, 45,017 segundos, sobre PostgreSQL 17.11 desechable. Las 83 regresiones de referencia se ejecutaron también antes de migrar y no se suman como casos distintos. Se comprobaron rollback de DDL, 165 filas sintéticas en 71 tablas históricas, restricciones anteriores y repetición de migración sin cambios. El contenedor se eliminó.

La suite mantiene los casos de fases 0–6 y agrega fusión/reversión, dos ediciones, ISBN diferentes, privacidad y elección explícita de reseña anterior, biblioteca compartida, intentos preservados, huella acotada, cambio relevante, caducidad, idempotencia, confirmaciones simultáneas, escritor concurrente, fallo después de insertar la redirección y rollback completo, dependencias posteriores, atribución posterior ambigua, buscador, ETL y evidencia de recomendaciones.

Frontend: compilación Vite correcta, 1714 módulos; bundle 513,48 kB, gzip 152,70 kB. Continúa el aviso superior a 500 kB. Pasaron las pruebas existentes de selección y lectura opcional y la prueba de navegador con HTTP simulado para permisos, flag apagado y recuperación de errores.

El recorrido real usó Chrome sin ventana, la API habitual en `127.0.0.1:8000`, Vite en `127.0.0.1:5173` y PostgreSQL local. Se reutilizaron los procesos de desarrollo y se solicitó la recarga de configuración de Uvicorn; no se inició un worker adicional de Gemini.

1. Se creó una cuenta de prueba con rol lector y permiso administrativo efectivo.
2. Dos publicaciones sintéticas explícitamente marcadas se importaron mediante `resolution.import_book()`, con ISBN, idiomas, editoriales y páginas distintos. No se atribuyó esa evidencia a una consulta real del proveedor.
3. En la sesión real del navegador se crearon biblioteca, intentos, progreso y reseñas mediante REST auténtico. Se usaron las páginas registradas 5/120 y 6/240.
4. La interacción administrativa completa se hizo con controles de la pantalla: comparación, simulación, elección de la reseña anterior con nota 5, confirmación y reversión.
5. Durante la unión se comprobaron una pertenencia, ambos intentos y ediciones, una reseña pública vigente, media 5 y un lector activo.
6. El buscador público devolvió una obra canónica y la ficha antigua navegó a su URL canónica. La respuesta externa quedó en Open Library, sin estado parcial. La consulta no implica haber validado una incorporación real de ese proveedor: las publicaciones de este recorrido eran fixtures.
7. La reversión restituyó las dos identidades, pertenencias y reseñas originales. Se hicieron dos iteraciones reales y ambas quedaron revertidas y auditadas.

Las credenciales de prueba están únicamente en `tmp/catalog-phase7-fixture.json`, ignorado por Git. Los informes no incluyen contraseña ni tokens.

## Ejemplos y mediciones

Ejemplo real de la última iteración: fusión `94b581d8-c8a6-4a71-b06f-50524c9a0a1c`, compensada por la reversión `0e9a1af0-d013-4e7e-aa61-27476b252c01`.

- Origen conservado: `35cd4be3-4f1d-43a7-b3d7-270b223e8518`.
- Destino conservado: `eed983ca-b5b9-477e-97e3-8c0015d718f1`.
- Ambos UUID siguen existiendo y ya no tienen una redirección activa entre ellos.

Medición local reproducible del último ensayo en PostgreSQL desechable, una observación por volumen; incluye la fachada HTTP TestClient y su transacción:

| Obras independientes adicionales | Simulación | Confirmación |
| --- | ---: | ---: |
| 0 | 109,090 ms | 114,869 ms |
| 100 | 91,052 ms | 102,525 ms |
| 1000 | 85,110 ms | 122,638 ms |

Es una comprobación básica de independencia frente a obras ajenas, no una prueba de capacidad para una obra con miles de lectores. La barrera exclusiva y la invalidación global siguen siendo costes a medir con cargas mayores.

## Estado final y límites

- Desarrollo en 0060; fases 3–7 activadas. API y frontend disponibles mediante el procedimiento local existente.
- 485 obras: 483 preexistentes y dos nuevas de prueba. No se fusionó ninguna obra preexistente.
- Dos entradas, dos intentos con sus ediciones/páginas y dos reseñas de prueba conservados. Cero redirecciones de prueba activas; cero redirecciones sobre otras obras.
- Cero jobs y cero análisis IA para el usuario de prueba. El código de fusión/reversión no llama a Gemini ni encola trabajos; las proyecciones futuras usan los procesos existentes.
- Las separaciones que requieren atribuir registros a otra obra, restaurar eliminaciones o resolver fusiones dependientes están bloqueadas para una recuperación específica. No se añadieron movimientos arbitrarios de historial.
- Sigue pendiente un editor bibliográfico por campo, paginación avanzada del historial y mediciones con muchas relaciones afectadas. No se sustituyó el modelo existente.
- La incorporación previa conserva su rechazo explícito de transiciones entre ediciones incompatibles con un intento físico existente; esta fase no reasigna ni sustituye la edición de una lectura para evitar ese rechazo. Se mantienen los flujos de intentos y selección explícita existentes.

Para suspender nuevas fusiones, apagar solo `CATALOG_ADMIN_MERGE_ENABLED`: las selecciones ya registradas siguen aplicándose mientras los consumidores canónicos permanezcan activos. No volver a lectores heredados apagando todo el conjunto después de crear lecturas sin edición o identidades confirmadas. La recuperación de una unión usa una operación compensatoria; restaurar el respaldo completo no sustituye ese procedimiento y podría perder actividad posterior.

Evidencias: `catalog-canonical-phase7-results.json`, `catalog-canonical-phase7-performance.json`, `catalog-canonical-phase7-example.json` (PostgreSQL desechable), `catalog-canonical-phase7-browser-results.json` (recorrido real), `catalog-canonical-phase7-frontend-results.json`, `catalog-canonical-phase7-development-migration.json` y `catalog-canonical-phase7-development-results.json`.
