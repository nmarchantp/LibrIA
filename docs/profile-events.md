# Mis eventos

La quinta pestaña del perfil proyecta `PublicationEvent`, su `Post` original y
`EventAttendance`. No crea eventos, publicaciones ni asistencias adicionales.
Las cancelaciones conservan la fila histórica con `attending=false`.

## Acceso y persistencia

- `GET /api/profiles/{profile_id}/events/access`: autorización de la pestaña,
  sin conteos ni información de asistencia. Acepta `me`.
- `GET /api/profiles/{profile_id}/events`: agenda paginada; acepta `me`,
  `period=upcoming|past`, `participation=all|attending|organizing`, `offset`, `limit`.
- `PATCH /api/profiles/me/events/privacy`: `visibility=private|contacts|public`.
  Solo modifica la cuenta autenticada.

Las tres rutas requieren autenticación, como los perfiles comunitarios existentes.
La migración aditiva `0080_profile_events_privacy` agrega una preferencia con
valor inicial `private`, una restricción de valores y un índice de asistencias
activas por usuario. Se aplicó y se verificó como head en el entorno local.

`contacts` comprueba que el visitante siga al propietario, no la relación inversa.
Los permisos se comprueban antes de contar o paginar. `visible_posts()` también
se aplica antes de paginar: la privacidad pública de una agenda nunca habilita
una publicación eliminada o inaccesible. Las respuestas no se almacenan en caché.

La política `can_create_events` comparte la regla de publicación del servidor,
comprueba el actor personal, el estado de cuenta y su permiso actual. El endpoint
de creación y los filtros de organización usan esa misma política. React utiliza
la capacidad devuelta por el servidor.

## Fechas e imágenes

Un evento sigue siendo próximo mientras su término no haya pasado. Si no tiene
término explícito, se usa el final del día de inicio en su zona IANA. No se borran
asistencias al finalizar. Los eventos históricos sin fechas estructuradas siguen
en el mural; no se inventan fechas para incluirlos en una agenda temporal.

Las tarjetas usan las fuentes actuales de presentación del evento: imagen de obra
personalizada de la publicación, primera fotografía adjunta y portada disponible;
si no hay imagen válida, muestran un libro como placeholder. Esto no altera la
portada del catálogo ni reactiva el selector de imagen representativa retirado.

Las tarjetas enlazan al diálogo de la publicación original. La edición reutiliza
`ContentManagementDialog`; la cancelación reutiliza el estado compartido y el
endpoint de asistencia. Una notificación local de cambios de asistencia actualiza
la agenda; volver a la sección o enfocar la ventana consulta los datos actuales.

## Validación

- 103 pruebas backend: agenda, privacidad, dirección de seguimiento, filtros,
  límites temporales, deduplicación, consultas por lotes, eventos, edición,
  identidades e interacciones.
- `npm run test:profile-events`: pestañas, propietario/visitante, filtros de lector,
  privacidad, sincronización/cancelación, guardado de edición, enlace original,
  dos tarjetas alineadas y nueve temas en anchos 1760, 1024 y 390 px.
- `npm run lint`: sin errores; advertencia preexistente en `Layout.jsx`.
- `npm run build`: correcto; aviso de tamaño del bundle existente.

Los datos de navegador son fixtures aisladas; las pruebas backend revierten sus
transacciones. No se alteraron eventos reales para probar esta función.
