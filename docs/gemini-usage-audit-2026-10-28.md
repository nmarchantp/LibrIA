# Auditoría de consumo Gemini — 28 de octubre de 2026

Auditoría del código actual y de la base PostgreSQL local mediante transacciones READ ONLY. No se ejecutaron workers, generaciones, migraciones ni cambios de .env. Se añadió únicamente un script de auditoría de lectura y estos resultados. Los registros históricos pueden proceder de revisiones anteriores del código; no demuestran que todos los límites actuales estuvieran activos entonces.

## Mediciones persistidas

Modelo filtrado: gemini-3.5-flash-lite. Las cifras provienen de ia.usage_metrics, agrupadas por trabajo, intento y versión del prompt. Todos los análisis publicados encontrados tienen provider_request_ids. No se consultó la factura de Google ni se recuperó el usage_metadata bruto de cada respuesta: el sistema conserva contadores agregados por intento, no ese objeto original. Un cero de razonamiento no permite distinguir cero real de metadatos ausentes, porque el adaptador convierte ambos a cero.

| Operación | Trabajos | Llamadas contabilizadas | Entrada | Salida visible | Razonamiento registrado | Costo equivalente total USD | Promedio USD/trabajo | Máximo observado USD/trabajo |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| recommendations-v5-es, incluye perfil global | 2 | 9 (4 y 5) | 114127 | 6821 | 0 | 0.05129060 | 0.02564530 | 0.02693760 |
| reading-event-v2-es | 11 | 11 (1 por evento) | 11046 | 4522 | 0 | 0.01461880 | 0.00132898 | 0.00180490 |
| Perfil global por separado | No existe trabajo separado | Incluidas arriba | No desglosable | No desglosable | No desglosable | No sumar nuevamente | No disponible | No disponible |

Dos trabajos v5: 49910 entrada + 3752 salida, USD 0.02435300; 64217 entrada + 3069 salida, USD 0.02693760. Los 11 eventos varían entre 776–2033 tokens de entrada y 375–478 de salida. Los trabajos v5 registran dos fragmentos en total. No se puede asignar con precisión el costo entre resumen del perfil y selección de candidatos porque falta contabilidad por llamada/fase.

Historia completa, incluidas recomendaciones v1–v4: 565478 tokens de entrada, 33095 de salida y 45 llamadas de recomendaciones; más los 11 eventos anteriores. Costo equivalente de metadatos total: USD 0.26699970. Costo guardado/usado por el control mensual: USD 0.33967720. Diferencia: USD 0.07267750 en un trabajo v1 fallido con tres intentos, compatible con reservas conservadoras por consumo desconocido. No es consumo medido adicional. El registro no conserva el desglose de esa reserva para verificarla a posteriori.

En modo gratuito estos importes son equivalentes a tarifa pagada, no prueba de cargos reales. Google confirma USD 0.30/M entrada y USD 2.50/M salida incluyendo pensamiento, y acceso gratuito en el nivel gratuito: https://ai.google.dev/gemini-api/docs/pricing#gemini-3.5-flash-lite

## Datos y construcción de prompts

El adaptador envía system_instruction, JSON canónico como contents y response_json_schema con temperature=0. No envía historial de chat, herramientas de búsqueda ni archivos multimedia. Los prompts identifican los datos del usuario como evidencia no confiable, piden español, referencias evidence_ids y prohíben diagnósticos e invenciones.

### Recomendaciones y perfil global

El ETL genera un perfil determinista persistido: lecturas terminadas, valoraciones generales de al menos 4, valoraciones por dimensión, reflexión de cierre, reseña, cuaderno privado, notas, teorías y metadatos de obra/edición, con procedencia. Excluye datos de demostración y respeta el corte ETL. No hace llamadas a Gemini.

gemini_context.profile_evidence_units convierte esos datos en unidades citables. _summarize_profile SIEMPRE las fragmenta, incluso si el perfil cabe en contexto. CHUNK_SYSTEM interpreta cada fragmento; REDUCE_SYSTEM reduce los resúmenes cuando exceden aproximadamente la mitad del contexto configurado. Cachea ambos por propietario, contenido, modelo y versión de prompt.

Luego _merge_profile_summaries combina localmente siete categorías del perfil, hasta 12 valores por categoría y 200 evidence_ids. No hay una llamada final independiente para redactar el perfil global. /me/ai/profile lee el campo profile del mismo análisis de recomendaciones. /profile/refresh prepara el perfil y solicita el mismo trabajo de recomendaciones.

La selección obtiene hasta 200 candidatos del catálogo local, excluye libros de la biblioteca y datos demo, y envía título, descripción truncada a 2000 caracteres, autores, categorías, idioma, edición, páginas, portada, ISBN y fuentes. Algunos campos de presentación podrían omitirse para ahorrar tokens. Divide los candidatos en lotes; repite los resúmenes del perfil en cada lote; solicita hasta ocho recomendaciones y detiene el recorrido cuando reúne ocho obras distintas. El título y autores finales se adjuntan desde el catálogo local.

Llamadas por intento: fragmentos NO cacheados + reducciones NO cacheadas + lotes de candidatos efectivamente consultados. Perfil pequeño sin cache: normalmente al menos dos llamadas. Perfil íntegramente cacheado: una o más llamadas de selección. Las 4–5 llamadas observadas incluyen ambas fases.

### Eventos de lectura

Solo finish y abandon crean trabajos. _individual_context envía evento concreto, fecha, página, total, motivo y reflexión; estado y fechas de la lectura; descripción, título, autores, categorías y edición; cuaderno; última reseña del usuario para la obra con dimensiones; todas sus notas y teorías no heredadas para esa obra. No hay límite de cantidad de notas/teorías en esta consulta, ni truncamiento de esos textos. Se leen al ejecutar el trabajo, no se congela una instantánea al encolarlo.

Con contexto pequeño: una llamada READING_SYSTEM. Con contexto grande: una llamada CHUNK_SYSTEM por fragmento, reducciones jerárquicas si hacen falta y una llamada final READING_SYSTEM. Estos resúmenes individuales no usan la cache de fragmentos del perfil. El resumen usa un contrato de preferencias lectoras, aunque su destino final sea el análisis del evento: puede perder matices emocionales al comprimir. Si las fuentes cambian durante la generación, se descarta el resultado y se reintenta.

## Límites efectivos y estimaciones

Configuración local cargada: contexto 12000, fragmento 6000, salida 2048, tokens por intento 100000, llamadas por intento 24, intentos por trabajo 3, concurrencia 2, solicitudes/minuto 10, retraso de evento 30 minutos.

- estimate_tokens usa ceil(bytes UTF-8 del JSON / 4). Es una heurística: no se invoca count_tokens y no constituye un límite exacto de tokens Gemini.
- El límite de 12000 se aplica al JSON de candidatos o a la decisión de fragmentar el evento, no a toda la solicitud. El system prompt y el esquema no están incluidos en esos 12000. Las envolturas de fragmentos añaden index, total y hash después de dimensionar la evidencia.
- _invoke estima system y user, pero no el response_json_schema. El JSON canónico del texto también añade escapes. La última envoltura del análisis individual no vuelve a verificar el contexto completo.
- max_output_tokens=2048 sí se manda al proveedor. No se fija thinking_config. El razonamiento puede ocupar parte de la salida disponible y provocar JSON incompleto.
- context_fragments es una métrica, no un tope independiente. Contabiliza fragmentos y reducciones, incluso elementos cacheados en el perfil.
- max_calls y max_tokens se reinician por intento: pese al nombre por trabajo, permiten nominalmente hasta 72 llamadas y 300000 tokens en tres intentos.
- reserve acumula entrada+salida visible conocidas, pero omite razonamiento. Comprueba estimaciones ANTES de llamar; no rechaza un exceso real posterior. No hay un máximo monetario absoluto demostrable con este mecanismo.

| Estimación, NO medición | Por intento | Con tres intentos |
|---|---:|---:|
| Reserva conservadora actual: 100000 tokens a USD 2.50/M | USD 0.25 | USD 0.75 |
| Techo nominal más ajustado si 100000 fuese exacto y 24×2048 limitase toda la salida facturable | USD 0.13813440 | USD 0.41440320 |
| Evento de una llamada con exactamente 12000 entrada + 2048 salida facturable | USD 0.00872 | USD 0.02616 |

Los mismos presupuestos compartidos aplican a recomendaciones y eventos. El perfil global está incluido en recomendaciones. Los valores anteriores NO son garantías: excluyen subestimación del tokenizador, esquema/instrucciones omitidas y consumo remoto sin respuesta. Para un perfil servido desde resultados persistidos, leer la vista cuesta cero llamadas.

## Registro de usage_metadata y costo

providers/gemini.py mapea prompt_token_count → input_tokens, candidates_token_count → output_tokens, thoughts_token_count → reasoning_tokens, cached_content_token_count → cached_input_tokens y total_token_count → total_tokens.

Fórmula de esta auditoría:

    costo_USD = (input_tokens * 0.30 + (output_tokens + reasoning_tokens) * 2.50) / 1000000

candidates_token_count excluye pensamiento; total_token_count ya lo incluye. No sumar pensamiento nuevamente a total_token_count, ni sumar cached_input_tokens a prompt_token_count. Referencia oficial: https://firebase.google.com/docs/ai-logic/count-tokens

Fallo: _estimated_cost usa únicamente input_tokens y output_tokens; infravalora cualquier respuesta con reasoning_tokens>0. En las mediciones guardadas aquí el razonamiento es cero, por lo que el costo recalculado coincide en los trabajos actuales exitosos. La barra gratuita suma entrada+salida+razonamiento correctamente para los campos separados existentes.

Fallo: GeminiProvider valida JSON y negocio ANTES de devolver el uso. Respuestas vacías, truncadas, bloqueadas o inválidas pierden sus metadatos aunque Gemini sí pueda haberlos devuelto y facturado. El worker guarda entonces una reserva estimada. Metadatos ausentes se convierten silenciosamente en cero. total_tokens no se persiste en usage_metrics ni se comprueba coherencia del total.

El registro es uno por (job_id, attempt), idempotente, con entrada, salida, pensamiento, cache, request_count, context_fragments, duración, estado y costo estimado. No hay una fila por solicitud ni distinción persistente entre costo observado y reserva. request_count se incrementa antes de obtener slot/invocar, de modo que es un contador de reservas de llamadas, no una prueba universal de solicitudes HTTP efectivamente enviadas. Una pérdida de lease abandona el intento sin registrar el consumo acumulado; una caída de proceso puede perderlo igualmente.

## Duplicados, retraso y reintentos

Recomendaciones deduplicadas por perfil/proveedor/modelo/prompt. Eventos deduplicados por evento/proveedor/modelo/prompt. Los resultados persistidos evitan regeneraciones al abrir/pollear vistas. El target textual de evento incluye proveedor y prompt, pero omite modelo: cambiar solo el modelo puede chocar con la unicidad owner_id,target y no encontrar el trabajo al consultarlo con el nuevo modelo.

El retraso NO agrupa: not_before = fecha del evento + 30 minutos para cada evento. Dos eventos generan dos trabajos; cambios de reseña/notas no reinician esa ventana. La ruta administrativa puede adelantar un pendiente a now(). Los eventos siguen analizando evidencia actual de la obra, por lo que relecturas pueden reutilizar/reprocesar notas antiguas. El perfil global vuelve a interpretar parte de los textos ya usados por eventos; no reutiliza sus análisis emocionales.

La cache de perfil evita repeticiones con contenido idéntico, pero cambiar la versión del prompt invalida sus claves incluso si CHUNK_SYSTEM no cambió. El perfil se resume antes de verificar que existan candidatos, pudiendo gastar llamadas para terminar en no_verified_candidates. Las selecciones de lotes no se cachean, por lo que un reintento puede repetirlas.

429/cuota, timeout y errores 5xx son reintentables. Esperas del worker: 3.75–6.25 s tras el primer intento y 7.5–12.5 s tras el segundo; no hay tercer reintento porque el máximo incluye el intento inicial. No distingue cuota diaria de límite por minuto y no procesa Retry-After. Un 429 de cuota diaria puede consumir los tres intentos rápidamente. Autenticación y respuesta inválida no se reintentan automáticamente; las rutas admin pueden reactivar fallidos mientras queden intentos. Los lotes de recomendaciones capturan respuesta inválida y continúan con otros lotes.

SDK local google-genai 2.33.0, ruta síncrona generate_content: HttpOptions no fija retry_options; retry_args(None) aplica un solo intento. La constante de cinco intentos del SDK solo entra al habilitar opciones de retry; no debe multiplicarse por cinco en esta configuración. Timeouts y leases vencidos aún pueden duplicar cálculo remoto aunque PostgreSQL impida publicación duplicada.

## Modo gratuito y presupuesto mensual

Valores locales verificados: app_env=development; worker_enabled=True; paid_service_confirmed=False; free_test_mode=True; free_daily_pool=0; monthly_budget=10.00. Son valores de la configuración local, no evidencia de despliegue/configuración de producción.

AI_FREE_DAILY_TOKEN_POOL=0 solo produce configured=false y oculta el porcentaje mostrando cuota no configurada. No desactiva IA, no bloquea trabajos y no impone reparto real ni control por usuario. El worker no consulta este campo.

AI_MONTHLY_BUDGET_USD se aplica también en modo gratuito. Acumula estimated_cost_usd, agrega USD 0.25 por trabajo processing y exige espacio para otro intento antes de reclamarlo, bajo advisory lock. Snapshot: USD 0.33967720 registrado, cero en curso, no agotado. Puede bloquear pruebas gratuitas por costo equivalente y reservas aunque la factura sea cero. Al agotarse, posterga trabajos al siguiente mes; no verifica el nivel de facturación real en Google. Un saldo menor a USD 0.25 impide un intento nuevo, incluso si su costo esperado es menor.

El modo gratuito permite ejecutar el worker únicamente en development/test y con worker_enabled. No habilita facturación, pero tampoco fuerza al proyecto/API key a ser de nivel gratuito: esa condición se configura en Google. No hay verificación del nivel de cuenta ni fallback pagado implementado. Los límites reales dependen del proyecto/modelo y de RPM, TPM y RPD; el limitador local solo controla concurrencia/RPM, no TPM ni RPD. La renovación diaria UTC de la barra no coincide necesariamente con cuotas de Google, cuyos RPD se renuevan a medianoche del Pacífico: https://ai.google.dev/gemini-api/docs/rate-limits

## Verificación y siguientes correcciones

Ejecutadas ocho pruebas unittest del adaptador: correctas, sin llamadas externas. Ejecutado scripts/audit_gemini_usage.py en modo lectura. Resultado agregado sin textos privados ni claves: gemini-usage-audit-2026-10-28.json.

Prioridad: conservar usage_metadata incluso ante respuesta inválida; separar una fila por solicitud/fase y costo medido de reservas; incluir razonamiento exactamente una vez tanto en costo como en límite acumulado; conservar total y presencia de metadatos; contabilizar pérdida de lease/caída; usar conteo completo del prompt y backoff sensible a cuotas. Decidir explícitamente si el retraso debe convertirse en agrupación y si la cuota personal debe bloquear trabajos. Ninguna de estas correcciones fue aplicada al runtime en esta auditoría.
