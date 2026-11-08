# Agenda literaria de Eventos

## Arquitectura y alcance

La página anterior ya consultaba `/api/events` y compartía la asistencia con el mural mediante `EventAttendanceContext`. Cada `PublicationEvent` tiene como clave el UUID de su publicación `Post`; fotografías, portada personalizada, obra, comentarios e interacciones pertenecen a esa publicación. La creación y edición utilizan `PostComposer` dentro de `ContentManagementDialog`.

Este cambio conserva esa arquitectura. Añade calendario mensual, detalle, Lista, Cuadrícula y próximos eventos. No introduce tablas, migraciones, datos de ejemplo ni publicaciones paralelas. El sistema no tiene un estado independiente de cancelación de eventos: conserva la eliminación lógica existente y la cancelación de asistencia. No se fabrican estados de cancelación.

## Consultas

`GET /api/events` conserva `offset` y `limit` y admite opcionalmente:

- `from_date=YYYY-MM-DD`: incluye eventos cuya fecha local de término alcanza el inicio del rango.
- `to_date=YYYY-MM-DD`: incluye eventos cuya fecha local de inicio no supera el fin del rango.

Los límites son inclusivos y se comparan en la zona IANA guardada de cada evento. Un evento de varios días aparece en todos los días comprendidos en su inicio y término. Un afiche o descripción no se utiliza para deducir fechas. Los eventos antiguos sin fecha estructurada permanecen en el mural.

El calendario consulta el rango de sus celdas visibles, no una petición por día. Cada página contiene como máximo 100 registros; si hay más, se informa y se ofrece cargar el siguiente bloque. Próximos eventos consulta nueve registros desde la fecha actual de Chile; «Ver todos» abre Lista con el mismo rango de próximos eventos y paginación. La agenda permite explorar meses anteriores.

`eventsService` mantiene una caché en memoria de hasta doce consultas, durante treinta segundos, separada por sesión. Se invalida al crear, editar o eliminar desde cualquier ruta, y al recuperar el foco de la página. La asistencia sigue usando su estado compartido y no se simula en esta caché.

No cambian las rutas `GET/PUT/DELETE /api/events/{id}/attendance` ni `POST /api/posts`, `GET/PUT/DELETE /api/posts/{id}`. El enlace original utiliza `/?category=events&publication={id}`: el mural recupera la publicación autorizada por su UUID y abre su diálogo existente.

## Componentes

- `EventsPage.jsx/.css`: composición de la agenda y cambio de vistas.
- `AgendaMonth.jsx` y `eventCalendar.js`: semanas de lunes a domingo y operaciones sobre fechas locales, sin reinterpretarlas en la zona del navegador.
- `AgendaEventCard.jsx`: en el detalle prioriza la portada personalizada de la obra y luego la del catálogo; las tarjetas conservan la fotografía adjunta como primera opción. Prueba las alternativas disponibles antes del placeholder si una imagen falla; detalle y tarjetas reutilizables.
- `useAgendaEvents.js` y `eventsService.js`: consultas por rango y paginación acotada.
- Reutilizados: `MuralCarousel`, `EventAttendanceButton`, `EventAttendanceCount`, `EventDate`, `EventInformation`, `ContentManagementDialog`, `PostComposer` y `MuralActivityDialog`.

El compositor comunica al modal la publicación guardada para seleccionar inmediatamente la nueva fecha. El ID, los asistentes y las demás relaciones se conservan. Las acciones de edición permanecen limitadas por `can_manage` y la autorización del servidor.

## Verificación ejecutada

- Backend: `tests.test_publication_events`, `tests.test_content_management`, `tests.test_activity_interactions`, `tests.test_post_comments` y `tests.test_post_interactions`: 84 pruebas aprobadas. Incluyen el filtro local de un evento del 30 de noviembre a las 23:30 de Chile, cuya fecha UTC es diciembre, eventos que comienzan antes del rango y duran varios días, paginación, rangos inválidos, contenido no visible y borrado lógico.
- `npm run test:agenda`: fixture aislada; calendario correcto, varios eventos el mismo día, tres vistas, asistencia compartida, creación, edición con cambio de mes, conservación de asistentes, publicación original, eliminación, imágenes ausentes o fallidas, errores, mes vacío y permisos de creación. Nueve temas y anchos de 1536, 1100, 768, 390 y 320 px; navegador configurado en Honolulu para comprobar que los días de Chile no se desplazan.
- `npm run test:events`: edición, asistencia, recarga y sincronización de rutas sobre fixtures de prueba.
- `npm run build` y `npm run lint`: compilación aprobada, lint sin errores y una advertencia preexistente en `Layout.jsx`.

Las capturas de prueba se guardan en `artifacts/events-agenda`. No se alteran permanentemente eventos reales para validar estos recorridos.
