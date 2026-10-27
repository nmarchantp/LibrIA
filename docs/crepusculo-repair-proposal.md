# Propuesta separada: reparación de Crepúsculo

**Estado: NO EJECUTADA.** Este documento no es una migración ni un script. Los IDs son los identificados en el diagnóstico anterior; deben comprobarse nuevamente antes de cualquier intervención.

## Registros involucrados

| Obra actual | ID | Situación |
| --- | --- | --- |
| Crepúsculo | `06574399-dee7-4743-bf75-b480fd6d97c9` | Mezcla documento de 1843 y dos ediciones de Meyer |
| Crepúsculo (Saga Crepúsculo 1) | `ae502678-4db3-4e5f-b9de-fd641a8c018d` | Edición de Meyer de 2010 |

| Edición | ID | Google Books | Destino propuesto, pendiente de verificación |
| --- | --- | --- | --- |
| El crepúsculo, 1843, sin autor identificado | `8ae6371d-7bb9-4d8b-9d13-7d26a2b834c4` | `AqYoAAAAYAAJ` | Conservar obra `06574399-…` |
| Meyer, 2008, ISBN 9788420471938 | `b5bb02a9-31a3-4b62-92ed-9d77fc9ba5fd` | `aEyfQwAACAAJ` | Obra `ae502678-…` |
| Meyer, 2015, ISBN 9786073139755 | `497fb442-cef6-4a6d-bcd6-aab6078fc02b` | `npXvCgAAQBAJ` | Obra `ae502678-…` |
| Meyer, 2010, ISBN 9788420499062 | `4697aed8-ace4-4ab7-9b75-7052ce94aa83` | `a_6j9IHQ2NkC` | Conservar obra `ae502678-…` |

## Procedimiento propuesto

1. Respaldar y restaurar una copia aislada de PostgreSQL. Revalidar fuentes, autores e ISBN y capturar todas las FK y referencias textuales a ambos IDs. El diagnóstico anterior no encontró bibliotecas, lecturas, reseñas ni publicaciones asociadas, pero esto debe revisarse de nuevo.
2. Conservar ambos IDs de obra y los cuatro IDs de edición. La primera obra conservaría el documento histórico; la segunda representaría la novela de Meyer. No aplicar la función de consolidación heredada, que elimina obras.
3. Reasignar únicamente las dos ediciones modernas verificadas a la obra de Meyer. Conservar sus ISBN, portadas, fechas, editoriales, fuentes y referencias externas. No mover el documento histórico.
4. Corregir título, autoría y clave de la obra histórica con evidencia; retirar la asociación errónea a Meyer. Revisar también descripción, categorías, títulos alternativos y procedencia para no dejar metadatos contaminados. No inventar el autor del documento de 1843.
5. Registrar el año original de Meyer solo tras verificarlo documentalmente. La ficha de [Little, Brown](https://www.littlebrownlibrary.com/titles/stephenie-meyer/twilight/9780316160179/) es una fuente propuesta para comprobar 2005. Registrar la evidencia editorial definida en `bibliographic-identity.md`. No crear una edición ficticia de 2005. El año original del documento histórico permanece desconocido hasta verificarlo.
6. Si aparecieron relaciones personales desde el diagnóstico, detener la ejecución automática. Las lecturas con edición identificable permiten estudiar la corrección conjunta de `work_id` y `edition_id`; las relaciones sin edición necesitan revisión. Conservar IDs de entradas, lecturas, avances, reseñas, revisiones, notas y demás entidades. Resolver explícitamente colisiones usuario/obra y perfil/obra; nunca descartar una reseña para satisfacer una restricción única.
7. Preservar las rutas con los IDs actuales. Un enlace antiguo a la obra contaminada no permite saber qué contenido pretendía consultar el usuario: no redirigirlo silenciosamente a Meyer si ahora identifica el documento histórico. Una eventual resolución de alias requiere diseño y revisión independientes.
8. En la copia aislada, comprobar constraints compuestas de edición/obra, referencias privadas, conteos e identidad de todas las filas antes y después. Ensayar rollback completo. Revisar cachés y proyecciones actuales del catálogo; no reescribir manualmente hechos históricos ni estadísticas personales.
9. Entregar un diff de datos y resultados del ensayo para aprobación separada antes de intervenir la base real. La futura ejecución debe ser transaccional, acotada por los IDs exactos y abortar ante cualquier precondición distinta.

No incluir «Vida y muerte» ni otras obras homónimas en esta reparación. La similitud de título no demuestra que sean la misma obra.
