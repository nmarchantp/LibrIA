# Motor de datos e inteligencia

El análisis individual del libro valorado y el ADN global son privados y distintos.
LibrIA Insights es exclusivo de autores y miembros de librerías/editoriales no
rechazadas ni suspendidas. Ser administrador, lector o influencer por sí solo no
otorga acceso. La comprobación ocurre en el servidor, además del menú.

## Recorrido de datos

1. **ETL-01** ingiere Google Books, normaliza y persiste obras/ediciones en `app`.
   La búsqueda conserva la ingesta bajo demanda y devuelve registros locales.
   Existe además un proceso independiente para ingesta y actualización del catálogo.
2. **ETL-02** extrae biblioteca, lecturas, eventos, valoraciones, historial de
   reseñas, reflexiones, notas, teorías, personajes, lugares, resúmenes y feedback.
   Las revisiones de reseñas conservan su orden; cuadernos y publicaciones son
   su estado vigente. No se inventa un historial inexistente.
3. **ETL-03** incorpora seguimientos, comentarios y reacciones con el contexto de
   su destino. Una reacción a una crítica negativa no se transforma en aprobación
   del libro. Las publicaciones tienen vínculos de obra/edición; las referencias
   antiguas ambiguas no se atribuyen a una obra por aproximación.
4. ETL-02/03 publican instantáneas inmutables en `analytics.projection_runs` y un
   puntero vigente por lector en `analytics.reader_current`. Se conservan corte,
   versión, hash, identificadores de origen y fecha de procesamiento. Catálogo
   normalizado para recomendaciones en `analytics.catalog_current`.
5. **IA-01** lee esas proyecciones persistidas. `reader_snapshot` solicita una
   actualización ETL si falta la proyección o está marcada como modificada; luego
   consulta analytics. El modelo no recibe el resultado directo del extractor.
   El análisis por libro usa solo esa obra; ADN contrasta la biblioteca del titular.
   Resultados en `ia.analyses`, con `analytics_run_id`. Las recomendaciones y las
   interpretaciones de Insights también se almacenan físicamente en `ia`; vistas
   de compatibilidad conservan las consultas antiguas desde analytics.
6. **ETL-04** calcula IND-001 a IND-010 sobre las proyecciones analíticas. El
   dashboard `/insights` muestra definiciones, unidades, períodos, estados sin
   evidencia y resultados respaldados. El ADN sigue en `/profile?tab=analysis`.

Los cortes diarios/manuales de métricas anteriores siguen funcionando y refrescan
también las proyecciones afectadas dentro de la publicación transaccional. La IA
personal no necesita esperar al cierre del día para reflejar un aporte nuevo.

## Incremental y reconstrucción

Los eventos relevantes marcan únicamente al lector o la obra afectados. Un
consumidor revisa cambios cada cinco segundos, sin llamar al modelo durante el
ETL. La lectura interactiva puede procesar ese lector antes de construir su
contexto. Una misma entrada sin cambios reutiliza el hash y la versión, sin crear
duplicados. Las eliminaciones retiran la fuente de la siguiente proyección.

Desde `apps/backend`:

```powershell
.venv/Scripts/python.exe -m scripts.run_analytics_etl
.venv/Scripts/python.exe -m scripts.run_analytics_etl --watch
.venv/Scripts/python.exe -m scripts.run_analytics_etl --rebuild
.venv/Scripts/python.exe -m scripts.run_catalog_ingest --query "inauthor:Gabriel García Márquez"
.venv/Scripts/python.exe -m scripts.run_catalog_ingest --refresh-known
```

`--rebuild` reconstruye el estado analítico vigente desde las fuentes actuales y
preserva los cortes históricos. No afirma reconstruir textos eliminados ni
versiones pasadas de cuadernos sin historial. Con workers internos desactivados,
ejecutar `run_analytics_etl --watch` junto a los consumidores de IA independientes.

## Recomendaciones y afinidades entre lectores

La señal principal sigue siendo las obras valoradas con 4 o 5 por el titular y su
perfil corregido. Se incorporan interacciones como descubrimiento complementario,
nunca como gustos confirmados. Ollama elige identificadores existentes y motivos
comprobables de candidatos analíticos; se mantienen tandas de cuatro y exclusión
de obras ya mostradas o incorporadas a la biblioteca.

El descubrimiento colaborativo requiere coincidencias explícitas en valoraciones
positivas y una comunidad de al menos diez lectores con valoraciones positivas.
Requiere cinco lectores coincidentes y cinco respaldos por obra sugerida. Solo
utiliza reseñas públicas de otros lectores; no envía sus identidades, reseñas
privadas ni textos al modelo. Sus resultados se fijan por lector y día. No se
infiere una preferencia personal exclusivamente de popularidad comunitaria.

## Publicación de indicadores

- Comunidad mínima: diez participantes con actividad en los períodos considerados.
- Cada desglose requiere cinco contribuyentes; conteos redondeados a múltiplos de
  cinco y contribuciones limitadas. Un vacío nunca se reemplaza con ejemplos.
- IND-001/002 cuentan lectores únicos por obra, aunque haya relecturas o ediciones.
- IND-003 usa una cohorte iniciada entre 60 y 30 días antes del corte y el primer
  desenlace dentro de 30 días. Exige cinco abandonos y cinco finales; la tasa
  publicada se deriva de los conteos redondeados. No incluye intentos sin desenlace.
- Los géneros reparten peso 1/n por obra multietiqueta. La distribución publicada
  se calcula sobre categorías con suficiente evidencia y pesos redondeados; las
  categorías suprimidas quedan fuera y se declara esa limitación.
- Valoraciones: última reseña pública vigente por lector/obra, mínimo cinco
  contribuyentes, promedio redondeado a medio punto.
- IND-005 compara participación de géneros entre dos períodos de 30 días;
  IND-010 compara inicios, finales, reseñas e interacciones con límites por lector.
- La publicación se fija por día para impedir consultas sucesivas que permitan
  aislar aportes. Los agregados internos sí reflejan cambios incrementales; el
  dashboard no ofrece filtros arbitrarios de personas, fechas o segmentos.

Los datos marcados como demostración se excluyen. Los no marcados no se presentan
como certificados de origen real. No se ejecutan semillas al operar el ETL.

## Validación y límites operativos

Las solicitudes repetidas de un análisis ya pendiente o en ejecución se unen al
mismo trabajo: no cambian revisión ni vencimiento y no descartan la generación.
Consultar el ADN en pantalla solo lee el último corte publicado; el ETL se ejecuta
en el consumidor. Los cambios de estado de una tarea IA no invalidan analytics;
sí lo hacen los cambios de fuentes transaccionales y feedback.

Las inferencias comparten un único turno PostgreSQL entre procesos. Libros,
recomendaciones e Insights ceden ante un ADN pendiente, incluyendo la cancelación
de su stream. Se usan contextos de Ollama compatibles para entradas pequeñas y
referencias cortas restauradas antes de guardar. Las recomendaciones liberan los
bloqueos del ETL antes de llamar al modelo. No se retiran aportes del lector para
acelerar la generación.

Las pruebas de integración usan transacciones revertidas, incluyendo aislamiento,
correcciones, versiones, reacciones negativas, reconstrucción y permisos. Pruebas
de indicadores comprueban lectores únicos, cohortes, ponderación y supresión.
La ausencia de participantes suficientes es un resultado esperado del producto.

Comprobación local: 170 pruebas aprobadas, lint y build del frontend correctos.
La ejecución normal del ADN sobre la biblioteca de 11 libros y 5 valoraciones
completó y persistió un resultado en 27,3 segundos con `analytics_run_id`.
Otra llamada de validación necesitó 49,9 segundos: el rendimiento no es constante.

Corrección de timeouts posterior: se verificaron solicitudes idempotentes en
0,11 segundos, ADN completado y persistido en 51,8 segundos y el libro afectado
completado al primer intento en 38,3 segundos, con su trazabilidad analítica.
El presupuesto total del ADN continúa en 55 segundos; no se amplía al reintentar
la misma solicitud activa. Se usa hasta el margen disponible de ese presupuesto.
Las referencias cortas y el formato interno acotado del libro se convierten al
contrato público original; no se mezclan los dos análisis.

Se conserva el presupuesto de 55 segundos para ADN, incluyendo cola e inferencia,
y se mantiene la última versión válida cuando Ollama no alcanza a terminar. El
ETL no garantiza el rendimiento del modelo local. Los textos de IA requieren
evaluación continua; validar estructura y referencias no garantiza cada inferencia
semántica. No hay seguimiento de clics ni permanencia en el feed.
