# Backend

Monolito modular de LibrIA. La primera implementación funcional será `auth`; los demás módulos se incorporarán incrementalmente sin crear servidores FastAPI adicionales.

## Ejecución local

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
alembic upgrade head
uvicorn app.main:app --reload
```

API: `http://localhost:8000`; documentación interactiva: `http://localhost:8000/docs`.

## Endpoints disponibles

- `POST /api/auth/register`: crea siempre una cuenta `lector`, hash Argon2 y token.
- `POST /api/auth/login`: valida credenciales y entrega token.
- `GET /api/auth/me`: obtiene el usuario del JWT enviado como Bearer.
- `POST /api/posts`: publica reseñas con libro y valoración o publicaciones breves (máximo 500 caracteres); solo `lector` tiene restringidas las publicaciones libres. Acepta hasta 10 imágenes JPEG, PNG, GIF o WebP (5 MB cada una, 25 MB en total).
- `GET /api/posts`: lista las últimas publicaciones del mural con sus imágenes, cantidad de me gusta y estado de interacción de la sesión.
- `GET /api/posts/{post_id}/images/{image_id}`: sirve imágenes de publicaciones visibles.
- `PUT|DELETE /api/posts/{post_id}/like`: agrega o quita un me gusta para la sesión autenticada.
- `POST|DELETE /api/profiles/{profile_id}/follow`: sigue o deja de seguir un perfil para la sesión autenticada.
- `POST /api/readings/events`: registra inicio, avance por página, término o abandono y genera automáticamente una publicación de avance.
- `POST /api/roles/requests`: solicita verificación como `influencer` o `autor`.
- `GET /api/roles/requests/me`: consulta el historial de solicitudes propias.
- `GET /api/roles/requests/pending` y `POST /api/roles/requests/{id}/approve|reject`: revisión administrativa.
- `POST /api/roles/bookstores`: creación de cuentas de librería exclusiva de administradores.
- `GET /api/roles/profiles`: listado paginado para administradores, con búsqueda por nombre o correo y filtro de rol.
- `PATCH /api/roles/profiles/{id}`: edita nombre visible y biografía sin cambiar permisos.
- `POST /api/roles/profiles/{id}/revoke`: revoca el permiso de autor o influencer y guarda el motivo.
- `GET /api/roles/profiles/{id}/requests|history`: consulta solicitudes y revocaciones de un perfil.
- `GET /api/posts/{post_id}/comments`: lista los últimos 100 comentarios de una publicación, reseña o avance.
- `POST /api/posts/{post_id}/comments`: crea un comentario de hasta 1000 caracteres con el token Bearer del usuario.

El registro público no acepta `role`. Un lector puede comentar, indicar que le gustan las publicaciones, seguir perfiles, reseñar libros y generar avances de lectura, pero no escribir publicaciones libres. Los perfiles influencer, autor, librería, editorial y administrador pueden publicar libremente en el mural. Las publicaciones aceptan un comentario breve y hasta 10 imágenes; las interacciones están disponibles para todas las cuentas autenticadas. La aprobación de autor e influencer y el alta de librerías pasan por una cuenta administradora. El mural devuelve `author_role`, `book_title`, `rating` y los datos del avance para mostrar el tipo de contenido.
Las publicaciones de ejemplo antiguas que incumplen estas reglas permanecen en la base, pero no se incluyen en `GET /api/posts`.
El administrador accede al mantenedor desde **Gestionar perfiles** en el menú o en `/admin/profiles`. Desde allí busca cuentas, revisa solicitudes, edita datos públicos, revoca permisos de autor o influencer y crea librerías. El influencer puede publicar en la comunidad; el autor y la librería también pueden publicar eventos. La librería usa publicaciones normales para promociones. Los lectores siguen publicando solo reseñas y avances de lectura. Las publicaciones nuevas guardan el tipo de perfil del autor al publicarse, de modo que una revocación posterior no las cambia ni las oculta. Las publicaciones anteriores a esta migración toman el rol vigente al momento de aplicar la migración.

Para habilitar el primer administrador, registra su cuenta normal y ejecuta desde el servidor:

```powershell
python -m scripts.grant_admin --email admin@ejemplo.com
```

Para ejecutar las pruebas del backend en desarrollo, instala `requirements-dev.txt` y ejecuta `python -m unittest discover -s tests`.

El [ingreso con Google](../../docs/google-login.md) complementa el acceso con correo y contraseña. Incluye configuración de OAuth, vinculación de cuentas y comprobación manual.

## Datos de demostración y ETL

Las [reseñas normalizadas](../../docs/reviews.md) se crean en `/api/reviews`, con obra canónica y una sola reseña por perfil–obra. `/api/posts` solo admite publicaciones manuales. El feed de lectura combina las tres entidades y sus comentarios comprueban destinos y visibilidad. `python -m scripts.seed_reviews_demo` prepara escenarios de reseñas para el siguiente cierre `daily-v2`; editar no vuelve a contar la primera publicación y los cierres anteriores permanecen intactos.

El [ETL diario](../../docs/etl-daily.md) procesa una sola vez cada día cerrado a las 00:00 de Santiago, recupera pendientes al iniciar y muestra seguimiento en `/admin/etl`. Se programa con FastAPI y, en este equipo, con la tarea de Windows `LibrIA-ETL-Diario`. Las credenciales técnicas se leen del `.env` local y no se publican.

En esa pantalla, **Ejecutar ETL ahora** inicia una carga manual real de los últimos 30 días, incluyendo hoy. Requiere permiso administrativo; registra extracción, limpieza, carga y conciliación en `analytics`, por separado de los cierres diarios. Las solicitudes son idempotentes por UUID y se recuperan si se interrumpe la API. Aplicar primero `alembic upgrade head` (migración `0018_manual_etl`). Ver [demostración y consultas de comprobación](../../docs/etl-daily.md#ejecución-manual-desde-la-web).

**Mis análisis / ADN lector** y **Pulso de la comunidad** consultan los datos limpios e interpretan sus indicadores con **Ollama local**, sin clave ni envío a un proveedor externo. Aplicar la migración `0019_ai_interpretations`, iniciar Ollama y descargar `qwen3:1.7b`. El panel grupal requiere capacidad de autor o membresía editorial/librería y publica únicamente agregados con umbrales mínimos. `python -m scripts.seed_group_demo` prepara una cohorte ficticia repetible; después ejecutar el ETL manual desde la web. Ver [contrato, configuración y demostración](../../docs/ai-interpretations.md).

Primero aplica las migraciones y levanta la API. `run.cmd` inicia el generador continuo de publicaciones, que crea un post cada 20 segundos y lo guarda en las tablas transaccionales mediante `POST /api/posts`. El generador asegura las cuentas demo de forma idempotente y publica reseñas como lector, además de publicaciones y eventos como perfiles profesionales u organizaciones. Solo funciona con `APP_ENV=development` y necesita `LIBRIA_DEMO_PASSWORD` en `apps/backend/.env`; el instalador la genera automáticamente.

```powershell
# Generación continua cada 20 segundos; detener con Ctrl+C
python -m scripts.generate_posts
# Carga finita de escenarios versionados con resultados esperados
python -m scripts.seed_analytics_demo
# Inicialización histórica: procesa una vez cada día cerrado
python -m scripts.run_etl --from-date 2026-09-21
# Recuperar cierres pendientes, sin duplicar los completados
python -m scripts.run_etl
```

El generador continuo sirve para actividad del mural; sus fechas y referencias aleatorias no constituyen escenarios de validación repetibles. Para comprobar indicadores se usa `analytics_demo.json` y su cargador estable. El ETL lee fuentes operacionales, excluye contratos incoherentes y reseñas/avances legados, escribe hechos limpios e indicadores privados y registra reglas y cantidades por cierre. Un fallo revierte la carga y permite reintentar la misma ejecución; un día exitoso nunca se vuelve a cargar. Los análisis grupales siguen deshabilitados hasta validar anonimización.

Para revisar el último cierre diario:

```sql
SELECT business_date, status, source_cutoff_at, summary
FROM analytics.ejecuciones_etl
WHERE business_date IS NOT NULL
ORDER BY business_date DESC LIMIT 1;
```
