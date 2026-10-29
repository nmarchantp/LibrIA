# Motor de Análisis Literario e Identidad Lectora Adaptativa

> Contrato histórico. La operación vigente está documentada en `gemini-stage6-production-readiness.md`.

La [arquitectura de pipelines vigente](analytics-pipelines.md) sustituye el acceso
transaccional directo del motor: la extracción pertenece al ETL y ambos análisis
leen proyecciones persistidas en analytics con trazabilidad por ejecución.

## Presupuesto de un minuto para el ADN

La migración 0031 añade un vencimiento persistido de 55 segundos desde la
solicitud, incluyendo cola y generación, con margen de entrega en pantalla.
El ADN ahora se obtiene en una sola llamada sobre todas las experiencias reales:
no espera una cadena de tareas individuales. Consulta los aportes transaccionales
originales directamente, sin sustituirlos por interpretaciones previas de libros.
La identidad y la interpretación global tienen espacio para explicar matices;
puede identificar hasta cuatro afinidades distintas cuando hay evidencia, sin
forzar un mínimo ni mostrar porcentajes simulados. Cada conclusión cita sus obras.

Las referencias enviadas a Ollama son cortas y se traducen a identificadores
reales antes de validar y persistir. Se eliminan envoltorios y valores vacíos,
no comentarios del lector. La salida es compacta y conserva las mismas reglas
de evidencia, privacidad y calidad. Un consumidor dedicado de perfiles evita
esperar a que el consumidor de libros acabe su cola. En un despliegue externo,
pueden ejecutarse dos procesos: `python -m scripts.run_ai_worker --profiles-only`
y `python -m scripts.run_ai_worker --books-only`.

Los análisis individuales comprueban cada segundo si hay un ADN pendiente y
cancelan su llamada para ceder el modelo. La tarea individual vuelve a la cola
sin consumir un intento por esa interrupción. Solicitar un ADN no relanza libros
fallidos. Las conclusiones idénticas del modelo se muestran una sola vez.

La llamada usa un límite total cancelable que incluye conexión, espera de
Ollama y streaming completo. No se reinicia al recibir un token. El presupuesto
no se amplía por eventos coalescidos ni por reintentos automáticos. Si no termina,
la tarea falla con `deadline_exceeded` y se conserva el perfil previo válido.
La pantalla también aplica el vencimiento del servidor; un nuevo intento explícito
abre otro presupuesto. El límite evita esperas indefinidas, pero no garantiza
una inferencia exitosa si Ollama está saturado o el hardware no alcanza.

Las descripciones posteriores del worker que indiquen una espera previa de todos
los análisis individuales quedan reemplazadas por este recorrido de una llamada.

## Separación entre ficha y ADN lector

Las conclusiones deben ser frases explicativas y concretas. Se rechazan textos de
relleno (`resumen`, `texto`, `string`) y conclusiones repetidas entre categorías.
La misma comprobación impide que un análisis individual con relleno alimente el
perfil global. Los resultados guardados que no pasan esta validación no se muestran;
se conservan como versiones anteriores y se solicita su regeneración.
La interfaz explica las categorías con lenguaje cotidiano y nombra las obras
que respaldan cada conclusión. Una sola obra se identifica como señal inicial,
no como preferencia recurrente confirmada.

La ficha muestra el análisis individual únicamente después de una valoración
general propia (`rating` no nulo). La API aplica la misma regla: devuelve
`awaiting_rating` sin análisis ni tarea y rechaza la actualización con HTTP 422
si no hay valoración. La interfaz nunca usa el perfil global como alternativa
cuando falta el identificador de una obra.

El ADN utiliza el esquema `ReaderProfile`, con identidad literaria e interpretación
global distintas del esquema de experiencia individual. Su contexto abarca todas
las entradas activas del titular: análisis de obras valoradas y aportes/intereses
de las restantes, sin atribuirles satisfacción. Sus conteos por estado se calculan
directamente con los registros actuales. Las afinidades muestran cantidad de obras
de respaldo, no porcentajes inventados.

Para generalizar un perfil se requieren al menos dos obras distintas valoradas;
con una sola se muestran los conteos y la insuficiencia de evidencia, sin convertir
su reseña en una identidad lectora. La validación exige referencias a dos análisis
distintos y rechaza la copia literal de la interpretación de una obra. Los perfiles
anteriores que no tienen esta estructura se regeneran y no se muestran como el
nuevo ADN. Esta regla prevalece sobre el alcance inicial de análisis visibles
para libros todavía sin valorar.

Implementación de la especificación funcional v1.0 del 16 de octubre de 2026.
Este documento incorpora sus requisitos al SRS técnico y a la matriz de reglas.
La especificación original queda conservada en `ai-functional-spec-v1.txt`.

## Flujo y límites

Cada experiencia pertenece al par **titular–obra de su biblioteca**, nunca a la
ficha pública. El contexto incluye los intentos de lectura de esa obra, estados,
motivo opcional de abandono, cuaderno completo, revisiones cronológicas de sus
reseñas con puntuaciones generales y por aspecto, notas, teorías y reflexiones.
Solo se utilizan fuentes persistidas y vinculadas de forma verificable; se
excluyen entidades marcadas como demo. La ausencia de marca no acredita por sí
sola la autenticidad histórica de registros antiguos.

El análisis individual y el perfil global leen las fuentes transaccionales,
sin esperar al cierre del ETL. El ETL sigue disponible para indicadores e
instantáneas históricas. El perfil consolida las experiencias de **toda la
biblioteca activa**, con sus referencias y fechas; no suma distintas versiones
del mismo libro como si fueran obras distintas. Las revisiones anteriores de
las reseñas permiten conservar cambios de preferencia.

La capacidad actual es de 42000 caracteres de contexto por llamada; al superar
ese límite se informa `context_capacity`, conservando la última versión válida.
No se presenta una muestra truncada como un perfil de la biblioteca completa.
El procesamiento jerárquico de bibliotecas que excedan esa capacidad es una
ampliación pendiente. Los cuadernos todavía no tienen un historial de versiones
transaccional; se interpreta su contenido actual, sin reconstruir notas borradas.

## API privada

Todos los contratos están bajo `/api/me/ai`, requieren sesión y obtienen el
titular de ella; ninguno admite un `user_id` elegido por el cliente.

| Método | Ruta | Comportamiento |
|---|---|---|
| GET | `/books/{work_id}` | Análisis vigente, referencias y tarea de una obra propia activa |
| POST | `/books/{work_id}/refresh` | Solicita trabajo; HTTP 202 |
| GET | `/profile` | Perfil vigente y estado de procesamiento |
| POST | `/profile/refresh` | Solicita actualización; reintenta libros fallidos |
| GET | `/profile/history?limit=20&before=version` | Historial privado paginado |
| POST | `/feedback` | Confirma, corrige o rechaza una versión propia vigente |
| GET | `/feedback` | Estado de las correcciones propias |
| GET | `/jobs/{id}` | Estado de una tarea propia |

El identificador de libro es `work_id`, disponible en la biblioteca; no es el
identificador externo de Google Books. Los resultados nuevos no tienen el mínimo
de diez libros que conserva la interpretación numérica anterior y recomendaciones.
Ningún rol profesional ni administrativo concede acceso a análisis ajenos.

## Persistencia y ejecución

Migración `0030_adaptive_reader_ai`, esquema `ia`:

- `analyses`: versiones de libro y perfil, hash, modelo, versión del prompt y vigencia.
- `evidence`: referencias al origen, clave de fuente y hash; no copia textos originales.
- `feedback`: interpretación original, acción, información del lector, fecha y estado.
- `jobs`: cola duradera, revisión solicitada, intentos, vencimiento y estado.

Los triggers guardan la solicitud **en la misma transacción** que el cambio real.
El worker solo puede observarla después del commit. Estado, cuaderno, puntuación,
reseña, nota, teoría, reflexión y retirada de fuente son cambios relevantes.
Un avance de página por sí solo no llama a Ollama. Se consolidan eventos durante
tres segundos y se compara el hash para evitar inferencias redundantes.

El worker reclama con `FOR UPDATE SKIP LOCKED`, confirma la reclamación y libera
la transacción antes de llamar a Ollama. Tiene una concesión de siete minutos,
comprobación de revisión/hash antes de publicar y hasta dos intentos automáticos
ante indisponibilidad o respuesta inválida para los libros. El perfil no reintenta
automáticamente y tiene su propio vencimiento. Los estados expuestos son `pending`,
`processing`, `completed` y `failed`. El perfil tiene prioridad sobre los libros.

Por defecto el backend ejecuta el consumidor en segundo plano. Para desplegarlo
independientemente: `AI_WORKER_ENABLED=false` en el servidor y, desde
`apps/backend`, `python -m scripts.run_ai_worker` en otro proceso con el mismo
entorno. `--once` procesa una sola tarea disponible. No requiere Redis ni Celery.

El frontend muestra cola, procesamiento, error y finalización y conserva el
resultado vigente mientras llega uno nuevo. Una corrección/rechazo aceptados
invalidan inmediatamente su versión; no se recupera como alternativa una versión
más antigua contradicha. Las confirmaciones y correcciones tienen prioridad en
el siguiente contexto. No se reentrena el modelo.

## Reglas del SRS y matriz de trazabilidad

| Regla | Aplicación |
|---|---|
| RN-IA-001/002 | Cada versión usa `owner_id` y `book:work_id` |
| RN-IA-003 | Esquema y validación impiden sentimiento, emociones y valoraciones experimentadas en Por leer |
| RN-IA-004 | Leyendo no puede quedar consolidado |
| RN-IA-005/006 | Motivo opcional; sin evidencia se devuelve indeterminado; no se asume rechazo |
| RN-IA-007 | Feedback prioritario e invalidación inmediata de resultados contradichos |
| RN-IA-008 | Versiones y referencias con hashes; revisiones originales consultables en origen |
| RN-IA-009 | Hash y revisión impiden publicar resultados obsoletos; fallo conserva la última versión válida |
| RN-IA-010 | Rutas sin selección de titular, filtros por sesión, caché privado y `no-store` |
| RN-IA-011 | Estados insuficiente/provisional y listas vacías permitidas |
| RN-IA-012 | Prompt excluye diagnósticos y personalidad; requiere evaluación semántica continua |
| RN-IA-013 | Pydantic, esquema restringido a fuentes existentes y validaciones de negocio |
| RN-IA-014 | Cola persistida con cuatro estados y reintentos |
| RN-IA-015 | Retirar libro o borrar reseña invalida y vacía narrativas derivadas de libro/perfil, incluido su historial |

Las preferencias confirmadas requieren feedback citado. Un factor recurrente de
abandono requiere referencias a dos obras distintas. La frecuencia no equivale
a afinidad. La separación de tristeza y desagrado es una regla del prompt y una
evaluación de calidad, no una garantía derivada de validar JSON.

Las narrativas retiradas y el texto original de feedback dependiente se vacían;
se conserva metadato técnico y referencias para trazabilidad. Retirar un libro
archiva su entrada transaccional y permite volver a agregarlo. Borrar una reseña
elimina también sus revisiones y su hilo público. Las instantáneas analíticas
históricas del ETL tienen retención separada; esta entrega no implementa la
eliminación integral de una cuenta ni una política legal de conservación.

## Validación y alcance evolutivo

`python -m unittest discover -s tests -p test_adaptive_ai.py` verifica propiedad,
correcciones, no resurrección de versiones, coalescencia, progreso sin inferencia,
resultados obsoletos, fallo del proveedor, retirada de fuentes y estados de lectura.
`python -m scripts.evaluate_reader_ai` evalúa ejemplos etiquetados de la
especificación contra Ollama sin persistirlos como actividad de usuarios.
La ejecución local con `qwen3:1.7b` aprobó seis de seis casos: reseña positiva,
tristeza con satisfacción, abandono sin motivo, abandono por tiempo, lectura
sin comentarios y opinión mixta. Es una evaluación inicial, no una medición
exhaustiva de ironía o de todas las formas de expresar preferencias.
Las pruebas de integración usan transacciones revertidas; no cargan bibliotecas
ficticias para el producto.

Las recomendaciones reciben el perfil estructurado vigente, además de su
historial, y mantienen la validación de libros candidatos y criterios comprobables.
Las narrativas antiguas del ETL no se reintroducen como preferencias vigentes.
Si hay correcciones y todavía no existe un perfil válido que las incorpore,
las recomendaciones esperan su actualización en vez de ignorar la corrección.
No se implementan puntuaciones inventadas ni el algoritmo avanzado IA-010.
IA-008 conserva versiones básicas; IA-009 (gráficas históricas), fine-tuning,
predicción clínica y comparaciones emocionales públicas quedan fuera del MVP.
