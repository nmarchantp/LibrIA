# LibrIAverse

Plataforma social de lectura con React, FastAPI y PostgreSQL. Permite organizar bibliotecas, registrar lecturas y relecturas, publicar reseñas, conservar cuadernos, notas y teorías, participar en la comunidad y consultar analítica y resultados persistentes de IA.

Esta guía describe el código revisado el **9 de noviembre de 2026**, incluidos los cambios locales del modo demostración. No acredita un despliegue productivo ni una instalación completa en otro equipo. Los comandos Windows usan PowerShell y parten de la raíz del repositorio, salvo indicación expresa.

## Contenido

- [Estado actual](#estado-actual)
- [Arquitectura y tres esquemas](#arquitectura-y-tres-esquemas)
- [Instalación Windows desde cero](#instalación-windows-desde-cero)
- [Instalación con Docker](#instalación-con-docker)
- [Configuración](#configuración)
- [Primer uso y preparación de datos](#primer-uso-y-preparación-de-datos)
- [ETL y pipelines](#etl-y-pipelines)
- [Gemini y worker](#gemini-y-worker)
- [Recomendaciones, análisis e interpretaciones](#recomendaciones-análisis-e-interpretaciones)
- [Sesiones, permisos y acceso a IA](#sesiones-permisos-y-acceso-a-ia)
- [Actualizar, respaldar y verificar](#actualizar-respaldar-y-verificar)
- [Problemas frecuentes](#problemas-frecuentes)
- [Repositorio y documentación](#repositorio-y-documentación)

## Estado actual

| Área | Comportamiento actual |
|---|---|
| Cuentas y comunidad | Registro, login, OAuth Google opcional, perfiles, biblioteca, lecturas, reseñas normalizadas, publicaciones e interacciones. |
| Gestión | Administración de perfiles/entorno, gestión de contenido, eventos/agenda, desafío anual y moderación. |
| Datos | Catálogo de obras/ediciones, ETL diario y manual, proyecciones incrementales y trazabilidad. |
| Gemini | Cola persistente para `recommendation` y `reading_event_analysis`; apagado por defecto. |
| ADN/perfil personal | Lectura del perfil persistido asociado al flujo Gemini de recomendaciones e historial. Es distinto de la interpretación clásica de indicadores. |
| Interpretaciones clásicas personal y grupal | Generación pendiente: los POST devuelven HTTP 501; puede consultarse evidencia o contenido histórico autorizado. |
| Demo | Interruptor persistente, cuentas ficticias y actividad por APIs; requiere preparación del catálogo. |
| Migraciones | El árbol revisado llega a `0087_demo_mode`. Consultar siempre `alembic heads`; esta referencia escrita no sustituye esa comprobación. |

La aplicación básica funciona sin clave Gemini, sin Ollama y sin GPU. Código y reportes históricos no garantizan disponibilidad actual de servicios externos ni configuración correcta de una instalación.

## Arquitectura y tres esquemas

El backend es un **monolito modular**: una API FastAPI con módulos de dominio. Scheduler y worker Gemini son procesos separados que comparten PostgreSQL. No se requiere Redis ni broker externo: PostgreSQL conserva la cola y coordina consumidores.

```mermaid
flowchart LR
    U[Navegador React] --> W[Vite / Nginx]
    W --> A[FastAPI]
    A --> APP[(app: operación)]
    A --> AN[(analytics: hechos y proyecciones)]
    A --> IA[(ia: trabajos y resultados)]
    S[Scheduler separado] --> E[ETL diario / manual / incremental]
    APP --> E
    E --> AN
    E --> IA
    IA --> G[Worker Gemini separado]
    G --> API[Google Gemini API]
    API --> G
    G --> IA
    A --> C[Google Books / Open Library]
```

El navegador consulta LibrIA; la clave Gemini permanece en backend. La evidencia necesaria sí se transfiere al proveedor externo. El generador demo actual tiene una tarea propia en el ciclo de vida de la API y un bloqueo PostgreSQL; no sustituye al scheduler ni al worker IA.

| Esquema físico | Responsabilidad y ejemplos | Consumidores |
|---|---|---|
| `app` | Fuente operacional: usuarios/autenticación, perfiles, catálogo (`obras`, `ediciones`, autores/fuentes), biblioteca, lecturas/eventos, reseñas/revisiones, publicaciones, interacciones y procedencia demo. | API y extracción ETL. |
| `analytics` | Preparación y medición: `ejecuciones_etl`, hechos de lectura/reseñas/publicaciones, `indicadores_personales`, validaciones, `projection_runs`, `reader_current`, `catalog_current`. Conserva cortes, versiones y referencias de origen. | API de indicadores, preparación IA y scheduler. |
| `ia` | Orquestación/resultados: `reader_profile_versions`, `reader_profile_etl_states`, `reading_analysis_requests`, `reading_analysis_snapshots`, `jobs`, `analyses`, `evidence`, `reader_dna`, `recomendaciones_ia`, `interpretaciones_ia`, `usage_metrics`, `call_ledger`. | Sincronización, worker y consultas privadas. |

Son tres esquemas de la misma base, no tres servidores. El nombre vigente es **`ia`**; algunos diseños antiguos dicen `ai`. Hay vistas de compatibilidad para consultas históricas desde `analytics`; los resultados IA se almacenan físicamente en `ia`.

Una **obra** agrupa la identidad bibliográfica; una **edición** concreta idioma, ISBN y paginación. La biblioteca relaciona a la persona con la obra; cada intento de lectura y sus eventos conserva su propia experiencia, incluso al releer. La reseña pertenece al perfil y la obra; el análisis individual se asocia además al evento terminal concreto. Ejecuciones y huellas enlazan evidencia con versiones de resultados.

Los esquemas separan responsabilidades, pero no anonimizan datos. Backend aplica autorización por titular; las credenciales técnicas PostgreSQL tienen otro alcance. Para el esquema exacto consulta [modelos y migraciones](apps/backend/migrations/versions), no solo el [diseño histórico](docs/data-model.md).

## Instalación Windows desde cero

### 1. Instalar herramientas base

Necesitas PowerShell 5.1 o posterior y WinGet. Ejecuta cada instalación y atiende el instalador cuando lo solicite:

```powershell
winget --version
winget install --id Git.Git --exact --source winget
winget install --id Python.Python.3.12 --exact --source winget
winget install --id OpenJS.NodeJS.22 --exact --source winget
winget install --id PostgreSQL.PostgreSQL.17 --exact --source winget --interactive
```

Node incluye npm. Se propone Node 22 para desarrollo; el Dockerfile frontend fija Node `20.19`. El proyecto usa React 19 y Vite 6 con dependencias fijadas en `package-lock.json`. Python debe ser 3.12, como la imagen backend. FastAPI, Alembic y `google-genai` se instalan en `.venv` desde `requirements.txt`; no los instales globalmente.

Si no tienes WinGet, instala **App Installer** desde Microsoft Store o usa los instaladores oficiales de [Git](https://git-scm.com/downloads/win), [Python](https://www.python.org/downloads/windows/) (elige 3.12), [Node.js](https://nodejs.org/en/download) y [PostgreSQL](https://www.postgresql.org/download/windows/). El [manifiesto WinGet PostgreSQL 17](https://github.com/microsoft/winget-pkgs/tree/master/manifests/p/PostgreSQL/PostgreSQL/17) identifica el paquete indicado.

En PostgreSQL selecciona servidor y herramientas de línea de comandos. Conserva la contraseña del administrador `postgres`, anota el puerto (habitualmente `5432`) y deja el servicio iniciado. pgAdmin es opcional; Stack Builder no es necesario.

**Cierra y vuelve a abrir PowerShell** para actualizar el PATH. Comprueba:

```powershell
git --version
py -3.12 --version
node --version
npm.cmd --version
& 'C:\Program Files\PostgreSQL\17\bin\psql.exe' --version
& 'C:\Program Files\PostgreSQL\17\bin\pg_dump.exe' --version
Get-Service -Name 'postgresql*'
```

Para usar `psql`/`pg_dump` sin ruta completa en la terminal actual:

```powershell
$env:Path = 'C:\Program Files\PostgreSQL\17\bin;' + $env:Path
```

Ajusta la ruta si instalaste en otra carpeta. Si el servicio está detenido, inícialo desde Servicios de Windows o con `Start-Service -Name <nombre-del-servicio>` en una terminal administradora.

### 2. Descargar el código

Sustituye `<URL_DEL_REPOSITORIO>` por la URL entregada por el equipo, sin los signos `< >`:

```powershell
git clone <URL_DEL_REPOSITORIO> LibrIA
cd LibrIA
git status
```

Si ya lo clonaste, abre la terminal en esa carpeta. Cada integrante debe usar una base propia; no pruebes migraciones o semillas sobre el entorno de otra persona.

### 3. Crear usuario y base PostgreSQL

El setup **no crea el servidor, el rol ni la base**. Conéctate como administrador PostgreSQL; `-W` solicita la contraseña:

```powershell
& 'C:\Program Files\PostgreSQL\17\bin\psql.exe' -h localhost -p 5432 -U postgres -d postgres -W
```

Dentro de `psql`, para una instalación nueva:

```sql
CREATE ROLE libria_dev LOGIN;
\password libria_dev
CREATE DATABASE libria_dev OWNER libria_dev;
\q
```

`\password` pide dos veces una contraseña propia. El propietario puede aplicar las migraciones en esa base sin ser superusuario. Si el rol/base ya existen, verifica su uso; no los elimines para repetir la guía.

Comprueba la conexión con la nueva contraseña:

```powershell
& 'C:\Program Files\PostgreSQL\17\bin\psql.exe' -h localhost -p 5432 -U libria_dev -d libria_dev -W -c 'SELECT current_database(), current_user;'
```

### 4. Configurar los archivos locales

Desde la raíz, copia las plantillas **solo si aún no existen**:

```powershell
if (-not (Test-Path apps\backend\.env)) { Copy-Item apps\backend\.env.example apps\backend\.env }
if (-not (Test-Path apps\web\.env)) { Copy-Item apps\web\.env.example apps\web\.env }
```

Puedes dejar `DATABASE_URL` vacío en el primer setup: el script pide host, puerto, base, usuario y contraseña, y codifica la contraseña para la URL. También puedes completarla manualmente en `apps/backend/.env`:

```dotenv
APP_ENV=development
DATABASE_URL=postgresql+psycopg://libria_dev:CLAVE_CODIFICADA@localhost:5432/libria_dev
FRONTEND_ORIGINS=http://localhost:5173
GEMINI_WORKER_ENABLED=false
GEMINI_PAID_SERVICE_CONFIRMED=false
GEMINI_FREE_TEST_MODE=false
```

En una URL, caracteres como `@`, `:`, `/`, `#` y `%` requieren codificación porcentual. El asistente evita hacerlo a mano. No uses `CLAVE_CODIFICADA` como contraseña real.

Setup genera `JWT_SECRET` y `LIBRIA_DEMO_PASSWORD` aleatorios si están vacíos. Para elegir la contraseña del administrador inicial, configura `LIBRIA_DEMO_PASSWORD` con al menos ocho caracteres antes de migrar. En `apps/web/.env`, conserva `VITE_API_URL=http://localhost:8000/api`.

Los `.env` están excluidos de Git. Las variables `VITE_*` son públicas en el navegador: **nunca pongas allí claves Gemini, secretos OAuth ni contraseñas**.

### 5. Instalar dependencias y aplicar migraciones

```powershell
.\setup.cmd
```

Respalda el `.env`, añade variables faltantes, crea `.venv`, instala dependencias Python/frontend, comprueba conexión y revisiones Alembic y valida configuración IA sin contactar Gemini. **No migra por defecto**. En una base vacía es normal que `alembic current` aún no muestre revisión.

Para crear el esquema nuevo o actualizar uno existente:

```powershell
.\setup.cmd -AllowMainDatabaseMigration
```

El script exige escribir **`MIGRAR-POR-EXPLICITO`**, requiere `pg_dump`, crea un respaldo SQL en `backups/` y después ejecuta `alembic upgrade head` y la semilla inicial. No continúes si termina con error.

Cuenta inicial: **`demo.admin@example.com`**, contraseña local `LIBRIA_DEMO_PASSWORD`. En el modo de catálogo predeterminado se preparan diez lecturas terminadas, valoradas y reseñadas. Con `CATALOG_DISCOVERY_ENABLED=true`, se prepara solo la cuenta; para cargar su biblioteca debes importar ediciones autorizadas y usar el mapa descrito por `python -m scripts.seed_default_admin --help`. Esta cuenta inicial es distinta del generador de ocho perfiles demo.

### 6. Iniciar, comprobar y detener

```powershell
.\run.cmd
```

Comprueba/instala dependencias, exige la base en `head` e inicia API, frontend y scheduler según flags. Solo inicia el worker Gemini si está habilitado y se permite su modalidad. No migra.

| Servicio | Dirección Windows |
|---|---|
| Aplicación | <http://localhost:5173> |
| API | <http://localhost:8000> |
| Swagger / contratos HTTP | <http://localhost:8000/docs> |
| Health API | <http://localhost:8000/health> |

```powershell
Invoke-RestMethod http://localhost:8000/health
.\scripts\run-local.ps1 -PreflightOnly
```

Health confirma que responde el proceso; no comprueba ETL ni Gemini. El preflight es de solo lectura: dependencias, configuración y revisión Alembic. Comprueba además login y biblioteca en el navegador.

```powershell
.\scripts\stop-local.ps1
```

### Arranque manual por proceso

Para ver logs en primer plano, abre una terminal por proceso, sin duplicar los que ya inició `run.cmd`. Desde `apps/backend`:

```powershell
# Terminal 1: API
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload
```

```powershell
# Terminal 2: ETL, proyecciones y recuperación
.\.venv\Scripts\python.exe -m scripts.run_scheduler
```

```powershell
# Terminal 3: solo con Gemini configurado y habilitado
.\.venv\Scripts\python.exe -m scripts.run_gemini_worker
```

En otra terminal, desde `apps/web`:

```powershell
npm.cmd run dev
```

La ruta al Python de `.venv` evita activar scripts o seleccionar otro intérprete. Detén procesos en primer plano con `Ctrl+C`.

## Instalación con Docker

Esta alternativa instala Python, Node y PostgreSQL **dentro de contenedores**. En el host necesitas Git y Docker Desktop con Compose v2; no requiere esas herramientas nativas.

```powershell
winget install --id Git.Git --exact --source winget
winget install --id Docker.DockerDesktop --exact --source winget
```

Completa los requisitos de virtualización/WSL que indique [Docker Desktop para Windows](https://docs.docker.com/desktop/setup/install/windows-install/), reinicia si lo pide y abre Docker Desktop con contenedores Linux. Desde tu clon:

```powershell
docker version
docker compose version
if (-not (Test-Path apps\backend\.env)) { Copy-Item apps\backend\.env.example apps\backend\.env }
```

En `apps/backend/.env` configura `JWT_SECRET` aleatorio, `LIBRIA_DEMO_PASSWORD` de al menos ocho caracteres y `FRONTEND_ORIGINS=http://localhost:8080`. Para generar cada secreto puedes usar:

```powershell
$secretBytes = New-Object byte[] 32
$secretGenerator = [Security.Cryptography.RandomNumberGenerator]::Create()
$secretGenerator.GetBytes($secretBytes)
$secretGenerator.Dispose()
[Convert]::ToBase64String($secretBytes)
```

Copia el resultado únicamente a tu configuración local. Mantén Gemini apagado durante la instalación. En esta terminal configura DB y puerto web:

```powershell
$postgresSecret = Read-Host 'Contraseña del PostgreSQL Docker' -AsSecureString
$env:POSTGRES_PASSWORD = [Net.NetworkCredential]::new('', $postgresSecret).Password
$env:WEB_PORT = '8080'
docker compose config --quiet
docker compose build
docker compose --profile migration run --rm migrate
docker compose up -d
docker compose ps
```

`migrate` aplica Alembic y semilla de forma explícita. En bases existentes, respalda antes. `schema-check` bloquea el arranque con revisiones pendientes. Compose reemplaza `DATABASE_URL` por la conexión al servicio interno `db`; no necesitas configurar la conexión nativa para esta modalidad.

Aplicación: <http://localhost:8080>. El `/health` público verifica Nginx. Compose no publica el puerto de FastAPI y Nginx solo redirige `/api/`: Swagger `/docs` no está expuesto en esta modalidad. Para comprobar directamente FastAPI:

```powershell
docker compose exec api python -c "import urllib.request; print(urllib.request.urlopen('http://127.0.0.1:8000/health').status)"
docker compose logs --tail 100 api scheduler
```

PostgreSQL no publica puerto en el host. El frontend compilado usa `/api` y no necesita el `.env` web local. El volumen `postgres_data` conserva la base.

```powershell
docker compose stop
docker compose start
```

`docker compose down` conserva el volumen; **`down -v` elimina los datos**. Usa la misma contraseña en siguientes comandos Compose. Puedes conservarla en un `.env` raíz ignorado por Git (`POSTGRES_PASSWORD=...`, `WEB_PORT=8080`); variables de terminal prevalecen. Cambiar esa variable no cambia la contraseña de un volumen PostgreSQL ya inicializado: requiere rotación explícita en la base.

Después de preparar Gemini:

```powershell
docker compose --profile gemini up -d gemini-worker
docker compose logs --tail 100 gemini-worker
docker compose stop gemini-worker
```

Tras cambiar `.env`, recrea los servicios afectados con `docker compose up -d`; para el worker usa su perfil. `compose.prod.yaml` contiene solo frontend, no un despliegue completo. Compose no monta actualmente la carpeta de portadas demo: si usas esa función, configura persistencia adicional para `/app/var/demo-covers`.

## Configuración

Listas completas: [backend/.env.example](apps/backend/.env.example) y [web/.env.example](apps/web/.env.example). Los scripts añaden variables faltantes, pero preservan valores existentes; revisa cambios de plantilla al actualizar.

| Variables | Propósito |
|---|---|
| `APP_ENV`, `API_PREFIX` | Desarrollo: `development`, `/api`. No publiques producción con configuración de desarrollo. |
| `DATABASE_URL` | URL SQLAlchemy `postgresql+psycopg://...`; obligatoria en nativo, reemplazada por Compose. |
| `JWT_SECRET`, `JWT_ALGORITHM` | Firma JWT con secreto aleatorio propio; algoritmo predeterminado `HS256`. |
| `FRONTEND_ORIGINS` | Origen CORS exacto: `http://localhost:5173` nativo o `http://localhost:8080` Docker. |
| `VITE_API_URL` | URL API frontend. Cambiar variables Vite exige reiniciar desarrollo o reconstruir la aplicación compilada. |
| `LIBRIA_DEMO_PASSWORD` | Clave local para cuenta inicial/cuentas propias de demo; no reemplaza contraseñas existentes. |
| `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, `GOOGLE_REDIRECT_URI` | OAuth opcional; callback debe coincidir exactamente con el registrado. No son credenciales Gemini. |
| `GOOGLE_BOOKS_API_KEY`, `VITE_GOOGLE_BOOKS_API_KEY` | Integración opcional de catálogo servidor/navegador; la segunda es pública. |
| `OPEN_LIBRARY_CONTACT` | Identificación del responsable para uso regular de Open Library; no requiere otra API key. |
| `SMTP_HOST`, `SMTP_PORT`, `SMTP_USERNAME`, `SMTP_PASSWORD`, `SMTP_FROM` | Correo saliente de flujos de cuenta. No es requisito para iniciar procesos básicos. |
| `ANALYTICS_SCHEDULER_ENABLED`, `PROJECTION_SCHEDULER_ENABLED` | Habilitan cierre diario/proyecciones dentro del scheduler; no crean el proceso por sí solas. |
| `CATALOG_*` | Descubrimiento, identidad canónica, ediciones y herramientas administrativas. Plantilla desactivada; requieren migraciones y condiciones de despliegue. No actives todo para resolver un error. |
| `SESSION_*`, `ACCESS_TOKEN_EXPIRE_MINUTES` | Duración de sesiones, cookie, actividad y access JWT. |
| `AI_*`, `GEMINI_*`, versiones de prompts | Proveedor, habilitación, límites y contratos del worker. |

## Primer uso y preparación de datos

1. Entra con una cuenta registrada o el administrador inicial. La etiqueta pública de perfil no sustituye permisos administrativos.
2. Busca en Explorar y agrega libros. Los proveedores requieren Internet; una base nueva no incluye automáticamente un catálogo general completo.
3. Inicia una lectura, registra avances y termina o abandona el intento. Al releer, crea otro intento, sin duplicar la obra.
4. Escribe una reseña propia con texto y valoración. La señal positiva de recomendaciones exige lectura **terminada y valorada con 4 o 5**.
5. Añade cuaderno, notas, teorías o reflexión para enriquecer la evidencia privada correspondiente.
6. Espera al siguiente cierre o ejecuta, como administrador, el ETL manual en `/admin/etl`. Revisa éxito, corte y validaciones.
7. Para recomendaciones, inicia/reanuda actividad autenticada para sincronizar la versión preparada. Con worker habilitado, consulta el estado hasta disponer del resultado persistido.

**Demo opcional:** Administración > Configuración > Modo demostración. Requiere `CATALOG_DISCOVERY_ENABLED=true`, catálogo compatible y `LIBRIA_DEMO_PASSWORD`. Selección actual: doce títulos curados y ocho perfiles, con portadas verificadas y procedencia registrada. Empieza apagada; desactivarla detiene nuevas operaciones y conserva historial. No llama directamente a Gemini ni garantiza elegibilidad IA: cada consumidor filtra sus fuentes. Sigue [modo demostración](docs/demo-mode.md) antes de activarla.

Para dar administración a una cuenta ya registrada, desde `apps/backend`:

```powershell
.\.venv\Scripts\python.exe -m scripts.grant_admin --email tu-cuenta@ejemplo.com
```

## ETL y pipelines

El ETL **prepara y persiste datos; no llama a Gemini**. Existen tres operaciones diferentes:

| Operación | Cuándo y qué procesa | Resultado |
|---|---|---|
| Cierre diario | Día anterior completo a las 00:00 de `America/Santiago`; scheduler revisa aproximadamente cada 30 segundos. | Hechos, indicadores, validaciones, proyecciones y preparación IA versionada al corte. |
| ETL manual administrativo | Desde medianoche local de hace 29 días hasta el instante solicitado, incluido hoy. | Instantánea independiente, UUID idempotente y preparación de perfiles para todos los titulares elegibles, no solo el administrador. |
| Proyección incremental | Cambios pendientes revisados cada cinco segundos o ejecución explícita. | Estado analítico actual por lector/catálogo; por sí solo no autoriza el análisis individual coordinado por ETL. |

`scripts.run_scheduler` ejecuta recuperación manual, cierre diario, proyecciones y tareas del ciclo de vida de cuentas **fuera de FastAPI**. Las referencias antiguas a ETL dentro de la API no describen el arranque actual. No asumas que una tarea Windows existe en todos los equipos: `scripts/register-etl-task.ps1` es una alternativa opcional para cierres diarios.

### Extracción, transformación y carga

- **Extraer:** catálogo, biblioteca, intentos/eventos, revisiones de reseñas y aportes propios. Los pipelines sociales añaden contexto autorizado de seguimientos, comentarios y reacciones.
- **Transformar:** validar identidad obra/edición, titularidad, transiciones, páginas, fechas, contenido y procedencia. Una reacción a una crítica negativa no se convierte en gusto positivo. Referencias ambiguas y registros inválidos se excluyen con reglas contadas.
- **Cargar:** persistir hechos/proyecciones con ejecución, corte, versión y huellas; conciliar cantidades antes de publicar éxito. Preparar perfiles/solicitudes IA según su contrato.

Los cierres contemplan horario de verano: un día local puede durar 23 o 25 horas. Bloqueos PostgreSQL y unicidad impiden dos publicaciones exitosas de la misma fecha; un fallo puede reintentarse. El cierre exitoso es inmutable: importaciones tardías no reescriben el pasado silenciosamente.

Instantáneas manuales distintas pueden contener las mismas fuentes: **no sumes cortes como si fueran entidades únicas**. Reconstruir proyecciones actuales tampoco recupera textos eliminados ni versiones de campos sin historial.

### Comandos de operación

Desde `apps/backend`, con la base migrada:

```powershell
# Recuperar cierres pendientes; no procesa el día abierto
.\.venv\Scripts\python.exe -m scripts.run_etl

# Fecha individual cerrada; sustituye por tu fecha
.\.venv\Scripts\python.exe -m scripts.run_etl --date 2026-11-08

# Inicialización histórica explícita
.\.venv\Scripts\python.exe -m scripts.run_etl --from-date 2026-11-01

# Procesar proyecciones pendientes una vez
.\.venv\Scripts\python.exe -m scripts.run_analytics_etl

# Consumidor continuo de proyecciones, alternativa al scheduler para esa tarea
.\.venv\Scripts\python.exe -m scripts.run_analytics_etl --watch

# Reconstruir proyecciones actuales conservando ejecuciones históricas
.\.venv\Scripts\python.exe -m scripts.run_analytics_etl --rebuild
```

Escriben datos analíticos. Usa fechas correspondientes a tu instalación; sin argumentos no implica cargar toda la historia desde el origen. Para una instantánea actual usa el ETL manual web.

El catálogo dispone de ingesta explícita con conectividad externa:

```powershell
.\.venv\Scripts\python.exe -m scripts.run_catalog_ingest --query 'inauthor:Gabriel García Márquez'
.\.venv\Scripts\python.exe -m scripts.run_catalog_ingest --refresh-known
```

No es obligatorio para instalar ni una autorización de recolección masiva. En modo de descubrimiento/canónico revisa [incorporación](docs/catalog-incorporation-rules.md) y documentos de fase: algunos scripts conservan contratos anteriores.

En `/admin/etl` revisa ejecución, fase, corte, cantidades extraídas/cargadas/excluidas y reglas. La procedencia distingue `simulated`, `unclassified` y `operational`: desconocida no significa real acreditada. No mezcles demo para completar umbrales. Los hechos personales y su preparación siguen siendo privados.

## Gemini y worker

### Preparación y activación

El SDK `google-genai` está en `requirements.txt`; no necesitas Gemini CLI. Obtén una credencial de proyecto mediante [la guía oficial de API keys](https://ai.google.dev/gemini-api/docs/api-key). Comprueba modelo, cuota, tratamiento de datos y facturación antes de consumir.

La plantilla configura `GEMINI_MODEL=gemini-3.5-flash-lite`: es el valor del repositorio, **no una garantía de disponibilidad o precio actuales**. Revisa [modelos](https://ai.google.dev/gemini-api/docs/models), [precios](https://ai.google.dev/gemini-api/docs/pricing), [condiciones](https://ai.google.dev/gemini-api/terms) y [facturación](https://ai.google.dev/gemini-api/docs/billing). Si cambias modelo, actualiza identificación y tarifas de estimación.

Configuración inicial sin consumo:

```dotenv
AI_PROVIDER=gemini
GEMINI_API_KEY=
GEMINI_WORKER_ENABLED=false
GEMINI_PAID_SERVICE_CONFIRMED=false
GEMINI_FREE_TEST_MODE=false
```

Para servicio pagado previamente revisado, configura localmente:

```dotenv
GEMINI_API_KEY=TU_CREDENCIAL_LOCAL
GEMINI_WORKER_ENABLED=true
GEMINI_PAID_SERVICE_CONFIRMED=true
GEMINI_FREE_TEST_MODE=false
```

La confirmación es una decisión de configuración; no activa billing ni comprueba automáticamente la cuenta Google. La evidencia puede contener reseñas privadas, cuaderno, notas, teorías y reflexiones. Revisa esa transferencia antes de usar datos reales; no se envía el texto completo del libro ni credenciales de sesión.

`GEMINI_FREE_TEST_MODE=true` solo permite pruebas ficticias en `development`/`test`; no autoriza datos personales. Resultados guardados permanecen consultables con el worker apagado.

Desde la raíz, validar/agregar configuración faltante sin inferencias:

```powershell
.\scripts\prepare-ai.ps1
```

Puede añadir claves al `.env`; no es un chequeo estrictamente pasivo. Reinicia el worker tras cambiar configuración. Desde `apps/backend`:

```powershell
# Consumo continuo
.\.venv\Scripts\python.exe -m scripts.run_gemini_worker

# Alternativa: reclamar como máximo un trabajo elegible
.\.venv\Scripts\python.exe -m scripts.run_gemini_worker --once
```

### Procesamiento y controles

1. Reclama un job elegible mediante bloqueo, lease e intentos limitados.
2. Comprueba propietario, vigencia y evidencia autorizada por el corte.
3. Prepara contexto con referencias de evidencia; puede dividir/resumir conservando trazabilidad si excede el presupuesto.
4. Llama a Gemini y valida estructura Pydantic, citas y reglas de negocio.
5. Publica resultado y métricas en PostgreSQL; REST/UI recuperan lo persistido.

Idempotencia de publicación no equivale a facturación exactamente una vez: un timeout puede ocurrir después del procesamiento remoto. Un reintento podría tener costo adicional aunque solo se publique un resultado.

| Control | Valor de plantilla / efecto |
|---|---|
| `AI_TIMEOUT_SECONDS` | `180`, límite de solicitud. |
| `AI_MAX_CONCURRENT_REQUESTS`, `AI_REQUESTS_PER_MINUTE` | `2`, `10`; coordinación entre procesos que comparten base. |
| `AI_JOB_MAX_ATTEMPTS`, `AI_JOB_LEASE_SECONDS` | `3`, `600`; lease debe superar timeout al menos en 30 segundos. |
| `AI_MAX_CALLS_PER_JOB`, `AI_JOB_TOKEN_BUDGET` | `24`, `100000`; acotan el trabajo completo. |
| `AI_CONTEXT_TOKEN_BUDGET`, `AI_CHUNK_TOKEN_BUDGET`, `AI_OUTPUT_TOKEN_BUDGET` | `12000`, `6000`, `2048`; contexto, fragmentos y salida. |
| `AI_MONTHLY_BUDGET_USD` | `10.00`; corte global estimado con reservas, no saldo Google. |
| `AI_PRICING_MODEL`, `AI_INPUT_COST_PER_MILLION_USD`, `AI_OUTPUT_COST_PER_MILLION_USD` | Modelo y tarifas para estimación; revisar antes de consumir. |
| `AI_FREE_DAILY_TOKEN_POOL` | `0`; configuración local, no detección de cuota del proveedor. |

`ia.usage_metrics` y `ia.call_ledger` registran intentos/llamadas, tokens, duración y costo estimado; no equivalen a factura. El presupuesto puede dejar jobs pendientes como `budget_exhausted`. Subirlo no soluciona cuota externa, credenciales o evidencia inválida. Los 429/timeouts/5xx tienen recuperación acotada; investiga antes de reiniciar intentos manualmente.

## Recomendaciones, análisis e interpretaciones

### Recomendaciones y perfil lector

El ETL diario/manual prepara perfiles `recommendation-profile-v1` con lecturas terminadas y valoración general de al menos 4. Puede incluir dimensiones, reseña, cuaderno, notas, teorías y reflexión propias. Terminar sin valorar no equivale a preferencia positiva.

Login, OAuth y actividad autenticada sincronizan de forma deduplicada la última versión preparada. El worker elige candidatos del catálogo; backend verifica identidad, autoría, pertenencia, duplicados y evidencia. El ADN persistido acompaña este recorrido; el antiguo refresh de perfil no genera directamente.

| Ruta | Contrato actual |
|---|---|
| `GET /api/analytics/me/recommendations/state` | Lee estado/resultado; no encola ni llama al proveedor. |
| `POST /api/analytics/me/recommendations/sync` | Sincronización idempotente; puede crear el job deduplicado. |
| `GET /api/analytics/me/recommendations` | Lectura compatible. |
| `POST /api/analytics/me/recommendations` | HTTP 405; generación manual antigua deshabilitada. |
| `GET /api/me/ai/profile` y `/api/me/ai/profile/history` | Perfil persistido e historial autorizado. |
| `POST /api/me/ai/profile/refresh` | HTTP 405. |

Estados internos: `waiting_for_etl`, `insufficient_data`, `pending`, `processing`, `ready`, `outdated`, `failed`, `budget_exhausted`. La respuesta de compatibilidad de `/state` puede presentar `insufficient_data` como `no_positive_ratings`. Abrir/recargar pantallas no sustituye al ETL ni genera otra inferencia. Los antiguos botones de tandas manuales descritos en documentos Ollama no son el contrato vigente.

### Análisis de una lectura terminada o abandonada

Requiere biblioteca activa, evento `finish`/`abandon`, lectura todavía terminada/abandonada y una reseña personal vigente con texto no vacío de esa obra. Puntuaciones solas no bastan. **No exige diez libros.** Una relectura tiene otro evento/análisis; no se rellena con el de otra experiencia.

Los cambios crean solicitudes en `ia.reading_analysis_requests`. **Solo el ETL diario o manual administrativo** publica la instantánea y habilita `reading_event_analysis`. Proyecciones incrementales y refresh no saltan esa preparación. `READING_ANALYSIS_DELAY_MINUTES=30` permanece por compatibilidad; ya no gobierna el flujo.

El worker comprueba elegibilidad/huella, valida citas y guarda versiones. Cambios posteriores al corte esperan otra ejecución. Puede conservarse el último resultado permitido marcado como anterior; retirar fuentes puede retirar textos derivados. Validar estructura y citas no garantiza corrección semántica de toda inferencia.

| Ruta | Uso |
|---|---|
| `GET /api/me/ai/books/{book_id}` | Último análisis permitido del evento terminal correspondiente. |
| `POST /api/me/ai/books/{book_id}/refresh` | Consulta estado; incluso `force=true` respeta el ETL. |
| `POST /api/me/ai/books/{book_id}/retry` | Recuperación limitada para el siguiente cierre; conserva costos/intentos. |
| `GET /api/me/ai/books/{book_id}/history` | Historial privado paginado. |

Detalle de elegibilidad, estados y retiro de evidencia: [contrato nocturno vigente](docs/nightly-book-analysis.md).

### Interpretaciones clásicas y analítica grupal

La interpretación numérica personal de `/analytics/me/insights` y grupal de `/analytics/group/insights` son distintas del perfil lector y del análisis de libro. Sus POST de generación devuelven **501**: falta contrato Gemini aprobado. Encender el worker no los habilita.

Pueden consultarse indicadores y resultados históricos autorizados. Acceso profesional: capacidad de autor o membresía válida en editorial/librería; administración o influencer por sí solos no bastan. Agregados aplican umbrales, supresión y redondeo; comunidad insuficiente debe mostrarse como ausencia, sin inventar ejemplos. No representan necesariamente al mercado ni diagnostican personalidad.

[Interpretaciones](docs/ai-interpretations.md), [recomendaciones](docs/ai-recommendations.md) y partes de [pipelines](docs/analytics-pipelines.md) conservan diseños y mediciones históricas de Ollama. Para rutas activas usa esta guía, [preparación Gemini](docs/gemini-stage6-production-readiness.md), contrato nocturno y Swagger. **Ollama no tiene camino operativo; no se instala ni se descargan sus modelos.**

## Sesiones, permisos y acceso a IA

- Access JWT: **15 minutos** por defecto (`ACCESS_TOKEN_EXPIRE_MINUTES`), distinto de la duración total de sesión.
- Refresh cookie HttpOnly, rotación y revocación; `SameSite=Lax`. Cookie segura según entorno o `SESSION_COOKIE_SECURE`; producción requiere HTTPS.
- Inactividad: **24 horas** (`SESSION_INACTIVITY_HOURS`); máximo absoluto: **168 horas** (`SESSION_ABSOLUTE_HOURS`). Actividad explícita renueva inactividad, no el máximo absoluto; polling de fondo no debe mantener una sesión indefinidamente.
- La sesión determina al titular; una consulta personal no puede elegir otro usuario para acceder a evidencia. Resultados persistidos también requieren autorización.
- Las rutas clásicas `GET /api/analytics/me/insights` y `GET /api/analytics/me/recommendations` conservan el mínimo de **diez obras distintas activas**. Cuentan pendiente/leyendo/terminado/abandonado; relecturas no suman obras, y se excluyen entradas archivadas o identificadas como demo. Archivar puede revocar ese acceso sin borrar historial. Las rutas nuevas `/recommendations/state` y `/recommendations/sync` consultan el perfil preparado sin aplicar ese mismo chequeo de diez obras.
- No traslades ese mínimo a todo `/api/me/ai`: análisis individual por evento tiene reglas propias. Diez libros tampoco garantizan señal positiva ni un corte preparado para recomendaciones.
- Permisos administrativos de cuenta y capacidades públicas/profesionales son comprobaciones diferentes, aplicadas en backend.

Ver [acceso lector](docs/reader-ai-access.md), [cuentas](docs/cuentas-usuario.md), [Google OAuth](docs/google-login.md) y [perfil adaptativo](docs/adaptive-reader-ai.md), considerando sus avisos históricos.

## Actualizar, respaldar y verificar

### Actualizar un clon

1. Detén procesos, revisa `git status` y conserva/coordina cambios locales.
2. Respalda PostgreSQL y prueba restauración en una base separada.
3. Actualiza tu rama con el flujo Git acordado. `update.cmd` **no ejecuta `git pull`**.
4. Revisa plantillas y ejecuta `update.cmd`: sincroniza dependencias/variables, preserva y respalda `.env`; no migra ni inicia.
5. Compara revisiones Alembic y migra explícitamente si corresponde.
6. Ejecuta preflight, inicia y comprueba login, biblioteca, ETL y resultados.

```powershell
.\update.cmd
cd apps\backend
.\.venv\Scripts\python.exe -m alembic current
.\.venv\Scripts\python.exe -m alembic heads
cd ..\..
# Solo si hay migraciones pendientes y después de revisar el respaldo
.\setup.cmd -AllowMainDatabaseMigration
.\scripts\run-local.ps1 -PreflightOnly
.\run.cmd
```

### Respaldo nativo

Desde la raíz; ajusta conexión. `-W` pide contraseña:

```powershell
New-Item -ItemType Directory -Path backups -Force
$backupFile = Join-Path (Resolve-Path backups).Path ('libria-dev-' + (Get-Date -Format yyyyMMdd-HHmmss) + '.dump')
& 'C:\Program Files\PostgreSQL\17\bin\pg_dump.exe' -h localhost -p 5432 -U libria_dev -W -d libria_dev -Fc -f $backupFile
& 'C:\Program Files\PostgreSQL\17\bin\pg_restore.exe' --list $backupFile
```

Comprueba salida exitosa y archivo no vacío. Listar contenido no sustituye restaurar de prueba. Setup genera SQL plano para `psql`; este ejemplo `-Fc` genera formato custom para `pg_restore`. No restaures sobre datos activos sin procedimiento acordado.

### Respaldo y actualización Docker

Evita redirigir dumps binarios con PowerShell 5.1: genera dentro del contenedor y copia:

```powershell
New-Item -ItemType Directory -Path backups -Force
$dockerBackup = 'libria-' + (Get-Date -Format yyyyMMdd-HHmmss) + '.dump'
docker compose exec db pg_dump -U libria -d libria -Fc -f /tmp/libria-backup.dump
docker compose exec db pg_restore --list /tmp/libria-backup.dump
docker compose cp db:/tmp/libria-backup.dump "backups/$dockerBackup"
```

Con respaldo verificado y código actualizado:

```powershell
docker compose stop api scheduler web gemini-worker
docker compose build
docker compose --profile migration run --rm migrate
docker compose up -d
docker compose ps
```

Si usabas Gemini, levanta nuevamente su perfil. PostgreSQL no respalda automáticamente archivos descargados como portadas demo; conserva también ese almacenamiento.

### Verificar el código

Desde la raíz:

```powershell
cd apps\web
npm.cmd ci
npm.cmd run lint
npm.cmd run build
cd ..\backend
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\.venv\Scripts\python.exe -m pip check
.\.venv\Scripts\python.exe -m compileall -q app tests scripts
```

Antes de pruebas backend, configura una base temporal aislada y revisa los flags opt-in de cada integración. Solo después:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

No apuntes pruebas/semillas a datos compartidos o productivos. Pruebas con proveedor simulado no acreditan llamadas reales. Reportes fechados en `docs/` describen esas ejecuciones, no garantizan costos o latencias actuales.

Antes de producción revisa HTTPS, secretos externos, backup/restauración, monitoreo, tratamiento de evidencia, CSP y cabeceras de seguridad. El access token se conserva en `localStorage`, expuesto frente a XSS; no hay token CSRF separado. Estos comandos de desarrollo no constituyen endurecimiento productivo.

## Problemas frecuentes

| Síntoma | Comprobación / siguiente paso |
|---|---|
| Python no existe o abre Microsoft Store | Reabre terminal, comprueba `py -3.12 --version` y la instalación Python 3.12. |
| `npm.ps1` bloqueado | Usa `npm.cmd` manualmente. Setup invoca `npm`; si una política lo bloquea, usa una terminal permitida por tu organización o `Set-ExecutionPolicy -Scope Process Bypass` solo en esa sesión para scripts revisados. |
| Falta `psql`/`pg_dump` | Usa ruta completa o añade PostgreSQL `bin` al PATH. Setup necesita dump para migrar. |
| Conexión rechazada | Comprueba servicio, host y puerto. Docker usa `db` internamente y no publica PostgreSQL al host. |
| Autenticación DB fallida | Verifica usuario/base/contraseña sin imprimir secretos; revisa codificación de caracteres en URL manual. |
| Base vacía o revisión atrasada | Compara `current`/`heads`, respalda y migra explícitamente. El arranque normal no migra. |
| Puertos ocupados | Detén instancia anterior o ajusta puertos, CORS, URL API y OAuth coordinadamente. |
| CORS o cookie inválida | No mezcles `localhost` y `127.0.0.1`; revisa origen, API y cookie segura frente a HTTP/HTTPS. |
| Catálogo vacío | Comprueba conectividad/proveedores. Migrar no importa automáticamente todo el catálogo. |
| `waiting_for_etl` | Espera/ejecuta un corte diario o manual exitoso y sincroniza actividad autenticada; proyecciones solas no bastan. |
| `insufficient_data` | Revisa lecturas terminadas y nota 4 o 5 antes del corte; diez libros agregados no garantizan señal positiva. |
| Análisis individual pendiente | Comprueba evento terminal, biblioteca activa, reseña textual y ETL posterior al cambio. Refresh no adelanta el corte. |
| Job no avanza | Revisa proceso worker, flags, clave, presupuesto, lease y logs. API/scheduler no consumen Gemini. |
| 429 o presupuesto agotado | Distingue cuota externa, RPM local y presupuesto estimado; revisa métricas/backoff antes de reintentar. |
| Interpretación 501 o POST antiguo 405 | Limitación explícita del contrato; instalar Ollama no la resuelve. |
| Se muestra versión anterior | Revisa corte/estado `outdated`; puede conservarse la última versión permitida hasta completar otra. |
| Demo sin portadas/libros | Revisa descubrimiento, permisos, migración 0087, conectividad y títulos pendientes del panel. |

## Repositorio y documentación

```text
apps/backend/       FastAPI, módulos, migraciones, ETL, scripts y pruebas
apps/backend/legacy/ollama/   Referencia histórica comentada
apps/web/           React, Vite, Nginx y pruebas de interfaz
docs/               Contratos, diseño, guías y reportes fechados
scripts/            Setup, arranque, detención y utilidades Windows
setup.cmd           Instalación conservadora y migración opt-in
run.cmd             Arranque local
update.cmd          Dependencias/configuración; no hace pull ni migra
compose.yaml        Stack Docker y perfiles migration/gemini
compose.prod.yaml   Frontend únicamente
```

| Tema | Referencias |
|---|---|
| Gemini vigente | [Preparación operativa](docs/gemini-stage6-production-readiness.md), [análisis por evento](docs/nightly-book-analysis.md) |
| ETL y proyecciones | [ETL diario/manual](docs/etl-daily.md), [pipelines](docs/analytics-pipelines.md), [indicadores](docs/analytics-catalog.md) |
| Datos e identidad | [Diseño histórico](docs/data-model.md), [modelo social](docs/social-model.md), [identidad bibliográfica](docs/bibliographic-identity.md), [migraciones](apps/backend/migrations/versions) |
| Catálogo | [Incorporación](docs/catalog-incorporation-rules.md), [mantenimiento](docs/catalog-maintenance.md), [fase canónica 7](docs/catalog-canonical-phase7.md) |
| Cuentas y acceso | [Cuentas](docs/cuentas-usuario.md), [OAuth](docs/google-login.md), [acceso lector](docs/reader-ai-access.md) |
| Lectura y contenido | [Reseñas](docs/reviews.md), [reflexiones](docs/reading-reflections.md), [contenido](docs/content-management.md), [agenda](docs/events-agenda.md), [interacciones](docs/activity-interactions.md) |
| Demo | [Modo demostración y validación aislada](docs/demo-mode.md) |
| Contexto histórico IA | [Worker etapa 5](docs/gemini-stage5-worker.md), [recomendaciones anteriores](docs/ai-recommendations.md), [interpretaciones anteriores](docs/ai-interpretations.md) |

Cuando un diseño histórico difiera del código, verifica Swagger, modelos y cadena Alembic de tu checkout. No ejecutes instrucciones Ollama antiguas ni asumas que un reporte de una máquina describe la tuya.
