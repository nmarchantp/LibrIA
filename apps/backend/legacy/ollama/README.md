# Referencia histórica de Ollama

Esta carpeta conserva la implementación específica de Ollama encontrada en
el commit `8fe48f7`. Los archivos `*.reference.py` y
`*.reference.ps1` están comentados línea por línea: no forman un paquete Python,
no se importan y no deben ejecutarse.

La preservación se divide por responsabilidad para no congelar como legado la
lógica de negocio que sigue siendo reutilizable:

- `prepare-ai.ps1.reference.ps1`: instalación, arranque y descarga local.
- `book_transport.py.reference.py`: prioridad del perfil y transporte local.
- `model_slot.py.reference.py`: serialización del modelo local.
- `interpretation_provider.py.reference.py`: disponibilidad, payload, prompt y
  manejo de respuestas de interpretaciones.
- `fast_profile.py.reference.py`: streaming, payload y prompt del perfil global.
- `adaptive_ai.py.reference.py`: payload, prompt y opciones del análisis por
  libro.
- `recommendations.py.reference.py`: payload, prompt, opciones y control de
  disponibilidad de recomendaciones.
- `config.py.reference.py`: variables y validación loopback originales.

Los prompts y opciones históricos (`think`, `num_ctx`, `num_predict` y
`keep_alive`) se conservan textualmente en esas referencias. Las migraciones
históricas no se copiaron: Alembic ya constituye su registro inmutable y esta
etapa no modifica triggers ni esquema.

En la etapa 6 estas referencias quedaron como el único lugar que conserva el
transporte local ejecutable en su forma histórica. Todo está comentado línea
por línea, no se importa y no participa en rutas, workers ni scripts activos.
También se preservan `adaptive_worker.py.reference.py` y
`run_ai_worker.py.reference.py`, que documentan los dos antiguos puntos de
arranque. Los datos y migraciones históricas con `provider='ollama'` se
mantienen intactos para trazabilidad.
