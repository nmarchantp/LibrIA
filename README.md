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
4. Creación de `apps/backend/.env` con JWT y credenciales aleatorias.
5. Creación del entorno virtual Python `.venv`.
6. Instalación de versiones Python fijadas en `requirements.txt`.
7. Ejecución de las migraciones de Alembic.
8. Instalación exacta del frontend mediante `npm ci` y `package-lock.json`.

El archivo `.env` es local y está excluido de Git. Nunca debe enviarse por correo, chat ni subirse al repositorio.

### 4. Levantar LibrIA

```powershell
.\run.cmd
```

También puede ejecutarse directamente `.\scripts\run-local.ps1`.

Se abrirán dos terminales:

- Frontend: <http://localhost:5173>
- Backend: <http://localhost:8000>
- Swagger: <http://localhost:8000/docs>

Para detener los servidores, presiona `Ctrl+C` en cada terminal.

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
