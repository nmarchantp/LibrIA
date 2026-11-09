# Moderación preventiva: entrega de etapa 1

## Estado

Etapa 1 implementada y validada en PostgreSQL local. La migración
`0082_moderation_foundation` se aplicó correctamente y es el head de Alembic.
No se activó la etapa 2. Las rutas actuales de publicación, edición, eliminación
y consulta pública conservan su comportamiento; el mural y su interfaz no se
modificaron en esta entrega.

## Archivos de esta etapa

| Archivo | Cambio |
| --- | --- |
| `apps/backend/app/modules/social/moderation_rules.json` | Reglas versionadas y configurables para las ocho categorías del MVP |
| `apps/backend/app/modules/social/moderation_rules.py` | Normalización, validación de configuración y resultado estructurado; solo `approved` o `pending_review` |
| `apps/backend/app/modules/social/moderation_models.py` | Estado base y tablas privadas de revisiones, adjuntos, auditoría e idempotencia |
| `apps/backend/app/modules/social/moderation_service.py` | Preparación transaccional de ediciones, propiedad, consulta privada, permisos reales y detección de propuestas obsoletas |
| `apps/backend/app/modules/social/models.py` | Columnas aditivas de moderación y versión en publicaciones, reseñas y comentarios; preparación de borrado lógico en comentarios |
| `apps/backend/app/core/config.py` | Ruta opcional `MODERATION_RULES_PATH` |
| `apps/backend/migrations/env.py` | Registro de los modelos de moderación |
| `apps/backend/migrations/versions/0082_moderation_foundation.py` | Migración aditiva, restricciones, índices y protecciones de auditoría/propuestas |
| `apps/backend/tests/test_moderation_foundation.py` | 23 pruebas específicas de reglas, persistencia, permisos, transacciones y concurrencia |
| `apps/backend/tests/test_reading_challenge.py` | Corrección de aislamiento: la prueba de reto vacío consulta al usuario de fixture, no todos los retos reales |

Los cambios del orden de pestañas del perfil ya estaban presentes antes de esta
etapa y se conservaron.

## Persistencia y protección del historial

En `publicaciones`, `resenas` y `comentarios_publicacion` se agregaron:

- `moderation_status`, inicialmente `approved`.
- `moderation_version`, inicialmente `1`.

En comentarios se agregó `deleted_at`, inicialmente nulo. Su ruta de eliminación
actual todavía no se cambió: el uso del borrado lógico corresponde a la etapa 2.
En reseñas, el estado editorial `draft/published/hidden` permanece separado.

Nuevas tablas privadas:

- `app.revisiones_moderacion`: destino exclusivo mediante FK tipada, autor,
  propuesta, hallazgos, versión de reglas, versión y huella de la base pública,
  estado y ciclo de vida. Solo puede existir una propuesta pendiente activa por
  contenido. Un trigger impide modificar el texto y los datos de una propuesta
  ya registrada: debe crearse otra revisión.
- `app.adjuntos_moderacion`: archivos nuevos de la propuesta, separados de la
  galería y portada públicas. Conserva formatos y límites existentes y no genera
  URLs públicas.
- `app.auditoria_moderacion`: registros anexados, protegidos en PostgreSQL contra
  modificaciones y eliminaciones.
- `app.solicitudes_moderacion`: clave única por usuario/operación/UUID y hash del
  cuerpo; un reintento devuelve el mismo resultado y un cuerpo diferente con la
  misma clave produce conflicto.

No se analizó retroactivamente contenido, ni se sustituyeron textos, adjuntos,
fechas, asistentes o interacciones. Tampoco se crearon reportes, notificaciones
ni decisiones administrativas: sus servicios y tablas de negocio se completarán
en sus etapas autorizadas, sobre esta base.

## Contrato de los servicios

`analyze_content` devuelve estado, hallazgos con categoría/motivo/confianza y
versión de reglas. No rechaza automáticamente. Las palabras de temas sensibles
no son por sí solas un motivo para alertar.

`prepare_edit` valida la estructura con los esquemas existentes, comprueba la
propiedad y prepara la revisión sin aplicar sus cambios al contenido público,
incluso cuando las reglas permiten la propuesta. Conserva la versión previa.
Analiza título, cuerpo, nombre de obra y metadatos textuales del evento por separado, evitando
formar una frase ofensiva artificialmente al unir campos.

La huella pública incluye texto, estados, obra, valoración, fechas, orden y
contenido de imágenes, portada y datos del evento. Normaliza números decimales y
zonas horarias para evitar conflictos falsos al recargar registros desde la BD.
No incluye likes, vistas o nuevas asistencias: esas interacciones no invalidan
una edición pendiente. `assert_revision_current` detecta cambios posteriores,
incluso si una ruta anterior todavía no incrementa `moderation_version`.

La preparación bloquea el contenido padre y respeta el orden de bloqueo de
comentarios. Una nueva propuesta sustituye la pendiente anterior mediante su
ciclo de vida y registra el hecho; no borra propuestas ni auditoría.

Los servicios no hacen `commit`: el futuro consumidor debe confirmar o revertir
conjuntamente solicitud, propuesta, adjuntos y auditoría. Las pruebas verifican
que un fallo revierte todo el conjunto.

La consulta privada comprueba la autoría de la propuesta. La lectura
administrativa reutiliza `get_admin` y `AccountPermission(user_id, 'admin')`;
tener únicamente `user.role='admin'` no otorga acceso.

## Pruebas ejecutadas

```powershell
.venv/Scripts/python.exe -m unittest tests.test_moderation_foundation tests.test_mural_feed tests.test_activity_interactions tests.test_content_management tests.test_publication_events tests.test_identities tests.test_reading_challenge tests.test_profile_events tests.test_reviews
.venv/Scripts/python.exe -m alembic current
git diff --check
```

Resultado: **156 pruebas correctas**, incluidas **23 específicas** de moderación.
La primera ejecución ampliada detectó una prueba de reto anual que suponía una
base global vacía. Se limitó su consulta al usuario de fixture y se repitió la
suite completa con éxito; ningún reto real se eliminó o modificó.

Se verificó:

- Conversaciones literarias legítimas y señales de las ocho categorías.
- Unicode, acentos, caracteres invisibles, evasiones comunes y límites de entrada.
- Configuración inválida que falla explícitamente, sin aprobar silenciosamente.
- Pendientes que conservan la versión publicada, incluidos archivos y evento.
- Propiedad, privacidad, permiso administrativo real y comentarios de los tres destinos.
- Reintentos, conflictos de claves, sustitución de propuestas y referencias exclusivas.
- Auditoría inmutable, propuestas inmutables y rechazo sin decisión humana impedido por la BD.
- Cuatro solicitudes concurrentes con un resultado único y serialización sobre el padre.
- Rollback completo, reseñas canónicas vigentes, fechas/decimales estables y compatibilidad de rutas existentes.
- Ausencia de nuevos endpoints o activación de consumidores de moderación.

## Evidencia de integridad

Se compararon conteos y huellas de los campos originales antes de la migración y
después de la suite en diez tablas: publicaciones, reseñas, comentarios, eventos,
asistencias, los tres tipos de likes, visualizaciones y eventos de lectura.
Coinciden todas las huellas y conteos. Los registros históricos quedaron en
`approved`, versión `1`; no quedó ningún registro de prueba en las cuatro tablas
de moderación.

La evidencia local está en `artifacts/moderation-stage1/before.json`, `after.json`
y `verification.json`. Contiene conteos y hashes, no textos ni identificadores
personales de los contenidos.

## Límites y riesgos pendientes

1. **La moderación todavía no protege los envíos reales.** No hay rutas ni flag
   que activen parcialmente el sistema. La integración de escritores, visibilidad,
   conteos y rutas compatibles debe hacerse conjuntamente en la etapa 2.
2. Las reglas son heurísticas acotadas, con cobertura inicial principalmente en
   español. Pueden producir falsos positivos o negativos; una alerta requiere
   revisión humana. No se promete comprensión de citas, ironía o contexto.
3. `MODERATION_RULES_PATH` es configuración del operador, no una entrada de usuario.
   Los patrones deben revisarse y probarse; se cachean por proceso y los cambios
   requieren reinicio y nueva versión del conjunto. La entrada se limita a 20 000
   caracteres para el análisis; la etapa 2 debe armonizar ese límite con los
   comentarios de 200 palabras que hoy no tienen un límite global de caracteres.
4. La preparación valida estructura, propiedad y archivos, pero la aplicación de
   una propuesta tendrá que revalidar reglas de negocio y referencias vigentes
   del catálogo/evento. No existe aún un servicio que publique una propuesta.
5. Las nuevas FK conservan la historia y restringen el borrado físico de contenidos
   con revisiones. No deben conectarse los servicios a los comentarios reales
   hasta adaptar su eliminación lógica en la etapa 2.
6. La revisión almacena adjuntos privados; todavía no hay visor, acceso HTTP,
   política de retención o limpieza automática. Ningún recurso de propuesta se
   sirve por las rutas de imágenes públicas.
7. La migración toma los bloqueos de esquema propios de `ALTER TABLE`; conviene
   programar su aplicación en producción. La reversión automática destructiva está
   deshabilitada para preservar auditoría y propuestas.

La etapa 1 queda cerrada para revisión. No se avanzó a la etapa 2.
