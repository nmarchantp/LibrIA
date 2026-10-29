# Corrección de Gemini: implementación y validación

Implementación posterior a la auditoría del 28 de octubre de 2026. No se ejecutaron generaciones reales de Gemini, no se habilitó facturación y no se modificó el .env. Las migraciones se ejecutaron únicamente en PostgreSQL desechable local, con API key vacía, worker y schedulers deshabilitados. El repositorio ya tenía cambios extensos: no se revirtieron.

## Archivos de esta intervención

- `app/modules/analytics/providers/base.py`: presencia/coherencia de metadatos; información técnica de errores.
- `app/modules/analytics/providers/gemini.py`: metadatos previos a validación, truncamiento, Retry-After y clasificación de cuota.
- `app/modules/analytics/call_accounting.py`: admisión atómica, registro por llamada, presupuestos acumulados y reconciliación.
- `app/modules/analytics/gemini_worker.py`: integración del ledger, límites, cachés, ADN independiente y recuperación de leases.
- `app/modules/analytics/reader_dna.py`: identidad de evidencia, lectura y solicitud independiente.
- `app/modules/analytics/persistence.py`: identidad del evento con modelo y ventana de consolidación configurable por trabajo.
- `app/modules/analytics/adaptive_router.py`: ADN independiente, compatibilidad de respuestas y reprocesamiento emocional explícito.
- `app/modules/analytics/free_usage.py`: usa el ledger nuevo sin duplicar agregados del intento; identifica llamadas pendientes de reconciliación.
- `app/modules/analytics/models.py`, `app/core/config.py`: modelos nuevos y versión de prompt ADN independiente.
- `migrations/versions/0054_gemini_ledger_dna.py`: migración aditiva, sin borrar filas históricas.
- `scripts/audit_gemini_usage.py`: auditoría compatible con instalaciones anteriores y con ledger, siempre READ ONLY.
- `apps/backend/README.md`: requisito de migración previo al arranque y enlace a esta validación.
- `tests/test_gemini_optimization.py`: pruebas nuevas con mocks y PostgreSQL aislado.
- `tests/test_stage5_gemini_worker.py`, `tests/test_analytics_projections.py`: compatibilidad de las pruebas con ADN independiente y cooldown compartido.
- `apps/web/src/components/AdaptiveAnalysis.jsx`: corrige exclusivamente el aviso de actualización del ADN, que ya no solicita recomendaciones.
- `apps/web/src/components/AiUsageBar.jsx`: muestra cuando existen consultas con consumo pendiente de confirmar, evitando presentarlo como cero verificado.

Las rutas del backend anteriores son relativas a `apps/backend/`.

## Costos y contabilidad

Se calcula con Decimal:

```text
USD equivalente = (entrada × 0.30 + (salida visible + razonamiento) × 2.50) / 1000000
```

El total de Gemini ya contiene razonamiento: el presupuesto usa el mayor entre total y suma de componentes, sin sumarlos entre sí. Los tokens de cache son un subconjunto de entrada y tampoco se agregan nuevamente. No se cambiaron las tarifas ni los límites configurados.

El adaptador conserva los contadores, su presencia, response_id y finish_reason antes de validar JSON/contrato. MAX_TOKENS es una respuesta inválida aunque su JSON parcial pueda parsearse. Ausencia o incoherencia de metadatos no acredita consumo cero. Un total completo coherente permite interpretar ausencia del contador opcional de pensamiento como cero; faltas de contadores obligatorios quedan pendientes.

`ia.call_ledger` registra trabajo, intento, ordinal acumulado, modelo, fase, reserva, contadores, total, presencia de campos, identificador remoto, terminación y error. Sus estados son:

| Estado | Tratamiento |
|---|---|
| reserved | Reserva confirmada en PostgreSQL antes de llamar; todavía no es gasto medido. |
| measured | Metadatos completos coherentes: costo equivalente observado; libera la diferencia con la reserva. |
| partial | Contadores incompletos/incoherentes: conserva los conocidos y una obligación conservadora. |
| unknown | Timeout, caída o transporte ambiguo: mantiene la reserva pendiente de reconciliación. |
| released | Rechazo HTTP verificable 400/401/403/404/429 sin generación: libera tokens/costo; la solicitud sigue contando para llamadas/RPM. |

Una respuesta tardía puede liquidar la llamada incluso después de perder el lease. Una caída deja una reserva durable; al reclamar el lease se marca desconocida. `reconcile_call` permite convertir una llamada desconocida/parcial a medida únicamente con consumo verificado, request_id concordante y referencia de auditoría. No hay liberación automática por antigüedad ni endpoint que presuma gratuitamente que un timeout no fue cobrado.

Los agregados de `usage_metrics` se conservan para compatibilidad. El nuevo cálculo presupuestario los excluye cuando ese intento tiene ledger, para evitar doble conteo. Los agregados históricos sin ledger conservan su costo original como legado no verificado: no se convierten a mediciones ni se reescriben reservas antiguas. La auditoría presenta ambas bases por separado.

## Presupuestos, concurrencia y reintentos

- Máximo de 100000 tokens y 24 llamadas acumulados por trabajo, incluyendo todos sus intentos y obligaciones desconocidas. Tres intentos continúan siendo el máximo. Los intentos no crean presupuesto nuevo.
- Reserva por solicitud: entrada completa estimada conservadoramente mediante bytes UTF-8 de instrucciones, usuario y esquema, con margen de 256; salida máxima configurada. También se rechaza contexto completo excesivo y se fragmenta antes. Es deliberadamente más restrictivo que bytes/4; no llama a count_tokens ni introduce RPC adicionales.
- Un advisory transaction lock compartido serializa lectura y reserva mensual. El control suma costo equivalente medido, legado no verificado y obligaciones pendientes; nunca reserva y mide dos veces la misma llamada. Las obligaciones nuevas pendientes se conservan al cambiar el mes.
- Concurrencia mediante slots PostgreSQL; cada worker fija la conexión física durante el trabajo para que los locks de sesión sobrevivan a commits del ledger y se liberen en la misma conexión.
- RPM se controla además con la ventana móvil compartida de llamadas de los últimos 60 segundos. Esperar el límite local no gasta intentos adicionales; el lease se mantiene vivo.
- 408/timeout y 5xx son transitorios; se respeta Retry-After cuando está disponible. Autenticación y contrato inválido no generan reintentos automáticos.
- 429 tiene pausa compartida entre workers/modelo: al menos 60 segundos con instrucción de reintento, 15 minutos si es ambiguo y 24 horas para cuota diaria/facturación agotada identificada. Nunca se acorta Retry-After. La pausa impide reclamar otros trabajos durante esa ventana.
- La reserva monetaria usa las tarifas locales como límite equivalente; no acredita facturación de Google ni detecta el nivel real de la cuenta.

`AI_FREE_DAILY_TOKEN_POOL=0` continúa significando cuota visual no configurada, sin bloquear IA. `AI_MONTHLY_BUDGET_USD=10.00` sigue aplicándose también a pruebas gratuitas. No cambian los controles development/test, los valores de activación ni la confirmación de servicio pagado.

## ADN y recomendaciones

`ia.reader_dna` identifica un ADN por propietario, huella de unidades de evidencia realmente interpretadas, modelo y `READER_DNA_PROMPT_VERSION` (por defecto `reader-dna-v1-es`). Un nuevo corte ETL sin cambios interpretables puede reutilizarlo. Cuaderno, reseña, dimensiones, reflexiones, notas, teorías o metadatos interpretados diferentes cambian la huella. El modelo y la versión del prompt también invalidan. Los campos ajenos al contexto interpretado no forman parte de la huella.

La generación se protege con un lock por esa identidad y una restricción única. Los resúmenes tienen ahora un namespace del ADN, independiente de `recommendations-v5-es`. El ADN publicado se guarda también como análisis versionado, con evidencias y trazas, para conservar historial y feedback.

`POST /me/ai/profile/refresh` prepara el corte determinista y encola exclusivamente `reader_profile`. `GET /me/ai/profile` devuelve ADN vigente sin generar ni encolar recomendaciones; conserva la estructura `analysis.content`, evidencia y estados consumida por el frontend. Los perfiles históricos incluidos en recomendaciones siguen siendo legibles. No se atribuye una nueva versión de prompt ADN a esos resultados antiguos.

Recomendaciones obtiene/reutiliza ADN antes de seleccionar. Comprueba primero que existan candidatos, para no gastar resúmenes si el catálogo está vacío. Mantiene filtros locales de biblioteca/catálogo, ordena por coincidencias semánticas simples e intercala autores. Envía solamente work_id, título, autores, descripción, categorías e idioma: portada, ISBN, fuentes y campos de presentación se adjuntan desde el catálogo al validar.

Los lotes exitosos se cachean por perfil compacto, datos semánticos de candidatos, instrucciones, modelo y prompt. Los reintentos reutilizan lotes válidos. Cambios relevantes en esos datos invalidan su caché; las recomendaciones publicadas continúan siendo instantáneas de perfil/modelo/prompt, no se regeneran automáticamente al abrir la vista ni ante toda alta de catálogo. Una nueva generación verifica el catálogo vigente y nunca acepta obras ajenas a sus candidatos.

## Eventos y consolidación

Se mantiene un trabajo por evento terminal concreto y contrato, incluyendo modelo en su target. Nunca se fusionan finish/abandon distintos ni libros diferentes. El hash completo incluye el evento y toda la evidencia que realmente se envía. Un resultado vigente con ese mismo evento/hash/modelo/prompt se reutiliza sin llamada adicional.

Los triggers nuevos reinician `not_before` para trabajos pendientes ante cambios pertinentes en cuaderno, reseña y notas/teorías del mismo propietario/obra; el cuaderno afecta únicamente su lectura. No reinician por no-op de cuaderno o actualizaciones solo de timestamps. No mezclan ni borran eventos. Cambios detectados durante una generación provocan una nueva espera de consolidación, manteniendo consumo ya registrado. Los fragmentos/resúmenes emocionales exitosos se cachean por evento y evidencia para reutilizarlos al reintentar.

Un administrador puede solicitar `POST /me/ai/books/{work_id}/refresh?force=true`. Genera otra versión conservando las anteriores, siempre dentro del presupuesto/contador de intentos del mismo trabajo; devuelve 409 si está en curso o agotó intentos. Sin force conserva el comportamiento idempotente. La acción administrativa existente puede adelantar un pendiente; se conserva esa excepción a la espera.

## Validación y comparación de fixtures

- Migraciones desde base vacía hasta 0054: correctas en `libria_gemini_validation_test`, separada de la base habitual.
- 63 pruebas de Gemini, optimización y compatibilidad: correctas, sin omisiones; 28 pertenecen al archivo nuevo. Cubren metadatos completos/parciales/ausentes, razonamiento, JSON inválido/truncado, reconciliación, caída de worker, presupuesto acumulado, RPM, reservas concurrentes, Retry-After, cuota diaria, ADN simultáneo, invalidación, caché de recomendaciones, consolidación y force versionado.
- Compilación Vite y ESLint del componente modificado: correctos. Vite mantiene el aviso de chunk mayor a 500 kB.
- Regresión general final: 405 pruebas, 72 omitidas por sus condiciones de integración; dos fallos y dos errores. Afectan `test_monitor_detects_a_gap_even_if_latest_day_succeeded` y `test_real_load_is_visible_and_does_not_change_daily_indicators`; los dos errores de limpieza de ETL manual intentan borrar ejecuciones aún referenciadas por `reader_profile_etl_states`. Estas pruebas dependen del estado de datos/fixtures; no se alteraron esas funcionalidades para ocultar sus fallos. Una ejecución anterior sobre la base recién creada tuvo un fallo y los mismos dos errores, sin el fallo del monitor.
- Auditoría de solo lectura sobre la base habitual: `gemini-optimization-local-audit.json`. No dispone aún del ledger porque no se le aplicó la migración; sus consumos son históricos, no mediciones posteriores de esta optimización.
- Auditoría de solo lectura de la fixture aislada: `gemini-optimization-fixture-audit.json`; todos sus contadores son sintéticos.

La fixture mantiene evidencia y catálogo equivalentes. El proveedor simulado devuelve 100 tokens de entrada y 20 visibles por llamada; no modela tokenización real:

| Escenario sintético | Llamadas antes | Llamadas después | Tokens antes/después | USD equivalentes antes/después |
|---|---:|---:|---:|---:|
| Perfil pequeño y una selección, cachés frías | 2 | 2 | 240 / 240 | 0.00016 / 0.00016 |
| Cambia solo el prompt de recomendaciones, ADN previo disponible | 2 | 1 | 240 / 120 | 0.00016 / 0.00008 |
| Reanudar publicación con lote exitoso ya persistido | 1 | 0 | 120 / 0 | 0.00008 / 0 |

La primera comparación reproduce las etapas heredadas con los requests de la misma fixture. La segunda verifica que el prompt nuevo no reinterprete el ADN. La tercera simula una interrupción antes de publicar. No son ahorros reales medidos con Gemini; perfiles grandes pueden requerir más fragmentos por la reserva conservadora. El ledger por fases permite medir el efecto real cuando se ejecute de forma autorizada.

## Aplicación y límites pendientes

Antes de arrancar el backend/worker actualizado en una instalación, aplicar `python -m alembic upgrade head` con su procedimiento de despliegue. La migración no se aplicó a la base habitual ni a producción en esta tarea. No tiene downgrade destructivo automático: se requiere una migración hacia adelante revisada para conservar contabilidad e historial.

No puede reconstruirse usage_metadata histórico que no se guardó, confirmar facturas ni confirmar cuota gratuita desde las banderas locales. Solicitudes desconocidas requieren reconciliación verificable. El estimador de entrada es conservador, no el tokenizador oficial; el consumo observado posterior prevalece y puede bloquear nuevas llamadas. No se implementa un limitador TPM/RPD de Google ni se modifica automáticamente la cuota visual; se respeta el 429 y su pausa. La consolidación cubre ediciones privadas habituales; una actualización administrativa del catálogo se incorpora al contexto al procesar, sin prometer reinicio automático de la ventana por cada cambio de metadatos. Se conserva el contrato de resumen existente para fragmentos emocionales; sigue siendo una compresión de evidencia, no sustituto de su registro original.
