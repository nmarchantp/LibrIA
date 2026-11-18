# MVP: solo Gemini

Por decisión del usuario se retiró OpenAI: adaptador, selección automática, clave y variables activas de entorno, configuración de secretos y mensajes de respaldo. El worker solo acepta proveedores con identidad Gemini; rechaza cualquier otro antes de reservar llamadas o contactar servicios.

Los registros históricos de consumo y errores se conservan. Los importes históricos de OpenAI siguen incluidos en la contabilidad; sus tarifas legadas se mantienen únicamente para conciliar esos registros, sin habilitar llamadas. No hay migraciones pendientes ni se modificaron los límites de gasto o de intentos.

Los errores históricos de proveedores retirados se presentan como intentos anteriores y no como un servicio activo. Gemini conserva las validaciones de contenido y el último ADN válido no se sustituye por resultados incompletos.

El worker recarga `.env` entre lotes completos. La única clave activa es `GEMINI_API_KEY` en `apps/backend/.env`. No se necesita una clave de OpenAI.

Validaciones: `tests/test_gemini_only.py`, `tests/test_worker_configuration_reload.py`, las suites existentes de Gemini/ADN y `apps/web/tests/analysis-errors.mjs`.

Verificación real del MVP: la nueva generación quedó en `completed`; la consulta privada devuelve `ready`, sin tarea pendiente, esencia con evidencia `sufficient` y resumen de 127 palabras. Todos los registros de llamadas de esa solicitud corresponden a Gemini. No se contactó OpenAI durante esa generación. Se reinició el worker con el código exclusivo de Gemini.
