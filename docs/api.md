# Documentación de la API

## Propósito

Este documento define el proceso mínimo para documentar y mantener actualizada la API de LibrIA. Su objetivo es garantizar que el backend quede comprensible para desarrolladores, reviewers y futuros integrantes del equipo, sin depender solo de Swagger.

La API se implementa con FastAPI, y la documentación operativa debe mantenerse junto con el código real y con los contratos HTTP que expone el sistema.

## Alcance

Este documento aplica a todas las rutas expuestas por el backend en `apps/backend/app`, especialmente:

- autenticación
- usuarios
- libros y biblioteca
- lectura y experiencia lectora
- integraciones externas como Google Books

## Fuente de verdad

La documentación oficial en tiempo real se encuentra en Swagger/OpenAPI:

```text
http://localhost:8000/docs
```

Este archivo actúa como referencia de proceso y como registro de convenciones, decisiones y estado del API. No reemplaza la documentación automática de FastAPI, pero sí complementa la descripción operativa del sistema.

## Proceso de documentación

Cada cambio en la API debe cumplir con este flujo:

1. Revisar el endpoint o servicio que cambia.
2. Actualizar el schema y la respuesta esperada.
3. Confirmar si el cambio modifica request, response, errores o permisos.
4. Actualizar la documentación técnica del módulo.
5. Verificar que la ruta quede visible en Swagger.
6. Registrar el cambio en este documento si afecta comportamiento o contratos.

## Convenciones

### Nomenclatura

- Usar nombres claros en plural cuando correspondan: `/auth`, `/users`, `/books`.
- Mantener rutas RESTful y consistentes con el dominio del negocio.
- Preferir verbos en el nombre del recurso solo si es necesario; en general, usar recursos y métodos HTTP.

### Respuestas

Los endpoints deben responder con:

- `200 OK` para consultas exitosas.
- `201 Created` para creaciones correctas.
- `204 No Content` cuando no hay body.
- `400 Bad Request` para datos inválidos.
- `401 Unauthorized` para sesiones o tokens inválidos.
- `403 Forbidden` para acceso no autorizado.
- `404 Not Found` si el recurso no existe.
- `500 Internal Server Error` solo para errores no controlados.

### Errores

Las respuestas de error deben ser consistentes y legibles. Se recomienda:

```json
{
  "detail": "Mensaje claro del error"
}
```

En casos complejos, puede incluirse un bloque adicional con validaciones por campo.

## Estructura del backend

Los módulos del backend deben organizarse de la siguiente forma:

```text
apps/backend/app/modules/<modulo>/
  __init__.py
  models.py
  schemas.py
  repository.py
  service.py
  router.py
```

### Responsabilidades

- `router.py`: define endpoints HTTP.
- `service.py`: aplica reglas de negocio.
- `repository.py`: encapsula consultas a base de datos.
- `models.py`: define entidades ORM.
- `schemas.py`: define DTOs y validaciones con Pydantic.

## Módulos y estado actual

### Auth

Responsable de autenticación, registro e identidad del usuario.

Endpoints esperados:

- `POST /auth/register`
- `POST /auth/login`
- `GET /auth/me`
- `GET /auth/google/login` (si se activa la integración OAuth)
- `GET /auth/google/callback` (si se activa la integración OAuth)

Documentar aquí:

- payload de entrada
- token emitido
- roles o permisos
- respuesta de usuario autenticado
- errores esperados

### Users

Responsable de perfil, datos del usuario y gestión de lectura.

Documentar aquí:

- datos públicos y privados del usuario
- restricciones de actualización
- validaciones de email, nombre y avatar

### Books

Responsable de catálogo y libros del sistema.

Documentar aquí:

- búsqueda por título, autor o categoría
- metadatos del libro
- campos de ISBN, editorial, páginas y resumen
- respuestas vacías o no halladas

### Library

Responsable de la biblioteca personal del lector.

Documentar aquí:

- estado del libro: pendiente, leyendo, terminado
- progreso de lectura
- relación entre usuario y libro
- reglas de consistencia en el estado

### Google Books

La integración con Google Books se documenta como parte de la capa externa del sistema.

Debe especificarse:

- endpoint externo usado
- clave/API key o configuración necesaria
- campos normalizados que se conservan en la app
- mapeo de campos de Google Books a los modelos internos
- manejo de resultados nulos o imágenes faltantes

## Reglas para actualizar la documentación

Cuando se modifica una ruta, se debe revisar y actualizar:

- comentarios y docstrings del endpoint
- descripciones del response model
- ejemplo de request/response
- estado o notas del caso de uso
- este archivo si el cambio afecta la operación del sistema

## Checklist antes de merge

Antes de cerrar un PR o integrar cambios al backend, revisar:

- [ ] La ruta existe y responde en Swagger.
- [ ] Los schemas están actualizados.
- [ ] Los errores esperados están documentados.
- [ ] Los permisos y autenticación están definidos.
- [ ] La respuesta de éxito coincide con el uso real del frontend.
- [ ] Se actualizó la documentación del módulo afectado.
- [ ] Se validó con pruebas o con una petición manual.

## Recomendación de mantenimiento

Se recomienda que cada módulo tenga una pequeña sección en este documento o en un archivo específico del módulo, con:

- finalidad del recurso
- endpoints disponibles
- payloads principales
- ejemplos de uso
- notas de negocio

Esto permite mantener la documentación estable y legible sin depender solo del OpenAPI.

## Ejemplo de registro de cambio

```text
Fecha: 2026-09-12
Cambio: integración de Google Books y normalización de metadatos
Impacto: /books/search y detalle del libro ahora usan datos reales de Google Books
Notas: se documentaron campos principales, fallbacks y respuesta esperada
```

## Referencias

- [Arquitectura de LibrIA](architecture.md)
- [Modelo de datos](data-model.md)
- [Base de datos](database.md)
- Swagger/OpenAPI disponible en el backend en ejecución
