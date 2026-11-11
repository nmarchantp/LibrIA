# Influencer: RF-INF-001 a RF-INF-004

## Alcance implementado

| Requisito | Comportamiento |
| --- | --- |
| RF-INF-001 | Lector activo solicita Influencer en Configuración → Mi cuenta. Formulario con descripción de actividad literaria, temáticas, motivación y entre uno y cinco enlaces de evidencia. Una sola solicitud pendiente por cuenta, incluso con envíos simultáneos. |
| RF-INF-002 | Administrador aprueba/rechaza con observación independiente. Se guardan responsable, fecha y observación; solicitante y administrador consultan el historial. Se impiden decisiones sobre solicitudes propias y dobles decisiones concurrentes. |
| RF-INF-003 | La aprobación usa el cambio de rol existente. Conserva cuenta, perfil, biblioteca, lecturas, reseñas, seguidores e interacciones. La política existente invalida las sesiones: el titular debe volver a iniciar sesión. |
| RF-INF-004 | Administrador suspende permisos profesionales hasta una fecha futura, puede reactivarlos antes con motivo o revocar el rol a Lector. Registra auditoría y conserva actividad y publicaciones históricas. |

No se implementaron publicaciones especializadas, enlaces sociales públicos, videos, guiones ni comunidades. Los enlaces del formulario son evidencia privada para la evaluación; el backend no los visita ni verifica su propiedad.

## Suspensión y compatibilidad histórica

La suspensión de Influencer es distinta de la suspensión general de la cuenta. El usuario puede iniciar sesión y conservar sus funciones de lector, incluyendo biblioteca, lecturas, reseñas, comentarios e interacciones. Se bloquean nuevas publicaciones profesionales, eventos, edición profesional y cambios de portada. Las notas/teorías vinculadas a obras que ya permite el lector siguen admitidas.

La fecha de término se comprueba en el servidor en cada operación: no depende de un cron. Una reactivación manual requiere motivo y auditoría. Al vencer el plazo se recuperan automáticamente los permisos en el backend; una pantalla abierta puede necesitar actualizarse para refrescar sus controles.

La revocación explícita de Influencer permite volver a Lector aun con publicaciones profesionales históricas. No las borra, oculta ni cambia su autoría almacenada. El mural, el detalle y las ediciones conservan ese rol histórico. No se cambia el bloqueo general que protege cambios de Autor/Librería con publicaciones existentes. El endpoint administrativo genérico de cambio de rol conserva sus restricciones.

Las comprobaciones se repiten al aprobar una revisión de contenido moderada: una propuesta pendiente no puede eludir una suspensión o revocación posterior. Las operaciones de publicación toman un bloqueo compartido de cuenta; los cambios administrativos toman un bloqueo exclusivo, antes de modificar permisos.

## API

Todas las rutas tienen el prefijo `/api`.

| Método y ruta | Contrato |
| --- | --- |
| POST /roles/requests | `requested_role: "influencer"`, `activity_description`, `topics`, `motivation`, `evidence_links`. Solo Lector sin permisos administrativos. |
| GET /roles/requests/me | Historial propio con formulario, estado, `decided_at`, `decided_by_user_id`, `decided_by_name` y `decision_reason`. |
| GET /roles/requests/pending | Cola administrativa existente, ampliada con los campos del formulario. |
| POST /roles/requests/{id}/approve | Administrador; JSON `{"reason":"observación administrativa"}`. |
| POST /roles/requests/{id}/reject | Mismos controles y observación independiente. |
| POST /roles/profiles/{id}/influencer-suspension | Administrador; JSON con `reason` y `until` ISO 8601, futuro y con zona horaria. Solo perfil Influencer. |
| POST /roles/profiles/{id}/influencer-resume | Administrador; JSON con `reason`. Requiere suspensión activa. |
| POST /roles/profiles/{id}/revoke | Ruta existente; motivo obligatorio. Revoca Influencer conservando publicaciones históricas. |
| GET /roles/me/influencer-permissions | Estado propio de suspensión, término y motivo de la última acción. |
| GET /accounts/admin/{id}/history | Auditoría existente, reutilizada para consultar acciones de permisos, responsable, fecha, motivo y estados anterior/posterior. |

Descripción: 10–2000 caracteres; motivación y observaciones: 10–1000. Temáticas: entre 1 y 10, de 2–80 caracteres cada una. Evidencia: entre 1 y 5 URL HTTP/HTTPS de hasta 2048 caracteres, sin credenciales, IP, host local ni puertos personalizados. No se permiten identidades o estados enviados por el cliente.

Las solicitudes administrativas existentes de Autor/Librería se mantienen. Sus clientes antiguos pueden seguir decidiendo sin cuerpo; se conserva su nota como motivo de compatibilidad. Influencer siempre exige observación administrativa independiente. Las solicitudes históricas sin formulario estructurado siguen visibles y no se rellenan con datos inventados.

## Migración

`0092_influencer_access` depende de `0091_influencer_phase1`, que permanece intacta como historial aplicado.

- Añade columnas nullable de actividad, temáticas, motivación y enlaces a `app.solicitudes_verificacion`.
- Añade `app.usuarios.influencer_suspended_until`.
- Reutiliza `decision_reason`, creado por la migración histórica 0091.
- Reutiliza las tablas de solicitudes, usuarios, perfiles, cambios de rol y auditoría; no crea otro usuario Influencer.

Durante la implementación se aplicó la cadena completa solo a `libria_influencer_access_test`. **No se aplicó 0092 sobre la base local `libria`.** Antes de iniciar esta versión del backend debe aplicarse esa migración mediante el procedimiento habitual, con respaldo y autorización explícita para la base configurada. El setup de Windows ya dispone de `-AllowMainDatabaseMigration` y confirmación para ese procedimiento; no es necesario cambiar la marca de Alembic manualmente.

No eliminar archivos de migraciones ya aplicadas al revertir interfaz o funcionalidades. Una reversión de código debe seguir reconociendo el historial de la base.

## Archivos principales

Backend, relativos a `apps/backend/`:

- `migrations/versions/0092_influencer_access.py` (nuevo).
- `app/modules/users/verification_models.py`, `role_schemas.py`, `roles_router.py`.
- `app/modules/users/models.py`, `schemas.py`, `account_router.py`, `account_service.py`.
- `app/modules/users/identities.py`, `identities_router.py`.
- `app/modules/social/router.py`, `publication_management.py`, `post_covers.py`.
- `app/modules/social/moderation_decisions.py`, `feed_service.py`.
- `tests/test_influencer_access.py` (nuevo).

Frontend, relativos a `apps/web/`:

- `src/components/AccountManagement.jsx`, `RoleManagementPanel.jsx`.
- `src/components/InfluencerApplicationDetails.jsx`, `InfluencerPermissionsPanel.jsx` (nuevos).
- `src/pages/AdminProfilesPage.jsx`, `HomePage.jsx`, `EventsPage.jsx`.
- `tests/influencer-access.mjs`, `tests/fixtures/influencer-access.html`, `tests/fixtures/influencer-access.jsx` (nuevos).
- `package.json`: comando `test:influencer-access`.

Infraestructura de pruebas: `compose.influencer-test.yaml` (nuevo). Documentación: este archivo.

## Pruebas reproducibles

Desde la raíz, con Docker iniciado:

```powershell
docker compose -f compose.influencer-test.yaml build test
docker compose -f compose.influencer-test.yaml run --rm test python -m alembic upgrade head
docker compose -f compose.influencer-test.yaml run --rm test
```

El Compose tiene nombre, credenciales, red y base propios; no publica puertos ni monta volúmenes de desarrollo. PostgreSQL usa tmpfs. No detener el contenedor entre migrar y ejecutar pruebas. La suite nueva rechaza cualquier otra base o ambiente. Gemini está deshabilitado y no se ejecutan scheduler ni tareas demo.

Desde `apps/web`:

```powershell
npm run lint -- --quiet
npm run build
npm run test:influencer-access
```

La prueba visual usa Chrome headless de Windows y API simulada. Renderiza `AccountManagement` con el proveedor de autenticación y las pantallas administrativas reales. Las pruebas HTTP del backend usan PostgreSQL real.

Cobertura: formulario incompleto, enlaces inseguros, autorización por rol, solicitud duplicada y concurrente, decisiones concurrentes, autoaprobación, observación/responsable/fecha, rechazo y reintento, activación y conservación de datos, suspensión con sesión existente, vencimiento, reactivación, auditoría, revocación con publicaciones históricas, edición de notas y portadas, propuestas moderadas pendientes y preservación de restricciones de Autor. La regresión cubre cuentas, contenido, agenda, interacciones y moderación.

Tras revisar los resultados:

```powershell
docker compose -f compose.influencer-test.yaml down
```

Esto elimina únicamente la base temporal y su red, sin tocar `libria`.

## Resultado de esta entrega

- Cadena completa hasta `0092_influencer_access` aplicada correctamente en PostgreSQL temporal.
- 140 pruebas backend correctas, incluidas 13 de acceso Influencer y concurrencia.
- Flujo Chrome headless correcto: solicitud desde Mi cuenta, rechazo/reintento, aprobación, responsable/fecha/observación, suspensión, reactivación, revocación y auditoría.
- ESLint y compilación Vite correctos. Vite conserva el aviso de tamaño del bundle.
- Sin migraciones sobre `libria`, generaciones Gemini ni commits. Entorno temporal retirado después de las pruebas.
