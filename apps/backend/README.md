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

## Datos de demostración y ETL

Primero aplica las migraciones y levanta la API. `run.cmd` inicia el generador continuo de publicaciones, que crea un post cada 20 segundos y lo guarda en las tablas transaccionales mediante `POST /api/posts`. El generador asegura las cuentas demo de forma idempotente y publica reseñas como lector, además de publicaciones y eventos como perfiles profesionales u organizaciones. Solo funciona con `APP_ENV=development` y necesita `LIBRIA_DEMO_PASSWORD` en `apps/backend/.env`; el instalador la genera automáticamente.

```powershell
# Generación continua cada 20 segundos; detener con Ctrl+C
python -m scripts.generate_posts
# Para preparar una carga fija, detener primero el generador continuo
python -m scripts.generate_posts --count 20 --interval 0.2
# Ejecutar ETL con la carga fija
python -m scripts.run_etl
# Reiniciar generación continua después del ETL
python -m scripts.generate_posts --interval 20
```

El generador permanece activo hasta detenerlo, reintenta si la API no está disponible y evita iniciar una segunda instancia. `--count` permite una carga finita y `--interval` cambia el intervalo en segundos. Mantén la misma clave para reutilizar las cuentas de demostración. La generación continua es independiente de la carga finita: ambas escriben en el esquema transaccional, mientras que el ETL se ejecuta explícitamente y guarda instantáneas históricas en `analytics`. El ETL toma una ventana móvil de 30 días, lee `app.publicaciones`, agrupa por fuente y categoría y escribe una instantánea JSONB en `analytics.instantaneas_actividad`. Cada ejecución queda registrada en `analytics.ejecuciones_etl`, incluso si falla. Las instantáneas son históricas; ejecutar el ETL otra vez crea otra instantánea. Puedes programar `python -m scripts.run_etl` con el planificador del sistema.

Para revisar la última instantánea:

```sql
SELECT period_start, period_end, metrics
FROM analytics.instantaneas_actividad
ORDER BY created_at DESC LIMIT 1;
```
