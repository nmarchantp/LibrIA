# Arquitectura de LibrIA

## Decisión

LibrIA se implementa como un **monolito modular**: un frontend React independiente, una sola aplicación FastAPI y una sola instancia PostgreSQL. No se crearán microservicios durante el MVP.

## Flujo principal

```text
React -> API REST -> FastAPI -> PostgreSQL
                         |
                         +-> API bibliográfica
                         +-> ETL -> schema analytics -> proveedor de IA
```

La IA nunca consulta directamente las tablas operacionales. FastAPI construye un JSON usando exclusivamente datos transformados del schema `analytics`.

## Límites del backend

Cada módulo puede contener `router`, `service`, `repository`, `models` y `schemas`. La dirección permitida es:

```text
router -> service -> repository -> PostgreSQL
```

- Router: HTTP y códigos de respuesta.
- Service: reglas de negocio.
- Repository: consultas mediante SQLAlchemy.
- Model: persistencia.
- Schema: validación con Pydantic.

Los módulos previstos son `auth`, `users`, `books`, `library`, `reading_experience`, `social`, `analytics` y `ai_insights`. Actualmente existen `auth` y `users`, además de los modelos de `books` y `library`; los servicios y endpoints de estos dos últimos están pendientes. El módulo `social` agrupará perfiles administrados, seguimientos, reseñas públicas, publicaciones y comentarios. Las integraciones externas dependen de interfaces propias, no de un proveedor concreto.

## Datos

- `app`: información operacional.
- `analytics`: indicadores generados por ETL.
- `ai`: historial de solicitudes, resultados de análisis y recomendaciones de IA.

El [modelo de datos completo](data-model.md) detalla entidades, campos, relaciones y reglas, distinguiendo las tablas existentes de las propuestas. Separa obras de ediciones y cada relectura de sus experiencias; el progreso se calcula usando las páginas de la edición seleccionada. Los perfiles son públicos; la visibilidad de experiencias y biblioteca está documentada como una decisión pendiente.

El ETL solamente lee `app` y escribe `analytics`; nunca modifica los datos operacionales.

## Decisiones de seguridad

JWT, contraseñas con Argon2, secretos en variables de entorno, CORS explícito, validación Pydantic, ORM, control de propiedad por usuario y logs sin datos sensibles.

## Fuera del MVP

Microservicios, Kafka, RabbitMQ, Kubernetes, GraphQL, Spark, Airflow, aplicación móvil, mensajería, pagos y entrenamiento de modelos.
