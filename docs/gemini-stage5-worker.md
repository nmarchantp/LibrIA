# Worker Gemini preparado en la etapa 5

> Registro de etapa 5. Etapa 6 reemplaza su estado operativo en `gemini-stage6-production-readiness.md`.

Esta etapa conecta `google-genai` exclusivamente con los trabajos persistentes
`recommendation` y `reading_event_analysis`. No desactiva los recorridos Ollama
restantes ni activa Gemini en producción: `GEMINI_WORKER_ENABLED` permanece en
`false` por defecto. El código histórico comentado continúa en
`apps/backend/legacy/ollama/`.

## Recorridos

- Recomendaciones: consume `recommendation-profile-v1`, que el ETL nocturno ya
  limita a lecturas terminadas con valoración general mayor o igual a 4. El
  worker interpreta reseñas, cuadernos, notas, teorías, reflexiones,
  valoraciones por dimensión y metadatos. Gemini elige entre candidatos del
  catálogo, y el backend vuelve a comprobar obra, título, autoría, identidad,
  propiedad, duplicados y evidencias antes de publicar.
- Análisis individual: consume una sola vez el evento concreto `finish` o
  `abandon` cuando vence su ventana de 30 minutos. Una relectura tiene otro
  `reading_id` y otro evento, por lo que produce un resultado independiente.

Ambos recorridos obtienen siempre el titular desde el job. No envían nombre,
correo, credenciales ni API keys. Los textos del usuario se etiquetan como
evidencia no confiable y los prompts ordenan ignorar instrucciones contenidas
en ellos.

## Contexto, trazabilidad y costos

Antes de cada solicitud se estima el número de tokens. El contexto privado se
convierte en unidades con `evidence_id`; si no cabe, se divide sin truncar el
texto y se resume jerárquicamente. Cada fragmento conserva hash, posición y
evidencias. Los resúmenes intermedios se almacenan en `ia.analyses` y se
reutilizan si contenido, modelo y prompt no cambian.

`AI_MAX_CALLS_PER_JOB` y `AI_JOB_TOKEN_BUDGET` acotan el trabajo completo. Los
tokens, duración, estado y costo estimado configurable se agregan por intento en
`ia.usage_metrics`; nunca se guardan prompts ni secretos en esa tabla.

## Concurrencia, cuotas y recuperación

El reclamo usa `FOR UPDATE SKIP LOCKED`, fechas `not_before` y lease. Un lease
vencido vuelve a reclamarse; si murió durante el último intento permitido se
marca `lease_attempts_exhausted`, evitando un `processing` permanente. Advisory
locks de PostgreSQL aplican concurrencia y rate limit a todos los procesos que
comparten la base.

429, timeout, 5xx y cambios de fuente durante una solicitud usan backoff
exponencial con jitter y un máximo de intentos. Autenticación, configuración,
JSON inválido y validación de negocio fallan sin reintentos indefinidos. Una
desconexión es ambigua: el proveedor pudo completar remotamente aunque LibrIA no
recibiera la respuesta. Los reintentos limitados pueden repetir ese costo remoto,
pero las restricciones de PostgreSQL y la comprobación del lease impiden publicar
dos veces el mismo resultado.

## Activación futura

Antes de cambiar `GEMINI_WORKER_ENABLED=true` se requiere una revisión explícita
de privacidad, condiciones del proveedor, retención, región, precios y límites.
No deben usarse bibliotecas, reseñas, notas o teorías reales en una prueba remota
sin esa autorización. Para una ejecución separada, una vez aprobada, existe:

```powershell
python -m scripts.run_gemini_worker
```

`--once` reclama como máximo un trabajo. Las pruebas automatizadas inyectan un
proveedor simulado y no construyen el cliente real.
