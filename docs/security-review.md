# Revisión de seguridad y coherencia — 2026-10-04

Esta entrega corrige fallos del contrato actual sin borrar datos ni aplicar migraciones. No equivale a cerrar todas las brechas estructurales de `transactional-gaps.md`.

## Correcciones implementadas

| Hallazgo | Corrección |
|---|---|
| HTML externo sin sanitización en la ficha del libro | React renderiza la descripción como texto; enlaces externos admiten solamente HTTP/HTTPS. Se pierde el formato HTML de la descripción. |
| OAuth sin comprobación de state y respuesta con credenciales del proveedor | Estado aleatorio vinculado al navegador mediante cookie HttpOnly de 10 minutos, comprobación antes del intercambio, eliminación de cookie y respuestas sin caché ni tokens. Errores del proveedor no exponen su respuesta. |
| Configuración productiva con clave JWT conocida | Producción rechaza la clave de desarrollo, claves menores a 32 caracteres y orígenes sin HTTPS. JWT exige subject y expiración. |
| Inicio implícito al avanzar, finalizar o abandonar | Esas acciones requieren `reading_id`, propiedad del intento y estado activo. Un nuevo inicio explícito permite releer sin reemplazar intentos anteriores. |
| Escrituras simultáneas sobre lectura o catálogo | Bloqueo transaccional de cuenta para comandos de biblioteca/lectura y bloqueo asesor PostgreSQL por referencia al resolver catálogo. No protege escrituras externas que omitan estos comandos. |
| Total de páginas modificable entre comandos | Se conserva la instantánea del intento y se rechazan totales diferentes. |
| Publicación automática de actividad privada | `share` es falso por defecto. Interfaz permite compartir explícitamente cada cambio. Motivo de abandono sigue privado. No se retiran publicaciones históricas. |
| Biblioteca en memoria y ejemplos presentados como propios | Alta persistente e idempotente por usuario/obra; estado pendiente, recarga desde API y biblioteca personal inicialmente vacía. Consultar una ficha no agrega automáticamente el libro. |
| Comentarios sobre publicaciones excluidas del feed | Feed y lectura/escritura de comentarios usan el mismo filtro de visibilidad. |
| Decisiones concurrentes de verificación y auditoría incompleta | Bloqueos de solicitud y perfil; aprobaciones y revocaciones registran actor y fecha de decisión. |
| Datos ficticios insertados al iniciar la aplicación | `run-local.ps1` deja de lanzar el generador. El generador manual fue adaptado al inicio explícito. |
| Nombres vacíos y campos sociales inconsistentes | Validación tras quitar espacios, rechazo de campos adicionales en publicaciones y comandos de biblioteca; valoración solo en reseñas. |

## Contrato e integración

- `POST /readings/library`: incorpora una referencia con título y paginación opcional. Repetir conserva el intento existente.
- `GET /readings/me`: incluye `reading_id`, pendientes y total nullable.
- `POST /readings/events`: `start` no recibe ID; otras acciones lo requieren. `post` puede ser null cuando el cambio es privado.
- OAuth sigue siendo una integración incompleta: valida el intercambio pero no guarda una conexión Google por usuario ni inicia una sesión LibrIA. Devuelve `connected: false`. No se debe presentar como una conexión persistente.

## Verificación y límites

Pruebas de integración sobre PostgreSQL con rollback cubren propiedad, privacidad, alta repetida, estados pendientes, avances, cierre, comentarios y roles. Pruebas con proveedor simulado cubren state OAuth y ausencia de credenciales en la respuesta. También se ejecutan ESLint y build de producción. No se ha realizado prueba de navegador automatizada, auditoría de dependencias ni prueba de carga/concurrencia con varios procesos.

## Pendientes importantes

1. Separar cuentas, capacidades, organizaciones y membresías; las librerías aún usan cuentas del modelo anterior.
2. Separar reseñas, publicaciones y avances, con FK canónicas, reseña única por perfil/obra, edición y moderación auditada. Los cambios compartidos todavía crean posts del prototipo.
3. Completar catálogo canónico, importación por proveedor y consulta de todos los intentos; el contrato actual conserva referencias `libria-feed`, títulos y paginación aportados por el cliente. Los autores y otros metadatos no se restauran completos desde la biblioteca.
4. Incorporar historial tipado de transiciones, idempotencia de comandos compartidos y protección de unicidad de intento activo en base de datos; los bloqueos actuales son del servicio.
5. Diseñar sesiones revocables y límites de intentos de autenticación compartidos entre procesos; el token del frontend sigue en localStorage.
6. Completar carga demo finita y reproducible. El generador manual aún usa referencias aleatorias.
7. Aislar analítica personal y salidas grupales anónimas antes de habilitar paneles o exportaciones.

Los puntos que cambian identidades y relaciones requieren inventario y migración conservadora de registros existentes, conforme a `transactional-gaps.md`. Esta entrega no certifica una aplicación lista para producción.
