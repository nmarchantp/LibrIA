# Gestión y presentación compacta del mural

## Diagnóstico previo

Existían carga/edición de portada por publicación, galerías y visor, likes,
comentarios y vistas tipadas, además de `PUT /reviews/{id}` con revisiones y
estados draft/published/hidden. Faltaban edición/eliminación de publicaciones
y comentarios. La eliminación anterior de reseñas borraba relaciones y era
incompatible con las vistas con FK restrictiva; ahora oculta y conserva historial.
No hay respuestas anidadas ni relaciones hijas de `PostComment`.

## Presentación

La portada relacionada tiene proporción 2:3 y hasta 180 px de altura. Portada y
título siguen dentro del enlace bibliográfico; no aparece «Ver ficha del libro».
El formulario de portada desapareció de la vista pública. Se mantiene la fila de
hasta cuatro fotos, con `+N` sobre la cuarta cuando corresponde, sin filas nuevas
ni desplazamiento horizontal.

El menú de tres puntos aparece solo para contenido gestionable por el usuario.
Reutiliza `PostComposer` en modo edición dentro de un modal responsive, con todos
los campos, adjuntos y portada precargados. La carga de portada conserva la
validación y almacenamiento de 0075 y no modifica el catálogo global.
Los errores conservan el editor abierto. Durante el envío se bloquea el cierre.
La eliminación solicita confirmación con el título y explica qué contenido dejará
de mostrarse. Al guardar/eliminar se recarga la categoría y se cierra el detalle
anterior para no dejar tarjetas obsoletas.

Los comentarios propios tienen edición compacta y confirmación de eliminación.
Se conserva ID, autor, destino y fecha de creación; `edited_at` permite mostrar
«Editado». La lista y los contadores se comparten entre superficies. Una respuesta
antigua de carga no sobrescribe una mutación posterior de comentarios.

La edición de reseñas usa `RatingControl` y las dimensiones existentes, además del
endpoint versionado original. Las versiones canónicas no vigentes se rechazan.
El listado propio devuelve la versión canónica actual, incluyendo su estado oculto.
La ficha bibliográfica y la biblioteca siguen usando esos mismos registros y rutas.

## Rutas

- `GET /api/posts/{id}`: detalle autenticado con capacidades reales.
- `PUT /api/posts/{id}`: edición in situ, JSON o multipart; portada y fotos atómicas.
- `DELETE /api/posts/{id}`: eliminación lógica, sin borrar hijos ni obras.
- `PUT /api/activities/{kind}/{id}/comments/{comment_id}`: corregir comentario propio.
- `DELETE /api/activities/{kind}/{id}/comments/{comment_id}`: borrar solo ese comentario.
- Reseñas: `PUT /api/reviews/{id}` conserva revisiones; DELETE pasa a ocultación segura.

La autorización se verifica siempre en servidor. Los administradores no obtienen
un permiso nuevo para actuar sobre contenido ajeno. Se conserva la autorización
existente de perfiles personales y administradores de organizaciones. Las imágenes
retenidas deben pertenecer a la misma publicación; no se admiten IDs ajenos.
Las solicitudes de edición/eliminación no registran vistas.

## Migraciones no destructivas

- `0076_content_management`: agrega `publicaciones.updated_at`,
  `publicaciones.deleted_at` y `comentarios_publicacion.edited_at`, todos opcionales.
  La visibilidad compartida excluye publicaciones eliminadas, también para imágenes,
  portadas, comentarios y likes desde tarjetas antiguas.
- `0077_hide_draft_reviews`: permite ocultar un borrador sin inventar una fecha de
  publicación. Relaja la restricción existente sin modificar filas históricas.

Ambas migraciones se aplicaron en la base local. En otros entornos se requiere
`alembic upgrade head` antes de desplegar.

## Archivos

Backend: `social/models.py`, `schemas.py`, `activity_access.py`, `router.py`,
`feed_service.py`, `post_covers.py`, `publication_management.py`,
`interactions_router.py`, `reviews_router.py`, registro en `app/main.py`, migraciones
0076/0077 y `tests/test_content_management.py`.

Frontend: `HomePage.jsx`, `FeedCard.jsx`, `MuralActivityCard.jsx`, `PostComposer.jsx`,
`MuralPage.css`, `ActivityOptionsMenu.jsx`, `ContentManagementDialog.jsx`,
`ContentManagement.css`, `ReviewEditForm.jsx`, `CommentEntry.jsx`,
`MuralManagementContext.jsx`, `ActivityInteractionContext.jsx`,
`activityInteractions.js`, `feedService.js`. `LibraryBookPage.jsx` conserva el ID de
la reseña oculta y ajusta la etiqueta de la acción al comportamiento seguro del API.
También se actualizaron la fixture y las pruebas del mural.

## Validación ejecutada

106 pruebas backend aprobadas, incluidas las nuevas de autoría, identidad conservada,
fotos/portadas atómicas, ausencia de publicaciones duplicadas, conservación de
interacciones, eliminación lógica, denegación de tarjetas antiguas, edición y
eliminación de comentarios en las tres fuentes, revisiones y ocultación de reseñas,
y borradores ocultos sin fecha inventada. Se repitieron pruebas focalizadas de
feed/portadas y reseñas después de los últimos ajustes.

`npm run test:mural` pasa con edición/eliminación de eventos, anuncios, promociones
y lanzamientos, selector de portada dentro del editor, fallo de guardado, comentarios
compartidos y reseñas. Incluye nueve temas y modales a 1440/768/390/320 px sin
desbordamiento. También pasan `test:feed-progress`, lint (advertencia previa en
Layout.jsx) y build (aviso previo sobre tamaño del bundle).
