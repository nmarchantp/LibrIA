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
- `POST /api/posts`: publica reseñas con libro y valoración; las publicaciones libres requieren `influencer`, `autor`, `libreria` o `admin`.
- `GET /api/posts`: lista las últimas publicaciones para el mural.
- `POST /api/readings/events`: registra inicio, avance por página, término o abandono y genera automáticamente una publicación de avance.
- `POST /api/roles/requests`: solicita verificación como `influencer` o `autor`.
- `GET /api/roles/requests/me`: consulta el historial de solicitudes propias.
- `GET /api/roles/requests/pending` y `POST /api/roles/requests/{id}/approve|reject`: revisión administrativa.
- `POST /api/roles/bookstores`: creación de cuentas de librería exclusiva de administradores.
- `GET /api/posts/{post_id}/comments`: lista los últimos 100 comentarios de una publicación, reseña o avance.
- `POST /api/posts/{post_id}/comments`: crea un comentario de hasta 1000 caracteres con el token Bearer del usuario.

El registro público no acepta `role`. Un lector puede comentar cualquier publicación, reseñar libros y generar avances de lectura, pero no escribir publicaciones libres. La aprobación de autor e influencer y el alta de librerías pasan por una cuenta administradora. El mural devuelve `author_role`, `book_title`, `rating` y los datos del avance para mostrar el tipo de contenido.
Las publicaciones de ejemplo antiguas que incumplen estas reglas permanecen en la base, pero no se incluyen en `GET /api/posts`.

Para habilitar el primer administrador, registra su cuenta normal y ejecuta desde el servidor:

```powershell
python -m scripts.grant_admin --email admin@ejemplo.com
```

Para ejecutar las pruebas del backend en desarrollo, instala `requirements-dev.txt` y ejecuta `python -m unittest discover -s tests`.

## Datos de demostración y ETL

Primero aplica las migraciones y levanta la API. `run.cmd` inicia además un proceso continuo que publica cada 30 segundos. El generador usa diez cuentas de prueba con los cinco tipos de usuario: crea lectores por registro, aprueba autores e influencers mediante solicitudes, crea librerías con el endpoint administrador y genera avances por `POST /api/readings/events`. Las reseñas se envían a `POST /api/posts`. Solo funciona con `APP_ENV=development`; el administrador de muestra se habilita localmente. Las fuentes `community`, `reading`, `review` y `event` representan escenarios sintéticos, no contenido descargado de servicios externos. Necesita `LIBRIA_DEMO_PASSWORD` en `apps/backend/.env`; el instalador la genera automáticamente.

```powershell
python -m scripts.generate_posts
python -m scripts.run_etl
```

El generador permanece activo hasta detener el proceso. Reintenta si la API no está disponible y solo admite una instancia activa en el equipo. Para una ejecución acotada usa `--count 20`; `--interval` permite cambiar el intervalo en segundos. Mantén la misma clave para volver a usar las cuentas de demostración. La ejecución de ETL toma una ventana móvil de 30 días, lee `app.publicaciones`, agrupa por fuente y categoría y escribe una instantánea JSONB en `analytics.instantaneas_actividad`. Cada ejecución queda registrada en `analytics.ejecuciones_etl`, incluso si falla. Las instantáneas son históricas; ejecutar el ETL otra vez crea otra instantánea. Puedes programar `python -m scripts.run_etl` con el planificador del sistema.

Para revisar la última instantánea:

```sql
SELECT period_start, period_end, metrics
FROM analytics.instantaneas_actividad
ORDER BY created_at DESC LIMIT 1;
```
