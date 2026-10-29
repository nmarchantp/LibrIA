# Mantenedor de libros

Disponible en **Administración → Gestionar libros**, ruta `/admin/catalog`.
Requiere permiso efectivo de administrador y el catálogo administrativo habilitado.

## Libros y ediciones

- Buscar obras guardadas por título, autor o ISBN, con paginación.
- Filtrar posibles duplicados, libros sin portada y ediciones con ISBN pendiente.
- Crear una obra y registrar sus ediciones desde su ficha.
- Corregir título, autores, sinopsis, categorías, saga y número de volumen.
- Corregir cada edición: ISBN, idioma, editorial, fecha, páginas, formato y portada.
- Consultar las fuentes y los motivos de las correcciones recientes.

Las obras agrupadas se muestran una sola vez con sus ediciones, aunque conserven
UUID históricos. Los posibles duplicados se detectan por título normalizado,
autores conocidos y tipo de publicación; una novela no se confunde con su libro
para colorear o adaptación gráfica.

Cada guardado exige un motivo y conserva una auditoría. La versión de la ficha
evita sobrescribir cambios realizados desde otra pestaña o por otro administrador.
Las solicitudes se identifican para que reintentarlas no duplique registros.
Un ISBN repetido bloquea el guardado e indica revisar la obra existente.

Las correcciones editoriales se guardan separadas de las respuestas originales
de Google Books/Open Library. La presentación pública y la biblioteca utilizan
esas correcciones. Cambiar las páginas de una edición no modifica los avances ni
el total de páginas elegido en lecturas anteriores.

## Agrupar libros

1. Seleccionar dos libros en el catálogo, o abrir un posible duplicado desde la ficha.
2. Revisar el duplicado y la obra principal, con todas sus ediciones.
3. Comparar o simular el impacto en bibliotecas, lecturas, reseñas y valoraciones.
4. Resolver las reseñas en conflicto, indicar el motivo y confirmar la agrupación.

La agrupación conserva los registros e identificadores históricos. El historial
permite simular y confirmar la separación de una agrupación, con sus controles de
conflictos y actividad posterior. Para agrupar más de dos registros, añadir los
restantes a la obra principal mediante el mismo recorrido.

## Validación

Backend: `python -m scripts.validate_catalog_incorporation_rules` desde
`apps/backend`; instancia temporal de PostgreSQL con proveedores simulados.

Frontend: `npm run build` y las pruebas de navegador
`tests/catalog-maintenance.mjs` y `tests/catalog-preview.mjs`. Usan un navegador
con CDP y fixtures HTTP aisladas; no corrigen libros de la base de desarrollo.
