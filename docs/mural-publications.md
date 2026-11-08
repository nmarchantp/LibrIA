# Mural híbrido: actividades compactas y publicaciones amplias

Se revisó `HomePage.jsx` en Git, versión `be61512`, y se reutilizó el componente
`FeedCard` extraído de ese diseño: encabezado, texto completo, libro enlazado,
galería y comentarios. No se restauraron archivos completos ni se sustituyeron
el encabezado, la columna derecha o los carruseles actuales.

## Presentación

- Contactos y Comunidad conservan las vistas previas con carruseles.
- Avances, inicios, terminados y reseñas conservan tarjetas y dimensiones actuales,
  incluyendo sus listados completos e historial.
- Eventos, Lanzamientos, Anuncios y Promociones tienen accesos independientes y
  listados amplios, con una publicación por fila y altura según su contenido.
- «Ver todo» de publicaciones sociales también usa el formato amplio.
- La audiencia actual se conserva al entrar en una categoría; permisos y orden
  cronológico se aplican antes de paginar.

La navegación principal es una única barra segmentada con Contactos, Comunidad,
Eventos, Lanzamientos, Anuncios y Promociones. Solo hay un segmento activo.
Contactos y Comunidad regresan a sus carruseles; las otras opciones abren sus
listados amplios. Se reutilizan `.mural-audiences` y su estado activo original,
sin una segunda fila de enlaces. Los segmentos tienen igual tamaño y altura;
cuando no caben, se desplazan horizontalmente dentro del mismo contenedor.
El segmento seleccionado permanece visible al cambiar de sección o anchura.
Actualizar sigue fuera del grupo, a su derecha. No hay cambios de backend en
este ajuste de navegación.

Las publicaciones amplias muestran el contenido completo sin abrir un modal.
`MuralPublication` conecta `FeedCard` al estado compartido de interacciones.
Likes y comentarios funcionan directamente; los comentarios se abren dentro de la
publicación. El icono de seguimiento permanece en el encabezado. El ojo solo muestra
el contador. Renderizar una publicación o cargar otra página no registra vistas.
Abrir intencionalmente una imagen, abrir comentarios, dar Me gusta o publicar un
comentario reutiliza el registro autorizado de vistas únicas.

`PostGallery` reutiliza el visor original. Las publicaciones amplias muestran una
sola fila de hasta cuatro miniaturas cuadradas. Con seis adjuntos la cuarta lleva
«+3», conservando la fotografía debajo. El visor conserva los seis archivos y se
abre en la imagen seleccionada. No hay carrusel ni segunda fila. Las otras
superficies mantienen su galería anterior. Los adjuntos originales no se modifican.

## Backend

Se amplió el parámetro de categoría del endpoint paginado existente:

| Ruta | Filtro previo a paginación |
| --- | --- |
| `/api/mural/events` | `publication_type=event`, o evento antiguo con `source=event` y tipo nulo |
| `/api/mural/launches` | `publication_type=launch` |
| `/api/mural/announcements` | `publication_type=news` |
| `/api/mural/promotions` | `publication_type=promotion` |

Conservan `audience`, `limit`, cursor firmado por usuario/audiencia/categoría,
privacidad compartida, hidratación por lotes e interacciones originales.
La vista previa sigue teniendo las cinco categorías anteriores. No se añadieron
modelos, migraciones ni registros.

## Archivos

Backend: `social/feed_router.py`, `social/feed_service.py` y
`tests/test_mural_feed.py`.

Frontend: `HomePage.jsx`, `MuralPage.css`, `MuralPublication.jsx`, `FeedCard.jsx`,
`PostGallery.jsx`, `tests/fixtures/mural.jsx` y `tests/mural-carousels.mjs`.

## Validación

Se ejecutaron 70 pruebas backend de mural, interacciones, comentarios, reseñas y
reflexiones. Incluyen filtros antes de paginar, separación entre categorías,
audiencias, alcance del cursor y eventos históricos con tipo nulo.

Las pruebas del navegador comprueban listados administrativos y sociales amplios,
texto completo, enlaces al libro, galerías de 1/2/3/6 imágenes, visor con navegación,
likes, comentarios dentro de la publicación, vistas únicas y paginación. Además
comprueban los nueve temas en escritorio y móvil sin desbordamiento, conservando
las pruebas de tarjetas compactas, sidebar, formulario y modal.

Comandos frontend: `npm run lint`, `npm run test:mural`,
`npm run test:feed-progress` y `npm run build`. Lint conserva una advertencia previa
en `Layout.jsx`; la compilación conserva el aviso de tamaño del bundle.
Capturas en `artifacts/mural-carousels/publications-1440.png` y
`publications-390.png`.

## Proporciones de las galerías

Los listados amplios ocupan todo el ancho de la columna principal. La obra enlazada
ocupa una columna derecha discreta, con portada grande y proporcionada. En móvil
se coloca después del contenido; sin libro no se reserva una columna vacía.

Las miniaturas usan `object-fit: cover`; el visor conserva las imágenes completas.
El detalle actual de la portada personalizada y la migración aditiva se documenta
en [publication-covers.md](publication-covers.md).
