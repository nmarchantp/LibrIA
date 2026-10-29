# Fase 6 — comparación y simulación administrativa

Implementación en la rama `Nicole`. No hay ejecutor de fusiones, confirmación operativa ni llamadas a Gemini. Las fases 3, 4 y 5 siguen desactivadas. La comparación administrativa tiene un interruptor independiente, `CATALOG_ADMIN_PREVIEW_ENABLED=false` por defecto.

## Contrato y comportamiento

`books/merge_preview.py` expone `compare_works()`, `preview_merge()` y `validate_preview()`. Comprueban el permiso efectivo de `app.permisos_cuenta` en el servicio, además del control del endpoint. No aceptan el rol visible como autorización. Se exige una transacción propia con aislamiento `REPEATABLE READ`; el llamador conserva la responsabilidad del commit/rollback.

La identidad procede exclusivamente de `identity_snapshot()` del servicio canónico compartido, incluso cuando la proyección pública está desactivada. Se resuelven los UUID históricos y todos sus miembros confirmados. Las obras que ya comparten raíz se rechazan con 409. Los errores de grafo, ciclos y profundidad fallan de forma cerrada a través del manejador canónico existente. No se llama a `consolidate_equivalent_works()`.

La comparación incluye UUID solicitado, raíz canónica, miembros históricos, títulos, variantes, autores, idiomas, publicaciones, ISBN, editoriales, fechas, formatos, fuentes y referencias externas. Los ISBN se validan y normalizan con el mismo código de incorporación. Los ISBN antiguos inválidos o contradictorios se muestran, sin corregirlos. ISBN diferentes pueden corresponder a ediciones de una misma obra: esa diferencia exige revisión y no demuestra que las obras sean distintas. Título coincidente e ISBN de publicación coincidente solo generan candidatos; nunca una fusión.

Las referencias muestran su estado, verificador, fecha, operación de procedencia, metadatos de procedencia disponibles y SHA-256 de la evidencia. Las rutas confirmadas muestran sus operaciones históricas. No se consultan proveedores externos durante la comparación.

El impacto distingue registros activos y archivados, bibliotecas compartidas, lectores propietarios únicos, intentos, relecturas actuales, ediciones, reseñas, valoraciones y estados originales. Las relecturas previstas después de una hipotética unión se muestran separadas de las actuales. Los conflictos del mismo perfil se identifican mediante UUID de reseñas y requieren una elección explícita futura. No se selecciona ni publica una reseña ganadora. Se conservan todos los estados.

No se exponen cuerpos de reseñas, cuadernos, nombres de lectores, correos ni identificadores de cuentas/perfiles de lectores. Los UUID de reseñas son necesarios para identificar los conflictos. El modelo actual tiene estados `published`, `hidden` y `draft`; no se ha inventado un estado `private` adicional.

Se cuentan las filas analíticas y de IA almacenadas que contienen referencias a las obras o a sus lectores propietarios. La invalidación propuesta también advierte que cambiar la versión global de identidad vuelve obsoletos los consumidores versionados. Los conteos directos no pretenden representar todas las dependencias indirectas contenidas en JSON. No se reconstruyen estadísticas, ejecutan ETL ni encolan trabajos.

## Endpoints

Todos los endpoints de catálogo requieren permiso administrativo efectivo y el interruptor de simulación:

| Método y ruta bajo `/api` | Función |
| --- | --- |
| `GET /admin/catalog/works?q=...` | Búsqueda interna, hasta 30 resultados; sin proveedores ni importación |
| `POST /admin/catalog/compare` | Comparación sin persistencia |
| `POST /admin/catalog/merge-previews` | Comparación y registro administrativo inmutable |
| `POST /admin/catalog/merge-previews/{id}/validate` | Comprobar versión, caducidad y huella; no ejecuta operaciones |
| `GET /roles/access` | Capacidades efectivas de la propia sesión; incluye `admin` y `catalog_preview` |

Los POST de comparación y simulación aceptan únicamente `source_work_id` y `target_work_id`, ambos UUID. Se preserva la dirección solicitada. Una referencia inexistente devuelve 404; raíces iguales, grafos inválidos, simulaciones vencidas o datos cambiados devuelven 409; falta de permiso devuelve 403. Timeouts, interbloqueos o errores de serialización reconocidos devuelven 503 con `Retry-After: 1`, después del rollback. No hay reintentos automáticos ni un endpoint de confirmación/ejecución.

## Auditoría y concurrencia

Migración aditiva `0059_merge_previews`, dependiente de `0058_canonical_versions`:

- Nueva tabla `app.simulaciones_fusion`, con UUID propio, administrador, versión 1, UUID origen y destino, huella, resultado JSONB y fechas de creación/caducidad.
- Claves foráneas restrictivas a usuarios y obras; ninguna relación existente se modifica.
- Restricciones de origen distinto de destino, versión soportada, huella hexadecimal de 64 caracteres, objeto JSON y caducidad posterior a la creación.
- Índice `(actor_user_id, created_at)` y clave primaria UUID.
- Trigger que rechaza UPDATE y DELETE: cada nueva simulación agrega su propio registro.
- No hay DML de saneamiento, reasignación, consolidación ni relleno de obras. La recuperación es mediante una migración posterior revisada; el downgrade rechaza borrar la auditoría.

El endpoint abre un snapshot coherente después de terminar la lectura de autenticación. Límite por sentencia de 10 segundos y espera de bloqueos de 2 segundos. No adquiere el bloqueo global de incorporación y no bloquea obras para una futura fusión.

La huella encadena SHA-256 de las filas, tablas y conjunto global de tablas de dominio de los esquemas `app`, `analytics`, `ia` y `ai`. El orden de filas es estable. PostgreSQL calcula los hashes de filas; los contenidos privados no se devuelven. Se excluyen únicamente el registro de simulaciones y la caché de descubrimiento. La comparación y la huella usan el mismo snapshot.

La simulación caduca a los 15 minutos. Una validación posterior usa otro snapshot y rechaza cualquier diferencia. La inserción de otra simulación no invalida las anteriores. Una modificación concurrente confirmada después del snapshot inicial sí provoca rechazo en una nueva validación.

**Una validación correcta no autoriza una ejecución posterior ni garantiza ausencia de cambios después de responder.** En fase 7 será obligatorio bloquear los escritores pertinentes, volver a comprobar permisos/versión/huella en la transacción de ejecución y conservar esos bloqueos hasta el commit. El servicio actual no ejecuta ninguna consolidación.

## Pantalla y permisos

Pantalla `/admin/catalog`, implementada en `AdminCatalogPage.jsx`: búsqueda interna, selección explícita de origen/destino, comparación de metadatos, evidencias, conflictos, impacto y simulación con UUID, huella y caducidad. No tiene botón operativo para confirmar una fusión. Un error borra el resultado anterior para evitar mostrar una simulación antigua como actual.

`AuthContext`, `AdminGate` y `Layout` consumen `/roles/access`. Una cuenta lectora con permiso administrativo efectivo puede entrar; una cuenta con etiqueta `admin` pero sin ese permiso se rechaza. El frontend espera la carga de permisos asociada al usuario antes de decidir la navegación. La autorización del servidor continúa siendo obligatoria en cada petición.

La pantalla usa bloques estructurados de datos para la comparación técnica. La traducción de los códigos de diagnóstico y la presentación de catálogos grandes pueden mejorarse sin cambiar el contrato de seguridad.

## Archivos de esta fase

- Backend: `app/modules/books/merge_preview.py`, `app/modules/books/admin_router.py`, `app/modules/users/roles_router.py`, `app/core/config.py`, `.env.example`.
- Migración: `migrations/versions/0059_merge_previews.py`.
- Verificación: `tests/test_catalog_phase6.py`, `scripts/validate_catalog_phase6.py`, ajuste de la cabecera Alembic y del entorno de pruebas de fase 6 en `scripts/validate_catalog_phase1.py`.
- Frontend: `src/pages/AdminCatalogPage.jsx`, `src/App.jsx`, `src/components/AdminGate.jsx`, `src/components/Layout.jsx`, `src/context/AuthContext.jsx`.
- Navegador aislado: `tests/catalog-preview.mjs`, `tests/fixtures/catalog-preview.html`, `tests/fixtures/catalog-preview.jsx`.
- Evidencias: este informe, `catalog-canonical-phase6-results.json`, `catalog-canonical-phase6-example.json`, `catalog-canonical-phase6-frontend-results.json`. El benchmark heredado de incorporación que produce el validador no mide la nueva simulación.

## Validación

Resultado final: **325 pruebas backend correctas, sin omisiones**, en 39,799 segundos; incluye las 304 anteriores y 21 nuevas. Las 83 regresiones de referencia también se ejecutaron antes de migrar (no se suman como casos distintos). PostgreSQL 17.11, 59 revisiones lineales, 71 tablas y 165 filas históricas sintéticas comprobadas sin modificaciones de sus valores existentes. Contenedor eliminado correctamente. Todos los flags efectivos se comprobaron en `false` al finalizar.

La ejecución final y los tiempos exactos están en `catalog-canonical-phase6-results.json`. El validador crea exclusivamente su propio PostgreSQL 17 con almacenamiento tmpfs, puerto local aleatorio y etiqueta de propiedad; no acepta una URL de una base existente. Comprueba migraciones desde 0054, rollback de DDL inyectado, preservación de filas/contratos históricos y repetición sin cambios; elimina exclusivamente su contenedor al terminar.

La suite incluye las 304 pruebas previas y los nuevos casos de fase 6: permiso efectivo, rechazo del rol sin permiso y revocación, interruptor apagado, comparación independiente, UUID desconocido, redirección histórica, raíz compartida, error de ciclo, bibliotecas compartidas, conflictos por perfil, borradores/ocultas, impacto analítico, separación de relecturas actuales y previstas, ISBN/autores/ediciones diferentes, ISBN histórico inválido, referencia confirmada, ausencia de escrituras de dominio o trabajos IA, rollback de simulación, inmutabilidad de auditoría, caducidad, cambio posterior y commit concurrente, y rechazo de transacción insegura. La prevención real de ciclos en PostgreSQL también sigue cubierta por la suite anterior.

La prueba de navegador usa Chrome sin ventana y un perfil separado, con todas las respuestas HTTP simuladas. Cubre un lector con permiso efectivo, rechazo de etiqueta admin sin permiso, flag apagado, búsqueda, selección, comparación, simulación, error recuperable, retirada del resultado anterior y ausencia de control de ejecución. No se comunica con un backend ni base de datos. También se ejecutan las pruebas existentes de selección bibliográfica y lectura opcional, y la compilación Vite. Permanece el aviso de bundle superior a 500 kB.

Las ejecuciones intermedias detectaron una colisión de ISBN fijos entre fixtures y una navegación prematura mientras cargaban permisos. Se corrigieron los fixtures para generar ISBN únicos y la carga de capacidades para esperar al usuario correspondiente; las evidencias finales corresponden al código corregido.

## Riesgos y condiciones para fase 7

1. La huella es deliberadamente global y conservadora: actividad ajena a las dos obras puede caducar una simulación. Escanear tablas completas, incluidos contenidos grandes, requiere medir latencia/memoria en una copia anonimizada representativa antes de habilitarla. Los timeouts fallan de forma cerrada; no se ha realizado una prueba de carga representativa.
2. No existe todavía un ejecutor ni reversión. Deben diseñarse y probarse la conservación física de UUID, una auditoría por entidad, resolución explícita de bibliotecas/reseñas, preservación de revisiones y privacidad, y recuperación con actividad posterior. Esta pantalla no autoriza esos cambios.
3. La fase 7 debe definir un protocolo común de bloqueo para todos los escritores relevantes y una revalidación atómica que impida el intervalo entre comprobación y uso. No basta con llamar al endpoint `/validate` antes de una transacción diferente.
4. Las propuestas de invalidación son conservadoras. Debe verificarse la reconstrucción coordinada de estadísticas, ETL, perfiles y recomendaciones con los datos resultantes antes de activar una fusión. Las salidas históricas deben conservar su versión.
5. Las decisiones bibliográficas y el resultado de conflictos no están automatizados. No hay una valoración final inventada para perfiles con reseñas en ambas obras. El futuro contrato de ejecución debe exigir elecciones y no inferirlas de título, autor o del último registro.
6. Deben acordarse acceso y retención del registro administrativo inmutable, cuotas y límites para catálogos grandes. La comparación técnica puede mejorarse con paginación y etiquetas traducidas, conservando una huella completa.
7. No se ha migrado ni consultado una base persistente. Aplicar 0059 en cualquier entorno persistente y activar `CATALOG_ADMIN_PREVIEW_ENABLED` requieren autorización posterior. El resto de los flags permanece apagado, incluido el de fusiones.

Recuperación de esta fase: ante un fallo, rollback de la transacción de simulación; el dominio bibliográfico no cambia. Para retirar la interfaz, apagar el flag de simulación y conservar el registro auditable. No borrar tablas, UUID ni resultados históricos.
