# Reto anual de lectura (MVP)

La tarjeta del perfil conserva su ubicación y usa `ProfileEditModal` para crear o
editar una meta entre 1 y 1000 libros. Las sugerencias son 5, 12, 20, 30 y 50.
El porcentaje se redondea para mostrarlo y se limita al 100 %, mientras que el
número de obras terminadas conserva su valor real. La insignia se calcula desde
el cumplimiento actual; no es un logro permanente ni un sistema de puntos.

## Persistencia y acceso

La migración aditiva `0081_annual_reading_challenge` crea `app.retos_lectura` con
clave primaria `(user_id, year)` y restricciones de rango. No modifica lecturas,
obras, ediciones, asistencias ni publicaciones. Los guardados utilizan un upsert
atómico: las solicitudes simultáneas actualizan la misma meta.

- `GET /api/me/reading-challenge`: reto del año actual.
- `GET /api/me/reading-challenge?year=2025`: consulta de un año anterior.
- `PUT /api/me/reading-challenge`: `{ "target": 12 }`, crea o edita el año actual.

Estas rutas requieren autenticación. El propietario siempre procede de la sesión,
no del cuerpo ni de un identificador recibido. Las respuestas usan `no-store`.
Los años y las fechas de finalización se interpretan en `America/Santiago`.

## Cálculo y actualización

Se consulta la biblioteca activa del usuario y se selecciona el intento actual
antes de filtrar su estado, siguiendo el criterio existente de la biblioteca y
sus estadísticas. Solo cuentan obras terminadas con `finished_at` verificable
del año consultado. Los distintos registros o ediciones de una obra cuentan una
vez; cuando están activadas las identidades canónicas, también se deduplican sus
alias. Una lectura pendiente, en curso o abandonada no recupera artificialmente
el estado de un intento anterior. Las correcciones se reflejan en la consulta.

No se inventan fechas antiguas ni se guarda un contador manual de progreso.
Las metas anteriores permanecen almacenadas. Cambiar la meta no altera la
biblioteca. La retirada de una obra de la biblioteca activa deja de contarla.

La tarjeta reutiliza `libria:book-activity-changed` y los cambios de identidad
del catálogo para invalidarse. Agrupa avisos cercanos y cancela consultas
obsoletas; no usa polling ni recarga toda la aplicación. Volver a enfocar la
ventana también actualiza el reto, incluido el cambio de año.

## Verificación

- Migración aplicada correctamente en PostgreSQL local.
- 11 pruebas específicas: creación, edición, persistencia, propiedad,
  autenticación, límites, deduplicación, fechas, correcciones, cumplimiento,
  superación, integridad y guardados concurrentes.
- 52 pruebas backend ejecutadas junto a las suites de mural y eventos: correctas.
- `npm run test:reading-challenge`: creación/edición, sugerencias, errores,
  actualización, logro recalculado, nueve temas y cuatro anchos.
- `npm run test:profile-tabs`: navegación y reutilización de datos conservadas.
- Lint sin errores (advertencia previa en `Layout.jsx`) y build correcto
  (aviso previo sobre tamaño del bundle).

Las pruebas de navegador usan fixtures aisladas. Las pruebas de biblioteca se
revierten; la prueba de concurrencia elimina únicamente sus propios registros.
