# Interpretaciones individuales y grupales con Ollama

> Archivo histórico. Sus instrucciones de instalación y generación no deben ejecutarse en etapa 6.

Entrega: 2026-10-10. Proveedor elegido: **Ollama local**, modelo configurable `qwen3:1.7b`. Los indicadores no se envían a un proveedor externo. El backend consulta la API de Ollama por loopback; el navegador conversa únicamente con LibrIA. No se requiere una clave de API.

## Pantallas y permisos

- **Tu ADN lector → Mis análisis** (`/profile?tab=analysis`): indicadores propios e interpretación iniciada por el titular. Sustituye el texto y porcentajes de emociones que anteriormente eran demostrativos.
- **Pulso de la comunidad** (`/community-insights`): sección nueva para quien tenga la capacidad `autor` en su perfil personal o sea miembro de una organización `editorial`/`libreria`. Perfiles suspendidos o rechazados no conceden acceso. La etiqueta `User.role` y el permiso administrativo de cuenta, por sí solos, no conceden acceso grupal. Backend revisa permisos en cada solicitud.
- Se elige procedencia: `simulated` (ficticia), `unclassified` (origen sin acreditar) u `operational` (real acreditada). Nunca se mezclan para completar un grupo ni se presenta un escenario ficticio como comportamiento real.

## Evidencia e interpretación

Las consultas de evidencia leen exclusivamente las tablas limpias de `analytics`. Las tablas de perfiles y miembros de `app` se consultan para autorización. Se usa la ejecución exitosa con el corte más reciente: si es manual, una sola instantánea; si es diaria, hasta treinta cierres anteriores, sin mezclar instantáneas manuales y diarias. Las reseñas se toman una sola vez desde el último corte, evitando sumar múltiples versiones diarias. La pantalla informa origen y fechas.

La interpretación personal filtra el titular desde la sesión. Los conteos utilizan `indicadores_personales`; los días activos se recalculan como fechas locales distintas de los hechos de lectura válidos, evitando confundir el L09 binario de una carga manual con número de días. El promedio personal considera valoraciones no nulas de reseñas publicadas al último corte. No se envían nombres, IDs personales, correos, textos de reseñas, motivos privados, títulos de libros ni imágenes al modelo.

La IA recibe métricas numéricas y sus etiquetas, período y procedencia. Produce título, resumen, observaciones vinculadas a métricas, sugerencias y limitaciones. El backend valida la estructura, longitud y referencias de evidencia; las cifras narradas deben existir en las métricas proporcionadas (además del máximo de la escala de valoración). No se aceptan porcentajes o cantidades nuevas calculadas por el modelo. Las tarjetas y referencias de evidencia muestran valores provenientes directamente del ETL. Esto reduce errores numéricos, pero no garantiza que el modelo asocie correctamente cada cifra en su narrativa ni que una interpretación verbal sea correcta: la pantalla lo indica.

No hay datos de emociones o géneros suficientes para inferirlos. El prompt prohíbe diagnósticos, rasgos de personalidad, causalidad, preferencias de género, ventas, pronósticos y porcentajes de finalización derivados de conteos de intentos. El cambio de posición de página no equivale a páginas efectivamente leídas. Sugerencias se presentan como opciones, no conclusiones demostradas.

## Publicación grupal protegida

El conjunto general requiere al menos **diez participantes distintos** de la misma procedencia con eventos de lectura no técnicos o reseñas publicadas. No se muestran tamaños inferiores al umbral. Cada métrica de inicios, finalizaciones, abandonos, reseñas o valoraciones requiere al menos **cinco contribuyentes distintos**; las métricas que no cumplen se omiten, incluyendo ceros de grupos sin contribuyentes.

Los conteos se redondean al múltiplo de cinco más cercano y cada participante aporta como máximo diez eventos/reseñas por métrica. El promedio de valoración da igual peso a cada participante y se redondea a medio punto. No se publican filas individuales, libros, distribuciones por puntuación ni filtros por perfiles, segmentos o períodos personalizados.

El primer conjunto elegible consultado cada día de Santiago se persiste en `analytics.resumenes_grupales` y queda fijo durante ese día, para que nuevas cargas manuales no habiliten consultas sucesivas sobre cortes ligeramente distintos. La IA grupal recibe solo esta publicación agregada. No se expone la preparación técnica por obra `preparacion_valoraciones_obras`.

Estas medidas constituyen una publicación agregada limitada; no se afirma anonimización formal ni privacidad diferencial frente a información externa o comparaciones entre días. Ampliar cohortes, filtros, métricas o exportaciones requiere revisar sus riesgos de identificación. Tampoco se afirma que el conjunto represente el mercado editorial completo.

## Persistencia y disponibilidad

`analytics.interpretaciones_ia` conserva contenido, proveedor, modelo, versión del prompt, fecha y huella de evidencia. Las interpretaciones personales están vinculadas a su titular y solo se consultan mediante su sesión. Las grupales comparten la publicación protegida entre perfiles autorizados. La respuesta usa `Cache-Control: no-store`; la caché del servidor evita repetir inferencias para la misma evidencia.

Un bloqueo por ámbito/titular evita generaciones simultáneas y se limita a una interpretación nueva por minuto. Si cambia la evidencia, se requiere una interpretación nueva; se mantiene la caché de la anterior. Si Ollama está apagado, falta el modelo, la respuesta es incompleta o falla su validación, se informa el error y no se inventa una interpretación ni se guarda un resultado inválido.

La generación se inicia con el botón de la pantalla. El modelo se carga bajo demanda y la primera inferencia puede tardar; el cierre ETL no espera a Ollama. Una interpretación ya guardada permanece consultable aunque el modelo esté temporalmente apagado.

## Instalación y demostración

En este equipo se instaló Ollama y se descargó `qwen3:1.7b`. En otra instalación:

```powershell
winget install --id Ollama.Ollama --exact
ollama pull qwen3:1.7b
```

Configurar en `apps/backend/.env` si se necesitan otros valores:

```dotenv
OLLAMA_BASE_URL=http://127.0.0.1:11434
AI_MODEL=qwen3:1.7b
AI_TIMEOUT_SECONDS=180
```

Ollama debe estar ejecutándose en el mismo equipo que el backend. Solo se permiten direcciones loopback; no se utiliza Ollama Cloud. Aplicar migraciones y reiniciar la API después de cambiar la configuración.

```powershell
# Desde apps/backend
.\.venv\Scripts\python.exe -m alembic upgrade head
.\.venv\Scripts\python.exe -m scripts.seed_group_demo
```

`seed_group_demo` agrega doce participantes ficticios sin credenciales de inicio de sesión, doce intentos, treinta y seis eventos y doce reseñas. Seis intentos finalizan y seis se abandonan. IDs y fechas son estables; repetir no duplica ni sobrescribe. Solo funciona en desarrollo. El conjunto está fechado el 10 de octubre de 2026: demostraciones posteriores necesitan un conjunto actualizado explícitamente, conservando este historial.

Después de cargarlo, un administrador pulsa **Ejecutar ETL ahora**. Un lector demo abre Mis análisis y genera su interpretación. Un autor, miembro de editorial o librería abre Pulso de la comunidad y genera la grupal. Ambas usan evidencia de `analytics`, conservan la marca de simulación y guardan el resultado real de Ollama.

Rutas:

| Método y ruta | Uso |
|---|---|
| `GET /api/analytics/access` | Permisos propios de acceso personal/grupal. |
| `GET /api/analytics/me/insights?provenance=simulated` | Evidencia propia e interpretación vigente, si existe. |
| `POST /api/analytics/me/interpretation` | Generar/recuperar interpretación propia. |
| `GET /api/analytics/group/insights?provenance=simulated` | Publicación general protegida para perfiles autorizados. |
| `POST /api/analytics/group/interpretation` | Generar/recuperar interpretación de esa publicación. |

Los POST admiten únicamente `{ "provenance": "simulated" }` (o las otras procedencias). No aceptan usuario ajeno, perfil objetivo ni SQL.

Referencias oficiales utilizadas: [salidas estructuradas de Ollama](https://docs.ollama.com/capabilities/structured-outputs) y [API de chat](https://docs.ollama.com/api/chat).

## Comprobación de entrega

Se cargó la cohorte ficticia y se ejecutó el ETL manual `876336a4-795e-47fa-a9b9-28e2d8d355f2`. Ollama generó y PostgreSQL conservó la interpretación personal del lector (`1e2db1b4-590c-4ac5-b085-5d8c79a2cee6`, aproximadamente 23 segundos) y la interpretación grupal (`540f17a7-1ace-44c3-adbd-4501daf5f3b3`, aproximadamente 21 segundos). También se inició una interpretación personal mediante el POST real de la API como autor (`3b70ec56-892b-4437-a6b7-694227908524`, aproximadamente 20 segundos).

Las consultas HTTP reales devolvieron el resultado grupal a autor, editorial y librería; lector, influencer y administrador sin capacidad profesional recibieron 403. La lectura personal recuperó únicamente su resultado guardado. Los datos ficticios permanecen identificados y el resumen grupal no contiene identidades individuales. Validación: 86 pruebas de backend, ESLint y build del frontend aprobados.
