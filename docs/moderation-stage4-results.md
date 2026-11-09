# Moderación preventiva: entrega de etapa 4

> Corrección posterior: el montaje inicial estaba en una ruta distinta de la opción
> «Configuración» del menú. La ubicación canónica es ahora `/settings?tab=moderation`.
> Véase `docs/moderation-access-fix.md`, que documenta la causa, la corrección y el
> estado pendiente de validación visual con una cuenta real.

## Resultado

La gestión de moderación está integrada dentro de la configuración administrativa
existente (`/admin/environment`, acceso «Configurar aplicación»), en la sección
**Moderación de contenido**. No se creó una página de moderación independiente ni
una entrada en el menú principal. Las configuraciones de Backend y Web conservan
sus formularios y orden anteriores.

La sección incorpora Pendientes de aprobación, Reportes de usuarios e Historial.
Los contadores proceden de la API. Se muestran autores, fechas, categorías y motivos
de alerta, propuestas completas, versiones públicas anteriores y adjuntos privados.
La decisión requiere seleccionar una acción, escribir un motivo y confirmarla.
Los envíos tienen protección contra doble clic y recuperación ante conflictos 409.
El historial es de solo lectura.

Se puede reportar desde publicaciones, eventos, comentarios y reseñas de la ficha
del libro. El formulario compacto solicita motivo y detalle opcional. Una confirmación
informa del envío; repetirlo no crea otro reporte en la base. El backend permite
reportar contenido propio, por lo que esta entrega no agrega una prohibición distinta
en React. Un reporte nunca oculta contenido automáticamente.

Los estados privados y motivos de decisiones están disponibles en **Mi perfil →
Mi actividad → Estado de mis contenidos**. Los envíos pendientes muestran un aviso
con acceso a esa sección y no se insertan como contenido público.

Notificaciones reemplaza únicamente su anterior arreglo de demostración por una
bandeja real y privada de moderación. No se inventaron notificaciones sociales.

## Archivos de esta etapa

Rutas relativas a `apps/backend/`:

| Archivo | Cambio |
| --- | --- |
| `app/modules/social/moderation_models.py` | Modelo de notificación privada con unicidad por autor, revisión y evento |
| `app/modules/social/moderation_notifications.py` | Persistencia transaccional, bandeja propia, conteo de no leídas y marcado de lectura |
| `app/modules/social/moderation_service.py` | Registrar aviso pendiente al preparar una revisión con alertas |
| `app/modules/social/moderation_decisions.py` | Registrar aviso de aprobación o rechazo en la misma transacción de la decisión |
| `app/modules/social/moderation_admin_router.py` | Autores reales, extractos, hallazgos, nombres de administradores y cantidades de reportes obtenidas por lotes |
| `app/modules/social/moderation_private_router.py` | Título, extracto y fecha de decisión en el estado privado del autor |
| `app/main.py` | Registro de la bandeja privada de notificaciones |
| `migrations/versions/0086_moderation_notifications.py` | Migración aditiva de notificaciones |
| `tests/test_moderation_notifications.py` | Siete pruebas nuevas de privacidad, persistencia, lectura, deduplicación, rollback, metadatos y paginación |
| `tests/test_moderation_decision_concurrency.py` | Incorporar notificaciones al esquema aislado de las pruebas concurrentes |

Rutas relativas a `apps/web/`:

| Archivo | Cambio |
| --- | --- |
| `src/components/ModerationSection.jsx` | Gestión administrativa, pestañas, contadores, paginación y diálogo de revisión |
| `src/components/ModerationContent.jsx` | Comparación completa y carga autenticada de imágenes privadas mediante URLs temporales |
| `src/components/ContentReportButton.jsx` | Formulario reutilizable de reportes y confirmación |
| `src/components/PrivateModerationStatus.jsx` | Estados privados dentro de Mi actividad y detalle accesible desde notificaciones |
| `src/components/ModerationNotice.jsx` | Aviso de envío pendiente con enlace al estado privado |
| `src/components/Moderation.css` | Estilos compartidos basados en las variables existentes de los nueve temas |
| `src/services/moderation.js` | Transporte autenticado, etiquetas y mensajes para 403/404/409 |
| `src/pages/AdminEnvironmentPage.jsx` | Integrar la sección en Configuración sin reemplazar los formularios existentes |
| `src/pages/NotificationsPage.jsx` | Bandeja real, lectura y enlaces privados; retirar solo datos de demostración |
| `src/pages/ProfilePage.jsx` | Integrar los estados en Mi actividad, manteniendo la navegación de paneles |
| `src/components/Layout.jsx`, `src/api/client.js` | Mostrar avisos de pendientes; admitir recursos privados binarios sin incluir credenciales en URLs |
| `src/components/ActivityOptionsMenu.jsx`, `CommentEntry.jsx`, `BookReviews.jsx`, `FeedCard.jsx` | Accesos a Reportar, incluida la cabecera especial de eventos |
| `src/pages/HomePage.jsx`, `LibraryBookPage.jsx` | Mensajes correctos para ediciones, notas, teorías y reseñas pendientes, sin afirmar que ya son públicas |
| `tests/moderation-ui.mjs`, `tests/fixtures/moderation.html`, `tests/fixtures/moderation.jsx`, `package.json` | Pruebas de navegador aisladas y comando `test:moderation` |

Se reutilizaron `AdminGate`, `ProfileEditModal`, Configuración, los menús de contenido,
Mi actividad, la página de notificaciones y la capa HTTP existentes. Los archivos de
las etapas previas y otros cambios no confirmados se conservaron. Las capturas del
mural se actualizaron al ejecutar su suite de regresión.

## Migración y notificaciones

`0086_moderation_notifications` se aplicó correctamente y es el head de Alembic.
Agrega `app.notificaciones_moderacion` con destinatario, revisión, tipo, fecha de
creación y fecha de lectura. Una restricción única impide duplicar un evento de
notificación para el mismo autor y revisión.

No se reconstruyeron notificaciones históricas. El registro de pendientes y de
decisiones comparte la transacción del contenido y la auditoría: un fallo revierte
también la notificación. Repetir una solicitud o decisión no genera avisos nuevos.

Los mensajes son:

- «Tu contenido fue enviado a revisión. Te avisaremos cuando esté aprobado».
- «Tu publicación fue aprobada y ya está disponible en LibrIAverse».
- «Tu contenido no fue aprobado porque incumple nuestras normas de convivencia».

El motivo de rechazo se obtiene de la decisión real y solo se entrega a su autor.
Las respuestas no se cachean públicamente. La interfaz no conserva la bandeja de
una cuenta anterior al cambiar de usuario.

## Endpoints conectados

Se reutilizan las rutas administrativas de etapa 3:

- `GET /api/admin/moderation`, `GET /api/admin/moderation/{id}`.
- `POST /api/admin/moderation/{id}/decision`.
- `GET /api/admin/moderation/reports`, `GET /api/admin/moderation/reports/{id}`.
- `POST /api/admin/moderation/reports/{id}/resolution`.
- `GET /api/admin/moderation/history`.
- Las rutas administrativas de fotografías, portadas y adjuntos privados.
- `POST /api/content-reports/{kind}/{id}`.

El estado propio reutiliza `GET /api/me/moderation`, su detalle y adjuntos.

Endpoints nuevos:

- `GET /api/me/notifications?limit=20&offset=0`: bandeja propia y total real de no leídas.
- `PUT /api/me/notifications/{id}/read`: lectura idempotente, autorizada por destinatario.

La autorización administrativa sigue basada en `AccountPermission`, comprobada
por el servidor, y la interfaz usa el acceso real de `AuthContext`/`AdminGate`.
No se introdujeron decisiones optimistas: después de guardar se actualizan la lista
y sus contadores desde la API. La restitución conserva las comprobaciones de versión
y ocultación vigente de etapa 3.

## Pruebas ejecutadas

**245 pruebas de backend correctas**, incluidas las 238 anteriores y siete nuevas:

```powershell
.venv/Scripts/python.exe -m unittest tests.test_moderation_notifications tests.test_moderation_administration tests.test_moderation_decision_concurrency tests.test_moderation_integration tests.test_moderation_http_concurrency tests.test_moderation_foundation tests.test_mural_feed tests.test_activity_interactions tests.test_content_management tests.test_publication_events tests.test_identities tests.test_reading_challenge tests.test_profile_events tests.test_reviews tests.test_publication_covers tests.test_analytics_projections tests.test_daily_etl
.venv/Scripts/python.exe -m alembic current
```

Frontend:

```powershell
npm run test:moderation
npm run test:mural
node tests/moderation-transport.mjs
npm run lint
npm run build
git diff --check
```

Resultados:

- Configuración existente conservada; acceso denegado a usuarios sin permiso.
- Contadores, comparación de versiones, aprobación, rechazo, reportes, ocultación,
  restitución, historial inmutable, estados privados y lectura de notificaciones.
- Prevención de dobles envíos y recuperación ante 409, exigiendo una nueva revisión
  y confirmación.
- Nueve temas a 360, 768 y 1440 px, sin desbordamiento de página ni modal.
- Reportar desde publicación, comentario y reseña; los eventos usan la misma acción
  en su cabecera especial. La regresión del mural conserva galería e interacciones.
- Sin excepciones de navegador. Captura revisada visualmente en
  `artifacts/moderation-stage4/admin-comparison.png`.
- Lint sin errores; conserva una advertencia previa de limpieza de una referencia
  en `Layout.jsx`. Build correcto, con la advertencia de tamaño del bundle de Vite.
- Las pruebas del navegador usan datos aislados de prueba; no son contadores de la
  aplicación publicada. Las pruebas backend usan PostgreSQL y rollback/esquemas
  aislados para no dejar decisiones de prueba en tablas reales.

El servidor local se reinició con esta versión. OpenAPI expone las dos nuevas rutas
y la bandeja sin autenticación devuelve `401`.

## Integridad y límites

Los conteos y hashes completos de las diez tablas comparadas coinciden antes y
después de la etapa: publicaciones, reseñas, comentarios, eventos, asistencias,
tres tipos de likes, visualizaciones y eventos de lectura. No quedaron registros
de prueba en revisiones, adjuntos, auditoría, solicitudes, reportes o notificaciones,
ni esquemas temporales de concurrencia.

La evidencia sin textos personales está en `artifacts/moderation-stage4/before.json`,
`after.json` y `verification.json`. No se modificaron datos históricos, progresos,
asistencias, biblioteca ni reto anual. En la ficha de biblioteca solo se corrigieron
los mensajes de resultado de sus envíos públicos.

Límites pendientes:

1. Las notificaciones son internas a LibrIAverse; no se agregaron correo, push,
   notificaciones sociales ni reconstrucción de avisos anteriores.
2. La bandeja y los estados se consultan al abrirlos o actualizar la vista; no hay
   un canal en tiempo real entre sesiones de administrador y autor.
3. Las reglas siguen siendo heurísticas y requieren revisión humana del contexto.
4. La política operativa de retención de revisiones, adjuntos, reportes, auditoría
   y notificaciones sigue pendiente. No se agregó limpieza destructiva.
5. La comparación histórica conserva texto y huellas de medios; no recupera
   fotografías públicas retiradas por una edición aprobada. Los adjuntos privados
   de propuestas continúan protegidos y disponibles según sus permisos.

No se agregaron capacidades de moderación fuera del alcance solicitado.
