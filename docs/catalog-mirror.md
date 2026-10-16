# Catálogo local y Google Books

Explorar y las fichas consultan `/api/books` y `/api/books/{volume_id}` en el backend. La clave `GOOGLE_BOOKS_API_KEY`, si se configura, permanece en el backend; el navegador ya no llama a Google.

La búsqueda con texto consulta siempre Google Books. Como `langRestrict=es` omite numerosas ediciones realmente españolas, recupera hasta tres páginas amplias y aplica localmente el filtro de idioma. Incorpora cada resultado aceptado al catálogo local y solo entonces responde desde los registros persistidos. La interfaz presenta cada edición seleccionable con título, autor y metadatos. Las variantes de una misma obra comparten identidad y reseñas mediante una clave normalizada de título y autor que ignora tildes, puntuación, orden del nombre y etiquetas de edición; los volúmenes posteriores de una saga permanecen separados. El JSONB conserva campos desconocidos, autores, identificadores, imágenes, valoraciones externas, datos de venta y acceso. Si Google no está disponible, la búsqueda puede mostrar coincidencias locales con una advertencia explícita.

La primera apertura de una ficha obtenida mediante búsqueda solicita y conserva el recurso de detalle completo (`projection=full`); las aperturas posteriores se resuelven desde PostgreSQL. Un resultado de búsqueda puede tener menos campos que una ficha de detalle; `detail_complete` registra esta diferencia. La respuesta refleja lo recibido por Google en la fecha `fetched_at`; no existe sincronización automática ni descarga del catálogo entero de Google.

Las columnas de obras y ediciones reciben título, descripción, idioma, páginas, editorial y portada. El JSON conserva el resto sin pérdida. Las fuentes Google Books y las referencias anteriores `libria-feed` apuntan a la misma edición. Si el libro ya tenía lecturas o reseñas, se completan sus datos conservando sus identificadores. No se fusionan automáticamente volúmenes distintos de Google por parecido de título o ISBN.

Las valoraciones externas permanecen dentro del catálogo y no se convierten en reseñas personales ni en hechos analíticos del comportamiento de los usuarios. Los intentos activos conservan su total de páginas; los pendientes pueden recuperar el total del catálogo.

Los registros antiguos creados solo con título y páginas no contienen todavía una respuesta completa de Google: se completan al consultar su ficha, cuando su referencia corresponde a un volumen de Google. Los libros ficticios con referencias locales siguen siendo locales. Los resultados de venta y acceso representan el país de la respuesta de Google; no se garantiza que sean idénticos para otros países.

Pruebas: `python -m unittest discover -s tests -p test_catalog_mirror.py`. Verifican la conservación íntegra del JSON, consultas repetidas sin proveedor, detalle disponible desde la base, resultados vacíos y conservación de los identificadores usados por reseñas y biblioteca.

Referencia: https://developers.google.com/books/docs/v1/reference/volumes
