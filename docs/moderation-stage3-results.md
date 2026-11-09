# Moderación preventiva: entrega de etapa 3

## Resultado y alcance

El backend permite consultar y resolver revisiones pendientes, recibir reportes,
descartarlos, ocultar preventivamente contenido y restituirlo con autorización.
Se reutilizan las revisiones, los adjuntos privados, la auditoría, las restricciones
de unicidad, las versiones y las políticas públicas de las etapas anteriores.

No se implementaron paneles, nuevas páginas, opciones de menú, notificaciones ni
sanciones. **No se inició la etapa 4.** Su ubicación queda definida para esa etapa:
**Configuración del panel de administración → Moderación de contenido**, con
Pendientes de aprobación, Reportes de usuarios e Historial. La interfaz deberá
reutilizar Configuración y sus estilos, sin reorganizar otras secciones ni agregar
una entrada al menú principal.

## Archivos de esta etapa

Rutas relativas a `apps/backend/`:

| Archivo | Cambio |
| --- | --- |
| `app/modules/social/moderation_decisions.py` | Autorización administrativa vigente, bloqueos, aplicación de propuestas, decisiones idempotentes, reportes, ocultación y restitución |
| `app/modules/social/moderation_admin_router.py` | Cola, detalle, historial, recursos privados, decisiones y resolución de reportes |
| `app/modules/social/moderation_models.py` | Reportes tipados; ampliación de la auditoría existente; estado independiente de ocultación |
| `app/modules/social/publication_management.py` | Extracción de la resolución de obra/edición para reutilizarla al aprobar |
| `app/modules/social/activity_access.py` | Excluir contenido ocultado de las consultas e interacciones públicas |
| `app/modules/books/community.py`, `consistency.py` | Mantener la selección canónica y excluir reseñas ocultadas de valoraciones públicas |
| `app/modules/analytics/adaptive_ai.py`, `canonical_views.py`, `etl.py`, `gemini_worker.py`, `projections.py`, `reader_evidence.py`, `transactional_sources.py` | Aplicar la ocultación en las fuentes analíticas protegidas en etapa 2 |
| `app/main.py` | Registro del router de etapa 3 |
| `migrations/versions/0084_moderation_decisions_reports.py` | Reportes, unicidad, ocultación, referencia de reportes en auditoría y protección de resoluciones |
| `migrations/versions/0085_moderation_audit_context.py` | Contexto anterior/posterior inmutable de las decisiones |
| `tests/test_moderation_administration.py` | 19 pruebas HTTP de permisos, decisiones, reportes, visibilidad, contexto, rollback y regresiones |
| `tests/test_moderation_decision_concurrency.py` | 3 pruebas con transacciones PostgreSQL concurrentes y esquema aislado |
| `tests/test_moderation_foundation.py`, `test_moderation_integration.py` | Sustituir la antigua expectativa de ausencia de rutas de etapa 3 por denegación de acceso sin permiso real |

Se agregaron este documento y `artifacts/moderation-stage3/`. Los cambios de etapas
anteriores y del perfil que ya estaban sin confirmar se conservaron. No se editaron
archivos de frontend durante esta etapa.

## Migraciones aplicadas

Se aplicaron correctamente `0084_moderation_reports` y
`0085_moderation_audit_context`; esta última es el head de Alembic.

- Nueva tabla `app.reportes_contenido`, con destino exclusivo a publicación,
  reseña o comentario, motivo, detalle, denunciante, copia textual del contenido
  reportado y resolución. Cada usuario puede reportar una sola vez cada destino;
  otros usuarios pueden reportar ese mismo contenido.
- `moderation_hidden=false` en publicaciones, reseñas y comentarios. La ocultación
  es independiente de `moderation_status`: una edición posterior del autor no la
  borra ni permite eludirla.
- La tabla existente `app.auditoria_moderacion` admite un destino exclusivo a
  revisión o reporte y conserva contexto anterior/posterior. Sus registros siguen
  protegidos contra cambios y eliminación.
- Triggers adicionales impiden reescribir decisiones definitivas, evidencia de
  reportes y resoluciones. Los reportes no se eliminan físicamente.

No se transformaron cuerpos, relaciones, imágenes, estados históricos o fechas.
Los nuevos campos tienen valores compatibles. Los downgrades destructivos están
deshabilitados para conservar evidencia. Las migraciones requieren los bloqueos
de esquema habituales; su aplicación productiva debe programarse.

## API implementada

Todas las rutas administrativas verifican `AccountPermission(user_id, 'admin')`
y el estado activo de la cuenta en PostgreSQL. El texto de rol `admin` por sí solo
no autoriza. Los permisos y la cuenta se bloquean en lectura durante la operación,
para que una revocación concurrente no permita una autorización inconsistente.

| Método y ruta | Función |
| --- | --- |
| `GET /api/admin/moderation` | Cola paginada, filtro opcional `kind`, total real y contador de reportes pendientes |
| `GET /api/admin/moderation/{identifier}` | Propuesta completa, alertas, estado, contenido actual, versión pública cuando existe y adjuntos |
| `POST /api/admin/moderation/{identifier}/decision` | Aprobar o rechazar una revisión |
| `GET /api/admin/moderation/history` | Historial paginado de decisiones y resoluciones con contexto inmutable |
| `GET /api/admin/moderation/reports` | Reportes paginados por estado: `pending`, `dismissed` o `hidden` |
| `GET /api/admin/moderation/reports/{identifier}` | Motivo, denunciante, contenido originalmente reportado, contenido actual y resolución |
| `POST /api/admin/moderation/reports/{identifier}/resolution` | Descartar, ocultar o restituir |
| `GET /api/admin/moderation/{identifier}/attachments/{asset_id}` | Adjunto privado de una propuesta |
| `GET /api/admin/moderation/content/publication/{identifier}/images/{asset_id}` | Fotografía actual para revisión administrativa, incluso con padre no público |
| `GET /api/admin/moderation/content/publication/{identifier}/cover` | Portada personalizada actual para revisión administrativa |
| `POST /api/content-reports/{kind}/{identifier}` | Reportar contenido accesible; requiere autenticación y cuenta activa |

`kind` usa `publication`, `review` o `comment`. Los resultados y recursos privados
usan `Cache-Control: private, no-store`; las imágenes usan además `nosniff`.
Las rutas públicas de medios conservan sus comprobaciones de visibilidad.

Una decisión recibe:

```json
{"action":"approved","reason":"Contexto literario revisado","expected_version":1}
```

`action` admite `approved` o `rejected`. El motivo es obligatorio y admite hasta
2000 caracteres. `expected_version` es la versión base de la propuesta. Una
repetición de la misma decisión, motivo y versión devuelve la decisión ya tomada;
una decisión contradictoria devuelve `409` y no aplica cambios adicionales.

Una resolución de reporte recibe:

```json
{"action":"hidden","reason":"Ocultación preventiva tras revisión","expected_version":1}
```

Las acciones son `dismissed`, `hidden` y `restored`. Para ocultar o restituir, la
versión debe coincidir con la del contenido revisado. Se admite `Idempotency-Key`
para repetir exactamente la solicitud sin duplicar sus efectos. La restitución
se refiere a la ocultación vigente: un reporte antiguo no puede levantar una
ocultación posterior originada por otro reporte.

Los motivos de reporte son `discrimination` (discriminación), `harassment` (acoso
o insultos), `threats` (amenazas), `sexual_content` (contenido sexual inapropiado),
`spam` y `other` (otro). El detalle opcional admite hasta 2000 caracteres.
Repetir un reporte devuelve el registro existente sin reemplazar su evidencia.
Los reportes nunca ocultan automáticamente contenido.

## Aplicación y consistencia

Las operaciones bloquean el padre antes de la revisión o reporte, respetando el
orden de los escritores existentes. En comentarios se bloquea primero su actividad
padre. La decisión comprueba versión, huella completa, ciclo de vida y eliminación.
Una propuesta obsoleta, sustituida o retirada no puede publicarse.

Al aprobar se revalidan esquema, adjuntos, referencias y reglas de negocio. Se
conserva el ID; se aplican los textos y archivos propuestos y se reutiliza la
sincronización de eventos. Los asistentes no se reescriben. Las reseñas conservan
su selección canónica y registran la revisión editorial aprobada; una reseña nueva
recibe su primera fecha pública únicamente al aprobarse.

El rechazo de una edición no modifica su versión aprobada. El rechazo de una
creación mantiene ese contenido fuera de las consultas públicas. El autor consulta
la decisión y su motivo mediante las rutas privadas de etapa 2.

Una ocultación conserva el registro y sus relaciones, retira propuestas pendientes
vinculadas e impide interacciones públicas. La restitución no revive contenido
eliminado, reseñas retiradas por su autor, revisiones históricas ni comentarios
cuyo padre dejó de ser visible. La resolución original del reporte permanece
inmutable; una restitución posterior queda como un nuevo evento de auditoría.

Contenido aplicado, archivos, calendario y auditoría se confirman en una sola
transacción. Un fallo revierte el conjunto. No hay sanciones automáticas.

## Pruebas y resultados

**238 pruebas correctas: 216 de regresión y 22 nuevas de etapa 3.**

```powershell
.venv/Scripts/python.exe -m unittest tests.test_moderation_administration tests.test_moderation_decision_concurrency tests.test_moderation_integration tests.test_moderation_http_concurrency tests.test_moderation_foundation tests.test_mural_feed tests.test_activity_interactions tests.test_content_management tests.test_publication_events tests.test_identities tests.test_reading_challenge tests.test_profile_events tests.test_reviews tests.test_publication_covers tests.test_analytics_projections tests.test_daily_etl
.venv/Scripts/python.exe -m alembic current
git diff --check
```

Tras un ajuste final del registro de fecha de edición de comentarios se repitieron
las 22 pruebas de etapa 3 con éxito. `git diff --check` no presenta errores.

Se verificaron permisos reales y revocación, aprobación y rechazo de creaciones
y ediciones, archivos y portada, calendario y asistencia, valoración e historial,
comentarios de los tres destinos, propuestas obsoletas o eliminadas, reportes
únicos e inaccesibles, ocultación, restitución, versiones, auditoría inmutable,
evidencia previa a una edición, exclusión analítica y rollback completo.

Las tres pruebas concurrentes usan conexiones PostgreSQL independientes, tablas
clonadas vacías y triggers de protección dentro de un esquema aleatorio exclusivo.
Comprueban decisiones contradictorias, repeticiones de aprobación y cuatro
reportes simultáneos. El esquema se elimina al terminar; las tablas reales no se
usan para guardar decisiones de prueba ni se desactivan sus protecciones.

El servidor local se reinició con esta implementación. Se comprobaron las rutas
en OpenAPI y el rechazo `401` de la cola sin autenticación. No fue necesaria una
nueva prueba visual: esta etapa no modifica JSX, CSS, temas ni navegación.

## Integridad y riesgos pendientes

La comparación de conteos y hashes de diez tablas coincide con la captura anterior
a la etapa: publicaciones, reseñas, comentarios, eventos, asistencias, tres tipos
de likes, visualizaciones y eventos de lectura. Se excluye únicamente el nuevo
campo `moderation_hidden` del hash comparable, y se verifica aparte que ningún
registro histórico quedó oculto. No quedaron filas de prueba en revisiones,
adjuntos, auditoría, solicitudes o reportes, ni esquemas temporales de prueba.

La evidencia sin textos personales está en `artifacts/moderation-stage3/before.json`,
`after.json` y `verification.json`. Biblioteca y reto anual no se modificaron y sus
pruebas de regresión pasaron.

Pendientes y límites:

1. La interfaz en Configuración y las notificaciones siguen reservadas a etapa 4.
   Por ahora la gestión se realiza mediante API autenticada.
2. Las reglas heurísticas y sus límites lingüísticos siguen vigentes; el contexto
   requiere revisión humana y motivo explícito. No hay rechazo automático.
3. La evidencia de decisiones y reportes conserva texto y huellas de imágenes, no
   una nueva copia binaria de cada archivo público anterior. Los adjuntos privados
   de propuestas sí se conservan. Una fotografía retirada por una edición aprobada
   puede dejar de estar disponible en su URL pública anterior.
4. La retención de propuestas, reportes, adjuntos y evidencia necesita una política
   operativa. No se agregó limpieza automática que pueda destruir auditoría.
5. No se reconstruyen proyecciones analíticas históricas; sus nuevas consultas de
   origen excluyen el contenido ocultado. No se modifican agregados históricos.
6. Un reporte resuelto con ocultación conserva `status=hidden` como resolución
   histórica aunque posteriormente se restituya el contenido. El estado actual y
   el historial de restitución se consultan en detalle e historial.

La etapa 3 queda entregada para revisión. No se avanzará automáticamente a etapa 4.
