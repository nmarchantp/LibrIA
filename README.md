# LibrIA

Red social literaria adaptativa construida con React, JavaScript, FastAPI, Python y PostgreSQL. El proyecto utiliza un monolito modular y mantiene frontend, backend y datos claramente separados.

## Instalación en otro computador Windows

### 1. Instalar herramientas base

Abre PowerShell y comprueba que estén disponibles:

```powershell
git --version
node --version
python --version
psql --version
```

Se requieren Git, Node.js LTS, Python 3.12 y PostgreSQL 17. Si falta alguno, puede instalarse con:

```powershell
winget install --id Git.Git --exact
winget install --id OpenJS.NodeJS.LTS --exact
winget install --id Python.Python.3.12 --exact
winget install --id PostgreSQL.PostgreSQL.17 --exact
```

Durante la instalación de PostgreSQL debes recordar la contraseña asignada al usuario administrador `postgres`. Cierra y vuelve a abrir PowerShell después de instalar herramientas para actualizar el `PATH`.

### 2. Clonar el repositorio

```powershell
git clone https://github.com/nmarchantp/LibrIA.git
cd LibrIA
```

### 3. Ejecutar la instalación automática

Desde PowerShell ejecuta el archivo comando incluido:

```powershell
.\setup.cmd
```

También puedes hacer doble clic en `setup.cmd`. El archivo ejecuta internamente:

```powershell
.\scripts\setup-windows.ps1
```

El script solicitará de forma oculta la contraseña de `postgres` y realizará automáticamente:

1. Validación de Python, Node.js y PostgreSQL.
2. Creación o actualización del usuario local `libria` con contraseña aleatoria.
3. Creación de la base `libria` si todavía no existe.
4. Creación de `apps/backend/.env` con la conexión local, JWT y contraseña de demostración propias de ese equipo.
5. Creación del entorno virtual Python `.venv`.
6. Instalación de versiones Python fijadas en `requirements.txt`.
7. Ejecución de las migraciones de Alembic.
8. Carga idempotente del catálogo popular general, de Chile y de Argentina, consultando Google Books y conservando solamente obras y ediciones en español.
9. Consolidación de versiones de una misma obra y limpieza de cualquier registro bibliográfico que no esté en español.
10. Creación de `apps/web/.env` desde su ejemplo, si todavía no existe, e instalación exacta del frontend mediante `npm ci` y `package-lock.json`.

La carga del catálogo se ejecuta cada vez que se usa `setup.cmd`, para que cada computador de desarrollo reciba una base bibliográfica inicial equivalente. Puede tardar varios minutos y necesita conexión a Internet. Es seguro repetirla: reutiliza las obras y ediciones existentes, consolida duplicados y no elimina usuarios ni perfiles. En producción, `setup.cmd` no forma parte del arranque normal; esta carga debe ejecutarse una sola vez durante la preparación inicial del entorno.

Los archivos [apps/backend/.env.example](apps/backend/.env.example) y [apps/web/.env.example](apps/web/.env.example) documentan todas las variables que usa cada aplicación. `setup.cmd` genera las contraseñas locales y deja listos ambos `.env`. Para habilitar Google OAuth o Google Books, cada integrante debe completar las variables `GOOGLE_*` y `VITE_GOOGLE_BOOKS_API_KEY` en sus archivos locales con las credenciales que tenga autorizadas. Los `.env` reales contienen secretos y siguen excluidos de Git.

### 4. Levantar LibrIA

```powershell
.\run.cmd
```

Antes de abrir los servidores, `run.cmd` comprueba las dependencias de Python y Node.js y aplica las migraciones pendientes de la base de datos. Si una comprobación falla, detiene el inicio y muestra el error. El archivo local `.env` debe existir; este comando no lo reemplaza.

Si el backend o el frontend de LibrIA ya están abiertos en sus puertos habituales, `run.cmd` los reutiliza y evita iniciar una segunda instancia.

Después de actualizar el repositorio desde GitHub, puedes preparar el entorno sin iniciar los servidores:

```powershell
.\update.cmd
```

Este comando ejecuta `git pull --ff-only` y las mismas comprobaciones de `run.cmd`. Si usas `git pull` por tu cuenta, `run.cmd` detecta los cambios al siguiente inicio.

### Nuevas funciones: IA local y analítica

`setup.cmd`, `update.cmd` y `run.cmd` también ejecutan `scripts/prepare-ai.ps1`. Este paso agrega las variables faltantes de `apps/backend/.env.example` al `.env` local, sin reemplazar los valores existentes. Instala Ollama mediante `winget` si falta, inicia su servidor local si está detenido y descarga el modelo configurado en `AI_MODEL` (por defecto `qwen3:1.7b`) solo si aún no está disponible. La primera preparación necesita Internet, espacio para Ollama y el modelo, y puede tardar varios minutos. Las siguientes ejecuciones reutilizan la instalación y el modelo.

Si `winget` no está disponible, instala [Ollama para Windows](https://ollama.com/download/windows) y ejecuta nuevamente `update.cmd`. Si una instalación o descarga falla, el comando se detiene con el motivo; después de corregirlo puedes repetirlo. No se requiere una clave de API para la IA local.

Las nuevas tablas de reseñas, catálogo, analítica, recomendaciones y reflexiones se crean con las migraciones de Alembic que ya aplica la actualización. `requirements.txt` incluye `tzdata`, necesario para las fechas del ETL en `America/Santiago` en Windows. El ETL diario se ejecuta desde el backend con `ANALYTICS_SCHEDULER_ENABLED=true`; la tarea de Windows de `scripts/register-etl-task.ps1` es opcional.

Después de actualizar, inicia LibrIA con `run.cmd`. Para llenar los análisis con actividad reciente, una cuenta administradora puede usar **Gestionar ETL → Ejecutar ETL ahora**. La instalación prepara las herramientas y las tablas; los datos y permisos de cada usuario determinan qué análisis puede consultar. Los escenarios ficticios de `scripts.seed_analytics_demo`, `scripts.seed_reviews_demo` y `scripts.seed_group_demo` se cargan manualmente desde `apps/backend` si se necesitan para una demostración.

También puede ejecutarse directamente `.\scripts\run-local.ps1`.

Se abrirán dos terminales:

- Frontend: <http://localhost:5173>
- Backend: <http://localhost:8000>
- Swagger: <http://localhost:8000/docs>

Para detener los servidores, presiona `Ctrl+C` en cada terminal.

### Documentación de la API

Con el backend en ejecución, abre <http://localhost:8000/docs> para consultar y probar los endpoints desde Swagger UI.

También puedes consultar la documentación en ReDoc en <http://localhost:8000/redoc> o el esquema OpenAPI en <http://localhost:8000/openapi.json>.

### Posts de demo

El generador de posts de demo no se inicia por defecto. Para activarlo, ejecuta desde la raíz del proyecto en PowerShell:

```powershell
.\scripts\run-local.ps1 -DemoPosts
```

Este comando inicia LibrIA y abre una terminal adicional que genera posts de prueba cada 20 segundos. Para detener el generador, presiona `Ctrl+C` en su terminal.

## Inicio manual

Backend:

```powershell
cd apps\backend
.\.venv\Scripts\Activate.ps1
uvicorn app.main:app --reload
```

Frontend, en otra terminal:

```powershell
cd apps\web
npm run dev
```

## Verificaciones antes de subir cambios

```powershell
cd apps\web
npm run lint
npm run build

cd ..\backend
.\.venv\Scripts\python.exe -m compileall -q app migrations
.\.venv\Scripts\python.exe -m alembic current
```

## Archivos que sí se suben

- Código dentro de `apps/`.
- Migraciones de Alembic.
- `package.json`, `package-lock.json` y `requirements.txt`.
- `.env.example`, documentación y scripts.
- Configuración Docker, aunque su uso local es opcional por ahora.

## Archivos que nunca se suben

- `.env` o credenciales.
- `.venv`, `node_modules` y `dist`.
- `__pycache__`, cachés, logs y cobertura.
- Configuración personal del editor.

Estas exclusiones están definidas en `.gitignore`.

## Estructura

Analítica: [catálogo de indicadores](docs/analytics-catalog.md), con públicos, fórmulas, granularidad, fuentes y brechas pendientes antes de implementar el ETL.

Revisión previa al ETL: [brechas transaccionales](docs/transactional-gaps.md), con separación de publicaciones, reseñas y avances, tratamiento de datos existentes y orden de implementación.

Documentación: [arquitectura](docs/architecture.md), [modelo de datos](docs/data-model.md) y [base de datos y pgAdmin](docs/database.md), con las tablas actuales, cómo visualizarlas y el diseño propuesto para las siguientes etapas.

```text
LibrIA/
├── apps/
│   ├── backend/       # Monolito modular FastAPI
│   └── web/           # Aplicación React
├── docs/              # Arquitectura
├── scripts/
│   ├── setup-windows.ps1
│   └── run-local.ps1
├── setup.cmd           # Instalación inicial con un comando
├── run.cmd             # Inicio diario con un comando
├── compose.yaml
├── .env.example
└── README.md
```

## Docker opcional

La configuración se conserva para usarla cuando el equipo tenga virtualización habilitada:

```powershell
docker compose up --build
```
