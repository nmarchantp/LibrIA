# Moderación preventiva: diagnóstico y plan del MVP

## Resultado del diagnóstico

El repositorio no contiene un servicio de moderación, una cola de revisión ni un
modelo de reportes. Esta primera entrega documenta la implementación propuesta;
no agrega todavía migraciones ni modifica la visibilidad de contenido existente.

| Área | Implementación actual | Integración necesaria |
| --- | --- | --- |
| Publicaciones | `social/models.py`: `Post`, `PostImage`, `PostBookCover`; creación en `social/router.py`, edición en `publication_management.py` | Analizar antes de publicar; conservar la versión pública durante ediciones pendientes, incluidos adjuntos, obra y datos del evento |
| Reseñas | `Review`, `ReviewRevision`; `reviews_router.py`; una reseña por perfil y obra, con revisiones | Mantener `status` editorial separado de moderación; aprovechar `ReviewRevision` para el historial aprobado |
| Comentarios | `PostComment`, con destino exclusivo a publicación, reseña o evento de lectura | Moderar comentarios en los tres destinos; filtrar listas y conteos; conservar historial de ediciones |
| Interacciones | `interaction_service.py`, `interactions_router.py` y rutas antiguas de `/posts` | Aplicar la misma política en rutas tipadas y de compatibilidad, también al abrir imágenes o registrar vistas |
| Permisos administrativos | `AccountPermission(user_id, 'admin')`, dependencia `get_admin` en `users/roles_router.py` | Reutilizar la autorización real; el texto `user.role == 'admin'` no es suficiente |
| Visibilidad | `visible_posts`, `public_reviews`, `resolve_activity` en `activity_access.py` | Ampliar las condiciones centrales y revisar consumidores que todavía consultan directamente las tablas |
| Edición/eliminación | Publicación: edición directa y borrado lógico. Reseña: edición directa, revisión e invisibilidad mediante `hidden`. Comentario: edición directa y eliminación física | La edición pendiente necesita una propuesta separada; el comentario requiere borrado lógico para conservar referencias e historial de moderación |
| Notificaciones | `NotificationsPage.jsx` muestra un arreglo de demostración; no hay un servicio persistente reutilizable | Incorporar notificaciones privadas mínimas de decisiones, vinculadas a su revisión y sin duplicados |
| Reportes | No existen | Agregar destino tipado, motivo, denunciante, estado de resolución y unicidad por usuario/contenido |

### Rutas de escritura que deben cubrirse

- `POST /api/posts` y `PUT /api/posts/{id}`.
- `POST /api/reviews` y `PUT /api/reviews/{id}`; solo el intento de publicación
  pública requiere revisión preventiva, no el guardado de un borrador privado.
- `POST /api/activities/{kind}/{id}/comments` y su `PUT .../comments/{comment_id}`.
- Ruta compatible `POST /api/posts/{id}/comments`, que también puede resolver
  reseñas y eventos de lectura: no puede quedar como vía para eludir el filtro.
- Las rutas de eliminación deben retirar propuestas pendientes vinculadas sin
  destruir su auditoría ni permitir que una aprobación posterior reviva contenido.

La lectura automática no se convierte en un nuevo tipo de publicación moderada:
sí se moderan sus comentarios, porque son contenido público escrito por usuarios.
Los textos privados de cuadernos o borradores no se envían a la cola por defecto.

### Lecturas públicas que necesitan protección

Además del mural paginado y sus carruseles, deben cubrirse:

- `GET /posts`, `GET /posts/{id}` y rutas antiguas de comentarios.
- Calendario, agenda del perfil y ficha original del evento; usan `visible_posts`.
- `GET /reviews/{id}`, `GET /reviews/by-book/{ref}`, reseñas en fichas de libros.
- `books/consistency.py::current_reviews(public=True)` y
  `books/community.py::public_rating`: mantienen selección canónica y deduplicación.
- Conteos de comentarios en `interaction_service.py::batch_counts`.
- Archivos y portada: la URL del recurso también debe autorizar el contenido padre.
- Proyecciones sociales de analítica y consultas SQL que usan reseñas publicadas;
  ningún conteo o recomendación pública puede revelar una reseña pendiente.

Los filtros se aplicarán antes de límites y paginación. No se reemplaza una
selección canónica por una consulta simple, ni se hace reaparecer una reseña
histórica al ocultar la vigente. La biblioteca, sus estados y el reto anual son
independientes y no requieren cambios.

## Cambios de persistencia propuestos

Migración exclusivamente aditiva:

1. `moderation_status` en publicaciones, reseñas y comentarios, con valores
   `approved`, `pending_review`, `rejected`. El valor de compatibilidad inicial
   será `approved`: los datos existentes mantienen su visibilidad actual y no se
   analizan retroactivamente. En reseñas, `draft/published/hidden` sigue siendo
   un eje separado: un borrador `approved` continúa siendo privado.
2. Revisiones de moderación: destino exclusivo con claves foráneas tipadas,
   autor, versión base, propuesta validada, estado, hallazgos y versión de reglas,
   fechas y datos de decisión. Una propuesta pendiente no sobrescribe el registro
   público ni incrementa sus contadores.
3. Adjuntos de propuesta: almacenar las fotografías nuevas en un área privada
   de la revisión, referenciar los adjuntos conservados y diferir su eliminación.
   Se conservan las validaciones de tamaño/formato. No se analizan imágenes.
4. Reportes: destino exclusivo publicación/reseña/comentario, denunciante, motivo,
   detalle limitado y resolución. Restricciones únicas por denunciante y destino;
   varios usuarios pueden reportar un mismo contenido, cada uno una sola vez.
5. Auditoría de decisiones y ocultaciones preventivas, con administrador, fecha,
   motivo obligatorio y revisión exacta evaluada. El historial es inmutable.
6. Idempotencia de solicitudes por usuario, operación y clave de cliente, con hash
   del contenido. Reutilizar una clave con otro cuerpo produce conflicto; repetir
   la misma solicitud devuelve el mismo resultado sin crear contenido adicional.
7. Notificaciones privadas de moderación, con destinatario, decisión y lectura;
   unicidad por decisión/destinatario. No se construirá un sistema general de
   notificaciones sociales ni se reutilizarán las cifras de demostración.
8. Borrado lógico de comentarios y versiones de concurrencia cuando el registro
   actual no disponga de una versión adecuada. Los comentarios previos conservan
   sus identificadores y relaciones.

Se aprovechará `ReviewRevision` al publicar una revisión aprobada. Las propuestas
pendientes se mantienen fuera de esa proyección pública. Los eventos conservan
su ID, sus asistentes, likes y comentarios al aprobar una edición. Cambios de
horario solo se sincronizan con el calendario cuando la propuesta se aprueba.

## Servicio central de reglas

Un módulo de FastAPI compartido analizará el texto original sin modificarlo.
Normalización para comparar: Unicode, mayúsculas/minúsculas, variantes de acentos,
caracteres invisibles y patrones de evasión acotados. Se conservará el texto
original para mostrarlo y evaluarlo.

Las reglas estarán versionadas y configuradas en un archivo validado, con
categoría, patrón contextual, motivo y umbral. Cubrirán racismo/xenofobia,
homofobia/transfobia, misoginia/sexismo, odio, insultos/acoso, amenazas, acoso sexual
y spam. No habrá sanciones ni rechazos automáticos.

La salida incluirá `flagged`, `findings[{category, reason, rule_id, confidence}]`
y `ruleset_version`. La confianza será una estimación de la regla, no una
probabilidad estadística ni una afirmación de comprensión del contexto.

Las palabras de temas sensibles por sí solas no activarán alertas. Se probarán
discusiones sobre violencia, racismo y sexualidad en libros, citas contextualizadas
y críticas literarias junto a ataques directos. Los casos dudosos se enviarán a
revisión humana; una cita no será una excepción automática que permita amenazas.
Los reintentos idempotentes no se considerarán spam nuevo.

## Flujos y consistencia

**Creación:** validar identidad y permisos, reclamar la clave idempotente,
analizar, persistir contenido y resultado en una transacción. Sin alertas se
publica normalmente; con alertas se guarda pendiente y solo es accesible para
autor y administradores mediante rutas privadas.

**Edición aprobada:** validar todos los campos y guardar la propuesta completa.
Si hay alertas, título, texto, valoración, imágenes, obra y datos del evento
actualmente aprobados se mantienen. El autor ve que su edición está pendiente.
Si la nueva versión no activa alertas, se publica mediante el mismo servicio,
con historial, evitando dos implementaciones de aplicación de cambios.

**Decisión administrativa:** bloquear revisión y contenido padre en un orden
estable; comprobar versión y vigencia; aprobar o rechazar con motivo; aplicar
cambios, auditoría y aviso privado en una sola transacción. La misma decisión
repetida es idempotente; una decisión contraria o una revisión obsoleta devuelve
`409`. Una propuesta anterior no puede reemplazar una edición más reciente.

**Reporte:** autorizar el acceso al contenido real antes de registrar el reporte;
insertar con unicidad, sin ocultar automáticamente. Un administrador puede
ocultarlo preventivamente con motivo, conservando la versión y el historial.
Las interacciones vuelven a comprobar visibilidad en el servidor aunque la
tarjeta ya estuviese abierta en el navegador.

**Eliminación:** una aprobación posterior no puede restaurar un contenido que el
autor eliminó u ocultó. La cancelación o sustitución de una propuesta queda
registrada en su historial, sin borrar decisiones ni informes anteriores.

## API y experiencia de usuario propuestas

Conservar las rutas actuales e incorporar metadatos de resultado de moderación.
Añadir:

- `GET /api/me/moderation`: estado propio, propuestas, decisiones y motivo de rechazo.
- `GET /api/admin/moderation`: cola paginada de revisiones y reportes.
- `GET /api/admin/moderation/{id}`: texto completo, propuesta, versión pública y contexto.
- `POST /api/admin/moderation/{id}/decision`: aprobar/rechazar con versión esperada y motivo.
- `POST /api/admin/moderation/{id}/visibility`: ocultación preventiva o restitución autorizada, auditada.
- `POST /api/content-reports/{kind}/{id}`: motivos cerrados y detalle opcional limitado.
- Consultas de historial y notificaciones privadas, con autorización por destinatario.

El frontend agregará una página administrativa usando la autorización existente,
«Reportar» en `ActivityOptionsMenu`, `CommentEntry` y reseñas de la ficha, y un
estado privado dentro de «Mi actividad». El evento del mural tiene una cabecera
especial que omite el menú común: también necesita un acceso real a reportar.
Se reutilizarán diálogos y estilos del proyecto, con foco y áreas táctiles accesibles.

Los mensajes serán los solicitados:

- «Tu contenido fue enviado a revisión. Te avisaremos cuando esté aprobado».
- «Tu publicación fue aprobada y ya está disponible en LibrIAverse».
- «Tu contenido no fue aprobado porque incumple nuestras normas de convivencia».

Los pendientes no se insertarán optimistamente en listas públicas de comentarios,
ni se mostrarán como errores de publicación que inviten a enviarlos otra vez.

## Etapas y criterios de cierre

1. **Núcleo y persistencia:** reglas configurables, modelos, migración aditiva,
   permisos y transacciones; pruebas de normalización, legitimidad contextual,
   propiedad, unicidad, concurrencia y compatibilidad de registros anteriores.
2. **Creación, edición y lecturas públicas:** integrar todas las rutas actuales y
   antiguas; preservar versiones públicas y adjuntos; revisar conteos, fichas,
   calendario y consultas canónicas. Ejecutar las suites existentes del mural,
   comentarios, gestión de contenido, reseñas, eventos e identidades.
3. **Revisión administrativa y reportes:** decisiones atómicas, historial,
   ocultación preventiva y reportes únicos; pruebas de administración por permiso
   real, propuestas obsoletas, decisiones simultáneas y eliminación durante revisión.
4. **Interfaz y avisos privados:** estados de envío, vista del autor, panel admin,
   reportar en los tres tipos y notificaciones persistentes. Validar nueve temas,
   móvil, teclado y ausencia de contenido o conteos pendientes en vistas públicas.

Cada etapa debe quedar probada antes de continuar. La funcionalidad solo se dará
por terminada cuando la migración, las rutas alternativas, la conservación de
la versión aprobada y las pruebas de permisos/concurrencia pasen correctamente.
