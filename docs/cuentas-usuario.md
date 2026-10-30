# Cuentas de usuario: funcionamiento, contratos y validación

Fecha: 29 de octubre de 2026. Rama: `Nicole`. Sin commits ni push.

## Alcance y decisiones aprobadas

Se reutilizan React, FastAPI, PostgreSQL, Alembic, SMTP y la autenticación existente. Los JWT cortos siguen respaldados por sesiones persistentes y refresh tokens rotativos; se mantiene la detección de reutilización.

El titular conserva su UUID y tiene un único `User.role`. El `username` es generado, único y de solo lectura para el titular; un administrador puede modificarlo con un motivo auditado. El nombre visible y la biografía son independientes del nombre de usuario.

Las decisiones confirmadas para esta implementación son:

- Conservar contenido y relaciones después de la eliminación definitiva, minimizando los datos de cuenta y mostrando «Cuenta eliminada» como autor. El texto libre con datos personales requiere una revisión separada.
- Librería es un tipo exclusivo de cuenta. Las organizaciones y membresías existentes se conservan; no se convierten ni borran automáticamente. No aparecen como identidades alternativas para publicar.

No se introduce un selector de perfil activo. Las capacidades históricas no prevalecen sobre `User.role` al autorizar publicaciones.

## Funcionalidad existente reutilizada y brechas corregidas

Ya existían registro con contraseña, login, Google OAuth con firma/issuer/audience/nonce y `sub`, verificación de correo para vincular Google, sesiones revocables, rotación de refresh, perfiles personales, verificación profesional, historial de roles y configuración de cuenta.

Faltaban edición propia completa, username estable, fotos validadas, límite uniforme de biografía, cambio/recuperación de contraseña, cambio de correo, desvinculación Google con acceso alternativo, suspensión, eliminación recuperable y procesamiento definitivo. La auditoría anterior cubría principalmente roles e identidades.

## Flujos del titular

En Configuración → Mi cuenta se puede editar el nombre visible y la biografía, subir/reemplazar/retirar una foto, cambiar contraseña, verificar/cambiar correo, gestionar Google y cerrar sesiones. Username y tipo de perfil son de solo lectura.

La biografía admite 70 puntos de código Unicode, tanto en backend como en el contador del frontend. No se recortaron biografías antiguas durante la migración: si superan el límite deberán corregirse al editarlas.

Las fotos admiten JPEG, PNG y WebP, hasta 2 MiB y 16 megapíxeles. Se decodifican y vuelven a codificar como JPEG de hasta 1024×1024, eliminando metadatos y evitando servir el archivo original. La lectura envía `nosniff` y `no-store`. Retirar la foto conserva los eventos administrativos.

Las operaciones sensibles verifican la contraseña actual en la misma operación. Todas las cuentas que permite registrar el sistema actual tienen contraseña; no se introdujeron cuentas Google sin contraseña. Si se incorpora ese tipo de registro, será necesario un flujo adicional de reautenticación con Google.

Cambiar contraseña, restablecerla, confirmar un nuevo correo o desvincular Google revoca las sesiones. Desvincular requiere contraseña válida y correo principal verificado. Se conserva la vinculación existente por `sub`, sin crear cuentas por coincidencia de correo.

El cambio de correo requiere contraseña y un desafío enviado al nuevo correo, válido durante diez minutos. El correo anterior sigue siendo principal hasta la confirmación y se intenta notificarle el cambio. Una colisión de correo al confirmar produce 409 y revierte la transacción.

La pantalla de acceso enlaza a `/recover-account` para restablecer contraseña o cancelar una eliminación. La respuesta al solicitar recuperación no confirma si existe una cuenta, y el límite de reenvío tampoco cambia esa respuesta. Se almacena el SHA-256 de un token aleatorio de 256 bits, nunca el token en claro. Los desafíos caducan en diez minutos, son de un solo uso y se invalidan al cambiar credenciales o estado.

## Estados y eliminación

`account_status` puede ser `active`, `pending_deletion` o `anonymized`. `suspended_at` es independiente, para que recuperar una cuenta no quite una suspensión.

Al confirmar la eliminación con contraseña:

1. Se registra `deletion_requested_at` en UTC.
2. `deletion_scheduled_at` se fija exactamente 30×24 horas después.
3. Se revocan todas las sesiones y se invalidan desafíos anteriores.
4. Se bloquea el acceso ordinario, incluido renovar sesiones.

La recuperación por correo solo funciona antes de la fecha límite. Cancelar borra las fechas pendientes e invalida los desafíos; requiere un nuevo login y conserva cualquier suspensión. Las fechas se muestran en la zona horaria del navegador.

El proceso definitivo conserva UUID, biblioteca, intentos/eventos de lectura, reseñas, revisiones, publicaciones y relaciones. Sustituye correo y username por valores técnicos, elimina nombre/biografía/foto y vinculaciones Google, inutiliza la contraseña, revoca sesiones y minimiza los datos de desafíos. También retira nombre, biografía y username de las instantáneas de auditoría, conservando operación, actor, fecha, motivo y correlación.

No borra contenido libre ni registros de consumo/analítica indiscriminadamente. La revisión de datos personales dentro de publicaciones, comentarios, notas, motivos administrativos o snapshots de IA queda separada, según la decisión aprobada. No debe presentarse esta minimización como garantía de anonimato de todo texto histórico.

Una cuenta que sea el único administrador activo de una organización debe transferir esa responsabilidad antes de solicitar la eliminación. Se bloquea la fila de la organización para serializar solicitudes y cambios de membresía.

El scheduler existente incorpora una tarea de cuentas cada 60 segundos, independiente de las opciones de ETL. El bloqueo de usuario y `SKIP LOCKED` permiten varios procesos sin duplicar la minimización. La recuperación toma el mismo bloqueo y verifica nuevamente el plazo y el estado.

También existe `python -m scripts.process_account_deletions`: por defecto solo informa cuántas cuentas vencieron. `--apply` procesa un lote de hasta 50. No se ejecutó `--apply` sobre datos existentes de desarrollo.

## Administración y tipos de perfil

El mantenedor incorpora filtros de estado, suspensión/reactivación, cambio excepcional de username, cambio de tipo y auditoría. Se reutiliza el permiso administrativo de cuenta existente y se verifica en backend.

Solo un administrador solicita verificaciones profesionales. Autor, Influencer y Librería requieren aprobación explícita de la evidencia presentada; cambiar el tipo directamente exige una aprobación previa. La verificación manual aprobada actualiza el estado de verificación del perfil. No se inventó un verificador automático de identidad o de actividad comercial.

El cambio de tipo conserva el anterior/nuevo tipo, administrador, fecha y motivo, elimina capacidades profesionales alternativas y revoca las sesiones. No permite cambiar el tipo propio. Cambiar a Administrador concede el permiso administrativo al destinatario; retirarlo conserva al menos otro administrador activo.

Las publicaciones profesionales asociadas a un tipo anterior impiden cambiarlo automáticamente; el backend explica la dependencia. Cambiar a Librería requiere archivar previamente la biblioteca personal, sin borrar su historial. Las cuentas legadas sin perfil personal se rechazan con una explicación y requieren adaptación explícita: no se convierten silenciosamente.

## Auditoría y seguridad

`app.auditoria_cuentas` registra entidad, actor, acción, origen, fecha, UUID de correlación, motivo e instantáneas mediante una lista explícita de campos permitidos. Nunca registra contraseñas, hashes de contraseñas, tokens ni credenciales. El origen distingue cuenta, administrador, recuperación y procesamiento definitivo.

Solo administradores autorizados pueden consultar el historial administrativo. Un trigger bloquea cambios y borrados; la única actualización permitida es quitar exactamente los campos identificables de las instantáneas cuando la cuenta ya está anonimizada. No permite alterar operación, actor, razón, fecha o correlación.

Los cambios críticos y su auditoría comparten transacción. Credenciales y restricciones incrementan una versión de seguridad, invalidando autorizaciones Google que estaban en curso. Antes de cada llamada de IA de un trabajo en cola se verifica que su titular siga activo y sin suspensión; esta es la única modificación del worker Gemini, por dependencia directa con la baja/suspensión. No se cambió configuración de Gemini, ETL ni Google Books. Una llamada externa ya enviada no puede deshacerse.

## Contratos HTTP

Todas las rutas llevan el prefijo `/api` configurado.

| Método y ruta | Función |
|---|---|
| `GET /accounts/me` | Cuenta propia, estado de correo y Google |
| `PATCH /accounts/me` | `display_name`, `biography`; otros campos se rechazan |
| `PUT /accounts/me/avatar` | Multipart `file` |
| `DELETE /accounts/me/avatar` | Retirar foto; no elimina auditoría |
| `GET /accounts/avatars/{user_id}` | Foto saneada de una cuenta activa |
| `POST /accounts/me/password` | `current_password`, `new_password` |
| `POST /accounts/me/email/request` | `current_password`, `email` nuevo |
| `POST /accounts/me/email/confirm` | `token` del nuevo correo |
| `POST /accounts/me/email/verify/request` | Verificar correo principal; contraseña actual |
| `POST /accounts/me/email/verify/confirm` | `token` de verificación principal |
| `POST /accounts/me/google/unlink` | Contraseña actual y correo principal verificado |
| `GET /accounts/me/sessions` | Sesiones propias vigentes |
| `DELETE /accounts/me/sessions/{id}` | Revocar una sesión propia |
| `POST /accounts/me/deletion` | Contraseña; devuelve ambas fechas y estado |
| `POST /accounts/recovery/request?purpose=password_reset` | Solicitar recuperación por correo |
| `POST /accounts/recovery/request?purpose=recover_deletion` | Solicitar cancelación por correo |
| `POST /accounts/recovery/password` | `token`, `new_password` |
| `POST /accounts/recovery/deletion` | `token`; indica si sigue suspendida |
| `GET /accounts/admin` | `q`, `state`, `limit`, `offset`; devuelve `items`, `total` |
| `PATCH /accounts/admin/{id}/suspension` | `suspended`, `reason` |
| `PATCH /accounts/admin/{id}/username` | `username`, `reason` |
| `PATCH /accounts/admin/{id}/role` | `role`, `reason` |
| `POST /accounts/admin/{id}/verification` | `requested_role`, `note` |
| `GET /accounts/admin/{id}/history` | Historial paginado, solo administradores |

Se reutilizan `/auth/*`, vinculación Google y `/roles/requests/{id}/approve` o `/reject`. `/auth/me` y las respuestas de login incluyen ahora `username`.

Cambios de contrato deliberados: `POST /roles/requests` del titular responde 403; la edición administrativa de datos exige `reason`; toda edición de biografía admite hasta 70 caracteres; los cambios de rol revocan sesiones; `/profiles/me` devuelve la identidad personal de la cuenta, sin organizaciones alternativas.

## Migraciones y archivos

Se aplicaron migraciones no destructivas sobre la base local:

- `0061_account_management`: username, estados, fechas, auditoría, desafíos y fotos.
- `0062_primary_email_verification`: verificación explícita del correo principal.
- `0063_exclusive_account_roles`: verificación de cuentas Librería.
- `0064_account_insert_default`: username por defecto para inserts legados.
- `0065_account_audit_redaction`: minimización limitada de instantáneas.
- `0066_normalized_account_email`: unicidad de correo sin distinguir mayúsculas.
- `0067_account_security_version`: invalidación de intenciones OAuth.
- `0068_account_state_integrity`: integridad de fechas y estados, incluidos valores nulos.

No se alteraron datos históricos para recortar biografías, convertir organizaciones o cambiar tipos existentes. El nuevo índice de correo rechaza duplicados normalizados en vez de fusionar cuentas. Los downgrades que perderían historia se rechazan explícitamente.

Archivos principales nuevos: `app/modules/users/account_{models,schemas,service,router,mail,lifecycle}.py`, `scripts/process_account_deletions.py`, migraciones `0061`–`0068`, `tests/test_account_management.py`, `tests/test_account_concurrency.py`, `docs/cuentas-usuario.md`, `AccountManagement.jsx`, `AdminAccountManagement.jsx`, `RecoverAccountPage.jsx`, `services/accountService.js` y fixtures/prueba de navegador de cuentas.

Archivos existentes ajustados: modelos/servicio/repositorio/router/sesiones de autenticación; modelos, esquemas, identidades, preferencias y rutas de roles de usuarios; `app/main.py`, `migrations/env.py`, `requirements.txt`, `scripts/run_scheduler.py`; guardia de cuentas en `gemini_worker.py`; `AuthContext.jsx`, `api/client.js`, `App.jsx`, pantallas Account/AdminProfiles/Home/Login, ProfileAboutCard/ProfileHeader/RoleManagementPanel, foto de lectores en BookDetailPage, estilos de cuenta y pruebas relacionadas. `tests/__init__.py` evita que un paquete externo llamado `tests` oculte las pruebas locales.

Los cambios previos de administración de entorno, navegación y detalle bibliográfico se conservaron. No se modificó `.env`, no se activaron servicios pagados y no se iniciaron workers de IA.

## Cobertura de reglas

| Reglas | Implementación |
|---|---|
| RN-USR-001 a 007 | UUID conservado, tipo exclusivo, username protegido, edición propia, fotos y biografía Unicode |
| RN-USR-008 a 012 | Cambio/reset de contraseña, desafíos por correo, confirmación y normalización/unicidad |
| RN-USR-013 a 016 | Google por `sub`, sin duplicación, desvinculación protegida, JWT/refresh existentes e invalidación OAuth |
| RN-USR-017 a 024 | Solicitud solo administrativa, verificación manual, dependencias, auditoría y prohibición de cambio propio |
| RN-USR-025 a 031 | Solicitud autenticada, revocación, 30 días exactos y recuperación que mantiene suspensión |
| RN-USR-032 a 035 | Procesamiento idempotente, serialización con recuperación, minimización y conservación de relaciones |
| RN-USR-036 a 042 | Auditoría saneada, permisos, protección de historial y transacciones |

La tabla describe la implementación. No implica validación completa del despliegue ni revisión terminada del texto histórico.

## Pruebas y límites de validación

La suite principal ejecutada contra PostgreSQL local pasó **79 pruebas**, incluidas **28 nuevas de cuentas y concurrencia**. Las pruebas generan cuentas dentro de transacciones con rollback; las de concurrencia usan dos conexiones y un esquema temporal propio. No dejaron cuentas ficticias persistentes.

Comando de la suite principal, desde `apps/backend`:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_account_management tests.test_account_concurrency tests.test_security tests.test_google_login tests.test_google_integration tests.test_identities tests.test_literary_preferences tests.test_post_comments tests.test_post_interactions -q
```

Las suites `test_gemini_optimization` y `test_gemini_provider` ejecutaron 36 casos: 17 pasaron y 19 se omitieron por las condiciones de su entorno. No invocaron servicios pagos.

En Edge headless pasaron `tests/account-management.mjs` y `tests/profile-edit-modals.mjs`: campos protegidos, conteo Unicode, guardado, motivo administrativo, recuperación, suspensión conservada y modales en nueve temas y varios tamaños. El build de Vite y ESLint de los componentes modificados pasaron. El build avisa del tamaño del bundle.

La suite antigua `test_user_roles` mantiene cuatro fallos de fixtures de biblioteca: tres fallos y un error. Se reprodujeron los mismos cuatro en una copia aislada del código de `HEAD`, sin cambiar de rama. Usan referencias sintéticas que el catálogo actual rechaza o intentan iniciar una lectura sin incorporar primero una edición. No se modificó la lógica de catálogo para ocultar esos fallos.

Tres casos ETL de `test_reviews` requieren el harness PostgreSQL desechable propio del catálogo y se negaron a ejecutar fixtures sobre la base de desarrollo. La regresión Docker completa no se ejecutó: Docker Desktop no tenía un daemon accesible. Tampoco se enviaron correos reales ni se realizó un login interactivo con una cuenta Google real: se verificaron los contratos con transporte/proveedor controlado y firmas RSA en las pruebas existentes.

**Estado de cierre:** funcionalidad implementada y validación local focalizada satisfactoria; no se declara el CRUD íntegramente validado hasta ejecutar la regresión en el harness Docker, resolver/actualizar los fixtures antiguos, completar la comprobación de integración externa que corresponda y revisar los datos personales del texto histórico según la política aprobada.
