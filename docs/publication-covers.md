# Galería de una fila y portada por publicación

La instrucción de una sola fila reemplaza la cuadrícula del adjunto anterior.
Las publicaciones amplias muestran hasta cuatro miniaturas cuadradas, con separación
de 8 px, sin segunda fila ni desplazamiento horizontal. Con más de cuatro fotos,
la cuarta conserva su fotografía y una superposición `+N`, donde `N = total - 3`.
Por ejemplo, seis adjuntos muestran tres miniaturas normales y una cuarta con `+3`.
Cada clic abre el visor existente en la foto seleccionada, manteniendo todos los
archivos originales y su orden. Solo las miniaturas usan `object-fit: cover`.

Se conserva el ancho completo de la publicación, la columna de obra relacionada,
su portada grande, navegación, acciones y sidebar. El corazón social usa `#E85D75`,
los comentarios `#75A9DF` y el ojo `#A99BD9`; los favoritos de biblioteca no reciben
estos estilos. El ojo se muestra en reseñas/publicaciones, no en eventos automáticos
de lectura. El registro de vistas no cambió.

## Portada personalizada

El usuario autorizó explícitamente completar esta funcionalidad además de la galería.
La tabla aditiva `app.portadas_publicacion` guarda una imagen opcional por publicación
con su tipo detectado, bytes originales y revisión UUID. No actualiza obras,
ediciones, bibliotecas ni imágenes de la galería. Los registros anteriores no se
reescriben. La migración es `0075_publication_book_cover`, posterior a 0074.

En el formulario de creación, después de enlazar un libro, se puede elegir
«Usar portada del catálogo» o «Subir imagen propia». Hay selector de archivo,
captura de cámara cuando el dispositivo la admite, vista previa y cambio/eliminación
de la selección antes de publicar. La creación con portada y adjuntos es atómica.
El conjunto conserva el límite de 25 MB, y cada portada admite hasta 5 MB.

En una publicación propia, el menú «Editar publicación» abre el compositor con
la portada precargada. La vista pública no muestra controles de carga.
El formulario permite conservarla, reemplazarla o elegir el catálogo y guardar. La eliminación
solo afecta a la portada personalizada; vuelve a usarse el catálogo o el placeholder
existente. Los cambios no modifican fotos, descripción ni libro enlazado.

El servidor valida JPEG, PNG, GIF y WebP mediante decodificación/verificación de
imagen, además del tamaño máximo. GET aplica la misma visibilidad que los adjuntos
existentes y usa `nosniff` y `private, no-store`. PUT/DELETE requieren autenticación
y autorización para actuar por el perfil de la publicación. Cambiar la visibilidad
invalida también el acceso a la portada.

## Rutas y respuestas

- Crear: `POST /api/posts` acepta el archivo opcional multipart `book_cover`.
- Leer: `GET /api/posts/{post_id}/book-cover`.
- Reemplazar: `PUT /api/posts/{post_id}/book-cover`, multipart `book_cover`.
- Volver al catálogo: `DELETE /api/posts/{post_id}/book-cover`, idempotente.

El mural devuelve `custom_book_cover_url` y `can_edit_book_cover`. La URL incluye
una revisión para invalidar la imagen anterior al reemplazarla. La portada del
catálogo sigue devolviéndose por separado; las portadas se consultan por lotes.
La lista antigua de publicaciones también devuelve la portada personalizada.

## Validación

Backend: pruebas de creación atómica, lectura posterior, reemplazo, eliminación,
autoría, visibilidad, imágenes inválidas/truncadas, tamaño máximo, conservación
de adjuntos, catálogo intacto, fallback y ausencia de vistas por cargar portadas.

Frontend: miniaturas iguales en una sola fila en nueve temas y distintos anchos,
regla `+3` para seis fotos y ausencia de indicador para cuatro, apertura de la foto
seleccionada, visor con los seis adjuntos, carga real de un archivo en la vista
previa del editor, guardado y vuelta al catálogo. También se conservan las pruebas
de likes, comentarios, sidebar, navegación y carruseles.

Se debe ejecutar `alembic upgrade head` en cada entorno antes del despliegue.
El selector de cámara depende del soporte del navegador/dispositivo.

## Archivos principales

Frontend: `PostGallery.jsx`, `FeedCard.jsx`, `MuralActivityCard.jsx`,
`MuralPage.css`, `PostComposer.jsx`, `PublicationCoverPicker.jsx`,
`PublicationCoverPicker.css`, `PublicationCoverEditor.jsx`, `feedService.js`
y las pruebas/fixture del mural.

Backend: `social/models.py`, `schemas.py`, `router.py`, `feed_service.py`,
`post_covers.py`, `app/main.py`, migración 0075 y `test_publication_covers.py`.
La migración se aplicó localmente y `alembic current` confirmó 0075 como revisión
actual. Pasaron 91 pruebas backend y las regresiones del navegador; después del
último ajuste de validación/autorización se repitieron las 30 pruebas de portadas
y feed. Lint sin errores (advertencia previa en Layout), build correcto con el
aviso previo de tamaño del bundle.
