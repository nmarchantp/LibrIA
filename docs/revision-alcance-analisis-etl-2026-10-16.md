# Revisión del alcance de Análisis y ETL

Este informe registra el estado **anterior** a la implementación solicitada tras
la revisión. La implementación posterior y sus límites están documentados en
[Motor de datos e inteligencia](analytics-pipelines.md).

Fecha: 16 de octubre de 2026. Referencia: documento del usuario «Alcance definitivo del módulo de Análisis y ETL — Motor de Datos e Inteligencia».

Revisión estática de código, migraciones y pruebas existentes. No constituye una comprobación de configuración de producción ni de calidad de todas las inferencias de Ollama. No se modificó la implementación durante esta revisión.

## Dictamen

Cumplimiento parcial. Hay catálogo normalizado, ETL diario/manual, evidencia personal, agregados protegidos y análisis personales separados por libro y biblioteca. Faltan el recorrido analítico único, el procesamiento de interacciones sociales y gran parte de los indicadores comunitarios propuestos.

## Arquitectura efectiva

- Catálogo: Google Books → persistencia en `app` → respuesta construida desde la base local. La ingesta se realiza durante consultas; no es un pipeline programado independiente.
- Analítica: `app` → `etl.py` y `reader_evidence.py` → `analytics` → métricas e interpretaciones de Insights. Estas interpretaciones se guardan en `analytics.interpretaciones_ia`.
- Análisis adaptativo: `app` + correcciones en `ia` → Ollama → `ia.analyses`, con trabajos y referencias de evidencia en `ia`. Este recorrido no pasa por el ETL.
- Recomendaciones: biblioteca, valoraciones y catálogo en `app` + indicadores en `analytics` + perfil en `ia` → Ollama. Tampoco consume exclusivamente la capa analítica.

Fuentes: `apps/backend/app/modules/books/router.py`, `apps/backend/app/modules/analytics/{etl,reader_evidence,insights,adaptive_ai,recommendations}.py`.

## Los cinco pipelines

| Pipeline | Estado | Evidencia y diferencia |
|---|---|---|
| ETL-01 Catálogo | Parcial | Google Books, obras/ediciones, normalización y consolidación existen. La ingesta está integrada en rutas de búsqueda/detalle, no en un proceso independiente. |
| ETL-02 Lecturas | Parcial | Eventos, reseñas, valoraciones, reflexiones, notas, teorías y cuadernos llegan a analytics. Faltan distribuciones por género y evolución de afinidades/géneros. |
| ETL-03 Social | Pendiente en su alcance principal | Se extraen publicaciones, pero no seguimientos, comentarios ni reacciones. Esas entidades existen en app. Las recomendaciones no las reciben. |
| ETL-04 Comunidad | Parcial | Hay agregados globales de actividad y valoraciones con umbrales de privacidad. No están los rankings y tendencias completos del documento. |
| IA-01 Interpretación | Parcial | Libro valorado y perfil global separados, correcciones y versiones. El análisis adaptativo consulta app directamente. Coexiste con interpretaciones antiguas guardadas en analytics. |

## Indicadores comunitarios

| ID | Estado | Observación |
|---|---|---|
| IND-001 | Pendiente | No hay ranking por obra basado en lectores únicos que terminaron. |
| IND-002 | Pendiente | No hay ranking por obra basado en lectores únicos que abandonaron. |
| IND-003 | Pendiente | No hay tasa de abandono con cohorte y período comparables. |
| IND-004 | Pendiente | No hay distribución de finalizaciones por género con política de ponderación. |
| IND-005 | Pendiente | No hay comparación de participación de géneros entre períodos. |
| IND-006 | Parcial | Se almacena promedio y distribución por obra en analytics; falta ranking comunitario con mínimo de valoraciones. |
| IND-007 | Pendiente | Los seguimientos no se agregan en el ETL. |
| IND-008 | Pendiente | Los comentarios y reacciones no se agregan por obra. |
| IND-009 | Parcial | Hay inicios y finales por período; se cuentan intentos/eventos, no los rankings de lectores únicos anteriores. |
| IND-010 | Pendiente | Tener cortes diarios no implementa comparaciones de tendencias entre períodos. |

## Reglas RN-ETL-015 a RN-ETL-027

| Regla | Estado | Observación |
|---|---|---|
| 015 | Pendiente | No se incorporan señales sociales complementarias al motor. |
| 016 | Sin integración que verificar | Hoy no se usan seguimientos para inferir gustos; falta garantizar la distinción al incorporarlos. |
| 017 | Sin integración que verificar | Hoy no se usan reacciones como valoraciones; falta el pipeline social que preserve esa semántica. |
| 018 | Parcial | Correcciones y preferencias explícitas tienen prioridad en los prompts y la invalidación; no hay señales sociales contradictorias integradas que contrastar. |
| 019 | Parcial | Identidad de obra/edición y valoraciones por obra existen; los indicadores comunitarios propuestos aún no están completos. |
| 020 | Parcial | Hay etiquetas, unidades, versiones y períodos de métricas actuales. No están definidas e implementadas todas las métricas propuestas y sus cohortes. |
| 021 | Parcial | Los agregados actuales tienen mínimo de 10 participantes, mínimo de 5 contribuyentes por métrica, redondeo y límites. El acceso grupal está restringido a ciertos perfiles profesionales, no a todos los usuarios. No hay dashboard público completo. |
| 022 | Implementada en las cargas actuales | Identificadores de fuente, fechas, ejecuciones ETL y versiones; también referencias de evidencia y versiones en ia. Falta enlazar el análisis adaptativo a una ejecución ETL porque la omite. |
| 023 | Parcial | Los cambios personales encolan invalidaciones/análisis en ia. Los agregados analytics se actualizan por cortes diarios/manuales, no por entidades afectadas; interacciones sociales no se procesan. |
| 024 | Parcial | Hay cargas reconstruibles por corte y carga manual. Un día exitoso se omite en run_day; no existe reconstrucción general selectiva de agregados históricos corregidos ni historial completo de todas las fuentes. |
| 025 | Implementada para la integración externa activa | Google Books es el proveedor bibliográfico externo invocado; existe compatibilidad con registros locales/legados libria-feed. |
| 026 | Implementada como base de identidad | Obras, ediciones y consolidación física con validaciones de identidad en ETL. No garantiza identificar perfectamente toda traducción posible. |
| 027 | Implementada en el flujo actual | Las recomendaciones se apoyan en valoraciones propias de 4/5 y el perfil; no derivan gustos personales exclusivamente de popularidad global. |

## Decisiones pendientes

1. Unificar la fuente de IA: proyectar la evidencia completa de cada lector y obra a analytics; hacer que el análisis individual y el global consuman esa proyección, con corte/revisión y trazabilidad ETL. Mantener los dos alcances separados.
2. Procesar seguimientos, comentarios y reacciones con su contexto: tipo de perfil seguido, destino de interacción, obra/edición y contenido. Una reacción a una crítica negativa no expresa gusto por el libro.
3. Fortalecer el vínculo de publicaciones con obras: existe book_ref textual; notas y teorías exigen actualmente una resolución no ambigua al catálogo. Comentarios de reseñas sí pueden llegar a una obra mediante review_id.
4. Definir lectores únicos, cohortes, mínimo de muestras y distribución de obras multigénero antes de publicar los indicadores IND-001 a IND-010.
5. Añadir actualización selectiva y reconstrucción explícita de agregados afectados; la cola IA actual no equivale a un ETL incremental.
6. Decidir si Insights comunitario se ofrece a todo usuario o mantiene el acceso profesional actual. Aplicar privacidad a cada nuevo desglose.

## Entregas

- Entrega 1: avanzada, pero incompleta respecto del recorrido ETL → analytics → IA. La disponibilidad de modelos y su tiempo de respuesta siguen siendo una limitación operativa conocida.
- Entrega 2: parcial; existen interacciones transaccionales y agregados básicos, pero falta llevar esas interacciones al motor analítico y de recomendaciones.
- Entrega 3: pendiente en sus elementos principales: tendencias por género, afinidades entre lectores y dashboard avanzado.

No se encontraron pipelines de clics o permanencia en el feed dentro del módulo analítico revisado, ni dependencias de Spark, Kafka o Airflow en este recorrido.
