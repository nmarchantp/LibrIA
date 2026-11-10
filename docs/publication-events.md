# Eventos del mural y calendario

## Diagnóstico y compatibilidad

Antes de este cambio, las publicaciones de eventos ya disponían de GET, PUT y DELETE en `/api/posts/{id}`. La edición de texto existía; faltaban campos estructurados de fecha, lugar, organizador y categoría. El acceso de edición estaba dentro del menú de opciones. La página Eventos mostraba tres ejemplos locales, sin consultar publicaciones, y su botón de asistencia no disponía de persistencia. No había dos conjuntos de eventos reales que reconciliar.

Ahora un evento del calendario utiliza el UUID de su publicación original. Los eventos antiguos sin fecha estructurada permanecen en el mural: no se interpreta su descripción ni se inventan fechas. El propietario puede completarlos desde el lápiz. No se insertan datos al consultar el calendario.

## Persistencia y seguridad

La migración aditiva `0078_publication_events` crea:

- `app.eventos_publicacion`: relación 1:1 mediante `post_id` como clave primaria y foránea, fechas con zona, ubicación, organizador y categoría.
- `app.asistencias_evento`: clave primaria compuesta `(post_id, user_id)`. Confirmar es idempotente; cancelar conserva el registro desactivado. Las operaciones bloquean la publicación y utilizan upsert para soportar concurrencia.
- `app.actualizaciones_horario_evento`: historial de inicio, término y zona anteriores y nuevos, responsable y revisión única por evento.

Modificar un horario conserva asistentes y muestra «Fecha u horario actualizado» con el horario previo. No envía notificaciones por correo. Cambiar el tipo de un evento con asistentes activos se rechaza: debe conservarse como evento o eliminarse con confirmación. La eliminación utiliza la política existente de borrado lógico y lo oculta de ambas consultas, conservando asistentes, comentarios e interacciones.

Las fechas se validan con `zoneinfo` y se almacenan como instantes. Se rechazan horas inexistentes o ambiguas durante cambios de horario, así como términos anteriores al inicio. La interfaz recibe por separado la fecha y hora locales del evento, sin convertir el recuadro de día/mes según la zona del navegador.

Los permisos reutilizan la autorización de publicaciones y la misma política de visibilidad del mural. No se expone la identidad de asistentes en las respuestas de asistencia.

## API

- `GET /api/events?offset=0&limit=20`: publicaciones visibles con fecha, orden cronológico, paginadas; incluye datos del evento y asistencia del usuario autenticado.
- `GET /api/events/{post_id}/attendance`: datos actuales, contador y estado propio.
- `PUT /api/events/{post_id}/attendance`: confirmar.
- `DELETE /api/events/{post_id}/attendance`: cancelar.
- `POST /api/posts`, `GET/PUT/DELETE /api/posts/{post_id}`: conservan sus rutas; creación y actualización aceptan `event_details` como objeto JSON o JSON dentro de multipart. La edición mantiene el UUID y las relaciones originales.

La asistencia no crea visualizaciones sociales. Likes, comentarios y visualizaciones siguen usando sus servicios existentes.

## Archivos principales

Backend: `social/models.py`, `schemas.py`, `event_service.py`, `events_router.py`, `router.py`, `publication_management.py`, `feed_service.py`, `main.py` y la migración 0078.

Frontend: `EventAttendanceContext.jsx` comparte estado entre rutas; `EventPresentation.jsx/.css` presenta fecha, asistencia y actualización; `EventFields.jsx` comparte los campos de creación y edición. Se integran en `FeedCard.jsx`, `PostComposer.jsx`, `ContentManagementDialog.jsx`, `EventsPage.jsx`, `HomePage.jsx`, `Layout.jsx` y `feedService.js`. Las portadas personalizadas siguen limitadas al formulario, sin cambiar el catálogo.

## Verificación

- Backend: `python -m unittest tests.test_publication_events tests.test_content_management tests.test_reviews tests.test_activity_interactions tests.test_post_comments tests.test_post_interactions`. Casos de edición de un evento Stella aislado con seis imágenes, mismo UUID, interacciones conservadas, fechas, categorías, permisos, asistencia, borrado lógico y eventos históricos sin fecha.
- `ConcurrentAttendanceTest`: seis conexiones simultáneas confirman un único asistente. Usa UUID de prueba nuevos y elimina únicamente esos registros al finalizar.
- `npm run test:events`: fixture aislada de navegador, asistencia compartida, edición desde Eventos, reprogramación, recarga, cancelación, eliminación y nueve temas a 1440/768/390/320 px. El navegador usa UTC para verificar que el día chileno no se desplaza.
- `npm run test:mural`: regresión de carruseles, publicaciones amplias, comentarios, portadas y gestión.
- `npm run lint`, `npm run build`, `git diff --check`.

También se ejercitó multipart con una copia temporal de los datos reales de Stella, sus seis adjuntos y portada, dentro de una transacción descartada. Se verificó que la copia no persistió. El evento real no se modificó ni se le asignó una fecha de prueba.

La migración debe aplicarse en cada entorno antes de desplegar el código. No tiene un downgrade destructivo automático.
