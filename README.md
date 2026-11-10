# LibrIAverse

Plataforma social de lectura con React, FastAPI y PostgreSQL. Permite organizar bibliotecas, registrar lecturas y relecturas, publicar reseñas, conservar cuadernos, notas y teorías, participar en la comunidad y consultar analítica y resultados persistentes de IA.

Esta guía describe el código revisado el **9 de noviembre de 2026**, incluidos los cambios locales del modo demostración. No acredita un despliegue productivo ni una instalación completa en otro equipo. Los comandos Windows usan PowerShell y parten de la raíz del repositorio, salvo indicación expresa.

## Contenido

- [Estado actual](#estado-actual)
- [Arquitectura y tres esquemas](#arquitectura-y-tres-esquemas)
- [Modelo analítico: granularidad, hechos, dimensiones y cálculos](#modelo-analítico-granularidad-hechos-dimensiones-y-cálculos)
- [Instalación Windows desde cero](#instalación-windows-desde-cero)
- [Instalación con Docker](#instalación-con-docker)
- [Configuración](#configuración)
- [Primer uso y preparación de datos](#primer-uso-y-preparación-de-datos)
- [ETL y pipelines](#etl-y-pipelines)
- [Gemini y worker](#gemini-y-worker)
- [Recomendaciones, análisis e interpretaciones](#recomendaciones-análisis-e-interpretaciones)
- [Sesiones, permisos y acceso a IA](#sesiones-permisos-y-acceso-a-ia)
- [Funciones adicionales del administrador del sistema](#funciones-adicionales-del-administrador-del-sistema)
- [Seguridad de la información, ciberseguridad y auditoría](#seguridad-de-la-información-ciberseguridad-y-auditoría)
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

### Flujo definido para los datos y la IA

La separación de responsabilidades acordada es **`app` → ETL → `analytics` → worker Gemini → resultados en `ia`**. El worker obtiene sus trabajos de `ia.jobs`, pero eso es coordinación: la evidencia que alimenta el análisis debe proceder de los datos preparados por ETL en `analytics`.

El siguiente diagrama representa **ese diseño definido**, no una migración ya aplicada al código:

```mermaid
flowchart TB
    subgraph WEB[Aplicación web]
        U[React: interfaz] --> W[Vite: desarrollo / Nginx: archivos y proxy]
        W --> A[FastAPI: API y permisos]
    end

    subgraph DATA[Preparación de datos]
        APP[(app: datos operacionales)] -->|Extraer| E[ETL: validar y transformar]
        S[Scheduler: programar y recuperar] -.->|Ejecutar| E
        E -->|Publicar datos preparados| AN[(analytics: hechos, perfiles e instantáneas)]
    end

    subgraph AI[Procesamiento de IA]
        J[(ia.jobs: cola de trabajos)] -.->|Reclamar trabajo| G[Worker Gemini: procesar y validar]
        G -->|Contexto preparado| API[Gemini API: inferencia]
        API -->|Respuesta estructurada| G
        G -->|Guardar resultados y métricas| R[(ia: resultados e historial)]
    end

    A <-->|Operación| APP
    A -->|Solicitar o sincronizar trabajo| J
    AN -->|Evidencia preparada por ETL| G
    AN -->|Indicadores| A
    R -->|Resultados persistidos| A
    A <-->|Consultar catálogo| C[Google Books / Open Library]
```

Las flechas continuas muestran circulación de datos; las discontinuas muestran coordinación del procesamiento. **La cola no es la fuente de evidencia del análisis.**

### Diferencia con la implementación actual

Actualmente el ETL sí prepara la evidencia antes de la inferencia, pero guarda perfiles en **`ia.reader_profile_versions`** e instantáneas en **`ia.reading_analysis_snapshots`**. El worker consume esas entradas desde `ia` y también consulta `app` para candidatos bibliográficos y comprobaciones. Por tanto, `ia` reúne hoy preparación de entrada, coordinación y resultados: **la separación física aún no coincide completamente con el diseño anterior**.

Para ajustarse estrictamente al diseño, los perfiles e instantáneas de entrada deberían residir en `analytics`, y los trabajos de `ia` referenciarlos. Esta aclaración documenta la diferencia; no modifica tablas, consultas ni procesos.

El navegador consulta LibrIA; la clave Gemini permanece en backend. La evidencia necesaria sí se transfiere al proveedor externo. El generador demo actual tiene una tarea propia en el ciclo de vida de la API y un bloqueo PostgreSQL; no sustituye al scheduler ni al worker IA.

### Distribución física actual de los tres esquemas

| Esquema físico | Responsabilidad y ejemplos | Consumidores |
|---|---|---|
| `app` | Fuente operacional: usuarios/autenticación, perfiles, catálogo (`obras`, `ediciones`, autores/fuentes), biblioteca, lecturas/eventos, reseñas/revisiones, publicaciones, interacciones y procedencia demo. | API y extracción ETL. |
| `analytics` | Preparación y medición: `ejecuciones_etl`, hechos de lectura/reseñas/publicaciones, `indicadores_personales`, validaciones, `projection_runs`, `reader_current`, `catalog_current`. Conserva cortes, versiones y referencias de origen. | API de indicadores, preparación IA y scheduler. |
| `ia` | Orquestación/resultados: `reader_profile_versions`, `reader_profile_etl_states`, `reading_analysis_requests`, `reading_analysis_snapshots`, `jobs`, `analyses`, `evidence`, `reader_dna`, `recomendaciones_ia`, `interpretaciones_ia`, `usage_metrics`, `call_ledger`. | Sincronización, worker y consultas privadas. |

Son tres esquemas de la misma base, no tres servidores. El nombre vigente es **`ia`**; algunos diseños antiguos dicen `ai`. Hay vistas de compatibilidad para consultas históricas desde `analytics`; los resultados IA se almacenan físicamente en `ia`.

Una **obra** agrupa la identidad bibliográfica; una **edición** concreta idioma, ISBN y paginación. La biblioteca relaciona a la persona con la obra; cada intento de lectura y sus eventos conserva su propia experiencia, incluso al releer. La reseña pertenece al perfil y la obra; el análisis individual se asocia además al evento terminal concreto. Ejecuciones y huellas enlazan evidencia con versiones de resultados.

Los esquemas separan responsabilidades, pero no anonimizan datos. Backend aplica autorización por titular; las credenciales técnicas PostgreSQL tienen otro alcance. Para el esquema exacto consulta [modelos y migraciones](apps/backend/migrations/versions), no solo el [diseño histórico](docs/data-model.md).

### Herramientas y su función

| Logo | Herramienta | Uso en LibrIAverse |
|---|---|---|
| <img src="https://cdn.jsdelivr.net/gh/devicons/devicon/icons/react/react-original.svg" width="32" height="32" alt="React"> | React | Construye la interfaz y sus componentes interactivos. |
| <img src="https://cdn.jsdelivr.net/gh/devicons/devicon/icons/vitejs/vitejs-original.svg" width="32" height="32" alt="Vite"> | Vite | Sirve el frontend durante desarrollo y genera la compilación web. |
| <img src="https://cdn.jsdelivr.net/gh/devicons/devicon/icons/nginx/nginx-original.svg" width="32" height="32" alt="Nginx"> | Nginx | Sirve el frontend compilado y redirige `/api/` a FastAPI en Docker. |
| <img src="https://cdn.jsdelivr.net/gh/devicons/devicon/icons/python/python-original.svg" width="32" height="32" alt="Python"> | Python | Ejecuta backend, ETL, scheduler y worker Gemini. |
| <img src="https://cdn.jsdelivr.net/gh/devicons/devicon/icons/fastapi/fastapi-original.svg" width="32" height="32" alt="FastAPI"> | FastAPI | Expone la API HTTP y aplica autenticación y permisos. |
| <img src="https://cdn.jsdelivr.net/gh/devicons/devicon/icons/postgresql/postgresql-original.svg" width="32" height="32" alt="PostgreSQL"> | PostgreSQL | Persiste los tres esquemas, la cola y los resultados; coordina procesos mediante bloqueos. |
| <img src="https://cdn.jsdelivr.net/gh/devicons/devicon/icons/sqlalchemy/sqlalchemy-original.svg" width="32" height="32" alt="SQLAlchemy"> | SQLAlchemy | Gestiona modelos, consultas y transacciones del backend. |
| <img src="https://cdn.simpleicons.org/googlegemini/8E75B2" width="32" height="32" alt="Google Gemini"> | Google Gemini API | Realiza la inferencia externa; el worker prepara solicitudes y valida respuestas. |
| <img src="https://cdn.jsdelivr.net/gh/devicons/devicon/icons/nodejs/nodejs-original.svg" width="32" height="32" alt="Node.js"> | Node.js | Ejecuta herramientas y scripts del frontend; no reemplaza al backend Python. |
| <img src="https://cdn.jsdelivr.net/gh/devicons/devicon/icons/npm/npm-original-wordmark.svg" width="32" height="32" alt="npm"> | npm | Instala dependencias web y ejecuta desarrollo, lint y build. |
| <img src="https://cdn.jsdelivr.net/gh/devicons/devicon/icons/docker/docker-original.svg" width="32" height="32" alt="Docker"> | Docker / Compose | Construye imágenes y coordina los servicios de la instalación con contenedores. |
| <img src="https://cdn.jsdelivr.net/gh/devicons/devicon/icons/git/git-original.svg" width="32" height="32" alt="Git"> | Git | Versiona el código y permite colaborar en el repositorio. |

Además, **Alembic** versiona las migraciones PostgreSQL, **Pydantic** valida configuración y contratos de datos/respuestas IA, y **google-genai** comunica el worker con Gemini. Google Books y Open Library aportan metadatos bibliográficos. Scheduler, ETL y worker son procesos propios de LibrIAverse, no herramientas externas adicionales.

Los logos se cargan desde [Devicon](https://devicon.dev/) y [Simple Icons](https://simpleicons.org/); requieren conexión y un visor Markdown compatible con imágenes HTML. Los nombres y descripciones siguen disponibles si el visor bloquea imágenes externas.

## Modelo analítico: granularidad, hechos, dimensiones y cálculos

Esta descripción procede de las migraciones y transformaciones del repositorio; no de una inspección de datos de una base en ejecución. **`analytics` es un modelo híbrido, no un esquema estrella completo**: combina hechos, catálogos al corte, agregados, proyecciones JSON y tablas de control. No tiene una única granularidad ni dimensiones físicas `dim_fecha`, `dim_lector` o `dim_edicion`.

### Granularidad de hechos y evidencia

El **grano** indica qué representa exactamente una fila. En las tablas del cierre, `etl_run_id` forma parte de la identidad: el mismo registro de origen puede aparecer en varios cortes sin ser una nueva actividad.

| Tabla de `analytics` | Clasificación | Grano / clave de una fila | Contenido y medidas |
|---|---|---|---|
| `hechos_lectura` | Hecho de evento | Una ejecución × un evento de origen; PK `(etl_run_id, source_id)`. | Titular, obra, edición opcional, tipo y fecha del evento, página previa/actual y total disponible. Permite contar eventos y calcular desplazamiento de página. |
| `hechos_publicaciones` | Hecho de publicación | Una ejecución × una publicación manual de origen; PK `(etl_run_id, source_id)`. | Ejecutor, perfil, subtipo, fecha y procedencia. No copia el cuerpo; excluye posts legados de avances/reseñas como fuente de esos hechos. |
| `hechos_resenas` | Hecho de instantánea | Una ejecución × una reseña, con su última revisión elegible anterior al corte; PK `(etl_run_id, source_id)`. | Titular, obra/edición, valoración, estado, primera publicación y revisión. No es una fila por cada edición del texto ni solo por las reseñas creadas ese día. |
| `hechos_reflexiones` | Evidencia cualitativa de evento | Una ejecución × un evento de finalización con reflexión válida; PK `(etl_run_id, source_id)`. | Reflexión autodeclarada en JSON, titular, obra, fecha y procedencia. No es una emoción inferida por el ETL. |
| `evidencia_lectora_personal` | Instantánea privada de aportes | Una ejecución × tipo de fuente × fuente; PK `(etl_run_id, source_kind, source_id)`. | Cuaderno, reseña, nota o teoría, con titular, obra, fecha y JSON. Evidencia acumulada al corte; no debe contarse como actividad exclusiva del intervalo. |

No todos los hechos son numéricos: algunos documentan que ocurrió una actividad y otros conservan evidencia cualitativa. Estos últimos no deben tratarse como una medida sumable ni ponerse a disposición del análisis grupal como textos individuales.

### Dimensiones y atributos de análisis

| Eje | Implementación actual | Límite |
|---|---|---|
| Obra | `catalogo_obras`, una fila por `(etl_run_id, work_id)`, con título normalizado. Cumple una función de dimensión bibliográfica mínima al corte. | No es una dimensión completa con historial de todos los atributos. Los hechos de lectura y reseñas la referencian por ejecución y obra. |
| Catálogo vigente | `catalog_current`, una fila por `work_id`, con ediciones/metadatos/categorías en JSON. | Es una proyección actual reemplazable, distinta del catálogo histórico por ejecución. No equivale a una `dim_edicion` normalizada. |
| Tiempo | Fechas de hechos más `business_date`, `period_start` y `source_cutoff_at` de `ejecuciones_etl`. | No existe tabla calendario. El día de negocio usa Santiago; los instantes se conservan con zona horaria. |
| Lector/perfil | Claves `user_id`, `owner_id` y `profile_id`, según la tabla. | Son referencias identificables para preparación restringida y análisis propio; no una dimensión pública o anonimizada de lectores. |
| Edición | `edition_id` en hechos que la admiten, con origen en el catálogo operacional. | Puede faltar; no asignar una edición ni paginación por suposición. |
| Procedencia | Atributo `provenance`: `simulated`, `unclassified` u `operational`, según el contrato de cada tabla. | No mezcla poblaciones ni acredita origen real por sí mismo. |
| Tipo de actividad | `event_kind`, `publication_type`, `source_kind` y `indicator_code`. | Atributos/códigos, no tablas de dimensiones independientes. |

Conceptualmente, los hechos de lectura y reseñas se conectan con el catálogo por **ejecución + obra** y con el control ETL por **ejecución**. No todas las referencias descriptivas constituyen claves foráneas a dimensiones físicas. No se debe dibujar un esquema estrella con tablas que el repositorio no crea.

### Agregados, proyecciones y control

| Tabla | Grano | Función |
|---|---|---|
| `indicadores_personales` | Ejecución × titular × indicador × procedencia. | Valor numérico y versión de definición de los indicadores personales. |
| `preparacion_valoraciones_obras` | Ejecución × obra × procedencia. | Conteos de reseñas/valoraciones, suma, media y distribución; preparación restringida. |
| `projection_runs` | Una versión de proyección de un titular, identificada por `id`. | JSON con biblioteca, eventos, reseñas, interacciones y feedback; huella, versión y fechas de corte/procesamiento. Se reutiliza si no cambian contenido y transformación. |
| `reader_current` | Un titular (`owner_id`). | Puntero al `run_id` de su proyección vigente; no es otro hecho de lectura. |
| `resumenes_grupales` | Fecha de publicación × procedencia. | Publicación agregada protegida del recorrido clásico. |
| `community_releases` | Una fecha de publicación. | JSON de indicadores comunitarios IND-001 a IND-010 y trazabilidad de fuentes. |
| `peer_releases` | Titular destinatario × fecha. | Publicación de descubrimiento colaborativo; no es un hecho ni una dimensión bibliográfica. |
| `ejecuciones_etl` | Una ejecución. | Día de negocio o solicitud manual, intervalo, estado, versión, intentos y resumen técnico. |
| `validaciones_etl` | Ejecución × regla. | Gravedad y cantidad afectada por exclusiones/validaciones y conciliación. |
| `dirty_readers`, `dirty_catalog` | Un titular pendiente / una obra pendiente. | Control incremental de cambios por procesar; no son datos para indicadores. |

`instantaneas_actividad` pertenece al modelo inicial y conserva métricas JSON por instantánea e intervalo; no sustituye a los hechos normalizados actuales. Las antiguas tablas de recomendaciones/interpretaciones de `analytics` se trasladaron a `ia`, con compatibilidad de consultas; no deben catalogarse como hechos analíticos actuales por aparecer en una migración antigua.

### Cálculos personales implementados en el ETL

En `etl.py`, la transformación vigente es `daily-v5-editionless`. Los cálculos se realizan sobre registros que superan las validaciones, agrupados por **titular y procedencia**, y se guardan con la ejecución y versión de definición.

| Código | Cálculo implementado | Interpretación / precaución |
|---|---|---|
| L02 | Conteo de entradas de biblioteca creadas dentro de `[inicio, corte)` cuya obra es válida. | Incorporaciones registradas; no tamaño actual total de biblioteca. |
| L04 | Conteo de eventos válidos `start` en el intervalo. | Inicios de intentos, no personas ni obras distintas. |
| L05 | Conteo de eventos válidos `finish` en el intervalo. | Finalizaciones declaradas; relecturas son otros intentos. |
| L06 | Conteo de eventos válidos `abandon` en el intervalo. | Abandonos explícitos; no se deducen por inactividad. |
| L09 | `1` si hay algún evento válido distinto de `correction`; `0` para una combinación titular/procedencia con indicadores pero sin esa actividad. | En cierre diario indica actividad de ese día. En manual es presencia en todo el intervalo, no cantidad de días activos. |
| L10 | `Σ(page − previous_page)` para `progress`, `correction` y `finish`. | Desplazamiento neto registrado: admite correcciones negativas, no equivale a páginas efectivamente leídas. |
| S02 | Conteo de reseñas elegibles cuya **primera publicación** cae en el intervalo. | Editar una reseña no vuelve a contar una publicación. |
| S03 | Conteo de publicaciones manuales válidas de perfiles personales en el intervalo. | No atribuye publicaciones de organizaciones al análisis personal del ejecutor ni duplica avances/reseñas. |

Si no hay fuentes elegibles que formen el grupo titular/procedencia, no se genera una serie de ceros para toda la población. Las exclusiones se registran por regla. Las restricciones de moderación, identidad, propiedad y corte condicionan las fuentes incluidas.

### Valoraciones por obra: preparación de S01

Para cada **ejecución × obra × procedencia**, el ETL usa las reseñas válidas con estado `published` al corte y calcula:

- `review_count = número de reseñas publicadas`, tengan o no valoración.
- `rated_count = número de valoraciones no nulas`.
- `rating_sum = suma de valoraciones no nulas`.
- `rating_average = rating_sum / rated_count`; si no hay valoraciones, queda **NULL**, no cero.
- `distribution = frecuencia de cada valor permitido`, de **0,25 a 5 en incrementos de 0,25** en el contrato actual.

Las reseñas `hidden` elegibles pueden conservarse en `hechos_resenas`, pero no alimentan este agregado de valoraciones públicas. Esta preparación no es por sí misma una autorización para publicar resultados de grupos pequeños.

Ejemplo: valoraciones `[4, 5, NULL]` producen `review_count=3`, `rated_count=2`, `rating_sum=9`, `rating_average=4,5`. Para combinar grupos compatibles se recalculan medias con sumas y denominadores; **no se promedian medias sin ponderar ni se suman instantáneas repetidas**.

### Cálculos comunitarios implementados

`community.py` calcula los siguientes indicadores sobre proyecciones persistidas. No crea diez tablas de hechos: construye una publicación JSON en `community_releases`. Usa un período actual de 30 días y los 30 días anteriores, con corte fijado para la publicación diaria de Santiago.

| Código | Cálculo y grano de salida |
|---|---|
| IND-001 | Por obra: lectores distintos con `finish` en el período; relecturas/ediciones no multiplican al lector. Conteo publicado redondeado. |
| IND-002 | Por obra: lectores distintos con `abandon` en el período. No implica rechazo del libro. |
| IND-003 | Por obra: inicios entre 60 y 30 días antes del corte; primer desenlace de cada intento dentro de sus 30 días iniciales, conservando un desenlace por lector/obra. `100 × abandonos_redondeados / (abandonos_redondeados + finales_redondeados)`, a un decimal. No es abandonos sobre todos los inicios. |
| IND-004 | Por categoría: cada obra terminada por lector reparte peso `1/n` entre sus categorías normalizadas. `100 × peso_redondeado_categoria / Σ pesos_redondeados_publicables`, a un decimal. |
| IND-005 | Por categoría publicable en ambos períodos: participación actual menos participación anterior, en **puntos porcentuales**. |
| IND-006 | Por obra: media de valoraciones públicas vigentes por lector/obra anteriores al corte; redondeo a medio punto. No se limita a reseñas publicadas en los últimos 30 días. |
| IND-007 | Por perfil de autor: seguidores distintos vigentes antes del corte; conteo redondeado. No equivale a lectores de sus obras. |
| IND-008 | Por obra: suma de comentarios/reacciones del período con vínculo bibliográfico no ambiguo, limitando cada lector a diez; conteo redondeado. |
| IND-009 | Por tipo `start`/`finish`: suma de eventos del período, máximo diez por lector y tipo; conteo redondeado. |
| IND-010 | Por tipo de actividad: conteo protegido actual menos anterior para inicios, finales, reseñas públicas o comentarios/reacciones. Es **diferencia absoluta**, no variación porcentual. |

Se requiere una comunidad de al menos **diez participantes** con actividad en las fuentes consideradas de los dos períodos; cada desglose requiere **cinco contribuyentes**. IND-003 exige cinco abandonos y cinco finales. Las categorías pequeñas se suprimen, por lo que IND-004 no representa etiquetas omitidas. El helper actual de conteos es `R(x) = 5 × floor((x + 2) / 5)`; para conteos enteros redondea al múltiplo de cinco más cercano y también se aplica a pesos de categorías. El redondeo a medio punto de valoraciones es `floor(2 × media + 0,5) / 2`.

El recorrido clásico de `resumenes_grupales` calcula además participantes, inicios, finales, abandonos y reseñas con umbrales y límites por persona. Para su media grupal primero obtiene la media de cada participante y luego promedia participantes con igual peso, redondeando a medio punto. No debe confundirse con la media por obra de S01 ni con IND-006.

### Reglas para consultar e interpretar

- Elige una ejecución/corte coherente y la procedencia adecuada; no mezcles manuales y diarios para sumar actividad.
- Suma indicadores diarios solo cuando su definición sea aditiva y las fechas no se solapen. Para L09 de varios días también puedes recalcular fechas locales distintas de eventos elegibles; no sumes el booleano de una carga manual como días.
- Recalcula lectores/obras distintos sobre todo el período: sumar únicos diarios puede duplicarlos.
- Recalcula porcentajes y medias desde sus componentes; denominador vacío significa ausencia de datos.
- Catálogo vigente y estados actuales no reconstruyen atributos eliminados o cambios anteriores que no se versionaron.
- Los agregados protegidos reducen exposición, pero no acreditan anonimización formal ni representatividad del mercado. Los hechos con titular y la evidencia textual permanecen privados.
- No todo indicador propuesto en `analytics-catalog.md` está implementado: esta sección identifica cálculos encontrados en código y los separa de generación narrativa con Gemini.

Fuentes verificables: [transformación ETL](apps/backend/app/modules/analytics/etl.py), [proyecciones](apps/backend/app/modules/analytics/projections.py), [indicadores comunitarios](apps/backend/app/modules/analytics/community.py), [evidencia y agregación clásica](apps/backend/app/modules/analytics/insights.py), [migraciones](apps/backend/migrations/versions). Los reportes históricos no sustituyen las fórmulas de estas implementaciones.

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

## Funciones adicionales del administrador del sistema

Además de las funciones personales habilitadas para su cuenta, el administrador dispone de herramientas para operar la plataforma. El acceso efectivo se comprueba con el permiso de cuenta **`admin`** en backend; una etiqueta pública de perfil no basta. El menú consulta `/api/roles/access` y muestra las herramientas según permisos y flags.

### Pantallas y capacidades

| Acceso | Funciones adicionales | Condiciones y trazabilidad |
|---|---|---|
| **Gestionar perfiles** — `/admin/profiles` | Buscar cuentas por nombre, correo o username según el mantenedor; paginar y filtrar por tipo o estado. Consultar cuentas activas, suspendidas, pendientes de eliminación y anonimizadas. | Acceso administrativo. La información de cuentas no se convierte en un directorio público. |
| **Cuentas**, dentro de Gestionar perfiles | Suspender o levantar la suspensión de otra cuenta; autorizar un cambio excepcional de username; cambiar el tipo de perfil cuando se cumplen las reglas. | Motivo requerido; auditoría de cuenta. Cambios de suspensión/tipo revocan sesiones. No permite modificar la propia suspensión ni cambiar el propio tipo. |
| **Verificación profesional** — Gestionar perfiles | Solicitar revisión para otra cuenta como autor, influencer o librería; consultar pendientes y aprobar/rechazar solicitudes mediante revisión administrativa. | No hay verificador automático. Asignar un tipo profesional requiere la verificación aprobada correspondiente. Se registra la decisión y su responsable. |
| **Perfil público e historial** — Gestionar perfiles | Editar nombre visible/biografía desde el mantenedor; consultar solicitudes, cambios de tipo y auditoría de cuenta con actor, motivo, fecha, correlación y antes/después disponibles. Revocar un tipo profesional mediante el cambio permitido a lector. | Se aplican límites y dependencias del servicio. La revocación no equivale a borrar automáticamente publicaciones históricas ni garantiza que cualquier cambio sea admisible. |
| **Configurar aplicación** — `/admin/environment` | Consultar/editar las variables admitidas de Backend y Web. Los secretos se muestran como configurados, sin revelar su valor, y pueden reemplazarse. | Validación de valores, revisión para detectar cambios concurrentes y escritura atómica. No hay historial persistente completo de estas ediciones. Cambios pueden requerir reiniciar procesos o recompilar frontend. |
| **Modo demostración** — Configurar aplicación | Activar/desactivar el generador ficticio, ajustar intervalo de 10 a 3600 segundos y consultar progreso, última ejecución/error, libros preparados y pendientes. | Requiere migración 0087, descubrimiento de catálogo y contraseña demo válida. Guarda último administrador/fecha de configuración; no un historial completo de cada cambio del interruptor. Detener conserva contenido e historial. |
| **Carga de datos** — `/admin/etl` | Consultar cierres y ejecuciones manuales, próxima ejecución, estado/fase, corte, cantidades y validaciones; solicitar **Ejecutar ETL ahora**. | Solicitud identificada por UUID, idempotencia y conflicto si otro ETL está activo. Prepara datos de todos los titulares elegibles; no muestra sus textos privados ni invoca Gemini directamente. |
| **Moderación de contenido** — `/settings?tab=moderation` | Revisar propuestas pendientes, contenido/adjuntos autorizados, alertas y versiones; aprobar/rechazar, revisar reportes y resolverlos con las acciones admitidas, incluido ocultar/restaurar contenido cuando corresponde. Consultar historial. | Motivo, versión esperada, controles de concurrencia y auditoría; notificaciones privadas al autor. Un reporte por sí solo no oculta contenido. |
| **Gestionar libros** — `/admin/catalog` | Inventario por título/autor/ISBN; filtros de posibles duplicados, sin portada o sin ISBN. Crear/corregir obras y ediciones, revisar fuentes y correcciones. | Mantenedor requiere `CATALOG_DISCOVERY_ENABLED` y `CATALOG_ADMIN_PREVIEW_ENABLED`, además del permiso administrativo y condiciones del servicio. Guardados con motivo, idempotencia, versión y auditoría. |
| **Agrupación bibliográfica** — Gestionar libros | Comparar obras, simular agrupación, validar impacto, resolver conflictos y consultar historial; ejecutar agrupación o simular/ejecutar reversión si están habilitadas. | Simular no equivale a ejecutar. La ejecución exige flags adicionales, confirmación, motivo y controles de conflicto; `CATALOG_ADMIN_MERGE_ENABLED` está restringido por configuración a desarrollo/test con sus dependencias. |
| **Importación autorizada de catálogo** — API administrativa | Incorporar una referencia externa validada con motivo y clave de idempotencia. | Requiere descubrimiento habilitado. No debe confundirse con la búsqueda de un libro ni con importación masiva automática. |

El mantenedor de libros puede estar oculto o devolver 404 aunque la cuenta sea administradora si sus flags están apagados. No los actives en bloque sin revisar el estado y contrato del catálogo. Las correcciones de metadatos no reescriben el total de páginas fijado en intentos de lectura anteriores.

### Reglas especiales de gestión de cuentas

- Cambiar una cuenta a administrador concede su permiso administrativo; retirarlo mediante cambio de tipo exige conservar otro administrador activo.
- No se permite cambiar el propio tipo. Cambios profesionales pueden bloquearse por publicaciones asociadas al tipo anterior; pasar a librería requiere archivar antes la biblioteca personal y conservar su historial.
- Las cuentas anonimizadas no admiten cambios ordinarios de suspensión/username. Recuperar una eliminación pendiente no levanta una suspensión independiente.
- La creación directa antigua de librerías mediante `POST /api/roles/bookstores` devuelve **410**. El flujo vigente es la verificación profesional de una cuenta existente; un texto antiguo de interfaz que diga «crear librerías» no reemplaza ese contrato.
- El registro público no permite autoasignarse administración. Para el primer acceso se usa la semilla autorizada o `scripts.grant_admin`, ejecutado por quien opera el servidor.

### Referencia de API administrativa

Todas las rutas siguientes usan el prefijo `/api` y requieren autenticación/permisos; parámetros y cuerpos exactos se consultan en Swagger o en los routers.

| Familia de rutas | Operaciones |
|---|---|
| `/api/accounts/admin` | Listado de cuentas; subrutas `/{user_id}/suspension`, `/username`, `/role`, `/verification` y `/history`. |
| `/api/roles/profiles` y `/api/roles/requests` | Perfiles, edición pública, solicitudes, historial, revocación y decisiones de verificación. |
| `/api/admin/environment/{backend\|web}` | GET de configuración enmascarada y PATCH de variables admitidas. |
| `/api/admin/demo` | GET de estado y PATCH de activación/intervalo. |
| `/api/analytics/admin/etl` | GET de historial/resumen, POST en `/run` y GET de `/{run_id}/validations`. |
| `/api/admin/moderation` | Cola, detalle/adjuntos, historial y decisiones; `/reports` contiene revisión y resolución de reportes. |
| `/api/admin/catalog` | Inventario, obras/ediciones, importaciones, comparación, simulaciones, ejecución y reversión condicionadas por flags. |

### Límites del rol y operación del servidor

La administración **no concede lectura general de cuadernos, notas, teorías, reseñas privadas o análisis personales de otras personas**. Los permisos para moderar propuestas/adjuntos corresponden a ese recorrido concreto. Tampoco concede por sí sola acceso profesional a Insights grupales, suprime umbrales de privacidad ni habilita las interpretaciones Gemini pendientes.

Ejecutar un ETL manual puede preparar trabajos de análisis elegibles, pero consultar estados o tener permiso administrativo no permite saltarse el corte del análisis individual mediante su endpoint refresh. Activar flags de Gemini tampoco garantiza un resultado si faltan evidencia, cuota, presupuesto o proceso worker.

Respaldar/restaurar PostgreSQL, aplicar Alembic, reiniciar procesos, revisar logs del host, rotar credenciales externas y desplegar contenedores requieren **acceso operativo al servidor**. Son tareas descritas en esta guía, no permisos que el rol web otorgue automáticamente. No se documenta un panel web de borrado arbitrario de bases ni de ejecución libre de comandos del sistema.

Referencias: [cuentas y restricciones](docs/cuentas-usuario.md), [mantenedor de libros](docs/catalog-maintenance.md), [ETL](docs/etl-daily.md), [moderación](docs/moderation-stage4-results.md), [ubicación de moderación](docs/moderation-access-fix.md) y [modo demo](docs/demo-mode.md).

## Seguridad de la información, ciberseguridad y auditoría

Esta sección reúne **controles implementados y evidencia versionada**, sus mecanismos de auditoría y sus límites. Se contrastó con el código y las migraciones; no constituye una auditoría externa, prueba de penetración, certificación de cumplimiento ni una nueva ejecución de las pruebas citadas. La trazabilidad cubre recorridos concretos: **no existe todavía una auditoría universal de todas las acciones y solicitudes HTTP**.

### Controles y acciones implementadas

| Área | Acción implementada | Alcance y límite |
|---|---|---|
| Contraseñas | Hash Argon2 mediante `pwdlib`; comparación del hash al autenticar. Operaciones sensibles requieren contraseña actual. | No se almacena contraseña de usuario en texto plano. Esto no cifra automáticamente la base ni los `.env`. |
| Tokens y sesiones | JWT con tipo, sujeto, sesión, identificador, emisión y expiración; validación de claims y firma con algoritmo permitido. Sesión persistida, refresh rotativo y almacenamiento de su hash; detección de reutilización y revocación. | Access de corta duración, inactividad y máximo absoluto separados. El access token del navegador sigue en `localStorage`. |
| Credenciales y estado de cuenta | Cambio/restablecimiento de contraseña, cambio confirmado de correo, desvinculación Google y restricciones críticas invalidan sesiones/desafíos según la operación. Versión de seguridad invalida intenciones OAuth en curso. | Una sesión revocada no se recupera solo conservando el JWT. El worker verifica que el titular siga activo antes de llamar a IA. |
| Recuperación de cuenta | Tokens aleatorios de 256 bits, solo SHA-256 persistido, expiración de diez minutos y uso único. Reenvío con espera de un minuto por cuenta/propósito. Respuesta de recuperación sin confirmar existencia de cuenta. | El límite de desafíos no equivale a una protección global contra fuerza bruta, abuso distribuido o denegación de servicio. |
| OAuth Google | Estado aleatorio vinculado al navegador mediante cookie HttpOnly temporal, comprobaciones antes de completar autorización y vinculación por identidad Google. | No se vinculan cuentas únicamente por coincidencia de correo. Los avisos de OAuth incompleto en la revisión de octubre describen una etapa histórica. |
| Autorización | Comprobaciones de sesión, titularidad, permiso administrativo y capacidad/membresía profesional en backend. Estados privados y adjuntos de moderación requieren acceso autorizado. | Ocultar controles en React no concede ni reemplaza permisos. Ser administrador no habilita automáticamente análisis personales ajenos. |
| Configuración de producción | Valida secreto JWT propio de al menos 32 caracteres, rechaza valores de desarrollo y exige orígenes HTTPS explícitos y cookie segura fuera de desarrollo/test. CORS se limita a orígenes configurados. | CORS no sustituye autenticación, CSRF ni un firewall; estos controles no instalan TLS en el servidor. |
| Contenido y archivos | Descripciones bibliográficas renderizadas como texto y restricciones de protocolos en enlaces. Validación de imágenes y límites por tipo de recurso. Avatares se decodifican y recodifican para retirar metadatos. | No se debe extender la garantía de recodificación de avatares a todos los adjuntos. No hay certificación de ausencia de XSS en toda la aplicación ni antivirus general acreditado. |
| Moderación | Propuestas privadas, reglas versionadas, reportes, decisiones motivadas, comprobación de versiones y acceso a contenido según visibilidad. Decisión, auditoría y notificación se publican transaccionalmente. | Reportar no oculta automáticamente. Moderación de contenido no sustituye controles de infraestructura o autorización. |
| Integridad y concurrencia | Transacciones, claves únicas, bloqueos de filas/asesores, idempotencia y controles de versión en comandos sensibles. ETL concilia cantidades y publica atómicamente. | Protege los caminos implementados; no garantiza escrituras directas de terceros que omitan servicios o controles. |
| Privacidad analítica | Aislamiento por titular, procedencia explícita, salidas grupales con umbrales, límites de contribución, supresión y redondeo. Tablas privadas de preparación revocan acceso de `PUBLIC` donde lo declaran las migraciones. | Es seudonimización/preparación restringida y publicación agregada limitada; no anonimización formal ni aislamiento frente a credenciales técnicas de la base. |
| IA externa | Worker apagado por defecto, activación explícita, evidencia delimitada como datos no confiables, validación de contratos/citas y candidatos; presupuestos de llamadas/tokens y costos, leases y reintentos acotados. | Reduce generación inválida y abuso de consumo; no elimina inyección de instrucciones, errores semánticos o transferencia de datos privados al proveedor. Una llamada ya enviada no puede deshacerse. |
| Secretos | `.env`, respaldos locales y artefactos sensibles excluidos de versionado/construcción según `.gitignore`/`.dockerignore`; campos sensibles ocultos en lectura del mantenedor de entorno. | Exclusión Git no cifra archivos ni elimina secretos previamente publicados. `VITE_*` forma parte del cliente público. |
| Disponibilidad y recuperación | Migraciones explícitas, respaldo previo en setup, chequeo de revisión antes de arrancar, cola persistente, recuperación de leases/cierres y volumen PostgreSQL. | No acredita alta disponibilidad, restauraciones periódicas verificadas ni un objetivo RPO/RTO comprometido. |

Referencias de implementación: [seguridad JWT/contraseñas](apps/backend/app/core/security.py), [sesiones](apps/backend/app/modules/auth/sessions.py), [configuración](apps/backend/app/core/config.py), [gestión de cuentas](apps/backend/app/modules/users/account_service.py), [autorización de contenido](apps/backend/app/modules/social/activity_access.py) y [worker Gemini](apps/backend/app/modules/analytics/gemini_worker.py).

### Registros de auditoría y evidencia técnica

| Registro | Qué permite reconstruir | Protección / límite |
|---|---|---|
| `app.auditoria_cuentas` | Cuenta afectada, actor, acción, origen, fecha, UUID de correlación, motivo e instantáneas anterior/posterior con campos permitidos. Incluye gestión de cuenta, recuperación y acciones administrativas. | Cambio crítico y auditoría comparten transacción. Trigger impide modificar/borrar, con excepción limitada de minimización de campos identificables tras anonimización. No registra contraseñas, sus hashes, tokens ni credenciales. |
| `app.auditoria_identidades` | Perfil afectado, actor, acción, detalle y fecha de operaciones de identidad. | Su estructura no es idéntica a la de cuentas: no debe suponerse que tiene el mismo UUID de correlación o antes/después. |
| `app.auditoria_moderacion` | Revisión o reporte afectado, actor, acción, motivo y fecha; contexto anterior/resultante en decisiones que lo incorporan. Se relaciona con propuestas, reportes y notificaciones. | Trigger de solo adición; versiones y conflictos evitan aplicar decisiones sobre contenido cambiado. Puede contener contexto de contenido: su consulta es restringida. |
| `app.simulaciones_fusion` y registros de decisiones canónicas | Administrador, obras implicadas, huella, resultado y fecha de simulaciones; decisiones de identidad cuando están habilitadas. | Simulaciones inmutables, caducidad y flags de despliegue. No implica que las fusiones estén habilitadas en todos los entornos. |
| `app.selecciones_edicion_lectura` | Selecciones explícitas de edición asociadas a una lectura en el contrato de progreso opcional. | Registro protegido contra modificación/borrado; no es un registro de todas las consultas al catálogo. |
| Sesiones persistidas | Sesión vinculada al usuario, fechas de vigencia/actividad, generación refresh y motivo/fecha de revocación. | Estado de seguridad de sesión; no es un historial completo de navegación ni de todos los intentos fallidos de login. |
| `analytics.ejecuciones_etl`, `validaciones_etl` y hechos | Quién solicitó una ejecución manual, intervalo/corte, versión, estado, intentos, cantidades, reglas y registros de origen incluidos. | Las claves ejecución/origen permiten explicar un corte y exclusiones contadas; no se conservan necesariamente los textos o filas completas rechazadas. |
| `analytics.projection_runs` y punteros vigentes | Titular, versión de transformación, hash, evidencia JSON y fechas de proyección; `reader_current` identifica la versión actual. | Historial técnico de proyecciones sujeto a políticas de conservación/minimización; no equivale a log inmutable externo. |
| `ia.jobs`, perfiles/instantáneas y resultados | Titular, tipo de trabajo, evidencia/huella, versión de perfil, modelo/prompt, ejecución ETL cuando corresponde, estado, intentos y resultado publicado. | Se distinguen la preparación al corte, los intentos y el resultado vigente/histórico. Las comprobaciones de elegibilidad pueden retirar resultados o textos derivados. |
| `ia.call_ledger`, `ia.usage_metrics` | Llamada e intento, ordinal, modelo/fase, reservas, contadores disponibles, errores, duración, identificador remoto cuando existe y costo estimado. | Un consumo ambiguo puede quedar pendiente de reconciliación; falta de contadores no acredita costo cero. No sustituye factura del proveedor. |

Las restricciones de solo adición protegen frente a operaciones ordinarias de la aplicación. **No son una firma digital, cadena criptográfica ni almacenamiento WORM externo**: quien controle la administración de PostgreSQL puede tener capacidad para alterar esos mecanismos. Los hashes permiten comparar contenido/versión; por sí solos no prueban autoría o integridad frente a un administrador comprometido.

### Recorrido de trazabilidad de un análisis

Para investigar un resultado, conserva los identificadores técnicos y sigue el recorrido correspondiente:

1. **Origen:** obra/edición, entrada de biblioteca, lectura y evento; reseña/revisión o aporte que sustenta el análisis. Comprueba titularidad, visibilidad y procedencia.
2. **Preparación:** localiza `etl_run_id` o `analytics_run_id`, según el flujo; revisa corte, versión de transformación/identidad, estado, validaciones y fuentes. No todos los resultados usan la misma clase de ejecución.
3. **Evidencia autorizada:** identifica versión de perfil o snapshot de lectura, su huella y vínculo con el corte. En el código actual estas entradas de IA están parcialmente en `ia`, como se explica en arquitectura.
4. **Trabajo:** busca `job_id` y revisa tipo, propietario, modelo, versión de prompt, intentos, estado y error. La identidad del evento distingue una relectura de otra.
5. **Llamadas:** consulta el ledger por trabajo/intento; distingue llamadas completadas, fallidas y consumo pendiente. Contrasta identificador remoto y métricas disponibles sin publicar evidencia privada.
6. **Resultado:** verifica resultado persistido, referencias de evidencia, versión vigente/histórica y fechas. Una respuesta estructuralmente válida no prueba la corrección de todas sus conclusiones.

La auditoría de cuentas usa su propio `correlation_id`; el análisis usa ejecuciones, hashes, eventos y jobs. **No hay un identificador global propagado a todas las capas**. No se debe afirmar que una edición de `.env`, una llamada HTTP y un cargo Google se unen automáticamente en una sola cadena de auditoría.

### Revisiones y auditorías documentadas

| Evidencia en el repositorio | Alcance documentado | Cómo interpretarla |
|---|---|---|
| [Revisión de seguridad del 4 de octubre de 2026](docs/security-review.md) | Hallazgos/correcciones sobre HTML externo, OAuth state, configuración JWT, propiedad, privacidad, concurrencia y roles. | Es histórica: parte de sus pendientes fue implementada después. No es un pentest ni describe por sí sola todo el estado actual. |
| [Gestión de cuentas](docs/cuentas-usuario.md) y migraciones `0061`–`0067` | Recuperación, revocación, minimización de cuentas, desafíos, versión de seguridad y auditoría. | Distingue la protección del registro administrativo de la eliminación integral de contenido personal, que no está garantizada. |
| [Auditoría de consumo Gemini del 28 de octubre](docs/gemini-usage-audit-2026-10-28.md) | Inspección de flujos, contabilidad de tokens/costos y límites del consumo. | Auditoría técnica de ese alcance; no auditoría integral de ciberseguridad. |
| [Corrección y validación Gemini](docs/gemini-optimization-2026-10-28.md) | Ledger, reservas, metadatos, recuperación y pruebas con proveedor simulado/PostgreSQL aislado. | El reporte declara su modalidad y límites; no demuestra nuevas inferencias reales ni facturación en esta actualización del README. |
| [Moderación: etapa 1](docs/moderation-stage1-results.md), [etapa 2](docs/moderation-stage2-results.md), [etapa 3](docs/moderation-stage3-results.md), [etapa 4](docs/moderation-stage4-results.md) y [corrección de acceso](docs/moderation-access-fix.md) | Preparación privada, integración, decisiones/reportes, auditoría contextual, notificaciones y acceso de interfaz. | Evidencia por etapa; las correcciones posteriores prevalecen sobre rutas y estados anteriores. |

Existen pruebas de contratos y seguridad en [test_security.py](apps/backend/tests/test_security.py), [sesiones](apps/backend/tests/test_stage4_sessions_and_triggers.py), [cuentas](apps/backend/tests/test_account_management.py), [concurrencia de cuentas](apps/backend/tests/test_account_concurrency.py), [OAuth](apps/backend/tests/test_google_login.py), [moderación](apps/backend/tests/test_moderation_administration.py) y [worker](apps/backend/tests/test_stage5_gemini_worker.py). Su presencia no equivale a ejecución aprobada en tu entorno. Para repetirlas usa una base aislada y los flags exigidos; no pruebes ataques ni mutaciones sobre datos compartidos.

### Brechas y cobertura pendiente

- **Auditoría de configuración:** el mantenedor `.env` comprueba administración, oculta secretos en lectura, valida campos, detecta cambios mediante hash de revisión y reemplaza el archivo de forma atómica. El código actual no añade un historial persistente de actor, motivo y antes/después de esa edición. El bloqueo del mantenedor es por proceso; no debe presentarse como coordinación distribuida completa.
- **Protección web:** access token en `localStorage`, ausencia de token CSRF separado y cabeceras CSP/HSTS completas pendientes de despliegue. La cookie `SameSite=Lax` no resuelve todos los escenarios de ataque.
- **Defensa perimetral:** no se acredita MFA, rate limiting global de login/API compartido entre réplicas, WAF, detección centralizada de intrusiones ni protección DDoS mediante estos componentes de aplicación.
- **Infraestructura y secretos:** no se acredita cifrado de discos/backups, TLS de conexión PostgreSQL, gestor externo de secretos o rotación automatizada en todos los entornos. Las configuraciones locales no equivalen a esos controles.
- **Registro operativo:** falta una correlación global de solicitudes y una política integral acreditada de retención, acceso, exportación, alertas y conservación externa de evidencias. Logs técnicos pueden contener información sensible; no deben compartirse sin revisión.
- **Privacidad y baja:** la minimización de cuenta preserva relaciones/historial; no garantiza retirar datos personales escritos dentro de textos, motivos administrativos, evidencias o snapshots históricos. Requiere revisión de retención por tipo de dato.
- **Aseguramiento:** esta revisión documental no ejecuta pentest, análisis dinámico, escaneo de secretos, auditoría actualizada de dependencias, pruebas de carga ni ejercicios de restauración/respuesta a incidentes. Los reportes anteriores no sustituyen esas verificaciones antes de producción.

Ante un incidente, la investigación debe conservar los IDs de cuenta/sesión, ejecución/evento/job y marcas de tiempo relevantes, con acceso restringido. Revocar sesiones o detener el worker evita parte de la actividad posterior, pero no revierte llamadas externas ni elimina una credencial comprometida del proveedor; la rotación y recuperación deben coordinarse en el servicio afectado. Este apartado describe capacidades y brechas existentes, no acredita un plan de respuesta a incidentes ya implantado.

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
