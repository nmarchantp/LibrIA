# Incorporación de libros a LibrIAverse

Buscar un libro o abrir su detalle no crea obras ni ediciones. Al agregarlo a
la biblioteca, el servidor verifica su ficha con el proveedor y aplica estas reglas:

1. Reutiliza una edición si coincide su referencia externa o su ISBN válido.
   ISBN-10 y su ISBN-13 equivalente identifican una misma edición.
2. Si la edición es nueva, reutiliza una obra cuando coinciden el título y el
   conjunto completo de autores normalizados. La normalización contempla acentos,
   puntuación y etiquetas explícitas de edición, incluidas `(NE)`, `Edición
   tapa dura` y separadores bilingües como `/ /`. Un subtítulo editorial `#1`
   no crea otra obra; se conservan los otros números, subtítulos y tomos.
   Un mismo título con otro autor corresponde a otra obra.
3. Si no encuentra la obra, crea `app.obras` y sus relaciones con autores.
4. Registra la edición en `app.ediciones`, con su procedencia en
   `app.fuentes_catalogo`. Esto también ocurre cuando la lectura personal todavía
   no tiene una edición elegida: catalogar una edición no la selecciona para leer.
5. Consulta otras ediciones en Google Books, pagina sus resultados y verifica
   cada ficha antes de incorporarla a la misma obra. Las ediciones con conflictos
   contra registros previos se omiten; no se reasignan obras históricas.

La consulta de ediciones tiene un presupuesto de tiempo. Guarda las ediciones
verificadas que el proveedor entrega; no garantiza recuperar todas las ediciones
publicadas. Una falla de esta consulta complementaria no impide guardar el libro
solicitado. Para agrupar por título y autores se requieren autores conocidos.

Las obras del flujo anterior que conservan una referencia externa pero carecen
de ediciones pueden recuperarlas al agregarse nuevamente a una biblioteca.
Repetir la misma solicitud no vuelve a consultar al proveedor ni duplica registros.

En Explorar libros, una obra persistida se etiqueta como **LibrIAverse**, aunque
su ficha provenga de Google Books. Los resultados externos que coinciden por
referencia, ISBN o título y autores se presentan como esa obra local, con sus
ediciones agrupadas. Los libros sin coincidencia local siguen siendo externos.
La procedencia original se conserva por separado de la pertenencia al catálogo.
Los libros para colorear, resúmenes, guías y adaptaciones gráficas conservan una
identidad distinta de la novela, incluso si comparten autor o nombre bilingüe.
Las fichas de búsqueda usan el título de la obra y pueden tomar su portada de
una edición del grupo sin seleccionar esa edición para la lectura personal.

Estos cambios se aplican al flujo `CATALOG_DISCOVERY_ENABLED`, activo en la
configuración local. No ejecutan una migración ni fusionan duplicados históricos.

Para duplicados existentes, `scripts.repair_catalog_group` permite revisar un
grupo explícito por UUID y, con `--apply` y un administrador existente, agruparlo
mediante las simulaciones y fusiones canónicas auditadas. Antes crea un respaldo
local. Conserva los UUID, ediciones, bibliotecas, lecturas, reseñas y revisiones;
rechaza formas bibliográficas diferentes y conflictos de reseñas sin resolver.
No ejecuta agrupaciones generales durante una búsqueda.

Validación en Windows, desde `apps/backend`:

```powershell
.\.venv\Scripts\python.exe -m scripts.validate_catalog_incorporation_rules
```

El validador crea un PostgreSQL temporal en un puerto local aleatorio, ejecuta
las migraciones y las pruebas con proveedores simulados, y detiene su servidor.
No utiliza la base de datos configurada para la aplicación.
