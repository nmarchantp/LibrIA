# Modelo social acordado

Decisión funcional para la siguiente evolución del módulo social. Este documento prevalece sobre las propuestas antiguas de perfiles, reseñas y publicaciones en `data-model.md`. La migración `0004_social_analytics` y el generador actual son un prototipo de actividad: todavía almacenan reseñas y avances simulados como publicaciones y no cumplen este contrato.

## Cuenta, perfil y capacidades

- `app.usuarios` representa a la persona que inicia sesión. El usuario tiene un único perfil personal público.
- El perfil personal puede tener simultáneamente las capacidades de lector, autor e influencer. Son distintivos y permisos de la misma identidad pública.
- Una librería es otro perfil público y puede tener varios usuarios administradores. Los miembros administradores tienen permisos propios dentro de esa organización; no comparten credenciales.
- La verificación (`pending`, `verified`, `rejected`, `suspended`) es independiente de los roles. El estado de verificación no concede por sí solo permisos de publicación.
- Cada operación de escritura indica el perfil actor. El backend comprueba que el usuario autenticado puede actuar por él y que ese perfil tiene la capacidad necesaria.
- En contenido creado por un perfil se guardan `author_profile_id` (autor visible) y `created_by_user_id` (persona autenticada que ejecutó la acción). Nunca se acepta `created_by_user_id` del cliente.

## Entidades de contenido

| Entidad | Propiedad y regla |
|---|---|
| `app.publicaciones` | Contenido manual de perfiles con permiso. Tiene subtipo explícito: `free`, `institutional`, `launch`, `event`, `news` o `promotion`. Puede vincular una o varias obras mediante una tabla puente; el vínculo no cambia el subtipo. |
| `app.resenas` | Opinión pública de un perfil sobre una obra. `author_profile_id` y `work_id` son obligatorios y únicos en conjunto. Tiene texto, calificación opcional, indicador de spoiler, estado y fechas. Puede editarse después de una relectura; una lectura nunca crea automáticamente otra reseña. |
| `app.progreso_lectura` | Registro operacional de un cambio de página en una sesión de lectura. Un avance visible se deriva de ese cambio y conserva la página, el total y el porcentaje al momento del evento. No contiene texto libre. Solo los perfiles personales con capacidad lectora generan avances. |

Las sesiones de lectura siguen siendo independientes y conservan las relecturas. Una reseña puede incorporar más adelante una referencia opcional a la sesión que motivó su última edición, sin cambiar su identidad `(author_profile_id, work_id)`.

## Feed, comentarios y reacciones

- El feed combina publicaciones, reseñas y avances mediante una consulta o servicio. Cada elemento declara `feed_item_type`: `publication`, `review` o `reading_progress`. Una publicación incluye además `publication_type`.
- Los comentarios y las reacciones aceptan los tres tipos de contenido. Se usará una referencia transversal con integridad referencial comprobable en PostgreSQL; el par libre `(type, id)` sin FK no basta.
- Una reacción de un usuario a un elemento de contenido es única por tipo de reacción. Los comentarios conservan tanto perfil visible como usuario ejecutor cuando alguien actúa como organización.
- Moderación y ocultamiento se aplican al elemento original; el feed no muestra contenido oculto. Las acciones administrativas se auditan.

## Consecuencias para la implementación actual

1. Sustituir `app.publicaciones.user_id/source/kind` por perfil actor, usuario ejecutor y subtipo de publicación. Migrar o retirar los datos sintéticos de `reading` y `review` creados en esa tabla; no reinterpretarlos como reseñas o avances reales.
2. Crear perfiles personales, roles/capacidades, membresías organizacionales y estado de verificación antes de habilitar escritura de publicaciones bajo las nuevas reglas.
3. Implementar reseñas por perfil y obra, con `UNIQUE (author_profile_id, work_id)` y edición controlada por el perfil actor.
4. Generar avances desde actualizaciones reales de lectura; adaptar el generador para llamar a endpoints de acciones válidas por rol y no enviar reseñas o avances a `POST /posts`.
5. Convertir el feed y el ETL para leer las tres entidades por separado y mantener métricas diferenciadas.

Estas reglas son el contrato funcional; los nombres de endpoints y la estrategia física de comentarios/reacciones pueden resolverse durante la implementación sin cambiar el comportamiento acordado.
