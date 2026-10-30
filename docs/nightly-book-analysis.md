# Análisis individual coordinado por ETL con Gemini

El análisis interpreta una experiencia concreta de lectura. Requiere un evento
`finish` o `abandon`, una lectura todavía `finished` o `abandoned`, una entrada
activa de biblioteca y exactamente una reseña personal vigente de la obra
canónica. El texto de la reseña debe contener algo distinto de espacios;
las puntuaciones solas no bastan. No exige diez libros.

Las reseñas siguen perteneciendo a la obra. Cada análisis y cada trabajo se
asocian explícitamente al evento y al propietario. Se muestra el último evento
terminal del libro; no se usa el análisis de otra relectura para completarlo.
La edición es opcional. Una reseña privada es válida: `draft` y `hidden`
controlan su visibilidad comunitaria y no equivalen a eliminarla. Cambiar esa
visibilidad sin modificar el contenido no provoca otra generación.

## Solicitud y corte del ETL

La migración `0069_nightly_book_analysis` crea solicitudes duraderas por evento
en `ia.reading_analysis_requests` e instantáneas privadas en
`ia.reading_analysis_snapshots`. Los disparadores de cambios de reseña, lectura,
reflexión, biblioteca, nota y teoría registran cambios en la misma transacción.
No llaman a Gemini ni crean trabajos ejecutables.

El ETL diario conserva su horario de las 00:00 de Santiago. Tanto su publicación
como la de un ETL manual iniciado por un administrador preparan trabajos de
`reading_event_analysis` usando la infraestructura `ia.jobs` existente. Solo
considera solicitudes anteriores al corte exclusivo; un cambio posterior espera
al siguiente ciclo automático o manual. La proyección incremental no habilita
análisis individuales. La preparación es transaccional e idempotente.
El resumen del ETL registra preparados, reutilizados y no elegibles.

El worker consume la instantánea autorizada y verifica nuevamente elegibilidad
y huella antes de usar el proveedor. El antiguo retraso de treinta minutos ya
no gobierna este flujo; su configuración permanece por compatibilidad.
`POST /api/me/ai/books/{book_id}/refresh` consulta el estado, incluso con
`force=true`: no salta el ETL automático o manual ni reinicia intentos.

## Evidencia, versiones y privacidad

Se incluyen reseña, puntuaciones, reflexión, motivo de abandono, cuaderno,
notas y teorías propias, datos de lectura y contexto bibliográfico. Nunca se
envía el texto completo del libro. La huella ordena las unidades, normaliza
espacios e ignora el contador de revisión de reseña y el contador global del
catálogo. No incluye portadas ni imágenes de reseñas. Incorpora la versión
`nightly-reading-v1` del contrato; la reutilización también exige mismo modelo
y versión del prompt. Un cambio de contrato debe incrementar esa versión.

Los cambios se consolidan en una sola versión de evidencia por cierre. Volver
al contenido ya analizado reutiliza el resultado compatible. Las consultas GET
leen PostgreSQL sin inferencias ni creación de trabajos. No hay caché adicional.

Mientras cambia la evidencia se conserva el último resultado permitido, marcado
como anterior. Un resultado generado durante un cambio se conserva como historia
de su instantánea; nunca se identifica como vigente para una huella distinta.
La evidencia nueva espera al siguiente cierre. Se serializa la publicación con
el registro de cambios del evento. La eliminación de fuentes retira los textos
derivados y las instantáneas afectadas conforme a la política previa. Una reseña
ausente o vacía impide mostrar el análisis o su historial.

La autorización se comprueba en backend con la sesión del propietario. Historial:
`GET /api/me/ai/books/{book_id}/history`, paginado mediante límite de hasta 100
resultados. No se exponen textos privados en estados ni registros de errores.

El contrato mantiene las categorías anteriores y agrega
`observation_evidence`: campo, índice y evidencias de cada observación, incluido
el resumen. Desde `reading-event-v3-es` el transporte a Gemini usa un esquema
inline reducido y cada observación lleva su texto y citas juntos. El backend
construye determinísticamente los índices del contrato persistido; el modelo
no tiene que sincronizar listas paralelas. Las cotas completas se siguen
validando localmente, sin multiplicarlas en la gramática del proveedor.
Se valida cobertura y existencia de citas; esto no constituye una
verificación semántica. El prompt prohíbe inventar experiencias, diagnósticos,
confundir argumento con vivencias y obedecer instrucciones de las fuentes.

## Interfaz y errores

| Estado | Comportamiento |
|---|---|
| `not_eligible` | Terminar o abandonar la lectura. |
| `requires_review` | «Tu historia aún guarda secretos» y acción para escribir reseña. |
| `waiting_nightly_processing` | «¡Tu lechuza está lista para partir!», sin sondeo. |
| `queued` | Historia preparada; espera disponibilidad. |
| `processing` | «¡Tu lechuza ha partido!». |
| `completed` | Muestra directamente el resultado, sin bienvenida repetitiva. |
| `update_pending` | «Tu historia tiene nuevos secretos», anterior visible y señalado. |
| `update_processing` | «Una nueva lechuza está en camino», anterior visible. |
| `failed` | «La lechuza encontró una tormenta», conserva resultado previo permitido. |

El nombre compatible `waiting_nightly_processing` representa la espera del
próximo ETL automático o manual administrativo, no una prohibición de adelantarlo.

Cuando la configuración de generación está desactivada, los estados de libros
y recomendaciones exponen `generation_enabled=false` y su motivo. La interfaz
indica la pausa y detiene el sondeo de trabajos pendientes, manteniendo los
resultados anteriores. Este indicador refleja configuración, no un monitoreo
de procesos. `AI_WORKER_ENABLED` es una clave antigua; el proceso Gemini usa
`GEMINI_WORKER_ENABLED` y requiere la autorización operativa existente. El ETL
puede preparar solicitudes aunque el consumidor esté desactivado.

El presupuesto compartido de USD 10, máximo configurado de tres intentos,
concurrencia, límites por minuto, tokens, reservas y métricas existentes se
mantienen. Los errores transitorios usan la política limitada del worker. Un
fallo definitivo no promete reintentos; «Actualizar estado» solo consulta.
Si quedan intentos, «Programar reintento» registra la recuperación
mediante `POST /api/me/ai/books/{book_id}/retry`; únicamente el siguiente ETL automático o manual
habilita de nuevo el mismo trabajo, sin reiniciar contadores. Al agotarlos se
indica contactar con soporte.

ADN lector y recomendaciones mantienen sus reglas e infraestructura; el mínimo
de diez libros sigue aplicándose donde ya correspondía. Esta implementación
reemplaza las descripciones anteriores de Ollama para el análisis individual;
los documentos de auditoría y `legacy/ollama` son antecedentes históricos.

## Verificación sin Gemini real

Desde `apps/backend`: `.venv/Scripts/python.exe scripts/test_nightly_reading.py`.
El script inicia un clúster PostgreSQL temporal en loopback, migra desde cero,
ejecuta el proveedor simulado y elimina exclusivamente su base temporal. No
requiere permisos de administrador de la base de desarrollo ni usa sus datos.
Configurar `PG_BIN` si los binarios no están en PostgreSQL 17 de Windows.

Las pruebas de integración verifican también la publicación manual completa,
su corte exclusivo, idempotencia, ejecución posterior del proveedor simulado
y conservación del análisis anterior durante una actualización.

Desde `apps/web`: `node tests/book-analysis-state.mjs`, `npm run build` y
`npm run lint`. El frontend es JavaScript y no tiene un script separado de tipos.
