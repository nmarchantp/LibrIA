# Recomendaciones personales con Ollama

> Archivo histórico anterior a etapa 6. No describe rutas ni comandos activos.

La versión actual `reader-books-v4-analytics-social` consume proyecciones de
analytics e incorpora descubrimiento social y colaborativo con controles de
privacidad. Detalles en [Motor de datos e inteligencia](analytics-pipelines.md).

## Selección por valoraciones positivas y más opciones

La versión `reader-books-v3-positive-batches` utiliza exclusivamente obras de la
biblioteca activa del titular con valoración general de 4 o 5 estrellas, tanto
privada como pública. Incluye sus reseñas, cuadernos, notas, teorías y reflexiones
actuales para que Ollama contraste qué apreció. Terminar una obra sin valorarla o
ponerle tres estrellas no se interpreta como una preferencia positiva. Sin libros
bien valorados devuelve `no_positive_ratings` y no consulta Ollama.

Cada tanda contiene cuatro opciones (o las restantes si quedan menos). El botón
“Recomendarme más opciones” conserva las anteriores y envía `exclude_ids` al POST
personal. El servidor excluye las obras completas de esos IDs, incluidas otras
ediciones, antes de limitar los candidatos. No se recirculan siempre los mismos
dieciséis libros. `has_more` informa si quedan alternativas reales en el catálogo.

El hash del caché incluye los datos actuales y las exclusiones. Repetir una
solicitud devuelve su tanda guardada; pedir otra tanda no exige esperar un minuto.
Se admiten hasta seis generaciones nuevas por minuto y un bloqueo por titular
evita peticiones simultáneas. Un fallo conserva las tarjetas mostradas y permite
reintentar la misma solicitud. Se mantiene el mínimo de diez obras de acceso
preexistente; esas obras no se usan como señal positiva sin 4 o 5 estrellas.

Las descripciones bibliográficas y metadatos de candidatos proceden del catálogo
persistido validado. Los motivos presentados usan coincidencias verificables;
Ollama selecciona los IDs y el criterio permitido, sin inventar libros o puntuaciones.

Las secciones siguientes conservan el diseño anterior y quedan subordinadas a
estas reglas cuando describan señales sin valoración o esperas entre tandas.

La sección `/recommendations` consulta `GET /api/analytics/me/recommendations`; si no existe una selección vigente, inicia `POST` con la procedencia elegida. Requiere sesión y no acepta el ID de otro titular. La clave del caché incluye titular, modelo, versión, historial, indicadores y candidatos.

Ollama elige hasta cuatro libros reales del catálogo interno, excluyendo las obras ya presentes en la biblioteca del titular y evitando duplicados por obra. El backend limita el conjunto a dieciséis candidatos, priorizando coincidencias comprobables de categorías, autores, idioma y extensión. El historial usa los cuarenta libros incorporados más recientemente; prioriza valoraciones de cuatro o cinco estrellas y lecturas finalizadas sin valoración, sin asumir que terminar equivale a disfrutar. Si estas señales no existen, usa otros registros propios que no estén abandonados o mal valorados.

El ADN procede de los mismos indicadores del ETL empleados por Mis análisis, para el origen elegido. Los metadatos y estados se completan con la biblioteca transaccional actual, incluso antes del próximo ETL. La página indica cuándo no existen indicadores analíticos y cuándo no hay historial. Los indicadores ficticios se identifican explícitamente; elegir una procedencia filtra los indicadores, no borra ni reclasifica libros de la biblioteca actual.

El modelo devuelve únicamente identificadores existentes y un criterio permitido para cada candidato. El servidor valida pertenencia, unicidad y criterio, y construye la explicación con los datos comprobados. No hay porcentajes de compatibilidad, inferencias de personalidad ni recomendaciones inventadas. Sin coincidencias, `discovery` identifica una propuesta exploratoria.

La migración `0021_ai_recommendations` crea `analytics.recomendaciones_ia`. El caché está aislado por titular. Un bloqueo PostgreSQL evita generaciones simultáneas del mismo usuario; se limita a una generación nueva por minuto, pero las lecturas de resultados vigentes son inmediatas. Ollama sigue usando el modelo local configurado en `AI_MODEL`; si no está disponible, se informa el error sin sustituirlo por recomendaciones ficticias.

Pruebas: `python -m unittest discover -s tests -p test_ai_recommendations.py`. Comprueban aislamiento, exclusión de libros propios, criterios respaldados, rechazo de duplicados o libros inexistentes, caché y autenticación.


## Pol?tica de datos vigente

Anal?tica e IA rechazan la procedencia `simulated` en sus endpoints p?blicos.
La interfaz abre registros `unclassified`: datos persistidos cuya procedencia real
no est? acreditada. No se reclasifican autom?ticamente como reales. Los cierres
hist?ricos permanecen intactos. No se ejecutan cargas demo ni se rellenan ausencias.
Las recomendaciones excluyen entidades identificadas en `app.procedencia_demo`
y usan candidatos con fuente `google-books` validada. Los libros demo no cuentan
para el m?nimo de acceso. La versi?n de cach? es `reader-books-v2`.
La anal?tica refleja el corte del ETL; registrar actividad no actualiza el cierre
inmediatamente. Sin indicadores se informa la ausencia; si Ollama falla se devuelve
un error sin sustituir su respuesta por una selecci?n prefabricada.


## Evidencia personal ampliada (daily-v4-personal)

Las migraciones 0028 y 0029 agregan `analytics.evidencia_lectora_personal` y
permiten persistir notas y teor?as. Cada ETL diario o manual extrae una instant?nea
acumulada al corte: cuadernos de personajes, sitios y resumen; rese?as propias
privadas (`draft`) y p?blicas, con texto, nota general y valoraciones por aspecto;
notas y teor?as del perfil personal con v?nculo bibliogr?fico verificable.
Los aportes de organizaciones, otras personas, rese?as ocultas, contenido legado
sin identidad verificable y entidades marcadas como demo quedan excluidos.
Una referencia de libro ambigua se omite, nunca se asigna por similitud de t?tulo.

La publicaci?n y conciliaci?n de la evidencia son at?micas con el resto del ETL.
Las rese?as se reconstruyen desde su ?ltima revisi?n anterior al corte. Los
cuadernos no tienen historial: una edici?n posterior al corte no se proyecta al
pasado. Las instant?neas anteriores permanecen intactas; una nueva carga es
necesaria para incorporar cambios. El origen contin?a siendo `unclassified` y
no se acredita autom?ticamente como real.

Solo `personal_evidence` consulta esta tabla, filtrando por titular, ?ltima
carga y procedencia. El an?lisis grupal no recibe los textos. La IA y las
recomendaciones personales reciben una muestra de hasta ocho aportes por tipo,
32 en total y 18000 caracteres de texto, m?s las reflexiones existentes.
El panel muestra la muestra utilizada y avisa del recorte; el ETL conserva los
aportes completos. No se suman instant?neas de varios cierres. Q02 cuenta aportes
incluidos en la muestra, no el total hist?rico ni un indicador de personalidad.
Cambios en la muestra invalidan el cach? por su hash. El prompt v9 exige analizar
Q02 cuando existe y tratar textos, res?menes y teor?as como evidencia no confiable,
nunca como instrucciones ni prueba autom?tica de una preferencia estable.
