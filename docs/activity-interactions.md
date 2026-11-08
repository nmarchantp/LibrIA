# Interacciones del mural

## Contrato

Las actividades se identifican por `(kind, UUID)`, donde `kind` es `publication`,
`review` o `reading_event`. Las rutas anteriores siguen disponibles. No se crean
publicaciones auxiliares ni se migran comentarios históricos.

Rutas autenticadas bajo `/api/activities/{kind}/{identifier}`:

- `GET /`: contadores y capacidades autorizadas; no registra vistas.
- `PUT /like` y `DELETE /like`: dar y quitar Me gusta de forma idempotente.
- `GET /comments`: comentarios originales, con el límite existente de 100.
- `POST /comments`: crear un comentario usando `PostComment`.
- `PUT /view`: intención explícita `{ "action": "open" }` o `open_comments`.

Los resultados incluyen `like_count`, `liked_by_me`, `comment_count`, `view_count`,
`capabilities` y `observed_at`. El total de comentarios se calcula independientemente
del límite de comentarios cargados. El mural obtiene los conteos por lotes.

## Persistencia y privacidad

La migración aditiva `0073_activity_interactions` agrega `ReadingEventLike` y
`ActivityView`, además de índices para comentarios por fuente. Reutiliza `PostLike`,
`ReviewLike` y `PostComment` sin modificar registros históricos. Fue aplicada en la
base local y `alembic current` confirmó `0073_activity_interactions (head)`.

Cada vista tiene exactamente un destino y una restricción única por destino y
usuario. Las inserciones usan `ON CONFLICT DO NOTHING`. La resolución y autorización
compartida se ejecutan antes de cada interacción; también rechaza tarjetas antiguas
que ya no son públicas, eventos ocultos y reseñas que dejaron de ser canónicas.

Solo cuentan aperturas intencionales, aperturas de comentarios, likes exitosos y
comentarios publicados. Las interacciones del autor y del propietario del perfil
no suman vistas. Retirar un like conserva la vista. Consultas, renderizados, scroll,
polling y precargas no registran vistas. No hay reconstrucción histórica.
El API devuelve únicamente el total, nunca la identidad de los espectadores.

## Archivos de implementación

Backend, bajo `apps/backend/`:

- `app/modules/social/models.py`: modelos aditivos.
- `app/modules/social/activity_access.py`: visibilidad y resolución centralizadas.
- `app/modules/social/interaction_service.py`: conteos, likes, comentarios y vistas.
- `app/modules/social/interactions_router.py`: rutas tipadas.
- `app/modules/social/router.py`: compatibilidad de rutas anteriores.
- `app/modules/social/feed_service.py` y `feed_router.py`: contadores y capacidades.
- `app/main.py`: registro del router.
- `migrations/versions/0073_activity_interactions.py`: migración.
- `tests/test_activity_interactions.py`: regresión e interacciones concurrentes.

Frontend, bajo `apps/web/`:

- `src/services/activityInteractions.js`: estado compartido por usuario y actividad;
  descarta respuestas anteriores mediante `observed_at`.
- `src/context/ActivityInteractionContext.jsx`: suscripciones compartidas.
- `src/components/MuralActivityCard.jsx`: pie social; corazón independiente,
  comentarios directos y ojo informativo.
- `src/components/MuralActivityDialog.jsx` y `FeedCard.jsx`: diálogo y comentarios
  existentes conectados a las interacciones compartidas.
- `src/pages/HomePage.jsx`: proveedor y aperturas intencionales autorizadas.
- `src/pages/MuralPage.css`: título accesible y pie social, conservando dimensiones.
- `tests/fixtures/mural.jsx` y `tests/mural-carousels.mjs`: contratos y pruebas visuales.

## Validación

```powershell
# apps/backend
.\.venv\Scripts\python.exe -m alembic upgrade head
.\.venv\Scripts\python.exe -m alembic current
.\.venv\Scripts\python.exe -m unittest tests.test_activity_interactions tests.test_post_comments tests.test_post_interactions tests.test_reviews tests.test_reading_reflections
# apps/web
npm run lint
npm run test:feed-progress
npm run test:mural
npm run build
```

Las 58 pruebas backend cubren las tres fuentes, compatibilidad, comentarios
históricos, conteos completos, exclusión del autor, unicidad, colisiones entre
fuentes, contenido privado, pérdida de visibilidad, solicitudes inválidas y
concurrencia real con conexiones independientes. La prueba concurrente combina
likes y comentarios y verifica una sola vista por usuario.

Las pruebas del navegador cubren los nueve temas, distintas anchuras, dimensiones,
ausencia de vistas por renderizado y navegación del carrusel, corazón sin apertura,
comentarios directos, sincronización entre tarjeta, historial y diálogo, retirada
del like sin perder vistas y enlaces bibliográficos. También conservan las pruebas
del encabezado, columnas y formulario originales.

Lint no presenta errores; conserva una advertencia previa en `Layout.jsx`.
La compilación conserva el aviso de bundle superior a 500 kB.
En otros entornos debe ejecutarse la migración antes de desplegar este código.
El diálogo mantiene el límite anterior de 100 comentarios cargados; el contador
muestra siempre el total real. No se añadió paginación de comentarios en esta entrega.

## Presentación del diálogo social

`MuralActivityDialog` usa un encabezado fijo, ancho máximo de 580 px y altura
limitada por el viewport visible (incluido el cambio de altura por teclado).
`FeedCard` activa una variante `socialDialog` exclusivamente dentro de este diálogo;
el componente conserva el sistema original de comentarios y las acciones existentes.
El libro se integra con portada de 84 × 124 px (76 × 112 px en móvil), título,
autor, contenido completo, progreso y enlace bibliográfico. Las imágenes conservan
sus proporciones y las reseñas mantienen su protección de spoilers.

Los comentarios se cargan automáticamente en ambas formas de apertura. Abrir desde
el título no enfoca el campo; abrir desde la burbuja posiciona la sección y enfoca
el campo sin desplazar el viewport al enfocar. La lista admite desplazamiento
interno y el formulario permanece en una zona adhesiva. El seguimiento existente
se encuentra en el menú de opciones del usuario. La fila social usa los mismos
contadores y estado compartido; el ojo permanece informativo.

Se modificaron `MuralActivityDialog.jsx`, `FeedCard.jsx`, `feedService.js` (avatar),
`MuralPage.css` y la prueba `mural-carousels.mjs`. No se cambiaron backend,
migraciones, tarjetas de los carruseles ni permisos en este ajuste.
Además de las verificaciones anteriores, la prueba del mural comprueba las cinco
clases de actividad en nueve temas y tres anchos (1440, 390 y 320 px), comentarios
visibles desde el título, ausencia de foco automático desde el título, seguimiento
contextual y cierre con Escape. Capturas: `dialog-desktop.png` y
`dialog-mobile.png` dentro de `artifacts/mural-carousels/`.

El compositor de comentarios del diálogo muestra el avatar con iniciales del usuario,
campo de dos líneas con crecimiento automático hasta 144 px, contador sobre el
límite existente de 1000 caracteres (`CommentCreate.body`) y botón integrado
«Publicar» con icono de envío. El foco usa un único borde del compositor. La lista
incluye avatares con iniciales y un estado vacío discreto. El encabezado muestra el
total real a la derecha. Un bloqueo inmediato mediante referencia evita envíos
duplicados antes del siguiente renderizado; al publicar, el campo vuelve a su altura
inicial y la lista desplaza su contenido hasta el nuevo comentario. Este ajuste
mantiene endpoints, permisos y modelos existentes.

### Límites por fuente e icono de envío

El botón del compositor muestra únicamente el icono de envío amarillo, con etiqueta
accesible «Publicar comentario» y estado de carga. Avances, inicios y términos
(`reading_event`) admiten hasta 200 palabras separadas por espacios en blanco;
reseñas y publicaciones conservan 1000 caracteres. El campo informa el límite
correspondiente y deshabilita el envío cuando se supera. La ruta tipada valida
también estos límites en el servidor, antes de crear comentarios o visualizaciones.

La migración `0074_reading_comment_words` amplía la restricción de longitud de la
tabla exclusivamente para eventos de lectura. No reescribe ni elimina comentarios
históricos. Las rutas antiguas conservan su contrato previo de 1000 caracteres.
La migración se aplicó localmente y `alembic current` confirmó la revisión 0074.
Las 59 pruebas backend pasan, incluyendo aceptación de 200 palabras con más de
1000 caracteres, rechazo de 201 y conservación del límite de reseñas/publicaciones.
