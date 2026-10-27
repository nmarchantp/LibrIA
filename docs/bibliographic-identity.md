# Identidad bibliográfica: prevención y verificación

## Reglas

- Búsqueda: conserva comparación sin tildes ni distinción de mayúsculas. No autoriza fusiones.
- Identidad: título completo normalizado y conjunto completo de autores conocidos coincidentes. No se eliminan artículos, números de volumen, subtítulos ni paréntesis arbitrarios. Solo se normalizan indicaciones explícitas de edición.
- Los nombres invertidos con coma y las iniciales admiten normalización tipográfica. No se supone que autores distintos sean equivalentes por compartir un apellido.
- Un autor ausente o un marcador como «Autor desconocido» no aporta identidad positiva, incluso frente a otro registro anónimo.
- Las fuentes originales de las ediciones tienen prioridad sobre una asociación de autor heredada de una obra contaminada. Una fuente anónima o autores contradictorios impiden reutilizar automáticamente esa obra.
- Las variantes bilingües explícitas pueden vincularse cuando los autores conocidos coinciden. Un ISBN identifica una edición; distintos ISBN no impiden que ediciones verificadas compartan obra.
- Un `workKey` de Open Library no evita la comprobación de título y autores. Se conserva la reutilización de una edición ya identificada por su fuente o ISBN sin conflicto de autor.
- La búsqueda no realiza consolidaciones físicas. La función heredada de consolidación queda inactiva salvo invocación explícita con `reviewed=True`; no debe usarse para la reparación de Crepúsculo.
- Las claves históricas no se reescriben. La importación comprueba evidencia bibliográfica en vez de confiar únicamente en una clave antigua. Si una clave pertenece a una obra incompatible, el nuevo registro queda sin esa clave, sin modificar la anterior.

## Candidatos para revisión

`duplicate_candidate` compara similitud de títulos; `duplicate_work_candidates(db, work_id)` produce un informe de solo lectura con IDs, títulos y motivo. No crea relaciones ni modifica fuentes o estados de consolidación.

«Crepúsculo» y «Crepúsculo (Saga Crepúsculo 1)» con Meyer son candidatos. No se agrupan automáticamente. La eliminación de un sufijo de saga se limita a esta sugerencia. Los títulos coincidentes sin autor también pueden sugerirse para revisión, nunca como identidad confirmada. Autores conocidos distintos impiden la sugerencia automática.

## Año original y fechas de edición

Ya existe `Work.first_publication_date`: no hace falta una nueva columna de fecha. Sus valores históricos no son confiables porque procedían de ediciones.

Para poder presentarlo como original, se exige una fuente editorial independiente en `CatalogSource`, proveedor `libria-verification`, estado `validated`, ligada a una edición de la misma obra. Su JSON debe incluir:

```json
{
  "originalPublication": {
    "workId": "UUID de la obra",
    "date": "fecha verificada igual a Work.first_publication_date",
    "evidenceUrl": "https://fuente-bibliografica-confiable/...",
    "verifiedBy": "identificador del responsable de la revisión",
    "verifiedAt": "fecha de la revisión"
  }
}
```

Esta estructura es una convención de procedencia reutilizando JSONB existente. No implica que una URL por sí sola verifique una fecha: el responsable debe comprobar la fuente antes de registrar la evidencia. Ninguna importación de Google/Open Library puede emitir esta verificación. No se creó ningún registro editorial en la base real.

La respuesta incluye `firstPublicationDate` solo si está verificada y `originalPublicationVerified`. `earliestEditionDate` conserva el criterio de ordenación por edición, sin presentarlo como año original. El frontend deja de usar `volumeInfo.publishedDate` como sustituto del año del encabezado. Las fechas individuales y la ficha técnica permanecen intactas.

## Validación

```powershell
# Desde apps/backend: sin PostgreSQL ni red real.
.\.venv\Scripts\python.exe -B -m unittest tests.test_bibliographic_identity tests.test_google_books_resilience tests.test_open_library.OpenLibraryNormalizationTest -v

# Desde apps/web.
node tests/book-publication-date.mjs
npm run build
```

Las pruebas bibliográficas usan SQLite en memoria con los modelos reales del catálogo y los handlers de importación. Simulan únicamente los bloqueos específicos de PostgreSQL y la consulta de valoración comunitaria. No sustituyen una validación posterior de constraints, concurrencia y reparación sobre una copia restaurada de PostgreSQL. No se ejecutó la suite que abre sesiones de escritura contra la base configurada.

La validación más estricta puede mantener separadas algunas ediciones legítimas con metadatos incompletos. Es preferible una revisión explícita a perder identidad y relaciones por una consolidación incorrecta.
