# Etapa 6: preparación operativa Gemini

Actualización del análisis individual: [contrato nocturno vigente](nightly-book-analysis.md).
Las restantes secciones conservan el contexto de la etapa operativa original.

Estado al 27 de octubre de 2026. Esta etapa no activa producción ni realiza
solicitudes reales. El proveedor nuevo queda desactivado por defecto mediante
`GEMINI_WORKER_ENABLED=false` y `GEMINI_PAID_SERVICE_CONFIRMED=false`.

## Arquitectura activa

FastAPI solo sirve HTTP. `python -m scripts.run_scheduler` ejecuta recuperación
de ETL manual, cierre nocturno y proyecciones. `python -m
scripts.run_gemini_worker` consume exclusivamente trabajos `provider=gemini`
de tipo `recommendation` o `reading_event_analysis`. PostgreSQL conserva cola,
leases, evidencias, resultados, intentos y costes. El frontend solo consulta
FastAPI. Varias réplicas API no crean workers adicionales.

Ollama no tiene transporte, configuración, instalador ni proceso activo. Su
implementación está comentada línea por línea en
`apps/backend/legacy/ollama/`. Las filas históricas conservan
`provider='ollama'`; la migración 0052 cambia únicamente el valor por defecto
para filas nuevas a `gemini`.

## Clasificación de endpoints de IA

| Ruta | Clase | Comportamiento |
|---|---|---|
| `GET /api/analytics/me/recommendations/state` | Lectura | Estado y resultado persistido; nunca encola. |
| `POST /api/analytics/me/recommendations/sync` | Sincronización | Comprobación barata e idempotente; puede crear un único job deduplicado. |
| `GET /api/analytics/me/recommendations` | Lectura compatible | No llama al proveedor. |
| `POST /api/analytics/me/recommendations` | Heredado deshabilitado | HTTP 405; no admite tandas manuales. |
| `GET /api/me/ai/books/{work_id}` | Lectura | Último análisis persistido de evento terminal. |
| `POST /api/me/ai/books/{work_id}/refresh` | Lectura de estado | Recupera PostgreSQL sin adelantar la preparación nocturna. |
| `POST /api/me/ai/books/{work_id}/retry` | Recuperación limitada | Registra un reintento para el siguiente cierre; conserva intentos y costos. |
| `GET /api/me/ai/books/{work_id}/history` | Lectura privada | Versiones permitidas de la misma experiencia. |
| `GET /api/me/ai/profile` | Lectura | Perfil Gemini persistido ligado a recomendaciones. |
| `POST /api/me/ai/profile/refresh` | Heredado deshabilitado | HTTP 405. |
| `GET /api/me/ai/profile/history` | Lectura | Historial, incluido proveedor histórico. |
| `POST /api/me/ai/feedback` | Feedback | Persiste feedback sin crear un segundo job por evento. |
| `GET /api/analytics/me/insights` | Lectura | Indicadores y resultado clásico histórico, si existe. |
| `POST /api/analytics/me/interpretation` | Pendiente explícito | HTTP 501; falta contrato Gemini aprobado. |
| `GET /api/analytics/group/insights` | Lectura | Agregados y resultado grupal histórico, si existe. |
| `POST /api/analytics/group/interpretation` | Pendiente explícito | HTTP 501; falta contrato Gemini grupal aprobado. |

Login, sesión Google y actividad autenticada llaman la sincronización segura de
recomendaciones. Una lectura de pantalla, un GET, un refresh del navegador o el
montaje de React no crean trabajo. El análisis individual exige un evento
`finish`/`abandon` y una reseña textual válida. El ETL nocturno o manual administrativo habilita
su trabajo; la ventana fija de treinta minutos ya no gobierna este flujo.

## Costes y límites

El modelo estable verificado es `gemini-3.5-flash-lite`, compatible con salida
estructurada. La tarifa standard pagada verificada es USD 0,30 por millón de
tokens de entrada y USD 2,50 por millón de tokens de salida, incluido
razonamiento:

- https://ai.google.dev/gemini-api/docs/models/gemini-3.5-flash-lite
- https://ai.google.dev/gemini-api/docs/pricing

Las tarifas no están ocultas: `AI_INPUT_COST_PER_MILLION_USD` y
`AI_OUTPUT_COST_PER_MILLION_USD` deben revisarse al cambiar modelo. Valores
cero o negativos son inválidos. `AI_MONTHLY_BUDGET_USD` limita el gasto global
estimado. Antes de reclamar un job, PostgreSQL serializa la decisión y suma:
costes registrados del mes, una reserva por cada intento en curso y una reserva
para el intento nuevo. La reserva usa todos los tokens permitidos por trabajo a
la tarifa más cara, para cubrir timeouts facturables y reintentos. Al agotarse,
el job permanece pendiente hasta el mes siguiente con
`monthly_budget_exhausted`, visible como `budget_exhausted`.

También se aplican `AI_JOB_TOKEN_BUDGET`, `AI_MAX_CALLS_PER_JOB`, concurrencia
global con advisory locks, `AI_REQUESTS_PER_MINUTE`, intentos máximos, lease y
backoff. `ia.usage_metrics` registra tokens, duración, coste, llamadas y
fragmentos por intento. Alertas de Cloud Billing son una defensa adicional, no
el control primario.

## Revisión de privacidad

Fuentes oficiales revisadas:

- Términos Gemini API vigentes: https://ai.google.dev/gemini-api/terms
- Facturación y tratamiento pagado: https://ai.google.dev/gemini-api/docs/billing
- Logging y retención configurable: https://ai.google.dev/gemini-api/docs/logs-policy

El nivel gratuito permite que Google use entradas y salidas para mejorar
productos y que revisores humanos las procesen; los términos indican no enviar
información personal, sensible o confidencial. No es apropiado para notas y
teorías privadas de LibrIA. En el nivel pagado Google declara que no usa prompts
ni respuestas para mejorar sus productos y los procesa bajo su DPA, aunque
mantiene registros limitados para seguridad/abuso y datos técnicos. El logging
de proyecto pagado, si se habilita, conserva por defecto hasta 55 días y puede
configurarse a 7, 14, 28 o 55; compartir datasets es opt-in y no debe habilitarse.

LibrIA envía metadatos bibliográficos, valoraciones, reseñas, cuaderno, notas,
teorías, reflexión de cierre y feedback necesarios para el contrato. No envía
nombre, correo, token, cookie, clave API ni ID de cuenta. Sí envía referencias
UUID pseudónimas de evidencia para validar citas; sigue pendiente decidir si se
remapean a IDs efímeros antes de producción. Las evidencias y resultados se
autorizan siempre por titular en FastAPI y se persisten en PostgreSQL.

Decisiones bloqueantes pendientes: aprobación legal del DPA y región; confirmar
que las usuarias son mayores de 18 y que el producto cumple el uso profesional
o comercial exigido por los términos; consentimiento/texto de privacidad para
notas y teorías; política de retiro que invalide derivados; plazo local de
retención; desactivar logging/datasets compartidos; y evaluación de transferencia
internacional. Hasta resolverlas, no establecer
`GEMINI_PAID_SERVICE_CONFIRMED=true`.

## Despliegue futuro

`compose.yaml` define PostgreSQL 17, migración one-shot, API, scheduler único,
worker Gemini bajo el perfil `gemini` y frontend Nginx. No usa GPU. En VPS:

1. Crear volúmenes cifrados y backups probados de PostgreSQL.
2. Guardar secretos en el gestor del hosting, nunca en la imagen o Git.
3. Terminar TLS en un proxy con HTTPS, HSTS y cookies secure.
4. Ejecutar una sola réplica de `scheduler`; escalar API independientemente.
5. Activar una sola réplica inicial del worker y observar presupuesto/cola.
6. Ejecutar `migrate` antes de API/worker y disponer de restauración verificada.
7. Monitorizar salud, jobs atascados, presupuesto, expiración de sesiones y
   backups. No publicar puertos de PostgreSQL ni FastAPI a Internet.

## Procedimiento de prueba real controlada (no ejecutado)

Solo tras autorización expresa y aprobación legal:

1. Proyecto Google separado con billing, sin logging compartido ni datasets.
2. Configurar `GEMINI_MODEL=gemini-3.5-flash-lite`, clave efímera,
   `GEMINI_WORKER_ENABLED=true`, `GEMINI_PAID_SERVICE_CONFIRMED=true`, máximo 1
   worker, 1 solicitud concurrente y `AI_REQUESTS_PER_MINUTE=2`.
3. Insertar únicamente una usuaria y dos libros ficticios identificados como
   tales; textos: «reseña ficticia A», «nota ficticia B» y «teoría ficticia C».
   Verificar por consulta SQL que ninguna evidencia pertenece a cuentas reales.
4. Ejecutar como máximo dos llamadas, 8.000 tokens de entrada y 1.000 de salida
   por llamada. Con las tarifas verificadas, tope calculado: USD 0,0098; fijar
   `AI_MONTHLY_BUDGET_USD=0.02` durante la prueba.
5. Aceptar solo JSON válido, referencias de evidencia existentes, libros del
   catálogo ficticio, una fila de uso por intento y cero secretos/textos en log.
6. Desactivar inmediatamente el worker, revocar la clave, eliminar el proyecto
   de prueba si corresponde y retirar los datos ficticios mediante un proceso
   revisado. Cualquier aparición de datos reales, coste sobre el tope, respuesta
   no validada o reintento no previsto detiene la prueba.

## Pendiente funcional explícito

Las interpretaciones clásicas de indicadores personales y grupales siguen
legibles como historia, pero no generan resultados nuevos. Su migración futura
requiere dos job kinds, esquemas estructurados separados, privacidad grupal,
presupuesto y persistencia equivalentes al worker actual. No se ha implementado
ni activado esa ampliación en etapa 6.
