# Informe de implementación — 29 de octubre de 2026

## 1. Diagnóstico anterior

Finalizar o abandonar una lectura creaba directamente un trabajo ejecutable,
con treinta minutos de espera. No exigía reseña textual. Actualizar manualmente
podía adelantarlo y existía regeneración forzada administrativa. La evidencia
se extraía al ejecutar el worker; los cambios durante la generación provocaban
reintentos. Faltaba una separación persistente entre solicitud y autorización
nocturna, y las referencias eran globales para el resultado.

## 2. Backend implementado

El servicio `reading_analysis.py` centraliza elegibilidad, normalización, huella,
reutilización y estados del análisis individual. Exige lectura terminal activa y
una reseña personal textual de su obra resuelta. Acepta reseñas privadas tanto
en borrador como ocultas del mural. Las puntuaciones solas no bastan. No aplica
el mínimo de diez libros.

Se conservaron notas, teorías, cuaderno, reflexiones, valoraciones, fechas,
páginas y contexto bibliográfico. La huella no depende del orden de las unidades,
del número de revisión, de cambios de visibilidad ni del contador global de
identidad del catálogo. Incluye identidad resuelta y versión de contrato; la
reutilización también exige proveedor, modelo y prompt compatibles.

GET y «Actualizar estado» recuperan PostgreSQL sin crear generaciones. Existe
historial privado del evento y un endpoint de reintento limitado. Las rutas
siguen autorizando al propietario en backend y enviando `Cache-Control: no-store`.

## 3. Frontend implementado

La biblioteca muestra el análisis aunque no exista una puntuación numérica.
Explica la necesidad de reseña, espera nocturna, preparación, generación,
actualización y error con mensajes de lechuzas. Permite ir al formulario de
reseña y consultar versiones anteriores. Muestra las fuentes de cada observación.

Mientras se actualiza conserva la interpretación anterior, identificada como
«Actualización pendiente». Los cambios locales de reseña, cuaderno, notas,
teorías y estado refrescan la consulta sin desmontar el análisis. No sondea
durante la espera nocturna. No ofrece «Analizar ahora» en el análisis individual.
El reintento explícito también espera la próxima ejecución del ETL y desaparece al agotarse intentos.

## 4. ETL y Gemini

Los cambios operacionales registran solicitudes transaccionales por evento y
obra, incluyendo sus alias canónicos. Cambiar otro libro no posterga la solicitud.
Los cambios bibliográficos pertinentes también participan del control de corte;
portadas y otros cambios visuales no forman parte de la huella.

La publicación diaria o manual administrativa del ETL prepara trabajos e instantáneas. Se mantiene
el horario de Santiago y su corte exclusivo; una modificación posterior espera
el próximo ciclo automático o manual. El ETL no consulta Gemini ni espera al proveedor.
Las proyecciones incrementales no habilitan estos trabajos.

El worker existente consume la instantánea autorizada. Revalida elegibilidad y
huella antes de generar y elegibilidad antes de guardar. Si cambia evidencia
durante la generación, la versión original puede quedar histórica; la API no
la presenta como actual para una huella distinta. Una fuente retirada impide
publicar y retira instantáneas y derivados afectados, incluidos resúmenes de
fragmentos individuales. Los contadores de intentos y consumo no se reinician.

## 5. Migración

Se creó y aplicó en desarrollo `0069_nightly_book_analysis`, sobre la revisión
0068. Agrega solicitudes e instantáneas privadas, índices y disparadores;
adapta la unicidad de los trabajos para distinguir versiones de evidencia y
retira los disparadores antiguos de consolidación de treinta minutos.

No elimina libros, reseñas, análisis existentes ni métricas de consumo.
La cadena completa de migraciones se ejecutó en PostgreSQL temporal. La base
de desarrollo quedó en `0069_nightly_book_analysis (head)`.

## 6. Estados y mensajes

Se implementaron `not_eligible`, `requires_review`,
`waiting_nightly_processing`, `queued`, `processing`, `completed`,
`update_pending`, `update_processing` y `failed`. Se derivan de elegibilidad,
huellas, trabajos y resultados; no se creó una infraestructura de ejecución
paralela. Los textos completos y las reglas están en
[el contrato funcional](nightly-book-analysis.md).

## 7. Pruebas y resultados

| Verificación | Resultado |
|---|---|
| Suite aislada completa: análisis, refresco privado, worker, optimización, recomendaciones, ETL y políticas de catálogo | 112 pruebas aprobadas |
| Verificación posterior del ajuste de privacidad y worker | 51 aprobadas: 27 de la nueva política y 24 del worker |
| Contratos del worker, proveedor Gemini simulado y legado deshabilitado | 23 aprobadas |
| Mensajes y política de sondeo del frontend | Aprobados |
| Render del resultado persistido durante actualizaciones y errores | Aprobado |
| `npm run build` | Aprobado |
| `npm run lint` | Aprobado |
| `git diff --check` | Aprobado |
| Alembic en PostgreSQL temporal y actualización de desarrollo | Aprobados |

Las ejecuciones se superponen: no se suman como pruebas distintas. La suite
completa cubre, entre otros, reserva mensual concurrente, límites acumulados,
recuperación de leases, concurrencia de workers y reutilización de ADN y
recomendaciones. La nueva política verifica relecturas, edición opcional,
resolución canónica, cambios durante generación, eliminación de fuentes,
reversión de contenido, consolidación y ejecución real del ETL con datos sintéticos.

El proyecto usa JavaScript y no tiene una comprobación de tipos independiente
configurada. No se agregó un comprobador ni dependencias nuevas. Las pruebas
de interfaz son de estados y renderizado; no constituyen una prueba visual
completa en todos los navegadores.

## 8. Problemas detectados y corregidos

Se corrigieron la generación sin reseña, la posibilidad de saltarse el cierre,
la pérdida de asociación al evento al consultar, la ausencia de citas por
observación, el tratamiento de reseñas ocultas como si no fueran evidencia
privada válida, y el desmontaje del resultado visible al editar fuentes.

Se adaptaron pruebas anteriores que exigían la política sustituida de espera
fija y generación forzada. También se precisó una comprobación estática antigua
de recomendaciones: la lectura de estado no hace POST; su botón explícito de
sincronización existente sí puede hacerlo. No se cambió ese comportamiento.

El ejecutor de pruebas usa un clúster PostgreSQL temporal en loopback porque la
cuenta de desarrollo no tiene permiso `CREATEDB`. El clúster se detiene al
terminar y no instala servicios del sistema. Se corrigió el cierre del ejecutor
en Windows y se aislaron los datos entre suites con fechas sintéticas distintas.

## 9. Límites prácticos

Validar un identificador de evidencia no demuestra que el texto respalde
semánticamente la afirmación. El prompt exige prudencia y reconoce insuficiencia,
pero no se presenta una garantía semántica inexistente.

No se evaluó la calidad de una respuesta real de Gemini: deliberadamente se
usaron proveedores simulados. La entrega final del modelo depende de la
configuración y disponibilidad operativas existentes; no se promete una hora.
La compilación conserva el aviso no bloqueante de un paquete mayor de 500 kB.

## 10. Archivos de este evolutivo

- `README.md`, `apps/backend/README.md`.
- `apps/backend/app/modules/analytics/reading_analysis.py`.
- `apps/backend/app/modules/analytics/adaptive_router.py`.
- `apps/backend/app/modules/analytics/etl.py`.
- `apps/backend/app/modules/analytics/models.py`.
- `apps/backend/app/modules/analytics/gemini_worker.py`.
- `apps/backend/app/modules/analytics/gemini_prompts.py`.
- `apps/backend/app/modules/analytics/gemini_contracts.py`.
- `apps/backend/app/modules/library/commands.py` y `router.py`.
- `apps/backend/migrations/versions/0069_nightly_book_analysis.py`.
- `apps/backend/scripts/test_nightly_reading.py`.
- `apps/backend/tests/test_nightly_reading_analysis.py`.
- `apps/backend/tests/test_private_analysis_refresh.py`.
- `apps/backend/tests/test_stage5_gemini_worker.py`.
- `apps/backend/tests/test_gemini_optimization.py`.
- `apps/backend/tests/test_ai_recommendations.py`.
- `apps/web/src/components/AdaptiveAnalysis.jsx`.
- `apps/web/src/components/BookExperience.jsx`.
- `apps/web/src/components/bookAnalysisState.js`.
- `apps/web/src/pages/LibraryBookPage.jsx`.
- `apps/web/tests/book-analysis-state.mjs` y `book-analysis-render.mjs`.
- `docs/nightly-book-analysis.md` y este informe.
- `docs/adaptive-reader-ai.md`, `docs/analytics-pipelines.md` y
  `docs/gemini-stage6-production-readiness.md`.

Los cambios preexistentes de cuentas, autenticación y otras pantallas se
conservaron. No se atribuyen a este evolutivo.

## 11. Regresiones y rama

Las pruebas de ADN, recomendaciones, presupuesto y políticas de catálogo
continúan pasando. Sus reglas de activación no fueron modificadas. El trabajo
se realizó directamente en `Nicole`, sin crear ramas y sin hacer commit.

## 12. Credenciales y consumo

No se modificó `.env`, credenciales, facturación, presupuesto ni activación de
servicios. No se realizaron solicitudes reales a Gemini ni se consumieron
tokens reales durante las pruebas. Los tokens registrados en las bases
temporales proceden exclusivamente de dobles de prueba.

## Corrección posterior: ETL manual

Se amplió la habilitación al ETL manual administrativo, además del automático
de las 00:00. El filtro anterior exigía fecha de cierre diario y excluía las
instantáneas manuales. Ambos caminos ahora preparan los análisis según su
propio corte; la proyección incremental continúa sin habilitarlos. Se ajustaron
los mensajes para explicar las dos opciones. No requiere otra migración.

La verificación de esta corrección aprobó 44 pruebas de backend e integración,
incluidas tres nuevas de preparación manual, idempotencia, ejecución posterior
del modelo simulado, corte y conservación del resultado anterior. También
aprobaron estados y render del frontend, lint y compilación, sin Gemini real.

## Corrección posterior: transporte Gemini y recuperación operativa autorizada

Con Gemini habilitado por autorización posterior del usuario, el proveedor
rechazó el esquema individual anterior con HTTP 400. Se redujo su gramática de
transporte, se incorporaron identificadores de evidencia permitidos y se publicó
el prompt `reading-event-v3-es`. Cada hallazgo recibe texto y citas juntos;
LibrIA construye los índices del contrato persistido sin pedir al modelo que
sincronice listas paralelas. Los límites y la validación local se conservan.

La interfaz distingue un primer análisis de un reintento registrado después de
un fallo. La recuperación usa los trabajos, solicitudes y ETL existentes;
conserva intentos anteriores, versiones y consumo. Se verificó la generación y
persistencia reales del libro afectado y se dejó el worker activo para la cola.

La corrección aprobó 70 pruebas aisladas de análisis, ETL y worker, además de
27 pruebas rápidas de contratos/proveedor. Estados, render, lint y compilación
del frontend aprobaron. Las pruebas automatizadas usan dobles; la ejecución
real correspondió a la recuperación operativa expresamente autorizada.
