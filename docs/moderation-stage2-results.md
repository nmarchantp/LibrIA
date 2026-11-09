# Moderación preventiva: entrega de etapa 2

## Resultado

La moderación está conectada a las creaciones y ediciones reales de publicaciones,
reseñas y comentarios, incluidas las rutas compatibles. Sin alertas se conserva
la publicación normal; con alertas el contenido nuevo queda pendiente. Una edición
sospechosa conserva la versión pública anterior y registra una propuesta privada.
No se implementaron decisiones administrativas, reportes, notificaciones ni una
interfaz de moderación: las etapas 3 y 4 no se iniciaron.

Las propuestas conservan imágenes, portada personalizada, obra, valoración y datos
del evento separados de la versión aprobada. Un cambio pendiente de horario o
fecha no modifica el calendario. Los identificadores, asistentes e interacciones
se conservan. Los comentarios se eliminan lógicamente y sus pendientes no suman
al contador público. Los borradores privados de reseñas no se moderan hasta intentar
publicarlos; estado editorial y estado de moderación siguen siendo independientes.

## Archivos de esta etapa

Rutas relativas a `apps/backend/`:

| Archivos | Cambio |
| --- | --- |
| `app/modules/social/moderation_integration.py` | Análisis por campos, recibos, idempotencia HTTP, control de versión y retiro auditado de propuestas |
| `app/modules/social/moderation_private_router.py`, `app/main.py` | Consulta privada de estado, propuesta y adjuntos por su autor |
| `app/modules/social/router.py`, `publication_management.py`, `reviews_router.py` | Integración en creación, edición y eliminación; conservación de versiones aprobadas |
| `app/modules/social/interactions_router.py`, `interaction_service.py` | Comentarios tipados y compatibles, pendientes, conteos y borrado lógico |
| `app/modules/social/activity_access.py`, `post_covers.py` | Visibilidad central y autorización de recursos; protección contra cambios de portada que eludan una edición pendiente |
| `app/modules/social/schemas.py`, `feed_service.py` | Metadatos de moderación y versión en respuestas |
| `app/modules/books/consistency.py`, `community.py` | Selección canónica y valoraciones públicas sin reseñas pendientes |
| `app/modules/analytics/projections.py`, `etl.py`, `reader_evidence.py`, `transactional_sources.py`, `gemini_worker.py`, `canonical_views.py`, `adaptive_ai.py` | Exclusión de fuentes pendientes y comentarios eliminados; autorización de sus padres |
| `migrations/versions/0083_pending_review_publication_date.py` | Compatibilidad de reseñas pendientes sin fecha de publicación pública |
| `tests/test_moderation_integration.py`, `test_moderation_http_concurrency.py` | Integración, privacidad, recursos, versiones, reintentos y concurrencia HTTP |
| `tests/test_moderation_foundation.py` | Verifica ausencia de rutas administrativas; permite las nuevas consultas privadas del autor |
| `tests/test_analytics_projections.py`, `test_daily_etl.py` | Ajustes de pruebas antiguas: contrato vigente de ejecución nocturna y fixture de ETL independiente de los datos locales |

Rutas relativas a `apps/web/`, exclusivamente transporte y manejo funcional de
respuestas, sin cambios estéticos:

- `src/api/moderationTransport.js`, `src/api/client.js`: claves de reintento,
  huellas de cuerpos y archivos, versiones y cabecera `If-Match`.
- `src/components/PostComposer.jsx`, `ReviewEditForm.jsx`, `CommentEntry.jsx`:
  conservar la versión que el usuario abrió al editar.
- `src/context/ActivityInteractionContext.jsx`,
  `src/services/activityInteractions.js`, `src/components/FeedCard.jsx`: transmitir
  versiones y evitar insertar comentarios pendientes en listas públicas optimistas.
- `tests/moderation-transport.mjs`: pruebas del transporte.

Los archivos de la etapa 1 y los cambios anteriores de pestañas del perfil se
conservaron; no corresponden a una ampliación de esta entrega.

## Migración y contrato HTTP

Se aplicó correctamente `0083_pending_review_date`, nuevo head de Alembic.
Solo amplía la restricción `ck_resenas_publicacion`: una reseña con intención
editorial `published` puede seguir pendiente y sin `published_at`. No actualiza
filas ni reconstruye fechas. La reversión automática exige resolver primero esas
reseñas, para evitar una pérdida de datos.

Se mantienen los endpoints de escritura actuales. Las respuestas incluyen
`moderation_status`, `public_moderation_status`, `moderation_version` y, cuando
corresponde, `pending_revision_id` y el mensaje de revisión. Un envío pendiente
es una operación guardada, no un error que deba reenviarse. Las creaciones
conservan su código HTTP de éxito existente.

Endpoints nuevos, autenticados y exclusivos del autor:

- `GET /api/me/moderation`
- `GET /api/me/moderation/{identifier}`
- `GET /api/me/moderation/{identifier}/attachments/{asset_id}`

No hay endpoints administrativos nuevos. Las consultas y recursos privados usan
`Cache-Control: private, no-store`. Las consultas públicas filtran antes de los
límites y paginación. Las reseñas se filtran después de seleccionar la vigente,
evitando que reaparezca una revisión histórica como sustituto de una pendiente.

Las escrituras aceptan `Idempotency-Key`; repetir clave y cuerpo devuelve el mismo
resultado y cambiar el cuerpo produce conflicto. Los comentarios tipados y
compatibles comparten la misma operación idempotente. `If-Match` detecta una edición
basada en una versión obsoleta con `409`. El cliente existente envía estas cabeceras;
se mantienen opcionales para compatibilidad. Los bloqueos y restricciones de la BD
serializan operaciones y conservan una sola propuesta pendiente activa.

## Validación

**216 pruebas de backend correctas**, mediante:

```powershell
.venv/Scripts/python.exe -m unittest tests.test_moderation_integration tests.test_moderation_http_concurrency tests.test_moderation_foundation tests.test_mural_feed tests.test_activity_interactions tests.test_content_management tests.test_publication_events tests.test_identities tests.test_reading_challenge tests.test_profile_events tests.test_reviews tests.test_publication_covers tests.test_analytics_projections tests.test_daily_etl
.venv/Scripts/python.exe -m alembic current
```

Incluyen creaciones y ediciones pendientes, publicación limpia, eliminación,
privacidad, medios, calendario, asistentes, valoraciones, reseñas canónicas,
comentarios en los tres destinos y rutas antiguas. Las pruebas HTTP concurrentes
comprueban cuatro solicitudes con la misma clave y dos ediciones con igual versión:
una sola creación y conflicto para la edición obsoleta.

Frontend: `node tests/moderation-transport.mjs`, `npm run lint`, `npm run build`
y `npm run test:mural`. El lint no tiene errores; conserva una advertencia previa
en `Layout.jsx`. Vite advierte del tamaño del bundle, sin impedir la compilación.
Las pruebas del mural verifican temas, responsive, navegación, interacciones,
comentarios y ausencia de vistas por renderizado. Las capturas de esa suite se
actualizan en `artifacts/mural-carousels/` como evidencia de ejecución.

`git diff --check` no presenta errores de formato. El servidor local se reinició
con esta implementación y su OpenAPI expone únicamente las tres rutas privadas
de moderación descritas, sin rutas de revisión administrativa ni reportes.

## Integridad y límites

`artifacts/moderation-stage2/before.json`, `after.json` y `verification.json`
comparan conteos y hashes completos de diez tablas: publicaciones, reseñas,
comentarios, eventos, asistencias, tres tipos de likes, visualizaciones y eventos
de lectura. **Todas coinciden**; las cuatro tablas privadas de moderación quedaron
sin registros de prueba. La evidencia contiene hashes y conteos, no textos privados.

- Las reglas siguen siendo heurísticas: pueden existir falsos positivos y negativos.
  Ninguna alerta rechaza automáticamente.
- Los pendientes todavía no pueden aprobarse desde un flujo administrativo: esa
  funcionalidad requiere la etapa 3. El autor puede consultar el estado por API y
  corregir el contenido por las rutas existentes.
- No se agregó interfaz de estados o notificaciones; corresponde a la etapa 4.
- Los clientes antiguos que omitan las cabeceras conservan compatibilidad, pero no
  obtienen la misma protección contra reintentos o ediciones obsoletas. El cliente
  actual mantiene las claves de reintento en memoria durante diez minutos; no son
  un mecanismo de recuperación de borradores tras cerrar el navegador.
- El análisis admite hasta 20 000 caracteres por campo. Los comentarios de lectura
  conservan su límite de 200 palabras y los demás el de 1000 caracteres, con un
  límite adicional de seguridad de 20 000 caracteres para el análisis.
- No se reconstruyeron proyecciones analíticas históricas ni se analizaron datos
  antiguos retroactivamente. Los nuevos consumidores excluyen pendientes.
- La retención y limpieza de adjuntos privados sigue pendiente. No se publican
  mediante URLs de medios públicos.

La etapa 2 queda entregada para revisión. No se avanzará automáticamente a otra etapa.
