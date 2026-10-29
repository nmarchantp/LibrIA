# Catálogo canónico — Fase 2

Fecha: 2026-10-28. Servicio interno de identidad e incorporación, sin activación pública.

No se añadieron migraciones: el head continúa en `0056_catalog_nullable_edition`.
No se aplicó esquema a bases persistentes, no se ejecutaron fusiones ni se modificaron
datos reales. Las redirecciones usadas por pruebas son fixtures sintéticas en tmpfs,
no operaciones de consolidación sobre un catálogo existente.

## Archivos

| Archivo | Responsabilidad |
| --- | --- |
| `app/modules/books/canonical.py` | Una proyección SQL compartida para resolución individual, bulk y miembros canónicos; bloqueos transaccionales. |
| `app/modules/books/evidence.py` | Referencias tipadas/normalizadas, validación ISBN y obtención de detalle desde proveedores, sin acceso a DB. |
| `app/modules/books/resolution.py` | Comando interno `incorporate_book()`, decisiones bibliográficas, biblioteca, recibo y efectos de auditoría. |
| `tests/test_catalog_phase2.py` | 35 casos nuevos de evidencia, servicio y concurrencia. |
| `scripts/validate_catalog_phase2.py` | Ejecuta el entorno desechable de fase 1 y agrega la suite nueva. |
| `scripts/validate_catalog_phase1.py` | Parámetros internos para suites extra/informe separado y resumen de consola; conserva aislamiento, marca y limpieza. |
| `docs/catalog-canonical-phase2-results.json` | Resultados completos, revisiones/hashes, aislamiento y salida de unittest. |

No se modifican routers, búsqueda pública, fichas, configuración, frontend, importadores
anteriores, modelos históricos, ETL ni IA. El servicio nuevo no se registra en `app.main`.
Las tres capacidades de fase 1 siguen en false y su activación por configuración sigue
rechazada. La agrupación lógica anterior continúa en los consumidores públicos hasta su
reemplazo autorizado; las garantías descritas aquí corresponden al servicio nuevo.

## Contrato y flujo

`AdditionCommand` exige actor, clave idempotente y exactamente una modalidad:

- UUID de obra interna más UUID de edición explícita.
- Referencia de publicación externa explícitamente seleccionada, con evidencia del servidor.

`edition_selected` debe ser true. Una incorporación sin edición produce
`EditionSelectionRequired`; nunca selecciona la primera ni fabrica una edición.
No se aceptan simultáneamente una selección interna y otra externa.

El llamador obtiene `EditionEvidence` mediante `fetch_edition_evidence()` antes de tomar
bloqueos del catálogo. El adaptador utiliza el detalle de Google Books o el detalle de
Open Library existente; este último comprueba pertenencia de la edición a su obra.
Las pruebas sustituyen ambos proveedores. No se hicieron peticiones externas reales.

La evidencia contiene referencia, título bibliográfico, autores, ISBN normalizados, idioma,
páginas/editorial si están presentes, snapshot JSON, fecha de obtención y referencia de
obra verificada de Open Library cuando exista. Es un objeto interno inmutable, no un
schema HTTP: el cliente no puede declarar que su JSON está verificado. La futura fachada
deberá construirlo exclusivamente con este adaptador; no deserializar evidencia del cliente.

`incorporate_book(session, command, evidence)`:

1. Valida selección, referencia y normalización; calcula hash del contenido semántico.
2. Abre un savepoint dentro de la transacción del llamador.
3. Toma el bloqueo del grafo y bloquea la cuenta; comprueba biblioteca personal permitida.
4. Busca operación anterior por actor/tipo/clave. Un reintento exacto devuelve el resultado
   guardado; cambiar el contenido con esa clave produce conflicto.
5. Para operaciones nuevas externas, exige evidencia y toma bloqueos de publicación/ISBN.
6. Resuelve referencias, edición y UUID canónico; contradicciones se rechazan.
7. Crea únicamente lo necesario: obra, autores/vínculos nuevos, edición seleccionada y fuentes.
8. Reutiliza o crea biblioteca y lectura pendiente, conservando la edición explícita.
9. Registra operación, referencias nuevas, incorporación y efectos antes/después.
10. Libera savepoint. **No hace commit:** el llamador confirma o revierte la transacción completa.

Un reintento ya registrado no necesita volver a obtener evidencia ni consultar al proveedor.
Con una clave nueva y la misma referencia se reutilizan obra, edición, biblioteca y lectura;
se registra otro recibo de incorporación. La idempotencia de entidades no elimina trazabilidad
de comandos distintos. El hash no incluye datos descriptivos variables del proveedor.

El resultado conserva UUID físicos y canónico, edición, entrada, lectura, operación, recibo,
estado de identidad, motivo, candidatos y banderas de reutilización. El replay devuelve el
snapshot de resultado original, incluido el canónico de aquel momento; la identidad actual
se obtiene por `resolve_canonical_work()`, no reescribiendo operaciones antiguas.

## Decisiones bibliográficas

| Evidencia | Decisión |
| --- | --- |
| UUID interno válido | Resuelve redirecciones auditadas; la edición debe pertenecer a la misma identidad canónica. |
| Referencia externa ya vinculada | Reutiliza su vínculo; una referencia provisional no se convierte por repetición en obra verificada. |
| ISBN válido coincidente | Reutiliza la publicación/edición si no hay contradicciones; obtiene su obra por la FK de esa edición. |
| Obra externa verificada y previamente vinculada | Reutiliza esa obra para otra edición; no necesita títulos iguales ni ISBN. |
| Nueva obra externa verificada | Crea obra y vínculo confirmado con evidencia de procedencia. |
| Solo título/autor coincidente | Crea una obra independiente y devuelve candidatos. Nunca agrupa ni redirige por esa coincidencia. |
| Información insuficiente | Crea obra independiente y referencia provisional estable, si hay publicación seleccionada. |
| Referencias/ISBN/autores incompatibles | Lanza `IncorporationConflict` y revierte el comando; no modifica la evidencia anterior. |

`identity_status` distingue `confirmed`, `candidate` e `insufficient`; las contradicciones
son errores explícitos, no resultados exitosos. `evidence_kind` aclara el fundamento:
UUID interno, obra externa verificada o publicación/referencia/ISBN. Confirmar la publicación
por ISBN no implica confirmar que todas las publicaciones de igual título pertenezcan a la
misma obra. El ISBN nunca se usa como identificador universal de obra.

ISBN: se validan estructura ASCII, prefijo 978/979 y checksum. Se eliminan espacios/guiones,
se normaliza X y se calcula la equivalencia 10/13. Dos ISBN no equivalentes en un snapshot
se rechazan. Si los equivalentes están repartidos entre dos ediciones históricas se rechaza
la ambigüedad; no se decide una ganadora ni se reasignan datos. No se comprueba emisión del
ISBN contra una agencia externa: validación de checksum no certifica la verdad del proveedor.

Los metadatos se usan como evidencia negativa, no para confirmar obra: discrepancias
conocidas en título, autores, idioma, editorial o páginas impiden reutilizar la edición.
También se revisan contradicciones de autor/título dentro de sus fuentes. Para ediciones
distintas de una obra externa confirmada no se exige mismo título, idioma ni paginación;
sí se rechazan autores conocidos incompatibles.

Una referencia con contradicción/rechazo previo no se vuelve a vincular silenciosamente:
exige revisión salvo que ya exista un vínculo activo confirmado. Un binding de obra externa
provisional no se trata como una confirmación.

No se enriquece ni corrige metadata de obras/ediciones/fuentes existentes en este comando.
Esto puede dejar datos incompletos y producir rechazos conservadores, deliberadamente.
No se completan ISBN históricos vacíos aprovechando una incorporación. No se reescribe
`identity_key`; las obras nuevas lo dejan NULL y no usan su heurística como identidad.

## UUID y relaciones históricas

`canonical_projection()` es la única definición SQL de resolución. `canonical_mapping()`,
`resolve_canonical_work()` y `canonical_members()` la comparten. Solo considera redirecciones
activas con operación auditada de tipo merge y par origen/destino correspondiente. Detecta
ciclos o profundidad excesiva y falla explícitamente. No crea ni retira redirecciones.

La proyección usa el instante de la consulta, no el inicio de la transacción, para no ignorar
redirecciones recién confirmadas después de esperar por un bloqueo. No implementa aún
resolución temporal por versión; las secuencias de operaciones no se usan como reloj de commit.
La futura integración de ETL requiere corte y versión compartidos y sus pruebas de paridad.

El resultado diferencia `physical_work_id` y `canonical_work_id`. Una edición histórica
conserva su FK original; la biblioteca/lectura/incorporación usan esa obra física compatible.
La obra canónica se presenta como identidad resuelta. No se mueven lecturas, reseñas ni ediciones.

Si ya hay biblioteca en otro UUID físico del mismo grupo, el comando rechaza una transición
implícita antes que crear otra pertenencia canónica o sustituir una edición. Si existe una
lectura con otra edición, también rechaza el cambio. Restaurar entradas archivadas y cambiar
de edición requieren comandos explícitos futuros. Los solapamientos históricos ya existentes
se preservan; este servicio no los sanea.

Los fuentes del proveedor conservan cada referencia externa. Para una edición reutilizada
no se agrega un segundo alias `libria-feed` si ya tiene uno; así el servicio no introduce por
sí mismo nuevas duplicaciones por alias al restaurar biblioteca. Alias históricos existentes
no se eliminan ni corrigen.

## Transacciones y concurrencia

- PostgreSQL y `READ COMMITTED` obligatorios para el comando de escritura.
- Bloqueo global `(73155,1)`, el mismo que protege el grafo de fase 1.
- Fila del usuario bloqueada durante la incorporación.
- Bloqueos de referencia y ISBN compatibles con importaciones individuales existentes:
  `catalog:libria-feed:<id>` / `catalog:open-library:<id>` y `catalog:isbn:<isbn13>`.
- Lectura de referencias y selección de reutilización después de tomar los bloqueos.
- Restricciones únicas existentes y nuevas como segunda barrera.
- Savepoint para que un llamador pueda capturar un error sin confirmar escrituras parciales.
- Sin commit/rollback de la transacción exterior ni llamadas HTTP dentro del servicio.

La serialización global privilegia integridad; no está optimizada para alto volumen.
Antes de activación, la fachada debe fijar timeouts y reintentos acotados para errores
transitorios de PostgreSQL. Los importadores heredados por lotes no toman el bloqueo global:
se debe coordinar su adopción/suspensión antes de activar escritores nuevos. La convivencia
de todos los lotes antiguos con el servicio no se declara validada; siguen pudiendo causar
deadlocks/rechazos transitorios, que deben revertirse y reintentarse como comandos completos.

## Procedencia

Cada comando nuevo registra `operaciones_catalogo`, `incorporaciones_catalogo`, referencias
nuevas y `efectos_operacion_catalogo`. La operación guarda selección solicitada, UUID físico,
canónico resuelto, camino y operaciones de redirección, resultado y snapshot original del
proveedor con fecha y SHA-256. Las nuevas referencias incluyen verificador cuando corresponde.
Los efectos describen las filas creadas, incluidos vínculos autor–obra y fuentes, sin alterar
los registros anteriores. La versión de operación la asigna PostgreSQL; puede tener huecos.

Los triggers existentes pueden invalidar proyecciones derivadas por las filas nuevas. No se
modifican eventos, reseñas, revisiones ni otras filas históricas del lector. El ensayo compara
esas relaciones antes/después de reutilizar registros existentes. Los intentos fallidos no
dejan recibos de éxito parciales; una futura auditoría de errores debe hacerse fuera de la
transacción fallida sin simular una incorporación completada.

## Pruebas ejecutadas

```powershell
# Desde apps/backend, usando Docker local:
.\.venv\Scripts\python.exe -B -m scripts.validate_catalog_phase2
```

Resultado: **168 pruebas correctas** tras preparar esquema, incluidas **35 nuevas de fase 2**.
También se ejecutan 83 regresiones sobre 0054 antes del upgrade. Las 133 pruebas anteriores
continúan pasando. No se ejecutó la suite completa del repositorio fuera de ese conjunto.

Pruebas nuevas: referencias repetidas y claves incompatibles; replay sin proveedor;
dos usuarios simultáneos y mismo comando simultáneo; ISBN equivalentes entre proveedores
en paralelo; ISBN contradictorios; equivalentes repartidos en filas históricas; autores
incompatibles; mismo título/autor sin identidad; sin ISBN/sin autor; referencia de obra
externa compartida; contradicción previamente registrada; selección explícita; rechazo
de lectura sin edición; fallo después de escribir procedencia con rollback completo;
ausencia de commit interno; preservación de filas históricas; UUID desconocido; paridad
individual/bulk; UUID redirigido con FK física preservada y sin duplicar pertenencia canónica.

Los detalles externos son mocks de los adaptadores reales; no son un ensayo de disponibilidad
de proveedores. Los grafos de prueba son fixtures sintéticas, no activación de fusión.

El arnés reutiliza PostgreSQL 17 desechable con contraseña aleatoria, puerto loopback,
marca de propiedad, PGDATA tmpfs y sin montajes persistentes. El nombre técnico de la base
sigue siendo `catalog_phase1_disposable` porque se reutiliza el mismo guard de seguridad;
es una instancia nueva por ejecución, independiente de las bases ya existentes.
El informe fase 2 se escribe separado y no reemplaza los informes aceptados de fase 0/1.
Se verifica eliminación del contenedor al finalizar. Se repiten las comprobaciones de
preservación de migraciones y rollback DDL del arnés; no se añaden migraciones en fase 2.

## Riesgos y condiciones para fase 3

1. Revisión y autorización de la siguiente fase. No hay despliegue ni activación implícitos.
2. Preparar una fachada transaccional que llame este servicio con selección tipada y evidencia
   exclusivamente del servidor. Definir límites de frescura de snapshots y errores/reintentos.
3. **No quitar la importación de búsquedas/fichas sin adaptar conjuntamente el POST de biblioteca**:
   el `resolve_book()` público anterior depende de esos registros y podría caer en creación
   manual por título. Conectar primero la modalidad explícita con edición, detrás del despliegue
   controlado; edición opcional continúa reservada para su fase posterior.
4. Adoptar los bloqueos comunes en todos los escritores o suspender lotes heredados durante
   la transición. Medir contención y ajustar sin perder invariantes.
5. Revisar restauración de biblioteca por referencias y deduplicación de alias históricos.
   No habilitar NULL hasta adaptar feed, API/UI, ETL e IA; los consumidores siguen incompletos.
6. Antes de sustituir la agrupación pública, completar la comparativa sobre snapshot anonimizado
   y migrar consumidores al servicio compartido. No mantener un segundo algoritmo canónico en ETL.
7. Antes de cualquier fusión, implementar permisos, simulación, decisiones, confirmación y
   recuperación con actividad posterior. Esta fase solo lee redirecciones confirmadas.

Pendientes explícitos: no hay enriquecimiento de metadata histórica, reasignación de ediciones,
restauración implícita, cambio de selección de lectura, importación administrativa nueva,
tool de fusión, selección vigente de reseñas ni resolución temporal de identidad. La política
conservadora puede rechazar fuentes legítimas con metadatos divergentes; exige revisión en lugar
de agruparlas incorrectamente. Las capacidades permanecen desactivadas.
