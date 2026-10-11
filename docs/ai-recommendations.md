# Recomendaciones personales con Ollama

La sección `/recommendations` consulta `GET /api/analytics/me/recommendations`; si no existe una selección vigente, inicia `POST` con la procedencia elegida. Requiere sesión y no acepta el ID de otro titular. La clave del caché incluye titular, modelo, versión, historial, indicadores y candidatos.

Ollama elige hasta cuatro libros reales del catálogo interno, excluyendo las obras ya presentes en la biblioteca del titular y evitando duplicados por obra. El backend limita el conjunto a dieciséis candidatos, priorizando coincidencias comprobables de categorías, autores, idioma y extensión. El historial usa los cuarenta libros incorporados más recientemente; prioriza valoraciones de cuatro o cinco estrellas y lecturas finalizadas sin valoración, sin asumir que terminar equivale a disfrutar. Si estas señales no existen, usa otros registros propios que no estén abandonados o mal valorados.

El ADN procede de los mismos indicadores del ETL empleados por Mis análisis, para el origen elegido. Los metadatos y estados se completan con la biblioteca transaccional actual, incluso antes del próximo ETL. La página indica cuándo no existen indicadores analíticos y cuándo no hay historial. Los indicadores ficticios se identifican explícitamente; elegir una procedencia filtra los indicadores, no borra ni reclasifica libros de la biblioteca actual.

El modelo devuelve únicamente identificadores existentes y un criterio permitido para cada candidato. El servidor valida pertenencia, unicidad y criterio, y construye la explicación con los datos comprobados. No hay porcentajes de compatibilidad, inferencias de personalidad ni recomendaciones inventadas. Sin coincidencias, `discovery` identifica una propuesta exploratoria.

La migración `0021_ai_recommendations` crea `analytics.recomendaciones_ia`. El caché está aislado por titular. Un bloqueo PostgreSQL evita generaciones simultáneas del mismo usuario; se limita a una generación nueva por minuto, pero las lecturas de resultados vigentes son inmediatas. Ollama sigue usando el modelo local configurado en `AI_MODEL`; si no está disponible, se informa el error sin sustituirlo por recomendaciones ficticias.

Pruebas: `python -m unittest discover -s tests -p test_ai_recommendations.py`. Comprueban aislamiento, exclusión de libros propios, criterios respaldados, rechazo de duplicados o libros inexistentes, caché y autenticación.
