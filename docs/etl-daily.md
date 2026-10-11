# ETL diario de LibrIA

Entrega: 2026-10-10. Transformación: `daily-v1`. El catálogo completo permanece como hoja de ruta; esta entrega implementa los indicadores diarios que tienen fuentes verificables. Los hechos e indicadores personales en `analytics` son privados: no son un conjunto anonimizado para consumo grupal.

**Ampliación actual:** [reseñas normalizadas](reviews.md) incorpora `daily-v2` para los siguientes cierres: S02 por primera publicación, `hechos_resenas` al corte y preparación técnica restringida de S01. Los cierres existentes `daily-v1` se conservan sin reejecutarlos. La afirmación de reseñas pendientes en el alcance original siguiente corresponde a la etapa inicial; el nuevo contrato y sus escenarios están implementados. El consumo grupal continúa deshabilitado.

**Consumo actual:** [interpretaciones con Ollama](ai-interpretations.md) conecta ADN lector y habilita Pulso de la comunidad mediante publicaciones generales con umbrales, redondeo y corte fijo diario. La preparación privada por obra permanece restringida; las referencias siguientes a consumo grupal deshabilitado describen las etapas anteriores.

## Catálogo implementado

| ID | Pregunta / público | Fórmula y grano | Fuente y límite |
|---|---|---|---|
| L02 | ¿Cuántas incorporaciones registré? / titular | Entradas creadas por titular y día local. | `entradas_biblioteca.created_at`; una relectura no crea otra incorporación. En legado puede ser la fecha de creación al iniciar lectura, sin recuperar el clic original. |
| L04 | ¿Cuántos intentos inicié explícitamente? / titular | Conteo de eventos válidos `start` por día. | `eventos_lectura`, fecha coincidente con `lecturas.started_at`. No se reconstruyen inicios desde posts antiguos. |
| L05 | ¿Cuántos intentos finalicé? / titular | Conteo de eventos válidos `finish` por día. | Evento coincidente con `finished_at`, página igual al total. Cuenta intentos, no obras distintas. |
| L06 | ¿Cuántos intentos abandoné? / titular | Conteo de eventos válidos `abandon` por día. | Evento coincidente con `abandoned_at`. No se copia motivo privado. |
| L09 | ¿Registré actividad lectora ese día? / titular | 1 si hay inicio, avance, finalización o abandono válido; 0 en fila elegible sin esos eventos. | Eventos; excluye correcciones técnicas. Sumar días, nunca posts del feed. |
| L10 | ¿Cuánto cambió mi posición registrada? / titular | Suma de `page - previous_page` en avances, correcciones y finalizaciones. | La página previa viene en el evento y puede quedar fuera del día. Correcciones pueden restar; no equivale a páginas efectivamente leídas. |
| S03 | ¿Cuántas publicaciones manuales hice? / titular de perfil personal | Conteo de publicaciones válidas por día; subtipo conservado en hechos. | `publicaciones`, solo `community/event` con perfil y subtipo válidos. Excluye reseñas y avances. No atribuye contenido organizacional al análisis personal del ejecutor. |

Los indicadores separan procedencia: `simulated` identifica entidades del manifiesto; `unclassified` indica origen real/ficticio desconocido. `operational` queda reservado a origen real acreditado y no se asigna automáticamente. Los ceros describen las fuentes válidas extraídas; no acreditan actividad histórica ausente del nuevo registro. Un titular sin hechos elegibles no recibe ceros inventados.

S01/S02 requieren normalizar reseñas. L01/L03/L08 necesitan un contrato de estado al corte: no se usa estado actual como histórico. Cohortes, emociones, recomendaciones y paneles comerciales quedan pendientes. Ningún análisis grupal se habilita antes de validar anonimización, grupos pequeños y cruces.

## Modelo analítico

| Tabla en analytics | Granularidad / uso |
|---|---|
| `ejecuciones_etl` | Una fila por día cerrado, corte, estado, versión, intentos y resumen técnico. Ejecuciones legadas sin fecha se conservan y no aparecen como cierres diarios. |
| `catalogo_obras` | Obra por ejecución, título normalizado. Metadatos actuales de obras creadas antes del corte; no es historial bibliográfico. |
| `hechos_lectura` | Evento por ejecución, obra, edición y titular; paginación verificable. Sin nombres, textos ni motivos. Información personal restringida. |
| `hechos_publicaciones` | Publicación manual por ejecución, perfil y ejecutor; sin cuerpo ni imágenes. Preparación restringida. |
| `indicadores_personales` | Titular–indicador–procedencia–ejecución, definición versionada. |
| `validaciones_etl` | Regla por ejecución, gravedad y cantidad excluida; sin filas identificables. |

`app.procedencia_demo` registra las entidades ficticias en el origen. No se entrega su mapa a un conjunto grupal. Las tablas nuevas revocan acceso de `PUBLIC`; la cuenta técnica configurada sigue accediendo a preparación privada. Los permisos de usuarios de la aplicación se comprueban en backend; no se afirma aislamiento frente a quien posea las credenciales técnicas de PostgreSQL.

## Cierre diario y recuperación

Horario: 00:00 de `America/Santiago`. El programador del servidor detecta el cierre aproximadamente dentro de 30 segundos y procesa el día anterior completo, intervalo `[00:00, 00:00 siguiente)` convertido a UTC con cambios de hora.

El intervalo se construye con dos fechas locales, no sumando 24 horas. Si el reloj vuelve a las 23:00, esa hora repetida sigue perteneciendo al día abierto: el cierre espera la medianoche posterior al retroceso e incluye ambas ocurrencias. El día puede durar 25 horas; al adelantar el reloj puede durar 23. Incluso si Windows dispara antes de tiempo o repite su disparo, el cargador rechaza días abiertos y no vuelve a publicar fechas completadas. Hay pruebas específicas del retroceso y del disparo anticipado.

Una restricción única por fecha y un bloqueo asesor compartido impiden cargas concurrentes o una segunda publicación del día. Repetir una fecha exitosa retorna `already_completed` sin extraer ni escribir hechos. Un fallo puede reintentarse: conserva la ejecución e incrementa intentos. Se garantiza una sola **carga exitosa**, no una sola tentativa si falla el proceso.

Extracción y publicación comparten una transacción `REPEATABLE READ`. Un fallo revierte toda la carga; el registro de ejecución queda `failed`. Si un proceso se interrumpe, el siguiente recupera `running` cuando su bloqueo ya fue liberado. El éxito se publica después de conciliar filas preparadas y escritas.

FastAPI mantiene el programador activo por defecto. Con el servidor apagado no se ejecuta: al iniciar recupera cierres pendientes desde la primera carga. `ANALYTICS_SCHEDULER_ENABLED=false` desactiva los cierres automáticos para pruebas u otro planificador. El cargador diario rechaza el día abierto; las cargas manuales de la pantalla utilizan instantáneas independientes, descritas abajo.

En este equipo también se registró la tarea de Windows `LibrIA-ETL-Diario`, a las 00:00 en la zona de Santiago. Ejecuta el mismo cargador con directorio de trabajo `apps/backend`, aunque la aplicación esté cerrada. No guarda contraseñas: requiere que la cuenta tenga sesión iniciada y que PostgreSQL esté disponible. Si el equipo estuvo apagado, `StartWhenAvailable` recupera la ejecución. Se puede registrar en otra instalación con `scripts/register-etl-task.ps1`. Ambos programadores comparten el bloqueo y la unicidad: no producen dos cargas del mismo día.

La inicialización histórica es explícita. Un cierre exitoso es inmutable; importaciones retrospectivas posteriores necesitan un futuro procedimiento de rectificación versionada. No se incorporan silenciosamente a una fecha ya completada.

Desde `apps/backend`:

```powershell
.\.venv\Scripts\python.exe -m alembic upgrade head
.\.venv\Scripts\python.exe -m scripts.seed_analytics_demo
.\.venv\Scripts\python.exe -m scripts.run_etl --from-date 2026-09-21
.\.venv\Scripts\python.exe -m scripts.run_etl
```

La carga histórica prepara una vez cada fecha cerrada. Sin argumentos solo se recuperan pendientes. `--date YYYY-MM-DD` procesa/comprueba una fecha individual y también impide duplicarla. El generador continuo no se usa como conjunto de validación.

## Limpieza, escenarios y acceso

Se validan título, obra–edición–biblioteca, propiedad, paginación, transición y fechas del evento. En publicaciones: fuente, subtipo, perfil y autoría personal. Reseñas sin modelo normalizado, avances del feed antiguo, perfiles ausentes y contratos inválidos se excluyen con motivos contados, sin modificar origen. No se copian emails, credenciales, textos ni motivos privados.

`scripts/analytics_demo.json` fija versión, namespace, fechas y resultados esperados. Cinco intentos cubren finalización, relectura en otra edición, abandono, nuevo intento con corrección hacia atrás y pendiente sin paginación. Hay 13 eventos privados, dos publicaciones manuales y una reseña legada excluida. La carga finita y transaccional usa IDs estables; repetir no duplica y una discrepancia detiene la operación sin sobrescribir. Solo funciona en desarrollo.

`/admin/etl` muestra último cierre, próxima ejecución, historial, cantidades, simulaciones y validaciones. Backend exige `AccountPermission(admin)`: la etiqueta de rol no basta. No expone historiales personales. `GET /api/analytics/me` toma el titular exclusivamente de la sesión; no admite ID ajeno. Todas estas respuestas usan `Cache-Control: no-store`.

Validación de entrega: 50 pruebas de backend, ESLint y build del frontend. Incluye resultados del manifiesto, repetición, días de 23/25 horas, rechazo de disparo anticipado durante la hora repetida, rechazo de día abierto, exclusiones, concurrencia entre conexiones, rollback, reintento, detección de cierres intermedios fallidos y permisos.

Referencias técnicas: [bloqueos asesores de PostgreSQL](https://www.postgresql.org/docs/17/explicit-locking.html#ADVISORY-LOCKS) y [zonas horarias de Python](https://docs.python.org/3/library/zoneinfo.html). `tzdata` está declarada para Windows.

## Ejecución manual desde la web

El administrador abre `/admin/etl` y pulsa **Ejecutar ETL ahora**. `POST /api/analytics/admin/etl/run` exige permiso administrativo de cuenta y recibe `{ "request_id": "UUID" }`. Responde 202 y persiste la solicitud antes de iniciar el trabajo en segundo plano. Repetir el mismo identificador consulta esa ejecución y no vuelve a cargar. Una nueva solicitud mientras otro ETL está activo responde 409.

Cada ejecución manual procesa desde la medianoche local de hace 29 días hasta el instante de solicitud, en UTC: incluye el día actual y usa el mismo extractor, transformador, validaciones y publicador del ETL diario. La revisión de reseñas respeta el corte. El origen no se modifica. Los estados de origen sin historial versionado no se reconstruyen retrospectivamente.

La solicitud tiene `run_kind='manual'`, `business_date=NULL`, `requested_by` y `phase`: `queued`, `extracting`, `transforming`, `loading`, `completed` o `failed`. La pantalla actualiza cada dos segundos mientras hay un proceso activo y muestra intervalo, identificador, filas extraídas/cargadas/excluidas y reglas de validación. Una ejecución rápida puede pasar por las etapas entre dos consultas; el resultado final conserva sus cantidades, sin demoras artificiales.

La extracción completa usa una transacción `REPEATABLE READ`; los datos preparados quedan en memoria y se publican juntos en otra transacción atómica. Se comparte el bloqueo asesor con los cierres diarios. La conciliación y el estado exitoso se publican en la misma transacción que los hechos: un fallo no deja filas parciales. Las solicitudes interrumpidas se recuperan cada cinco segundos con su identificador e intervalo original; este recuperador funciona incluso si la programación diaria está desactivada y necesita la API encendida. La tarea de Windows continúa ejecutando solamente cierres diarios.

Las instantáneas manuales **sí escriben** en las tablas `analytics.catalogo_obras`, `hechos_lectura`, `hechos_publicaciones`, `hechos_resenas`, `indicadores_personales`, `preparacion_valoraciones_obras` y `validaciones_etl`, vinculadas a su ejecución. Dos cargas manuales distintas pueden representar las mismas fuentes en cortes diferentes. Los totales del administrador suman instantáneas y no son conteos de entidades únicas. Los paneles personales y la detección de cierres pendientes usan exclusivamente `business_date` no nulo, evitando sumar datos manuales y diarios. L09 de una instantánea manual señala actividad en el intervalo; no debe interpretarse como número de días activos ni sumarse al indicador diario.

Para comprobar la carga ante el comité, usar el ID mostrado por la web:

```sql
SELECT id, run_kind, status, phase, period_start, source_cutoff_at, summary
FROM analytics.ejecuciones_etl
WHERE id = '<ID mostrado por la web>'::uuid;

SELECT source_id, event_kind, page, total_pages
FROM analytics.hechos_lectura
WHERE etl_run_id = '<ID mostrado por la web>'::uuid;

SELECT rule_code, severity, affected_rows
FROM analytics.validaciones_etl
WHERE etl_run_id = '<ID mostrado por la web>'::uuid;
```

Los datos simulados existentes permiten demostrar inclusiones y exclusiones sin cargar otro conjunto. La consulta SQL corresponde a la cuenta técnica; la web muestra solo cantidades y reglas, sin historiales de otras personas.

Comprobación local de entrega: solicitud HTTP real `7f0d2863-eda0-4e18-80cc-2b800d7e4576`, completada; se verificaron directamente en PostgreSQL 36 obras, 13 eventos de lectura, 523 publicaciones, 7 reseñas, 88 indicadores y 6 reglas para ese ID, con 353 exclusiones. Los cierres diarios anteriores permanecieron intactos. El generador sigue activo, por lo que las cantidades de solicitudes futuras pueden cambiar. Pasaron 69 pruebas de backend, ESLint y compilación del frontend.
