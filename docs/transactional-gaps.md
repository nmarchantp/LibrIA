# Revisión de brechas transaccionales

Fecha: 2026-10-04. Punto 2 del trabajo de analítica. Estado: revisión actualizada después de las correcciones de seguridad y coherencia. Hay cambios de aplicación y pruebas; no se han modificado tablas ni ejecutado migraciones en esta entrega.

## 1. Alcance y requisitos que prevalecen

Esta revisión contrasta el [modelo social acordado](social-model.md) y el [catálogo de indicadores](analytics-catalog.md) con backend, migraciones, frontend y generador actuales. No constituye un inventario de los datos existentes. Distingue las correcciones implementadas en [security-review.md](security-review.md) del diseño objetivo pendiente. Los nombres físicos nuevos y rutas sugeridas son propuestas; las reglas ya acordadas no se reabren por esa elección técnica.

Requisitos confirmados:

- Publicaciones manuales, reseñas y avances son entidades diferentes. El feed combina sus representaciones sin duplicarlas en `publicaciones`.
- Una reseña pertenece a un perfil y una obra; una relectura no crea automáticamente otra reseña.
- El perfil actor y la persona autenticada que ejecuta una acción se distinguen. Las organizaciones tienen miembros, no una cuenta personal compartida.
- Los análisis personales son exclusivos de su titular. Todo análisis grupal, incluso interno o con IA, recibe datos anonimizados antes de su consumo. Una dimensión de lectores con UUID o hashes no cumple esa regla.
- Las instalaciones de demostración deben reconstruirse desde datos ficticios versionados en GitHub. Repetir la carga no debe duplicar entidades ni indicadores.

## 2. Diagnóstico y prioridades

**B0:** bloquea coherencia o privacidad del núcleo. **B1:** bloquea indicadores iniciales específicos. **B2:** ampliación posterior. La existencia de una tabla no implica que la interfaz capture correctamente el hecho que queremos medir.

| ID | Estado actual y evidencia | Cambio necesario | Indicadores afectados | Prioridad |
|---|---|---|---|---|
| T01 | `usuarios.role` admite un solo rol. `roles_router.py` crea librerías como cuentas con contraseña y aprobar una solicitud reemplaza el rol. | Separar cuenta, perfil personal, capacidades múltiples, organizaciones, membresías y permisos administrativos. Verificación independiente de capacidades. | S03–S07 y todos los alcances comerciales. | B0 |
| T02 | `Post` usa `user_id/source/kind`; `POST /posts` acepta reseñas. `/readings/events` solo inserta un post cuando `share=true`, pero sigue duplicando el hecho operacional en publicaciones. | Reservar publicaciones a contenido manual y crear reseñas propias; derivar avances del registro operacional. | S01–S05, I02 y ETL actual. | B0 |
| T03 | Reseñas requieren calificación en `PostCreate`, usan `book_ref` sin FK y no son únicas por perfil–obra. No tienen edición, spoiler ni estado de visibilidad propios. | FK a obra, unicidad perfil–obra, calificación opcional, ciclo de publicación/edición/ocultamiento. | S01/S02. | B0 |
| T04 | Avanzar/finalizar/abandonar exige `reading_id`, propiedad, estado activo y total invariable; no inventa inicio. Se bloquea la cuenta durante el comando y se rechaza el rol librería. Aún se resuelve por `book_ref` y se exige que el ID coincida con el último intento. | Resolver el intento directamente por ID; validar capacidades del perfil y proteger unicidad activa en base. Registro retrospectivo separado si se adopta. | L04/L07/L09–L12, I02/I03. | B0 |
| T05 | `progreso_lectura` conserva página y fecha. Se escribe en progreso/finalización, no en inicio/abandono; el post de hito no tiene FK al intento o avance. | Historial tipado de estados y progreso con instantánea de paginación, sin reconstrucción desde textos del feed. | L09–L13; trazabilidad del feed. | B0 |
| T06 | `resolve_book` crea una obra por referencia desconocida; el generador cambia referencias con sufijos aleatorios. Idioma se fija a `es` y no se incorporan autores en ese flujo. | Catálogo estable, importación separada de registrar lectura, selección de edición por ID; mapeo explícito proveedor–referencia. | L07/L14/D01/D02 y rankings. | B0 |
| T07 | `LibraryContext.addBook` usa `POST /readings/library`: persiste entrada e intento pendiente, admite paginación desconocida y repetir conserva el intento. La recarga restaura desde `/readings/me`, pero solo devuelve el último intento por referencia `libria-feed`. | Completar archivo, consulta de todos los intentos y restauración de metadatos; eliminar dependencia del proveedor para consultar la biblioteca. | L01/L02/L03/D01/D02. | B1 |
| T08 | Comentarios apuntan solo a `publicaciones`. Sus consultas/escrituras ya comparten el filtro del feed; ese filtro valida contenido del prototipo, no un estado de moderación. No hay reacciones, ocultamiento ni auditoría general de moderación. | Destino con FK verificable para los tres tipos; reglas de visibilidad y auditoría. Reacciones pueden ser una fase posterior. | S04–S06. | B0 para comentarios/visibilidad; B2 para reacciones. |
| T09 | Feed y reseñas siguen usando `/posts`, `source/kind` y `book_ref`. La interfaz de lectura ya envía `reading_id` y `share`, admite `post=null` y restaura biblioteca persistida sin presentar ejemplos como lecturas propias. | Contrato de feed combinado, formularios separados y navegación por IDs canónicos. | Todos los indicadores derivados de acciones de interfaz. | B0 |
| T10 | ETL agrupa posts de 30 días por `source/kind`, incluidos posts excluidos del feed; cuenta usuarios distintos sin controles de grupos pequeños. No exporta IDs personales en esas métricas, pero eso no acredita anonimización. No lee avances privados ni distingue el recorrido personal. | Extraer hechos operacionales por entidad; separar acceso personal, preparación restringida y consumo grupal anonimizado. No presentar conteos de posts como actividad lectora total. | Todos los indicadores grupales. | B0 antes de habilitar analítica. |
| T11 | `run-local.ps1` ya no lanza el generador. Su ejecución manual sigue usando UUID/tiempo actual, carece de procedencia explícita y es continua si se omite `--count`. | Manifiesto versionado, claves estables, fecha base, registro de carga y carga finita reproducible. | Reproducibilidad de todos los indicadores. | B1 |
| T12 | No hay categorías, experiencias/emociones, seguimientos, exposiciones de recomendaciones ni identidad editorial formal. | Incorporar únicamente las fuentes de los indicadores elegidos para cada fase; no simularlas solo en analytics. | D03–D08/S06/S07 y acceso editorial. | B2; identidad editorial bloquea su panel privado. |

## 3. Entidades propuestas y reglas de integridad

### Estado de cierre tras las correcciones

Trabajo posterior en curso: se preparó `0010_profile_identities` con perfiles, capacidades múltiples, membresías, permisos administrativos de cuenta y auditoría. La migración crea perfiles para cuentas personales existentes y no convierte las cuentas de librería. Las rutas `/profiles` y sus cuatro pruebas de integración están preparadas; la migración se validó dentro de transacciones revertidas, sin aplicarla de forma persistente. Falta integrar estas identidades con registro, verificación, contenido e interfaz antes de cerrar T01. Las reglas de publicación/lectura y la asignación de responsables de librerías están consultadas al usuario; no se consideran confirmadas por esta implementación.

**Ninguna de las doce brechas está cerrada completamente.** Una mitigación del prototipo no equivale a cumplir el modelo social acordado.

| ID | Estado | Cubierto y condición pendiente para cerrar |
|---|---|---|
| T01 | Abierta | Bloqueos y auditoría de decisiones de rol mejoran el prototipo; no existen perfiles/capacidades/membresías separados. |
| T02 | Parcial | Compartir es explícito; falta separar las tres entidades y eliminar posts derivados de lecturas. |
| T03 | Abierta | Validaciones de entrada no sustituyen FK, unicidad, calificación opcional, edición y visibilidad de reseñas. |
| T04 | Parcial | ID, propiedad, inicio explícito y bloqueos implementados; faltan capacidades, resolución directa e integridad activa en base. |
| T05 | Parcial | Total del intento protegido por la API; faltan eventos tipados, instantánea por avance y vínculo verificable con el contenido compartido. |
| T06 | Parcial | Bloqueo asesor por referencia evita carreras dentro del resolver; no evita duplicar una obra con referencias distintas ni valida los metadatos aportados por el cliente. |
| T07 | Parcial | Alta, pendiente y recarga persistentes implementados; faltan archivo e historial completo independiente del proveedor. |
| T08 | Parcial | Se cierra acceso a comentarios de posts excluidos del feed; faltan destinos de las nuevas entidades y moderación real auditada. |
| T09 | Parcial | Interfaz adaptada al contrato de lectura corregido; falta feed combinado y navegación por identidades canónicas. |
| T10 | Abierta | El ETL conserva el modelo de posts; faltan extracción operacional y aislamiento/anonimización verificables. |
| T11 | Parcial | Arranque sin inserciones ficticias; falta conjunto versionado y carga repetible sin duplicados. |
| T12 | Abierta | No se implementaron las fuentes operacionales ni la identidad editorial. |

La prioridad sigue siendo T01 → T06/T07 → T04/T05 → T02/T03 → T08/T09, con T11 y la migración acompañando el cambio. T10 bloquea habilitar analítica, aunque no impide continuar las correcciones operacionales. T12 se limita a los indicadores elegidos, sin ampliar esta entrega a funcionalidades nuevas.

### Cuenta, perfil y organización

Conservar `usuarios` como cuenta personal y `cuentas_autenticacion` como credenciales. Proponer `perfiles` con clase personal u organización, perfil personal único por usuario y `miembros_perfil` para pertenencia a organizaciones. Las capacidades de lector/autor/influencer pertenecen al perfil; la administración del sistema es un permiso de cuenta separado.

La verificación conserva solicitudes y decisiones, pero no se equipara con el rol. `approved` en una solicitud histórica no es por sí solo el estado vigente de verificación; se deben modelar suspensión y cambios explícitos. Una editorial será una organización si se implementa ese alcance, con vínculos verificables a sus ediciones; el nombre textual de editorial no concede acceso.

Toda escritura por perfil comprueba membresía/capacidad al ejecutar la operación. `created_by_user_id` se obtiene de la autenticación y no del cuerpo enviado. Los datos personales analíticos no se comparten con miembros de una organización. Administrar identidades operacionales no autoriza consultar análisis personales ajenos.

### Publicaciones manuales

`app.publicaciones` conservaría identidad, texto, fechas y añadiría `author_profile_id`, `created_by_user_id`, `publication_type` y estado de publicación/moderación. Subtipos acordados: `free`, `institutional`, `launch`, `event`, `news`, `promotion`.

Proponer `publicaciones_obras` con PK `(publication_id, work_id)` y FK a ambas tablas. Una publicación puede citar varias obras, sin convertirse en reseña ni multiplicarse en los conteos. Retirar de este contrato `rating`, `progress_percent`, `reading_event` y el uso de `source/kind` para mezclar entidades.

Definir primera publicación, última edición y ocultamiento como instantes diferentes. Una edición no altera la primera publicación. El control de subtipos autorizados por capacidad se especificará antes de activar las rutas nuevas; el rol administrativo no implica autoría institucional automática.

### Reseñas

Crear `app.resenas` con FK obligatorias a perfil autor y obra, texto no vacío, calificación opcional entre 1 y 5, indicador de spoiler, estado y fechas. Restricción única `(author_profile_id, work_id)`, incluso si la reseña está oculta: volver a publicar o editar conserva la misma identidad.

Registrar autor visible y usuario ejecutor. Si se incorpora `reading_id` opcional, comprobar que sea de esa obra y del titular autorizado; no exigir lectura terminada para una reseña sin que se acuerde esa regla. No copiar automáticamente una experiencia privada a una reseña pública.

Para V1, S01 mide la calificación vigente y S02 la primera publicación. Guardar `updated_at` no proporciona versiones anteriores. Un historial de revisiones es necesario antes de habilitar evolución histórica de calificaciones; puede diferirse junto con ese indicador.

### Biblioteca e intentos de lectura

Conservar `entradas_biblioteca`, `lecturas` y sus FK compuestas que ya comprueban coherencia obra–edición. La incorporación ya crea una entrada y un intento pendiente si no existen; un inicio usa ese intento pendiente. Queda por seleccionar una edición canónica validada y habilitar archivo conservando intentos previos.

Las acciones posteriores deben identificar `reading_id`, no «la última lectura de esta referencia». Permitir consultar todos los intentos sin filtrar por proveedor bibliográfico. Retomar tras abandono crea un intento nuevo; nunca borra el cierre previo.

Propuesta de transiciones:

Esta tabla describe el objetivo. Actualmente, `start` también permite crear directamente un intento activo cuando no hay uno pendiente, incluso después de finalizar o abandonar; no obliga a pasar por un nuevo pendiente. El total se toma del cliente al iniciar y se mantiene fijo en comandos posteriores, pero todavía no se valida contra una edición canónica.

| Estado origen | Acción | Estado destino | Efecto |
|---|---|---|---|
| pending | iniciar | reading | Registra inicio explícito y copia el total de páginas de la edición validada. |
| reading | registrar avance | reading | Actualiza página y agrega evento de progreso en la misma transacción. |
| reading | finalizar | finished | Página final igual al total y fecha de cierre; conserva avance final e hito correlacionados. |
| reading | abandonar | abandoned | Conserva página alcanzada, motivo privado y fecha de cierre. |
| finished / abandoned | crear otro intento | pending | Fila nueva, sin modificar la experiencia previa. |

No inventar un inicio al recibir finalización/abandono. Si se desea permitir registrar libros leídos antes de usar LibrIA, crear un flujo retrospectivo explícito con fechas conocidas o desconocidas y procedencia; excluir duraciones desconocidas de L11/L12. Los registros antiguos con inicio inferido conservarán esa condición.

La política de intentos simultáneos por usuario–obra queda por formalizar en el modelo definitivo. El servicio actual serializa comandos mediante bloqueo de cuenta y rechaza iniciar si el último intento está activo. No hay una restricción de base que impida varios activos mediante escrituras externas o datos legados; tampoco se han probado carreras entre varios procesos.

### Avances e historial de estados

Conservar `progreso_lectura` como cambios de página. Añadir instantánea de total de páginas y procedencia. El porcentaje visible se calcula de esa instantánea con una regla única de redondeo; no se permite modificar página, total y porcentaje de forma independiente.

Proponer `eventos_lectura` para inicio, finalización y abandono, con FK al intento, tipo, fecha efectiva, fecha de registro y procedencia. El inicio o abandono no necesita un falso cambio de página. La finalización puede generar un avance final y un evento de estado en una transacción, vinculados por una misma operación para no duplicar acciones en I02/L09.

El feed acordado incluye `reading_progress`. Los hitos de inicio/abandono no deben conservarse como publicaciones manuales para mantener la apariencia actual: su futura presencia en el feed requiere una decisión explícita. Una finalización puede mostrarse mediante el avance a 100 %.

El documento histórico admite correcciones hacia atrás, mientras la API actual las rechaza. Propuesta: comando de corrección distinguido del avance, preservando registro previo y motivo técnico si corresponde; no reinterpretar una corrección como lectura negativa real. Resolver esta política antes de L10. No cambiar el total histórico de un intento cuando se edita la paginación del catálogo.

## 4. Feed, comentarios, reacciones y visibilidad

El feed será una consulta/servicio sobre las tres entidades; no una copia de ellas en otra tabla de publicaciones. Respuesta propuesta: `feed_item_type`, ID de entidad, perfil público autor, fecha pública y campos propios del tipo. No incluir el usuario ejecutor, motivo de abandono ni historial privado en la respuesta pública.

Para comentarios, proponer tres FK opcionales (`publication_id`, `review_id`, `reading_progress_id`) y un CHECK que exija exactamente una no nula. Así la base comprueba existencia y exclusividad del destino. Se conserva perfil autor y usuario ejecutor del comentario, además de visibilidad y fechas. Esta elección evita un par libre `(type, id)` sin integridad; no exige una tabla de feed persistida.

Si se implementan reacciones, aplicar el mismo patrón de destino y unicidad por usuario, destino y tipo de reacción mediante restricciones/índices adecuados a cada destino. No duplicar una reacción porque una persona actúe desde varios perfiles: el contrato acordado establece unicidad por usuario.

La alternativa de una entidad común de contenido es viable, pero añadiría sincronización de padre/subtipo. Para tres tipos conocidos se propone el patrón de FK exclusivas; se revisará si el número de tipos crece.

Ocultar un elemento lo retira del feed y de consultas públicas directas; sus comentarios/reacciones tampoco deben recuperarse a través de sus endpoints. Impedir nuevas interacciones sobre contenido oculto. Conservar auditoría de actor administrativo, acción, motivo y fecha. Preferir ocultamiento a borrado físico para no destruir relaciones e historia; la eliminación definitiva necesita su propio diseño.

Los avances públicos y el historial privado de lectura son cosas distintas. La implementación actual registra privado por defecto y exige `share=true` mediante una casilla de la interfaz para compartir cada cambio. Esto no cierra T02: todavía publica un `Post` sin FK al hecho original y permite compartir inicio/abandono, tipos no incluidos como avances en el contrato social acordado. Resolver su tratamiento al separar entidades. En ningún caso publicar un avance autoriza acceso al análisis personal.

## 5. Persistencia y contratos de aplicación

| Operación | Contrato actual | Dirección propuesta |
|---|---|---|
| Agregar libro | `addBook` llama `POST /readings/library`; alta persistente, pendiente e idempotencia para la misma obra resuelta. | Selección canónica de obra/edición, archivo e historial completo. |
| Publicar contenido | `POST /posts` con `source/kind`. | Ruta exclusiva de publicaciones con perfil actor y subtipo. |
| Crear/editar reseña | `POST /posts` con `source=review`. | Ruta de reseñas con `work_id`; edición de la misma reseña, unicidad respaldada por base. |
| Registrar lectura | `/readings/events` exige `reading_id` salvo en inicio, conserva `book_ref` y devuelve `post` nullable según `share`. | Resolución directa por `reading_id`, respuesta con evento operacional identificable y elemento público derivado solo si procede. |
| Consultar biblioteca | `/readings/me`, último intento por referencia `libria-feed`, incluidos pendientes; biblioteca personal sin ejemplos precargados. | Consulta de entradas e historial completo, independiente del proveedor. |
| Consultar feed | `GET /posts`. | Feed combinado con discriminador y paginación estable por fecha, tipo e ID. |
| Comentar | `/posts/{id}/comments`. | Destino tipado validado y traducido a FK; autorización y visibilidad comunes. |

No es necesario elegir ahora los nombres definitivos de rutas. Sí debe actualizarse backend y frontend juntos: `HomePage.jsx`, `ReadingPage.jsx`, `LibraryContext.jsx`, esquemas de respuesta y generador. Revisar también tests actuales de roles y comentarios que codifican el prototipo.

Cada comando debe ejecutar cambios de estado, eventos y referencias en una sola transacción. La ruta actual agrupa estado, progreso y post opcional en un commit, y serializa comandos de lectura por cuenta. Eso no implementa idempotencia: repetir un cierre devuelve conflicto, no el resultado original. Para comandos reintentables, proponer clave de idempotencia asociada a cuenta, operación y contenido de solicitud; misma clave con distinto contenido se rechaza. Completar FK/CHECK/UNIQUE para proteger integridad incluso fuera de la API; el servicio valida propiedad y transiciones.

## 6. Contrato de datos para la futura analítica

La fuente operacional conserva identidad porque debe autorizar acciones y calcular historia personal. Eso no habilita una dimensión de personas en la analítica grupal.

1. **Recorrido personal:** consultas/resultados vinculados al titular, accesibles solo por él; ningún permiso comercial o administrativo concede acceso a otro titular.
2. **Preparación restringida:** puede enlazar identidad con eventos para calcular únicos, relecturas y cohortes. Sus tablas temporales, errores y logs no son fuentes de exploración grupal.
3. **Salida grupal:** agrupaciones anonimizadas sin claves personales, seudónimos enlazables, IDs de eventos de personas ni correspondencias. Generalización y supresión antes del consumo por paneles, exportaciones o IA. Un mínimo numérico de personas por sí solo no demuestra anonimato.

Los permisos de base y las interfaces deben impedir unir la salida grupal con las tablas personales. Un simple esquema separado usando una cuenta con acceso a todo no proporciona esa separación. El diseño físico del punto 3 especificará cuentas de servicio, privilegios, aislamiento de preparación y controles de reidentificación.

Los extractores diferenciarán fecha efectiva del hecho y fecha de modificación/registro. Ediciones, ocultamientos y cambios tardíos deben llegar al ETL; `created_at` por sí solo no basta para carga incremental. Inicialmente una reconstrucción completa repetible puede simplificarlo, sin inventar estados históricos no registrados.

## 7. Tratamiento de registros existentes

No se autoriza borrar datos mediante este documento. Tampoco se debe interpretar «todavía nadie usa la plataforma» como prueba de que todas las filas sean ficticias. Antes de una migración se necesita inventario, respaldo y clasificación de procedencia.

| Registros | Tratamiento propuesto |
|---|---|
| Cuentas personales | Crear perfil personal y mapear capacidades con reglas explícitas. Mantener identidad y credenciales existentes. |
| Cuentas con rol librería | Crear organización; asignar responsables solo con evidencia de pertenencia. No convertir automáticamente la cuenta compartida en una persona ni inventar un administrador. Resolver credenciales del modelo anterior durante la migración. |
| Publicaciones manuales | Conservar IDs cuando sea posible; mapear actor y subtipo con evidencia. `community` no permite inferir si era noticia, lanzamiento o promoción: marcar para revisión cuando sea ambiguo. |
| Reseñas del prototipo | Convertir solo si hay correspondencia inequívoca con obra y perfil. Resolver colisiones perfil–obra de forma documentada; no conservar silenciosamente solo la última perdiendo texto. Las ambiguas quedan separadas del conjunto válido. |
| Posts `source=reading` | No convertir en avances a partir del texto o porcentaje. Vincular solo con evidencia inequívoca del evento original; el post no tiene FK y no se supone correspondencia por proximidad horaria. |
| Lecturas y progreso existentes | Conservar historia real disponible. Inicio inferido o total histórico no demostrable se identifican como desconocidos/legados; no certificar retroactivamente una duración. |
| Comentarios antiguos | Mantener destino en el mapeo; si el destino queda legado/pendiente, también sus comentarios. Nunca reasignarlos a una obra o reseña arbitraria. |
| Instantáneas analíticas antiguas | Marcar como versión del prototipo. No mezclarlas con métricas nuevas; reconstruir únicamente lo justificable desde fuentes válidas. |

Para instalaciones nuevas de demostración, cargar directamente el nuevo contrato con catálogo y claves estables. Para una instalación existente, usar una migración gradual: agregar estructuras, clasificar/mapear, validar, cambiar lecturas/escrituras y retirar estructuras antiguas solo cuando no queden dependencias y exista un procedimiento de recuperación probado.

El conjunto ficticio tendrá versión, semilla, fecha base, conteos esperados y registro de ejecución de carga. La procedencia por entidad permite distinguir y reemplazar únicamente filas propias del conjunto mediante una operación explícita; no se publicará en la salida grupal un mapa a participantes.

## 8. Orden de implementación y criterios de aceptación

| Orden | Entrega | Condición verificable para avanzar |
|---|---|---|
| 1 | Cuenta/perfil/capacidades y membresías. | Usuario puede tener lector y autor simultáneamente; organización admite varios miembros; actuar sin autorización falla; verificación y permisos son independientes. |
| 2 | Catálogo estable y biblioteca persistida. | Agregar y recargar conserva la biblioteca; misma referencia no duplica obra; cambiar de proveedor no oculta intentos; obra–edición inválida es rechazada. |
| 3 | Comandos e historia de lectura. | Evento identifica intento; cierre no inventa inicio; cambios y eventos son atómicos; reintentos/concurrencia no duplican; relectura conserva intento previo. |
| 4 | Publicaciones y reseñas separadas. | Reseña duplicada perfil–obra falla; editar conserva ID y primera publicación; calificación ausente es válida; lectura no inserta publicación manual. |
| 5 | Feed, comentarios, moderación y frontend adaptados. | Cada elemento conserva tipo e identidad; comentarios no admiten destinos inexistentes/múltiples; contenido oculto no se filtra por rutas directas; no se exponen usuario ejecutor ni datos privados. |
| 6 | Migración validada y carga demo reproducible. | Inventario conciliado, filas ambiguas identificadas, segunda carga sin duplicados, arranque sin generador continuo involuntario. |
| 7 | Preparación y accesos analíticos del punto 3. | Aislamiento personal/grupal verificable, sin claves enlazables en salida grupal; controles de grupos pequeños y cruces superados antes de mostrar resultados. |

Estos criterios son condiciones de cierre, no resultados ya alcanzados. En la entrega de correcciones se ejecutaron 25 pruebas de backend, ESLint y build de frontend, con resultado satisfactorio. Incluyen propiedad/privacidad de lecturas, alta pendiente repetida y acceso a comentarios, pero no acreditan los criterios estructurales completos, concurrencia multiproceso, carga demo repetible ni anonimización. Esta actualización documental contrasta código y pruebas existentes; no vuelve a ejecutar la aplicación ni realiza inventario de datos.

## 9. Decisiones pendientes delimitadas

Las siguientes son propuestas de esta revisión, no cambios ya aprobados del producto:

- Conservar o ampliar la elección individual de compartir ya implementada, y resolver el tratamiento de inicio/abandono al migrar al feed acordado. La opción actual no autoriza convertirlos en publicaciones manuales en el modelo definitivo.
- Admitir registro retrospectivo de lecturas y cómo declarar fechas desconocidas.
- Admitir correcciones hacia atrás y un único intento activo por usuario–obra.
- Adoptar las tres FK exclusivas para comentarios/reacciones.
- Definir permisos de publicación por capacidad/subtipo y acreditación de relaciones de autores/editoriales con catálogo.
- Resolver manualmente cualquier propiedad organizacional o mapeo legado ambiguo antes de migrar esos registros.

No bloquean documentar el modelo analítico: se pueden representar como dependencias. Sí deben resolverse antes de implementar las operaciones afectadas. Reacciones, emociones, seguimientos e instrumentación de recomendaciones no son necesarios para cerrar la separación inicial de publicaciones, reseñas y avances.

## 10. Evidencia principal

- [Modelo social](social-model.md) y [catálogo de indicadores](analytics-catalog.md).
- [Correcciones y límites de seguridad](security-review.md), [pruebas de roles y lecturas](../apps/backend/tests/test_user_roles.py) y [pruebas de comentarios](../apps/backend/tests/test_post_comments.py).
- [Modelos sociales](../apps/backend/app/modules/social/models.py), [esquemas](../apps/backend/app/modules/social/schemas.py) y [rutas](../apps/backend/app/modules/social/router.py).
- [Modelos de lectura](../apps/backend/app/modules/library/models.py), [esquemas](../apps/backend/app/modules/library/schemas.py) y [rutas](../apps/backend/app/modules/library/router.py).
- [Catálogo](../apps/backend/app/modules/books/models.py), [usuarios](../apps/backend/app/modules/users/models.py), [roles](../apps/backend/app/modules/users/roles_router.py) y [verificación](../apps/backend/app/modules/users/verification_models.py).
- [Biblioteca en interfaz](../apps/web/src/context/LibraryContext.jsx), [feed](../apps/web/src/pages/HomePage.jsx) y [registro de lectura](../apps/web/src/pages/ReadingPage.jsx).
- [Generador](../apps/backend/scripts/generate_posts.py), [inicio local](../scripts/run-local.ps1), [ETL actual](../apps/backend/scripts/run_etl.py) y [migraciones](../apps/backend/migrations/versions).
