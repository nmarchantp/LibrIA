# LibrIAverse

LibrIAverse es una plataforma social de lectura construida con React, FastAPI y PostgreSQL. Permite organizar bibliotecas, registrar lecturas y relecturas, publicar reseñas, conservar notas y teorías privadas, consultar analítica y recibir resultados de inteligencia artificial persistentes.

El frontend, la API, el ETL, el scheduler y el worker de IA comparten el mismo modelo de datos, pero se ejecutan como procesos separados.

## Estado actual

La rama de desarrollo contiene la migración desde Ollama local hacia Google Gemini API.

| Funcionalidad | Estado comprobado |
|---|---|
| Biblioteca, lecturas, reseñas y perfiles | Implementada y cubierta por pruebas backend |
| ETL diario y proyecciones | Implementados; scheduler separado de FastAPI |
| Sesiones revocables | Implementadas: access JWT corto, refresh HttpOnly y 24 horas de inactividad |
| Recomendaciones Gemini | Verificadas ahora con Gemini simulado; existe un reporte histórico de prueba real, no repetido ni corroborado por artefactos versionados |
| Análisis de lectura terminada, abandonada y relectura | Verificados ahora con Gemini simulado; existe el mismo antecedente histórico de prueba real |
| Interpretación personal | Pendiente; su generación devuelve HTTP 501 |
| Interpretación grupal | Pendiente; su generación devuelve HTTP 501 |
| Windows nativo | Scripts corregidos y validados estáticamente; requiere PostgreSQL preexistente y configuración local |
| Docker | Imágenes y Compose validados; las migraciones requieren ejecución explícita |

Gemini permanece desactivado por defecto. Las funciones básicas no requieren API key. Ollama no tiene ningún camino operativo y solo se conserva como referencia histórica comentada.

## Arquitectura

```text
React / Nginx ---> FastAPI <----> PostgreSQL
                       ^              ^
                       |              |
Scheduler ------> ETL nocturno        +-- jobs y resultados persistentes
Worker Gemini --> Gemini API --> validación Pydantic
```

- **Frontend:** React 19, Vite y React Router.
- **Backend:** Python 3.12, FastAPI, SQLAlchemy, Pydantic y Alembic.
- **Datos:** PostgreSQL 17.
- **IA:** SDK oficial `google-genai`, respuestas estructuradas y jobs asíncronos.
- **Ejecución:** Windows nativo o Docker Compose.

El ETL nocturno crea perfiles lectores versionados. Un login o una reanudación de actividad sincroniza, de forma deduplicada, el trabajo del último ETL con cambios. El worker guarda el resultado; consultar REST o React no vuelve a llamar a Gemini.

Las recomendaciones usan solo lecturas terminadas con valoración general igual o superior a 4 y pueden incorporar dimensiones, reseñas, notebook, notas y teorías. El [análisis individual](docs/nightly-book-analysis.md) exige una reseña personal con texto y una lectura terminada o abandonada. El ETL automático de medianoche o una ejecución manual administrativa habilitan sus trabajos; PostgreSQL permite consultar inmediatamente resultados existentes y conservar versiones anteriores durante actualizaciones.

Documentación técnica:

- [ETL diario](docs/etl-daily.md)
- [Pipelines analíticos](docs/analytics-pipelines.md)
- [Worker Gemini](docs/gemini-stage5-worker.md)
- [Preparación operativa Gemini](docs/gemini-stage6-production-readiness.md)
- [Recomendaciones](docs/ai-recommendations.md)
- [Interpretaciones pendientes](docs/ai-interpretations.md)
- [Sesiones y acceso a IA](docs/reader-ai-access.md)
- [Modelo de datos](docs/data-model.md)

## Requisitos

### Windows

- Git, Python 3.12, Node.js LTS, npm y PostgreSQL 17.
- PowerShell 5.1 o posterior.

```powershell
git --version
python --version
node --version
npm --version
psql --version
```

### Docker

- Docker Desktop con Compose v2.
- `apps/backend/.env` local.
- Espacio persistente para PostgreSQL.

No se necesita Ollama ni GPU.

## Instalación en Windows

> **Estado:** el flujo actual preserva instalaciones existentes, pero no aprovisiona PostgreSQL desde cero. `setup.cmd` requiere `apps/backend/.env` y la base indicada por `DATABASE_URL`.

### Configuración

```powershell
Copy-Item apps\backend\.env.example apps\backend\.env
Copy-Item apps\web\.env.example apps\web\.env
```

Configura una base de desarrollo propia en `DATABASE_URL`, un `JWT_SECRET` aleatorio de al menos 32 caracteres y `FRONTEND_ORIGINS`. Cada integrante debe usar una base independiente o un servidor acordado. Los `.env` están excluidos de Git.

El rol y la base deben crearse fuera de LibrIAverse. El setup seguro no crea, reemplaza ni elimina bases.

### Dependencias y validación

```powershell
.\setup.cmd
```

`setup.cmd` ejecuta `scripts/setup-windows-safe.ps1`: respalda `.env`, agrega variables faltantes, instala dependencias, comprueba PostgreSQL y revisiones Alembic, y valida Gemini sin llamar al proveedor. Por defecto **no migra**.

Para migrar una base propia ya respaldada:

```powershell
.\setup.cmd -AllowMainDatabaseMigration
```

Se exige `pg_dump` y la confirmación textual `MIGRAR-POR-EXPLICITO` antes de `alembic upgrade head`.

`scripts/setup-windows.ps1` se conserva como entrada compatible, pero ahora es solamente un wrapper del procedimiento seguro. Ya no crea roles/bases, no purga el catálogo y no migra sin autorización explícita.

### Arranque y detención

```powershell
.\run.cmd
```

- Frontend: <http://localhost:5173>
- API: <http://localhost:8000>
- Swagger: <http://localhost:8000/docs>
- Health: <http://localhost:8000/health>

`run.cmd` comprueba dependencias y Alembic, inicia API/frontend y, según flags, scheduler/worker. No migra automáticamente.

```powershell
.\scripts\stop-local.ps1
```

### Limitaciones conocidas

- `setup.cmd` no crea PostgreSQL desde cero.
- `update.cmd` **no ejecuta `git pull`**.
- `update.cmd` actualiza dependencias y completa variables faltantes mediante el setup seguro; respalda el `.env` antes de editarlo, no migra y no inicia servicios.
- `run-local.ps1 -PreflightOnly` es de solo lectura: comprueba dependencias, configuración y que Alembic esté en `head`; no instala, no migra y no inicia procesos.
- `scripts/configure-database.ps1` solo selecciona una URL ya declarada como `DATABASE_URL_LOCAL` o `DATABASE_URL_DOCKER`; no presupone puertos ni nombres de base.
- La instalación Windows no fue ejecutada desde cero en una segunda máquina durante esta corrección; se validaron sintaxis, preflight y contratos automatizados.

Por estas limitaciones, Windows todavía requiere acompañamiento para una integrante nueva.

## Instalación con Docker

### Configurar y construir

```powershell
Copy-Item apps\backend\.env.example apps\backend\.env
$env:POSTGRES_PASSWORD='una-clave-local-no-versionada'
$env:WEB_PORT='8080'
docker compose config --quiet
docker compose build
```

Configura también `JWT_SECRET`. Compose reemplaza `DATABASE_URL` dentro de los contenedores para usar `db`.

### Inicializar o actualizar la base

Una base nueva y una base existente desactualizada requieren una acción explícita. Para una base existente, crea y verifica primero un respaldo fuera del volumen:

```powershell
docker compose --profile migration run --rm migrate
```

Este paso también carga de forma idempotente
`demo.admin@example.com` con diez libros terminados, valorados y reseñados. Antes de
ejecutarlo, configura `LIBRIA_DEMO_PASSWORD` con al menos ocho caracteres en
`apps/backend/.env`.

La migración no forma parte del arranque normal. `schema-check` exige que la base ya esté en `head`; si es nueva o está desactualizada, API, scheduler y frontend no arrancarán hasta aplicar la migración autorizada. Una base ya actualizada no recibe escrituras de esquema.

### Iniciar sin Gemini

```powershell
docker compose up -d
docker compose ps
```

Esto inicia PostgreSQL, verifica el esquema, FastAPI, scheduler y frontend. No ejecuta migraciones. El worker está detrás del perfil `gemini` y el stack puede construirse e iniciarse con `GEMINI_API_KEY` vacía.

- Aplicación: <http://localhost:8080>
- Health: <http://localhost:8080/health>

### Detener o reiniciar conservando datos

```powershell
docker compose stop
docker compose start
```

`docker compose down` retira contenedores y red, pero conserva el volumen. No uses `docker compose down -v` como operación habitual.

### Actualizar Docker

Después del respaldo y de actualizar el código:

```powershell
docker compose build
docker compose --profile migration run --rm migrate
docker compose up -d
docker compose ps
```

`compose.prod.yaml` solo contiene el frontend; no es un despliegue completo.

## Variables de entorno

No copies secretos en commits, issues, capturas o logs.

| Variable | Propósito | Requisito | Ejemplo no sensible | Modalidad |
|---|---|---|---|---|
| `APP_ENV` | Entorno y seguridad | Obligatoria | `development` | Ambas |
| `DATABASE_URL` | Conexión SQLAlchemy | Obligatoria en Windows | `postgresql+psycopg://usuario:clave@localhost:5432/libria_nicole` | Windows; Docker la reemplaza |
| `FRONTEND_ORIGINS` | CORS | Obligatoria | `http://localhost:5173` | Ambas |
| `JWT_SECRET` | Firma de tokens | Obligatoria y secreta | valor aleatorio | Ambas |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | Duración access JWT | Opcional | `15` | Ambas |
| `SESSION_INACTIVITY_HOURS` | Expiración por inactividad | Opcional | `24` | Ambas |
| `SESSION_ABSOLUTE_HOURS` | Límite absoluto | Opcional | `168` | Ambas |
| `SESSION_COOKIE_SECURE` | Cookie solo HTTPS | Obligatoria en producción | `true` | Ambas |
| `GOOGLE_CLIENT_ID` / `GOOGLE_CLIENT_SECRET` | OAuth | Opcionales | vacío | Ambas |
| `GOOGLE_REDIRECT_URI` | Callback OAuth | Opcional | `http://localhost:8000/api/auth/google/callback` | Ambas; ajustar en Docker |
| `GOOGLE_BOOKS_API_KEY` | Catálogo backend | Opcional | vacío | Ambas |
| `LIBRIA_DEMO_PASSWORD` | Clave local de las cuentas demo y del administrador inicial | Obligatoria para la semilla inicial | valor aleatorio local | Ambas |
| `VITE_GOOGLE_BOOKS_API_KEY` | Catálogo navegador | Opcional | vacío | Frontend |
| `VITE_API_URL` | URL REST | Obligatoria al compilar | `http://localhost:8000/api` o `/api` | Frontend |
| `ANALYTICS_SCHEDULER_ENABLED` | ETL diario | Opcional | `true` | Ambas |
| `PROJECTION_SCHEDULER_ENABLED` | Proyecciones | Opcional | `true` | Ambas |
| `AI_PROVIDER` | Proveedor ejecutable | Fija | `gemini` | Ambas |
| `GEMINI_API_KEY` | Credencial Gemini | Solo llamadas reales | vacío | Ambas |
| `GEMINI_MODEL` | Modelo | Opcional | `gemini-3.5-flash-lite` | Ambas |
| `GEMINI_WORKER_ENABLED` | Activa consumo | Opcional | `false` | Ambas |
| `GEMINI_PAID_SERVICE_CONFIRMED` | Aprobación pagada/privacidad | Uso pagado | `false` | Ambas |
| `GEMINI_FREE_TEST_MODE` | Prueba ficticia gratuita en dev/test | Opcional, no verificada | `false` | Ambas |
| `AI_TIMEOUT_SECONDS` | Timeout | Opcional | `180` | Ambas |
| `AI_REQUESTS_PER_MINUTE` | Límite RPM local | Opcional | `10` | Ambas |
| `AI_MAX_CONCURRENT_REQUESTS` | Concurrencia | Opcional | `2` | Ambas |
| `AI_MAX_CALLS_PER_JOB` | Llamadas por job | Opcional | `24` | Ambas |
| `AI_JOB_TOKEN_BUDGET` | Tokens por job | Opcional | `100000` | Ambas |
| `AI_MONTHLY_BUDGET_USD` | Corte mensual estimado | Opcional | `10.00` | Ambas |
| `POSTGRES_PASSWORD` | Clave DB Docker | Obligatoria para compartir | valor local | Docker |
| `WEB_PORT` | Puerto Nginx | Opcional | `8080` | Docker |

Consulta la lista completa en [apps/backend/.env.example](apps/backend/.env.example) y [apps/web/.env.example](apps/web/.env.example).

## Gemini

El único proveedor ejecutable es `gemini`. El modelo configurado es `gemini-3.5-flash-lite`; comprueba disponibilidad y costos en la [documentación de modelos](https://ai.google.dev/gemini-api/docs/models) y [precios](https://ai.google.dev/gemini-api/docs/pricing) antes de activarlo.

Configuración desactivada:

```dotenv
AI_PROVIDER=gemini
GEMINI_API_KEY=
GEMINI_WORKER_ENABLED=false
GEMINI_PAID_SERVICE_CONFIRMED=false
GEMINI_FREE_TEST_MODE=false
```

La plataforma básica y los resultados persistidos siguen disponibles.

Para servicio pagado, solo después de revisar privacidad, billing, cuota y presupuesto:

```dotenv
GEMINI_API_KEY=<configurar localmente>
GEMINI_WORKER_ENABLED=true
GEMINI_PAID_SERVICE_CONFIRMED=true
GEMINI_FREE_TEST_MODE=false
```

En Docker:

```powershell
docker compose --profile gemini up -d gemini-worker
docker compose stop gemini-worker
```

`GEMINI_FREE_TEST_MODE` está restringido por código a `development`/`test` y desactivado por defecto. No debe usarse con datos privados ni presentarse como autorización de consumo.

### Evidencia de pruebas Gemini

Se distinguen tres estados:

1. **Antecedente histórico informado:** se reportó una prueba real con `gemini-3.5-flash-lite`, ETL y perfil versionado, dos solicitudes, 3.505 tokens, costo estimado de USD 0,00277630, recomendación validada/persistida y análisis individual persistido. La segunda consulta no habría duplicado llamadas.
2. **Verificado en esta corrección:** adaptador, worker, ETL, deduplicación, validación, persistencia, REST y frontend pasaron con proveedor simulado y PostgreSQL ficticio. No hubo llamadas externas.
3. **Pendiente:** el repositorio no contiene logs, resultados, facturas ni un reporte versionado que permita corroborar independientemente las cifras históricas. Tampoco se repitió la prueba real. Las interpretaciones personal y grupal continúan en HTTP 501.

El antecedente histórico no debe presentarse como una nueva verificación ni como evidencia de tarifas o disponibilidad actuales.

Los límites locales controlan concurrencia, RPM, llamadas, tokens y costo estimado. El costo guardado no equivale a un cargo confirmado por Google.

## PostgreSQL y migraciones

- Última revisión: `0052_ai_usage_calls`.
- `0049`–`0052` añaden persistencia/versionado Gemini, perfiles nocturnos, sesiones controladas, reducción de triggers amplios y uso por llamada.
- Recomendaciones, análisis, evidencia y métricas quedan en PostgreSQL.
- Cada integrante debe usar una base independiente.
- Respalda antes de actualizar y compara `alembic current` con `alembic heads`.
- `git pull` no migra, no crea backups y no actualiza `.env`.

```powershell
cd apps\backend
.\.venv\Scripts\python.exe -m alembic current
.\.venv\Scripts\python.exe -m alembic heads
```

## Autenticación y seguridad

- Login/registro y Google OAuth implementados.
- Access JWT de 15 minutos por defecto.
- Refresh cookie HttpOnly, `SameSite=Lax`, rotación y revocación.
- Sesión de 24 horas de inactividad y límite absoluto configurable.
- Resultados privados filtrados por propietaria y permisos.
- `.gitignore` y `.dockerignore` excluyen secretos y artefactos.

Pendientes antes de producción:

- access token almacenado en `localStorage`, con riesgo XSS;
- faltan CSP, HSTS y cabeceras completas en Nginx;
- no hay token CSRF separado; refresh depende de `SameSite=Lax`;
- existen vulnerabilidades en herramientas frontend de desarrollo;
- faltan HTTPS, secretos externos, backup y monitoreo productivos.

## Ollama

Ollama fue sustituido operativamente por Gemini. No se instala, no se descarga ningún modelo y no hay servicio en el puerto 11434.

El código histórico se conserva comentado en [apps/backend/legacy/ollama](apps/backend/legacy/ollama/README.md). Algunos documentos antiguos aún muestran comandos Ollama; son referencia de legado, no instrucciones vigentes.

## Trabajo colaborativo

1. Ejecuta `git status` y coordina cambios locales.
2. Respalda PostgreSQL.
3. Actualiza la rama mediante el procedimiento Git acordado.
4. Revisa `.env.example`; Git no actualiza secretos locales.
5. Actualiza dependencias.
6. Compara `alembic current` y `alembic heads`.
7. Migra solo después del respaldo y autorización explícita.
8. Comprueba health, login, biblioteca y resultados persistidos.

`update.cmd` no ejecuta `git pull`, no migra y no inicia servicios. Ejecuta el setup conservador para sincronizar dependencias y variables faltantes; crea una copia local ignorada de `.env` antes de modificarlo. Para una comprobación estrictamente pasiva usa:

```powershell
.\scripts\run-local.ps1 -PreflightOnly
```

```powershell
cd apps\backend
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m pip check

cd ..\web
npm ci
npm run lint
npm run build
```

## Verificación antes de compartir

```powershell
cd apps\web
npm run lint
npm run build

cd ..\backend
.\.venv\Scripts\python.exe -m compileall -q app tests scripts
.\.venv\Scripts\python.exe -m pip check
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

Las pruebas que escriben en PostgreSQL requieren una base temporal explícita y flags opt-in. No ejecutes la suite completa contra `libria` ni datos reales.

## Problemas frecuentes

- **`DATABASE_URL` incorrecta:** comprueba host, puerto, base y usuario sin imprimir la clave.
- **Falta `JWT_SECRET`:** genera un valor aleatorio local; no subas el ejemplo.
- **PostgreSQL desconectado:** revisa el servicio o `docker compose ps`.
- **Migraciones pendientes:** respalda y compara `current`/`heads` antes de `upgrade head`.
- **Puertos ocupados:** Windows usa 5173/8000; Docker publica 8080.
- **Falta API key:** deja el worker apagado; el resto debe funcionar.
- **Worker apagado:** revisa flags, aprobación y clave sin exponerla.
- **Error 429:** revisa cuota/RPM; los reintentos son acotados.
- **OAuth en Docker:** ajusta el callback al origen accesible.
- **Diferencias Docker/Windows:** Docker usa red/volumen propios y no publica PostgreSQL.

## Estructura

```text
LibrIA/
├── apps/
│   ├── backend/                 # FastAPI, Alembic, ETL, scheduler y worker
│   │   └── legacy/ollama/       # Referencia histórica comentada
│   └── web/                     # React y Nginx
├── docs/
├── scripts/
├── setup.cmd                    # Setup Windows conservador
├── run.cmd                      # Inicio Windows
├── update.cmd                   # Dependencias/config segura; no hace pull, migración ni arranque
├── compose.yaml                 # Stack Docker completo
└── compose.prod.yaml            # Solo frontend
```
