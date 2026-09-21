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

- `POST /api/auth/register`: crea usuario, hash Argon2 y token.
- `POST /api/auth/login`: valida credenciales y entrega token.
- `GET /api/auth/me`: obtiene el usuario del JWT enviado como Bearer.
- `POST /api/posts`: publica como el usuario autenticado.
- `GET /api/posts`: lista las últimas publicaciones para el mural.

## Datos de demostración y ETL

Primero aplica las migraciones y levanta la API. `run.cmd` inicia además un proceso continuo que publica cada 30 segundos. El generador usa cinco cuentas de prueba y envía cada publicación a `POST /api/posts`; no inserta filas directamente en la base. Las fuentes `community`, `reading`, `review` y `event` representan escenarios sintéticos, no contenido descargado de servicios externos. Necesita `LIBRIA_DEMO_PASSWORD` en `apps/backend/.env`; el instalador la genera automáticamente.

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
