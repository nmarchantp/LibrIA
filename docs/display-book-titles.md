# Títulos visibles en español

## Procedencia comprobada

La revisión de código y una consulta de PostgreSQL en una transacción `READ ONLY` confirmaron que los títulos concatenados de «El infinito en un junco» ya aparecen completos en `CatalogSource.payload.volumeInfo.title` de Google Books. Coinciden con `Edition.title`; LibrIAverse no añadió la traducción.

Google Books conserva `volumeInfo.title`; Open Library copia `edition.title` al mismo formato de respuesta. El catálogo local devuelve los títulos de origen. No se cambió ninguno de estos flujos, la identidad bibliográfica ni los valores almacenados.

## Criterio visual

`apps/web/src/utils/bookTitles.js` concentra la política de presentación. Exige que la edición esté identificada como española (`es`, `spa` y variantes compatibles), una única barra con espacios y evidencia explícita de un par de títulos paralelos.

El catálogo conservador de pares reconoce «El infinito en un junco / Papyrus» y los títulos ingleses completos observados, incluida la variante del proveedor «Inven Tion». También reconoce un título base idéntico con descriptores de edición traducidos de forma explícita a ambos lados. No se usa detección automática de idioma ni traducción automática.

También se reconoce la edición limitada firmada y el caso real en que Google Books deja un paréntesis abierto al final de la traducción inglesa. Se tolera una nota de edición inglesa truncada únicamente para comprobar el título paralelo conocido; esto no autoriza recortar cualquier título con paréntesis incompletos.

Se conservan las indicaciones españolas de edición. Se normalizan las mayúsculas del nombre conocido y de descriptores reconocidos; los paréntesis desconocidos se preservan literalmente para no cambiar nombres propios o subtítulos. El texto mostrado siempre procede de la parte española existente.

Un par desconocido, una barra legítima, un título bilingüe ambiguo o una edición sin idioma confirmado permanecen completos. El catálogo se puede ampliar con nuevas equivalencias verificadas; no se pretende reconocer automáticamente todos los pares posibles. La opción `preserveBilingual` permite conservar explícitamente un título bilingüe auténtico en futuras integraciones.

## Aplicación y conservación

- `booksService.normalizeGoogleBook`: búsqueda, detalle, recomendaciones y biblioteca con `catalog_volume` comparten la normalización.
- Las ediciones se copian con su título visible y `originalTitle`; seleccionar una edición conserva ambos valores.
- `rawVolume` permanece intacto. El libro normalizado también guarda `originalTitle`.
- La biblioteca sin datos de catálogo conserva su título, ya que no existe evidencia del idioma de su edición.
- Los envíos existentes de biblioteca y lectura usan el título original cuando está disponible, evitando persistir accidentalmente una etiqueta visual.
- No se modificaron estilos, endpoints, ISBN, identificadores, agrupación, tablas ni registros de PostgreSQL.

## Pruebas

Desde `apps/web`:

```powershell
node tests/book-titles.mjs
node tests/book-publication-date.mjs
npm run build
```

Se cubren 25 casos de títulos y 11 comprobaciones de integración/procedencia: ejemplos solicitados, variantes observadas, adaptaciones, ediciones limitadas/firmadas/ilustradas/especiales, notas inglesas truncadas, barras legítimas, inglés sin traducción, idioma desconocido, subtítulos y títulos bilingües auténticos. Se comprueba que no cambian el objeto original, los ISBN ni los IDs. Las pruebas de fechas conservan sus cinco comprobaciones.
