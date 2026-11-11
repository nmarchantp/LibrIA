# Landing de mantención

Configura `MAINTENANCE_MODE=true` en `apps/backend/.env` y reinicia el backend.
El frontend consulta `GET /api/status` al abrir y cada 30 segundos. No requiere
recompilar el frontend para cambiar el modo.

La landing permite crear cuentas sin tokens ni sesiones. El resto de `/api`
responde con 503, incluidos login, Google y sesiones existentes. `/health` sigue
disponible. La presentación incluye IA, comunidad literaria y estrellas con cinco
luceros animados. Ambos registros piden nombre, correo y confirmación de contraseña
y muestran una estimación de seguridad baja, media o alta.

Para recuperar el acceso habitual, configura `MAINTENANCE_MODE=false` (valor por
defecto) y reinicia el backend. Las cuentas creadas pueden ingresar normalmente.
