# Géneros más leídos y catálogo agrupado de tropos

## Estadística personal

`GET /api/profiles/me/reading-genres` exige autenticación y obtiene la cuenta
exclusivamente de la sesión. No admite un propietario alternativo ni se incorpora
a la respuesta del perfil comunitario.

Fuente: biblioteca operacional (`entradas_biblioteca`, `lecturas`, `obras.categories`).
Se excluyen entradas archivadas y se selecciona el intento más reciente por entrada,
ordenando por `created_at DESC, id DESC`, antes de filtrar `status = finished`.
Por ello, una obra actualmente en relectura no cuenta como terminada por una
finalización histórica. Una obra con varios intentos terminados cuenta una sola vez.

Cada categoría bibliográfica válida y distinta dentro de una obra es una asignación.
Se normalizan espacios, Unicode y mayúsculas para evitar duplicados. No se traducen,
dividen ni reclasifican categorías libres, y no se utilizan los favoritos declarados.
Los valores ausentes, estructuras inválidas, elementos no textuales, cadenas vacías
y etiquetas explícitas de ausencia de categoría no se cuentan.

```
porcentaje = asignaciones del género / todas las asignaciones válidas × 100
```

Ejemplo: una obra terminada con Fantasía/Romance y otra con Fantasía producen
3 asignaciones: Fantasía 66,7%, Romance 33,3%. Repetir Fantasía dentro de los
metadatos de una misma obra no aumenta su peso.

Se devuelven los cinco primeros, ordenados por número de asignaciones descendente,
con desempate alfabético determinista. El denominador incluye también géneros fuera
del top cinco. El redondeo es decimal a una cifra, `ROUND_HALF_UP`; no se fuerza una
suma de 100%, pues podría falsear las asignaciones. La interfaz usa formato español.

Respuesta: `status`, `finished_books`, `classified_books`, `unclassified_books`,
`total_assignments` y `genres` (nombre, asignaciones y porcentaje). Se informa cobertura
incompleta. Los estados vacíos distinguen ausencia de terminados y ausencia de
metadatos utilizables. No se crea una categoría ficticia «sin categoría».

El indicador grupal IND-004 no se reutiliza: aplica pesos 1/n, ventanas temporales
y umbrales de publicación distintos. No se modifican ETL, recomendaciones ni IA.

## Presentación y privacidad

«Sobre mí» conserva la biografía e incorpora las etiquetas de géneros favoritos.
«Mis gustos literarios» conserva la edición de géneros y tropos; muestra los tropos
guardados, sin repetir las etiquetas de géneros de Sobre mí.

La tarjeta inferior «Mis géneros más leídos» reemplaza el antiguo estado vacío de
frase favorita. Contiene barras semánticas adaptadas a las seis paletas, porcentajes
y cobertura. Se vuelve a consultar cuando cambia la biblioteca del contexto y al
montarse; incluye reintento de errores. No se escriben preferencias desde esta tarjeta.

En `/profiles/:profileId` se mantienen únicamente biografía y preferencias públicas,
sin barras, solicitudes de estadísticas privadas ni controles de edición.

Limitación bibliográfica: `obras.categories` son etiquetas libres del catálogo y no
una taxonomía homologada de géneros. La exactitud semántica depende de esos metadatos;
no se inventan equivalencias ni se deducen géneros a partir de títulos o favoritos.

## Migración y catálogo

`0044_trope_catalog_groups` agrega `group_name` al catálogo y 36 opciones, para un
total de 51 en la instalación base. Conserva los 15 registros originales, IDs,
nombres, estado activo y selecciones. Los cinco grupos son Romance y relaciones,
Fantasía y magia, Misterio y suspenso, Aventura y ciencia ficción, y Personajes y emociones.

La migración evita duplicados por ID y nombre normalizado. Ante un ID existente con
otro significado se detiene en lugar de sobrescribirlo. Reutiliza coincidencias de
nombre sin renombrar sus IDs. La reversión elimina solo la columna de agrupación:
conserva las opciones añadidas para no perder declaraciones ni romper claves foráneas.

Los catálogos y las preferencias guardadas incluyen el grupo de cada tropo. El selector
los organiza con encabezados, mantiene selección múltiple y permite buscar por nombre
ignorando diferencias de mayúsculas y acentos. Filtrar no borra selecciones ocultas.
Se conservan las opciones retiradas que el usuario ya tenía guardadas.

Se aplicó únicamente a la base local de desarrollo tras comprobar entorno y host.
Se compararon registros y relaciones antes/después: todos los IDs originales y las
selecciones existentes permanecieron intactos. No se migró producción.

## Validación

- 9 pruebas nuevas de fórmula, duplicados, redondeo, top cinco, metadatos, estados,
  intentos recientes, archivo, propiedad, proyección pública, grupos y migración.
- 10 pruebas de preferencias y 13 de roles/interacciones existentes.
- Navegador con API real y biblioteca temporal dentro de una transacción revertida:
  porcentajes, cobertura, errores y reintento, estados sin metadatos/sin terminados,
  51 opciones/5 grupos, búsqueda con acentos, selección oculta, guardado/recarga y
  conservación de selecciones anteriores. Sin estadísticas ni edición en perfil ajeno.
- Seis temas a 1440, 900, 390 y 320 px (24 combinaciones), incluido selector abierto,
  sin desbordamientos ni excepciones JavaScript. Revisión de capturas de las barras.
- ESLint, build, compilación Python y comprobación de Alembic.

Archivos nuevos: `reading_statistics.py`, `0044_trope_catalog_groups.py`,
`test_reading_genres.py`, `MostReadGenresCard.jsx`, `PreferenceTags.jsx` y este documento.
Modificados: `preference_models.py`, `preference_schemas.py`, `preferences_router.py`,
`profileService.js`, `ProfilePersonalColumn.jsx`, `ProfileAboutCard.jsx`,
`ProfileTastesCard.jsx` y `ProfilePreferences.css`.
