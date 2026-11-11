# Avisos de solicitudes de perfil

La campanita y `/notifications` consultan ahora `/api/me/notification-inbox`: combina los seguimientos existentes con avisos privados de solicitudes de perfil. Los endpoints antiguos de seguimiento y moderación se conservan.

- Solicitud nueva: un aviso para cada administrador activo autorizado, salvo el propio solicitante.
- Aprobación o rechazo: un aviso para el titular, con la observación administrativa y enlace a Mi cuenta. La aprobación conserva el aviso aunque invalide la sesión anterior.
- Al decidir, los avisos administrativos pendientes de esa solicitud quedan leídos para que el contador no indique trabajo pendiente resuelto.
- Cada destinatario puede marcar sus avisos como leídos; la operación es idempotente. Otros usuarios reciben 404. Si se retiran permisos administrativos, dejan de mostrarse los avisos de revisión.
- Los avisos se guardan en la misma transacción que la solicitud o decisión. La combinación de solicitud, destinatario y tipo es única.

La campanita muestra el total sin leer. Consulta al entrar/cambiar de ruta, al volver a la ventana y cada 30 segundos; los cambios locales de lectura y decisión disparan una actualización inmediata. No usa servicios externos ni WebSockets. La bandeja permite volver a intentar si falla la consulta.

`0094_role_notifications`, posterior a `0093_editorial_account`, crea `app.notificaciones_perfil` y recupera avisos para solicitudes pendientes y decisiones ya registradas, usando sus fechas reales. No modifica las solicitudes existentes. La migración se aplicó a `libria` tras un respaldo (`backups/before-role-notifications-20261111-193649.dump`): recuperó el rechazo ya registrado y preservó usuarios, lecturas, reseñas, publicaciones y solicitudes.

## Validación

En PostgreSQL aislado:

```powershell
docker compose -f compose.influencer-test.yaml build test
docker compose -f compose.influencer-test.yaml run --rm test python -m alembic upgrade head
docker compose -f compose.influencer-test.yaml run --rm test python -m unittest tests.test_role_notifications tests.test_account_management tests.test_moderation_notifications tests.test_community_profiles
```

Resultado: 61 pruebas correctas, incluidas privacidad por destinatario, autorizaciones administrativas, aprobación/rechazo, ausencia de duplicados, contador independiente de la paginación, rollback y convivencia con seguimientos.

Desde `apps/web`: `npm run test:role-notifications`, `npm run lint -- --quiet` y `npm run build`. Chrome headless valida campanita administrativa, rechazo del lector, observación, enlaces y actualización del contador al marcar como leído, mediante API simulada. Compilación y ESLint correctos.
