# Reseñas normalizadas

El detalle del libro muestra «Reseñas de los lectores» mediante `GET /api/reviews/by-book/{book_ref}`. Resuelve la referencia del catálogo a la obra e incluye sus reseñas publicadas, también las de otras ediciones de esa obra. Excluye borradores, reseñas ocultas y obras ajenas. La lista se ordena por primera publicación descendente y admite `offset` y `limit` (20 por defecto, hasta 50), con `has_more` para cargar más. Muestra autor, fecha, texto y estrellas cuando hay valoración; los spoilers permanecen plegados hasta abrirlos. La consulta es pública y usa `Cache-Control: no-store`.

Entrega: 2026-10-10. Migraciones `0016_normalized_reviews` y `0017_review_analytics`, aplicadas en la base local.

## Contrato

Una reseña pertenece a un perfil personal y una obra. La base impide duplicar `(author_profile_id, work_id)`, incluso al reseñar otra edición o volver a leer. La edición es opcional y, si existe, debe pertenecer a la obra. No se exige terminar una lectura para reseñar.

Texto obligatorio de 1–3000 caracteres; calificación opcional entre 1 y 5, nunca cero; indicador de spoilers. Estados: `draft`, `published`, `hidden`. Solo publicaciones visibles aparecen en el feed y aceptan comentarios, me gusta o acceso público a sus imágenes.

Crear o editar exige ser titular del perfil. Un administrador no puede editar ni consultar borradores ajenos por su rol. Los borradores se consultan con la sesión del titular. Primera publicación, ID, autor y obra no cambian al editar, ocultar o republicar. Un borrador obtiene `published_at` cuando se publica por primera vez; una reseña publicada puede ocultarse, pero no volver a borrador. La base refuerza identidad y primera publicación mediante trigger.

Cada cambio guarda `revisiones_resena` en la misma transacción que la reseña. Incluye estado, texto, valoración, edición, ejecutor y fecha. Las reseñas son textuales y no admiten imágenes. Los me gusta pertenecen a `me_gusta_resena`, y los comentarios tienen tres FK excluyentes: publicación, evento o reseña. Una relectura no genera otra reseña.

## API e interfaz

| Operación | Ruta |
|---|---|
| Crear borrador o reseña | `POST /api/reviews` con `work_id`, texto y opciones. |
| Editar, ocultar o publicar la propia | `PUT /api/reviews/{id}`. Conservar el ID. |
| Consultar propias, incluyendo privadas | `GET /api/reviews/me?work_id=...`. |
| Consultar una reseña pública | `GET /api/reviews/{id}`. Borradores/ocultas devuelven 404. |
| Feed combinado | `GET /api/posts`; `feed_item_type=review` distingue entidad. |
| Comentarios, imágenes y me gusta | Rutas compartidas `/api/posts/{id}/...`, con FK a la entidad correspondiente. |

Las rutas de reseñas aceptan JSON o multipart con campos de texto. Rechazan archivos, campos `images` y `replace_images` al crear o editar. La interfaz envía JSON, conserva valoración opcional y marca de spoilers, y no ofrece adjuntos. Las respuestas de reseñas usan `Cache-Control: no-store` y una lista de imágenes vacía. Los adjuntos históricos permanecen almacenados por compatibilidad, pero no se muestran ni se sirven desde la API. Solo las publicaciones admiten imágenes.

`POST /api/posts` solo crea contenido manual: rechaza `source=review`, valoraciones y campos de lectura. La base bloquea nuevas mezclas salvo registros marcados explícitamente como archivo legado por procesos técnicos. Esa marca no se acepta en la API.

La pantalla de lectura recupera la reseña propia por obra y ofrece editar, guardar borrador, publicar, ocultar y declarar spoilers. Biblioteca devuelve IDs canónicos de obra y edición. El feed combina entidades sin copiar reseñas o avances a publicaciones; los spoilers requieren desplegar el texto.

## Migración conservadora

La migración resolvió solo referencias exactas de `fuentes_catalogo` bajo el proveedor usado por el contrato anterior, y perfiles personales del titular. No creó obras a partir de títulos ni eligió entre duplicados perfil–obra. Las referencias ambiguas, autorías no verificables y contratos inválidos quedan registrados en `migraciones_resenas` con su motivo.

Resultado en la base local: **1 reseña migrada y 148 pendientes por obra no identificada**. El generador antiguo seguía insertando mientras se preparaba el cambio; se detuvo para aplicar la migración y se adaptó al contrato nuevo.

La reseña migrada conserva el UUID, primera fecha pública, imágenes, me gusta, comentarios y procedencia ficticia cuando estaba acreditada. Los originales permanecen archivados en `publicaciones`; no se eliminan y no aparecen duplicados en el feed. Los casos pendientes también se conservan, pero no se presentan como reseñas normalizadas ni se usan en sus indicadores. Su resolución necesita acreditar referencias canónicas y, si se detectan duplicados, elegir explícitamente la reseña que se conservará.

El historial de revisiones comienza al migrar: no se inventan versiones anteriores. La prueba de migración ejecuta el SQL real en un esquema aislado y revertido, con reseñas verificables, referencias inexistentes, duplicados, autoría inválida y conservación de interacciones.

## ETL daily-v2

El [ETL diario](etl-daily.md) conserva el horario y la carga única por día. Los 19 cierres anteriores siguen en `daily-v1`; no se recalculan. El próximo cierre incorpora `daily-v2`.

- **S02, nuevas reseñas:** primeras publicaciones en el intervalo local por titular y procedencia. Editar y republicar no cuentan otra vez. Ocultar después no borra que hubo una primera publicación.
- **S01, valoración vigente de obra:** preparación técnica restringida de promedio, suma, cantidad calificada y distribución 1–5, por obra y procedencia. Solo reseñas publicadas al corte; sin calificación no aumenta el denominador, y sin calificaciones el promedio es nulo. Este resultado no se expone como análisis grupal: sigue pendiente verificar anonimización antes de habilitarlo a lectores, administración o actores comerciales.

El extractor elige la última revisión con fecha estrictamente anterior al corte. Una edición posterior no cambia el histórico, y una publicación exactamente en el límite pertenece al siguiente intervalo. `analytics.hechos_resenas` conserva identificadores personales restringidos y excluye texto/spoilers/imágenes; `analytics.preparacion_valoraciones_obras` conserva los componentes de S01 sin publicarlos. El administrador solo ve cantidades y reglas.

## Datos ficticios y validación

`scripts/reviews_demo.json` fija namespace, versión, fecha 2026-10-10 y resultados esperados. Cinco reseñas nuevas incluyen edición de valoración, ausencia de valoración, spoilers, borrador, ocultamiento y republicación. Diez revisiones permiten comprobar el corte. `python -m scripts.seed_reviews_demo` carga sin duplicar ni sobrescribir; solo está habilitado en desarrollo. Los datos de hoy se incorporarán al cierre, no mediante una carga anticipada.

El generador continuo también usa IDs canónicos y la ruta nueva. Cuando ya hay reseña del lector y obra, edita la existente. Sigue siendo una herramienta de actividad demo; el manifiesto versionado es el conjunto usado para validar resultados.

Verificación: 63 pruebas de backend, incluyendo integridad, permisos, ciclo de publicación, bloqueo de interacciones, escenarios repetibles, selección de revisión al corte y conciliación del ETL. Frontend: ESLint y build aprobados.
