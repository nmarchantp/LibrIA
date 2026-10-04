# Catálogo de indicadores de LibrIA

Fecha de revisión: 2026-10-04. Estado: propuesta funcional para revisión, previa al diseño físico y la implementación del ETL.

Este documento define qué preguntas responder, para quién y con qué datos. No crea tablas, permisos ni métricas en ejecución. El [modelo social acordado](social-model.md) prevalece para perfiles, publicaciones, reseñas y avances. Las fuentes actuales se contrastaron con modelos, rutas y migraciones del repositorio; no se auditó una base de datos en ejecución.

La [revisión de brechas transaccionales](transactional-gaps.md) desarrolla el punto 2, con cambios propuestos, dependencias, migración y criterios de aceptación. Detectó que agregar libros en la interfaz todavía no persiste la incorporación: los indicadores de biblioteca afectados quedan condicionados a corregir ese flujo.

## 1. Propósito y públicos

La analítica debe ayudar a las personas a comprender sus lecturas y a autores, librerías y editoriales a interpretar la actividad observada dentro de LibrIA. Los indicadores no representan el mercado editorial completo, ventas ni comportamiento fuera de la plataforma.

| Código | Público | Alcance propuesto |
|---|---|---|
| L | Lector autenticado | Su biblioteca, intentos, progreso, preferencias e historial personal. |
| P | Público de la aplicación | Contenido público visible e indicadores agregados habilitados en fichas de obras. No incluye historiales privados. |
| A | Autor | Agregados de obras vinculadas a su identidad verificada; nunca historiales individuales de lectores. |
| E | Editorial | Agregados de sus ediciones verificadas. No basta coincidir con el texto `publisher_name` para autorizar acceso. |
| B | Librería | Tendencias agregadas generales y desempeño de su contenido. Un catálogo propio requerirá una relación explícita con obras/ediciones. |
| I | Administración interna | Calidad de datos, adopción y funcionamiento del ETL, con permisos internos. |

Los alcances A/E/B son propuestas de producto: el código actual no implementa todos esos perfiles ni las relaciones de propiedad necesarias. La verificación no sustituye la comprobación de permisos. Los filtros y el backend deben respetar el mismo alcance; ocultar elementos en la interfaz no constituye autorización.

### Requisito confirmado: privacidad personal y anonimización grupal

**Los análisis personales son privados y exclusivos de su titular. Todo análisis grupal debe trabajar con datos anonimizados, sin poder identificar a las personas participantes.** Esta regla está confirmada por el usuario y prevalece sobre las propuestas de acceso, granularidad e indicadores de este documento.

- Ningún autor, editorial, librería, otro lector o administrador obtiene acceso al análisis personal de otra persona por su rol. Los permisos se comprueban en el backend, también para exportaciones e historial de análisis.
- La regla grupal se aplica a públicos, actores comerciales, administración interna y análisis con IA. No basta ocultar nombres en el panel: los conjuntos disponibles para análisis grupal tampoco deben permitir identificar participantes.
- Reemplazar nombres por UUID, hashes, alias estables o claves con una tabla de correspondencia es seudonimización, no satisface por sí solo este requisito. No se entregan al análisis grupal identificadores de usuario/perfil participante, claves de sus eventos o contenido, enlaces a perfiles, textos identificables ni trayectorias individuales enlazables.
- Los datos operacionales y el análisis personal necesitan relaciones con el titular. El proceso técnico restringido de preparación puede usarlas para deduplicar, calcular cohortes y generar agregados, pero debe anonimizar su salida **antes** de ponerla a disposición del análisis grupal. Esa preparación no habilita la exploración analítica de personas ni conserva correspondencias en el conjunto grupal.
- El futuro modelo separará el recorrido personal del grupal. El conjunto grupal no tendrá una dimensión de personas ni un camino de consulta hacia el historial personal o las tablas de identidad. Solo admitirá medidas y agrupaciones que superen los controles de anonimización; no habrá desglose hasta individuos.
- Se revisarán combinaciones de atributos, fechas precisas, grupos pequeños, valores excepcionales y cruces con contenido público. Cuando una agrupación pueda revelar a una persona, deberá generalizarse o suprimirse; si no puede protegerse, no se habilita ese análisis.
- La identidad de un autor como atributo bibliográfico o de una organización como objeto del informe no autoriza identificar a lectores, comentaristas u otros participantes del grupo. Que una reseña sea pública no autoriza enlazar a su autor con un historial analítico.

La anonimización es un requisito del diseño pendiente de implementar y verificar; no se afirma que la plataforma actual ya lo cumpla.

## 2. Convenciones del catálogo

**Disponibilidad de la fuente**, no del panel o ETL:

- **D:** existen los campos operacionales básicos. Aún requiere transformación y validación de calidad.
- **C:** existe parte de la información, pero requiere corregir identidad, trazabilidad o reglas operacionales antes de publicar la métrica definitiva.
- **N:** necesita nuevos registros o funciones.

**Prioridad propuesta:** V1 = primer conjunto útil; V2 = ampliación; V3 = funcionalidades nuevas. La prioridad no elimina dependencias: una métrica V1 con estado C sigue bloqueada por su brecha.

En las tablas, `n` es la cantidad de observaciones válidas. Cada indicador conserva su numerador, denominador cuando corresponda, fecha de corte, filtros, versión de definición y ejecución del ETL. Las cantidades propuestas y los umbrales de este documento todavía no son requisitos aprobados.

### Tiempo, población y ausencia de datos

- Intervalos semiabiertos `[inicio, fin)`. Instantes conservados en UTC; días, semanas ISO y meses de presentación calculados en `America/Santiago`. Una semana comienza el lunes.
- Cada fila indica la fecha que ubica el dato en el período. Los estados actuales son fotografías al corte; no se presentan como estados históricos sin eventos o instantáneas que los respalden.
- No hay una única granularidad para toda la analítica. El detalle de intento, evento o contenido corresponde a la fuente y a la preparación restringida o al recorrido personal. El conjunto grupal solo conserva agrupaciones anonimizadas, por día, semana o mes cuando esa precisión sea admisible.
- Sin observaciones: mostrar «Sin datos». Un conteo puede ser cero con extracción completa; un promedio sin observaciones o una división por cero devuelve nulo, nunca cero.
- Comparaciones temporales usan períodos de igual cobertura. Variación: `100 × (actual - anterior) / anterior`; si anterior es cero, mostrar valores absolutos y «Sin base de comparación».
- Usuarios únicos se recalculan sobre todo el período. No sumar únicos diarios para obtener únicos mensuales. Promedios y porcentajes se recalculan desde sus componentes.
- Una relectura es otro intento; una obra distinta se cuenta por `work_id`. Las distintas ediciones no multiplican las obras.
- Roles y metadatos actuales no reconstruyen por sí solos sus valores históricos. El catálogo inicial usa atributos actuales y lo declara; el historial requerirá captura adicional.
- Separar conjuntos simulados de reales mediante procedencia explícita en la futura carga. Todo panel de demostración debe indicar «Datos simulados» y la fecha de referencia del escenario.

## 3. Lectura y biblioteca

Fuentes abreviadas: `LE` = `app.lecturas`, `BI` = `app.entradas_biblioteca`, `PR` = `app.progreso_lectura`, `ED` = `app.ediciones`, `OB` = `app.obras`, `OA` = `app.obras_autores`.

En todas las tablas del catálogo, «Grano y fecha» describe la unidad de cálculo en origen, no una autorización para conservar filas individuales en el conjunto grupal. Todo indicador con varios públicos tendrá una salida personal propia y/o una salida grupal anonimizada, según corresponda. Los conteos de personas distintas y las cohortes se preparan dentro del proceso restringido; al análisis grupal llegan medidas, no listas de participantes.

| ID / indicador y pregunta | Público | Fórmula y unidad | Grano y fecha | Fuente | Estado / prioridad / límite |
|---|---|---|---|---|---|
| L01. Obras guardadas: ¿qué tamaño tiene mi biblioteca? | L | Conteo distinto de `work_id` en entradas no archivadas. Obras. | Usuario–obra al corte. | BI | C / V1. Alta en interfaz aún no persistida; BI se crea con eventos de lectura. No equivale a libros comprados. |
| L02. Incorporaciones: ¿cuántas obras se agregaron? | L; A/E/B agregado | Conteo de entradas creadas en el período, incluyendo las archivadas posteriormente. Entradas y usuarios distintos por separado. | Entrada; `created_at`. | BI | C / V1. Persistir la acción de agregar antes de medirla. Mide primera incorporación conservada; no recupera altas eliminadas ni reincorporaciones sin historial. |
| L03. Intentos por estado: ¿qué está pendiente, activo o cerrado? | L; A/E/B agregado | Conteo por `pending`, `reading`, `finished`, `abandoned`. Intentos. | Intento al corte. | LE + BI | C / V1. La interfaz aún no persiste pendientes al agregar. No atribuir el estado actual a meses anteriores. |
| L04. Inicios: ¿cuántos intentos comenzaron? | L; A/E/B agregado | Conteo de intentos con `started_at` en período; usuarios distintos como medida separada. | Intento; `started_at`. | LE + BI | C / V1. Identificar inicios explícitos frente a los creados automáticamente al registrar otro evento. |
| L05. Finalizaciones: ¿cuántas lecturas se terminaron? | L; P/A/E/B agregado | Conteo de intentos finalizados en período y conteo distinto de obras, ambos visibles y diferenciados. | Intento; `finished_at`. | LE + BI | D / V1. Es finalización declarada por el usuario, no lectura verificada. |
| L06. Abandonos: ¿cuántos intentos se cerraron sin terminar? | L; A/E/B agregado | Conteo de intentos con `abandoned_at` en período. | Intento; `abandoned_at`. | LE + BI | D / V1. No inferir abandono a partir de inactividad. |
| L07. Relecturas: ¿qué obras se vuelven a leer? | L; A/E/B agregado | Intentos iniciados cuando existe un intento anterior terminado de la misma persona y obra; porcentaje sobre inicios elegibles. | Intento; `started_at`. | LE + BI | C / V2. Retomar tras abandono no cuenta como relectura bajo esta definición. Depende de identidad estable de obra e inicio trazable. |
| L08. Progreso vigente: ¿cuánto llevo de cada intento? | L | `100 × current_page / total_pages`, si total positivo. Porcentaje por intento. | Intento al corte. | LE | D / V1. No promediar porcentajes de distintos libros como un avance personal global. |
| L09. Días con actividad lectora registrada: ¿con qué continuidad registro mi lectura? | L | Días locales distintos con inicio explícito, avance, finalización o abandono. | Usuario–día; fecha del evento. | LE + PR | C / V1. Deduplicar eventos; no contar su publicación automática nuevamente. No mide todos los días realmente leídos. |
| L10. Avance neto registrado: ¿cuánto cambió mi posición? | L | Para cada evento, `página actual - página previa`; sumar diferencias del período por intento. Páginas, incluso diferencias negativas si se admiten correcciones. | Evento; `recorded_at`, orden estable por fecha e ID. | PR + LE | C / V2. La página previa puede estar fuera del período; usar cero solo con inicio conocido. No llamarlo páginas efectivamente leídas ni horas de lectura. |
| L11. Tiempo calendario hasta finalizar: ¿cuánto transcurre entre inicio y fin? | L; A/E/B agregado | Mediana de `(finished_at - started_at)` en días, con `n`. | Intento finalizado; `finished_at`. | LE | C / V2. Excluir inicios inferidos, fechas incoherentes y mostrar cobertura excluida. No equivale a tiempo dedicado a leer. |
| L12. Desenlace a 30 días: ¿qué ocurre después de empezar? | A/E/B; I | Para cohorte de inicios maduros, terminados antes de inicio+30d / inicios elegibles; abandonados antes de ese límite / mismo denominador; resto sin cierre en esa ventana. | Intento, cohorte por mes de inicio. | LE + BI | C / V2. Solo incluir inicios con 30 días completos observables y trazables. No dividir finalizaciones del mes por inicios del mismo mes. |
| L13. Punto de abandono: ¿en qué tramo se declara el abandono? | L; A/E/B agregado | Distribución de intentos abandonados por porcentaje alcanzado: [0,25), [25,50), [50,75), [75,100]. | Intento; `abandoned_at`. | LE | D / V2. Usar total del intento y datos válidos; comparar por edición cuando importe la paginación. No inferir capítulo ni causa. |
| L14. Afinidad observada: ¿qué idiomas y autores aparecen en mis lecturas? | L; A/E/B agregado | Intentos finalizados por idioma o autor / intentos finalizados con atributo conocido. Mostrar también cobertura conocida / total. | Intento terminado y atributo; `finished_at`. | LE + ED + OA | D / V1. En coautoría un intento cuenta para cada autor: porcentajes pueden superar 100 % y se debe advertir. Categorías literarias requieren nueva fuente. |

Para rankings comerciales de interés, finalización y abandono se reutilizan L02/L05/L06/L12/L13; no se crea una fórmula distinta por público. Autores con varias obras usan conteos de intentos distintos; editoriales se filtran por la edición del intento. L02 no identifica una edición preferida: no atribuir una incorporación a una editorial solo por existir alguna edición suya.

## 4. Reseñas y comunidad

Las reseñas actuales son filas de `app.publicaciones` con `source='review'`. `book_ref` no reemplaza una FK a obra. El contrato destino es una reseña por perfil y obra; no se deben presentar los registros del prototipo como si ya cumplieran ese contrato.

| ID / indicador y pregunta | Público | Fórmula y unidad | Grano y fecha | Fuente | Estado / prioridad / límite |
|---|---|---|---|---|---|
| S01. Valoración de obra: ¿cómo la valoran quienes opinan? | L/P/A/E/B | Media y distribución 1–5 de calificaciones vigentes de reseñas públicas visibles; `n` reseñas calificadas. | Perfil–obra al corte. | Futuras reseñas normalizadas. | C / V1. Una reseña sin calificación no es cero. No reconstruir evolución del promedio sin historial de ediciones. |
| S02. Nuevas reseñas: ¿cuánta opinión nueva se publica? | L/P/A/E/B | Conteo de primeras publicaciones en período y perfiles distintos. | Reseña; primera publicación. | Futuras reseñas con fechas y visibilidad. | C / V1. Editar no crea otra reseña ni otra primera publicación. |
| S03. Publicaciones por subtipo: ¿qué contenido genera la comunidad? | L para propias; A/E/B para propias; I global | Conteo de publicaciones por subtipo y autores distintos por separado. | Publicación; fecha de publicación. | Publicaciones del contrato social. | C / V1. Excluir reseñas y avances; `source/kind` actuales no representan todos los subtipos acordados. |
| S04. Conversación: ¿qué contenidos reciben comentarios? | P sobre contenido visible; A/E/B sobre propio; L propio | Conteo de comentarios visibles creados en período y comentaristas distintos; opcionalmente excluir al autor con regla declarada. | Comentario; `created_at`. | `comentarios_publicacion`; futuras referencias transversales. | C / V1. Hoy solo se enlaza a publicaciones; falta soporte de moderación y del contrato social. |
| S05. Contenidos con respuesta a 7 días: ¿qué proporción inicia una conversación? | A/E/B propio; I | Contenidos publicados con al menos un comentario ajeno visible en sus primeros 7 días / contenidos elegibles publicados. | Contenido, cohorte de publicación. | Contenido + comentarios + actor. | C / V2. Solo cohortes con 7 días completos; autoría organizacional requiere perfil actor. No es tasa de alcance. |
| S06. Reacciones: ¿qué respuesta explícita recibe un contenido? | P sobre visible; A/E/B propio; L propio | Conteo de reacciones vigentes por tipo y usuarios distintos. | Usuario–contenido–tipo al corte. | Futuras reacciones. | N / V3. Historial de altas/bajas necesario para evolución. |
| S07. Seguidores: ¿cómo evoluciona una comunidad? | L/A/E/B propio; P si se habilita | Seguidores vigentes al corte; altas menos bajas en período como métrica separada. | Seguidor–perfil; corte o fecha de evento. | Futuros seguimientos e historial. | N / V3. Estado vigente no permite deducir crecimiento histórico. |

## 5. Descubrimiento, emociones y recomendaciones

| ID / indicador y pregunta | Público | Fórmula y unidad | Grano y fecha | Fuente | Estado / prioridad / límite |
|---|---|---|---|---|---|
| D01. Interés relativo por obra: ¿qué obras concentran incorporaciones? | P/A/E/B | Usuarios distintos que agregaron la obra en período / usuarios distintos que agregaron alguna obra. Mostrar ambos conteos. | Usuario–obra; fecha de incorporación. | BI | C / V1. Depende de persistir incorporaciones e identidad estable de obra. Porcentajes no necesariamente suman 100 %. No representa demanda de compra. |
| D02. Cambio de interés: ¿qué obras ganan actividad? | A/E/B | Comparar D01 y número absoluto de incorporaciones entre períodos de igual duración y cobertura. | Obra–período. | BI | C / V2. Hereda brechas de D01. No afirmar crecimiento con base cero; aplicar muestra mínima en ambos períodos. |
| D03. Preferencias por categoría: ¿qué géneros predominan? | L; A/E/B agregado | Intentos finalizados vinculados a categoría / intentos finalizados con categorías conocidas; cobertura adicional. | Intento–categoría; `finished_at`. | Futuro catálogo de categorías y puente con obras. | N / V2. Clasificación múltiple implica porcentajes no aditivos. |
| D04. Emociones declaradas: ¿qué emociones acompañan mis lecturas? | L; A/E/B agregado | Experiencias que seleccionan emoción / experiencias con al menos una emoción; `n` experiencias y lectores. | Experiencia–emoción; fecha de registro. | Futuras experiencias y emociones. | N / V3. Selección múltiple; no deducir emociones desde abandono o calificación. Textos privados fuera de vistas comerciales. |
| D05. Satisfacción e intensidad: ¿cómo describe el lector su experiencia? | L; A/E/B agregado | Media y distribución de cada escala por separado, con su propio `n` no nulo. | Experiencia; fecha de registro. | Futuras escalas de experiencia. | N / V3. Separar experiencia de libro y capítulo; no diagnostica bienestar ni salud. |
| D06. Apertura de recomendaciones: ¿se exploran las sugerencias? | L historial; I evaluación; A/E/B solo agregado habilitado | Exposiciones con al menos una apertura atribuida en 7 días / exposiciones válidas maduras. | Exposición usuario–obra–posición; fecha de exposición. | Futura exposición y clic con ID correlacionado. | N / V3. Generar una recomendación no demuestra que se mostró; deduplicar reintentos. |
| D07. Inicio tras recomendación: ¿se empieza una obra sugerida? | L historial; I evaluación; A/E/B agregado habilitado | Exposiciones maduras a las que se atribuye un inicio dentro de 7 días / exposiciones maduras elegibles. | Exposición y primer inicio atribuido. | Exposiciones + LE + atribución. | N / V3. Propuesta: atribuir inicio a última exposición previa de la misma persona/obra; excluir intentos ya activos. Es asociación, no efecto causal. |
| D08. Cobertura y diversidad de recomendaciones: ¿se concentra demasiado el catálogo? | I; L explicación personal | Obras distintas expuestas / obras elegibles del catálogo al generar; distribución de exposiciones por autor e idioma. | Exposición y catálogo versionado; período. | Futuras exposiciones y catálogo de recomendación. | N / V3. Necesita conservar elegibilidad; no usar catálogo actual como denominador histórico. |

No se proponen ventas, ingresos, conversión a compra, horas de lectura, alcance ni retorno de campañas como indicadores disponibles. Necesitan, respectivamente, transacciones comerciales, sesiones de lectura o instrumentación de exposición y campañas que hoy no existen.

## 6. Adopción y calidad interna

| ID / indicador y pregunta | Público | Fórmula y unidad | Grano y fecha | Fuente | Estado / prioridad / límite |
|---|---|---|---|---|---|
| I01. Altas de cuentas: ¿crece la población registrada? | I | Usuarios creados por período. | Usuario; `created_at`. | `app.usuarios`. | D / V1. Separar simulados; no equivale a usuarios activos. |
| I02. Usuarios con actividad registrada: ¿cuántas personas participan? | I; A/E/B agregado de su ámbito | Usuarios distintos con inicio explícito, avance, cierre, publicación manual, reseña o comentario en período. | Usuario–evento; fecha del evento. | LE, PR y contenido normalizado. | C / V2. Excluir publicaciones automáticas duplicadas; no mide visitas o lectura pasiva del feed. |
| I03. Retención de actividad a 30 días: ¿vuelven los nuevos participantes? | I | Usuarios cuya primera actividad ocurre en cohorte y tienen otra entre días 30 y 59 desde ella / usuarios de cohorte con 60 días observables. | Usuario y cohorte de primera actividad. | Eventos normalizados de I02. | C / V2. No confundir con retención de inicios de sesión. |
| I04. Cobertura de atributos: ¿qué datos faltan para interpretar resultados? | I | Registros con atributo requerido válido / registros elegibles, por atributo. | Registro–atributo al corte. | Catálogo y fuentes de cada métrica. | D / V1. Evaluar autores, idioma, paginación y editorial separadamente. |
| I05. Calidad de carga: ¿se conserva lo esperado? | I | Filas extraídas, aceptadas, rechazadas, duplicadas y cargadas por entidad; conciliación por claves y regla de transformación. | Entidad–ejecución. | Futuro registro de controles del ETL. | N / V1. En agregaciones no exigir igualdad de número de filas origen/destino; conciliar medidas y población. |
| I06. Frescura y ejecución: ¿qué tan actualizado está el panel? | I; L/P/A/E/B solo última actualización | Tiempo desde último corte exitoso; duración `finished_at - started_at`; ejecuciones exitosas / ejecuciones terminadas en período. | Ejecución; inicio y corte. | `analytics.ejecuciones_etl`. | D / V1. Un corte global no prueba cobertura de todas las entidades; ampliar control por fuente. |

## 7. Exposición y filtros

La anonimización de todo análisis grupal es obligatoria, incluso para uso interno. Como control adicional, se propone un umbral de **10 personas distintas** por celda de comportamiento grupal. El valor está pendiente de revisión: cumplirlo no garantiza anonimato ni sustituye los demás controles.

- La vista personal solo puede mostrar al titular sus datos propios, sin ese umbral. Los conteos operacionales de contenido público no autorizan excepciones a la anonimización de los análisis grupales; si el desglose por contenido identifica participantes, se agrupa a un nivel mayor o se suprime.
- Aplicar el umbral después de todos los filtros. Si no se cumple, mostrar «Muestra insuficiente», sin revelar el conteo pequeño ni porcentajes derivados.
- Las distribuciones necesitan controlar también celdas complementarias y totales: ocultar una sola celda no sirve si se deduce restando las demás. Evitar filtros arbitrarios que permitan aislar individuos mediante consultas sucesivas.
- Rankings: declarar período, criterio, `n`, fecha de corte y reglas de empate; propuesta de desempate por ID estable. No comparar promedios sin mostrar tamaño de muestra.
- Ningún consumidor de análisis grupales, incluida administración e IA, recibe identidades de participantes, correos, credenciales, textos privados de experiencias ni motivos libres de abandono. La visibilidad del contenido en el feed no habilita unirlo con datos analíticos personales. Exportaciones, respuestas API, entradas y resultados de IA y logs analíticos respetan la misma separación.
- Período, obra, edición e idioma son filtros candidatos según indicador. Autor requiere OA; editorial requiere identidad y autorización verificadas. Categorías dependen de nueva fuente. Edad, ubicación y género de personas quedan fuera: no existen fuentes justificadas para esos filtros.
- En obras de varios autores, deduplicar intentos antes de totales generales. En todas las relaciones uno-a-muchos, evitar multiplicar lecturas, comentarios o valoraciones al unir tablas.
- Mostrar «Datos disponibles hasta…», «Datos simulados» cuando corresponda y ausencia de datos distinguible de cero.

## 8. Brechas verificadas y consecuencias

| Brecha actual | Evidencia en repositorio | Indicadores afectados / acción de diseño |
|---|---|---|
| Reseñas y avances se almacenan también como publicaciones. | `app/modules/social/models.py`, `app/modules/library/router.py`, `docs/social-model.md`. | S01–S05, I02: respetar entidades separadas y evitar doble conteo. |
| `progress`, `finish` y `abandon` pueden crear un intento con inicio en el mismo instante si no existía uno. | `app/modules/library/router.py`. | L04/L07/L09/L11/L12: registrar procedencia del inicio; no inventar duración ni reconstruirla desde publicaciones. |
| Progreso guarda página y fecha; no almacena el total por evento. La API actual solo admite avances crecientes, aunque el documento histórico propone correcciones. | `app/modules/library/models.py`, `router.py`, `docs/data-model.md`. | L10: definir contrato de correcciones y estabilidad del total del intento; identificar eventos con línea base desconocida. |
| El generador agrega sufijos aleatorios a referencias de libros en eventos de lectura; el resolvedor crea obras por referencia. | `scripts/generate_posts.py`, `app/modules/library/router.py`. | L07/L14/D01/D02 y rankings: preparar catálogo sintético con identidad estable; no fusionar libros por título automáticamente. |
| Reseñas usan `book_ref` sin FK a obra ni unicidad perfil–obra. | `app/modules/social/models.py`. | S01/S02: normalizar reseñas antes del indicador definitivo. |
| Agregar libro solo cambia el estado React; la entrada de biblioteca se crea al registrar lectura. | `apps/web/src/context/LibraryContext.jsx`, `app/modules/library/router.py`. | L01–L03/D01/D02: persistir incorporación y pendientes; no interpretar fechas legadas como la acción original de agregar. |
| No existen modelos operacionales de emociones, categorías, seguimientos, reacciones ni exposiciones de recomendaciones. | Modelos actuales de módulos y migraciones 0001–0009. | Indicadores N: instrumentación o funciones nuevas; no rellenar fuentes inexistentes solo en analytics. |
| Editorial es texto en edición; usuario tiene un rol simple y no el modelo actor completo. | `app/modules/books/models.py`, `app/modules/users/models.py`. | Alcances A/E/B: modelar relaciones y permisos antes de habilitar panel comercial privado. |
| ETL actual solo agrupa publicaciones de 30 días por origen y tipo en JSON. | `scripts/run_etl.py`. | No implementa este catálogo ni estados históricos; el modelo dimensional y sus controles son pasos posteriores. |
| No está implementada la separación entre análisis personal y conjunto grupal anonimizado ni controles de reidentificación. | ETL actual y diseño analítico pendiente. | Todos los indicadores grupales: preparar agregados en un proceso restringido y verificar anonimización antes de habilitar su consumo, incluso interno. |

## 9. Escenarios que deberán cubrir los datos ficticios

Estos casos definen necesidades del futuro conjunto; no autorizan todavía cambios de esquema ni generación.

1. Personas sin actividad y personas con diferentes frecuencias; períodos sin eventos.
2. Misma obra en distintas ediciones e idiomas; coautoría y metadatos faltantes.
3. Intentos pendientes, activos, terminados, abandonados y relecturas auténticas; retomar un abandono como caso distinto.
4. Inicios conocidos y desconocidos, cierres inmediatos y cohortes aún inmaduras para 7/30/60 días.
5. Varios avances el mismo día, límites de mes y cambio de zona horaria; correcciones si el contrato final las admite.
6. Reseñas sin calificación, edición de reseña y contenido oculto cuando esas funciones existan.
7. Grupos por debajo, iguales y por encima del umbral propuesto; filtros que reduzcan una muestra inicialmente suficiente.
8. Período anterior con cero actividad, obra con varios autores y múltiples fuentes de catálogo para detectar multiplicaciones en joins.
9. Repetición de la carga y del ETL sin duplicar entidades ni medidas; conciliación de resultados contra un escenario pequeño calculable manualmente.
10. Intentos de acceder al análisis personal de otro titular, incluso con rol administrador; deben denegarse en API y exportaciones.
11. Comprobar que el conjunto grupal no contiene identificadores directos, seudónimos enlazables, claves de eventos personales ni correspondencias con identidad; comprobar también entradas de IA y logs.
12. Intentos de reidentificación por cruces con contenido público, fechas precisas, diferencias entre consultas, totales y celdas pequeñas. Generalizar o suprimir los resultados que no superen la revisión, aunque cumplan el umbral numérico.

## 10. Decisiones propuestas y siguiente paso

El primer panel personal puede concentrarse en L01/L03/L05/L06/L08/L14. La primera vista de tendencias puede usar L02/L05/D01, una vez resueltas identidad, permisos y muestras. S01–S04 se incorporan tras cumplir el contrato social. I04–I06 acompañan la validación de la primera entrega.

La privacidad exclusiva de los análisis personales y la anonimización previa al análisis grupal son requisitos confirmados. Quedan para revisión funcional: umbral de 10 personas y demás controles concretos de anonimización, ventanas de 7/30/60 días, definición de relectura, alcance público de los agregados y relaciones que acreditan autor/editorial/librería. No se requiere decidir un proveedor de IA para implementar indicadores deterministas.

El paso 2 tomará estas dependencias para acordar las correcciones transaccionales. Después se diseñarán dimensiones, hechos y cargas. Este catálogo no sustituye ese diseño ni promete que las fuentes marcadas D ya tengan una calidad suficiente para producción.
