# Mural por categorías — Etapa 1

El mural muestra Contactos y Comunidad, con cinco carruseles: avances, inicios,
finalizaciones, reseñas y publicaciones sociales. No hay una segunda fila de filtros.
La audiencia predeterminada es Comunidad para que una cuenta sin seguidos tenga
contenido público disponible. Contactos es seguimiento unidireccional a perfiles.

## Contrato de consulta

- `GET /api/mural?audience=community&limit=9`: hasta nueve actividades por categoría;
  límite permitido entre 1 y 12, más `has_more` por categoría.
- `GET /api/mural/{category}?audience=community&limit=20&cursor=…`: historial de
  `progress`, `started`, `finished`, `reviews` o `social`. Límite entre 1 y 50.
  Devuelve `items` y `next_cursor`.
- Ambas rutas requieren sesión válida. `GET /api/posts` mantiene su contrato.

La consulta aplica privacidad y audiencia antes del límite. El resumen de avances
usa `row_number` por usuario e intento (`reading_id`), con fecha e identificador
descendentes. No mezcla distintas relecturas. El historial no aplica esta reducción:
expone todos los eventos originales autorizados, incluidos avances sin total de páginas.

La paginación usa fecha e ID, no desplazamientos. El cursor está firmado con HMAC,
ligado al usuario, audiencia y categoría, y conserva un corte temporal entre páginas.
Las reglas de privacidad se vuelven a evaluar; el corte no congela permisos ni el
contenido editable de una reseña. Las actividades nuevas se incorporan al actualizar.

Se conservan las restricciones actuales para lecturas abandonadas y las reseñas
canónicas: primero se selecciona la reseña vigente, después su visibilidad. Una
versión antigua publicada no reaparece si la vigente es privada. Las consultas de
metadatos, portadas, autores, imágenes, likes y seguimiento se ejecutan por lotes.
La selección canónica reutiliza la proyección existente del catálogo; evaluar índices
y coste con volúmenes reales forma parte de la optimización posterior.

Los elementos conservan ID y tipo originales. Las actividades completas reutilizan
`FeedCard` y sus endpoints existentes de comentarios, likes y seguimiento. Abrir el
mural no crea publicaciones. No se agregaron tablas ni migraciones.

## Archivos de implementación

Backend:

- `app/main.py`: registro de las rutas.
- `app/modules/social/feed_router.py`: validación y respuestas tipadas.
- `app/modules/social/feed_service.py`: clasificación, privacidad, cursores y lotes.

Frontend:

- `src/pages/HomePage.jsx` y `MuralPage.css`: navegación, categorías e historial.
- `src/components/MuralCarousel.jsx`: carrusel con flechas, teclado y scroll táctil.
- `src/components/MuralActivityCard.jsx`: resumen compacto de una actividad.
- `src/components/MuralActivityDialog.jsx`: actividad completa con comentarios.
- `src/components/FeedCard.jsx`: componente existente extraído del mural anterior.
- `src/hooks/useMural.js`: carga, cancelación, errores y paginación sin duplicados.
- `src/services/feedService.js`: cliente y adaptación del contrato anterior.
- `package.json`: comando `test:mural`.

No se modificaron sidebar, topbar, temas globales, biblioteca, Mi espacio, fichas ni
el registro de lecturas. El compositor original conserva sus permisos y se muestra
en la columna izquierda, entre el encabezado y las pestañas de audiencia.

## Recuperación de la composición original

La primera implementación había dejado de renderizar el `aside.mural-aside`, que
contenía “Tu rincón”, “Sigue leyendo” y la nota de comunidad. Eran bloques JSX de
`HomePage.jsx`, no componentes eliminados. Sus estilos originales seguían en
`styles.css`, y `PostComposer` y `BookCover` también permanecían en el repositorio.
El encabezado `mural-heading` se había reemplazado por `mural-screen-heading` y el
contenedor `mural-layout` por una superficie a todo el ancho.

Se recuperaron selectivamente el JSX exacto del encabezado y de la columna derecha
desde `be61512:apps/web/src/pages/HomePage.jsx`; el último cambio de ese archivo en
esa revisión es `35394ad`. Los estilos originales siguen disponibles en el árbol
actual. No se reemplazó el archivo completo ni se revirtieron cambios pendientes.
El snapshot `tests/fixtures/mural-original-layout.json` conserva los dos bloques y su
procedencia; la prueba comprueba que siguen siendo los originales.

El contenedor vuelve a usar `mural-layout` y `mural-feed`, por lo que recupera los
anchos, tipografía, colores, separaciones y márgenes de los estilos existentes. Los
carruseles calculan sus tarjetas según el ancho de la columna izquierda. Se mantienen
los 280 px originales de la columna derecha en escritorio (desde 1000 px); en
pantallas menores las tres tarjetas se apilan debajo, sin las reglas antiguas que
ocultaban contenido en ciertos tamaños. Las pestañas y el botón de actualización
ocupan una fila propia después del compositor. El saludo superior queda intacto.

Archivos de esta recuperación: `HomePage.jsx`, `MuralPage.css`, la fixture y prueba
de carruseles, el snapshot original y este documento. No hay cambios de backend,
endpoints, datos ni permisos en esta recuperación.

## Validación

Backend, desde `apps/backend`:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_mural_feed tests.test_post_comments tests.test_post_interactions tests.test_reviews tests.test_reading_reflections
```

Los datos de prueba quedan dentro de transacciones revertidas. Se verifica resumen
por intento, historial profundo, cursores, privacidad canónica, abandonos, avances
por páginas, autenticación, comentarios, seguimiento no recíproco y consultas cuyo
número no crece por tarjeta. También se validó el contrato sobre datos locales reales
dentro de una transacción explícitamente de solo lectura.

Frontend, con Vite en 5173 y Chromium/Edge aislado con CDP en 9224:

```powershell
npm run lint
npm run test:mural
npm run test:feed-progress
npm run build
```

`test:mural` usa exclusivamente `tests/fixtures/mural.html` y `mural.jsx`; sus datos
sintéticos no se importan en producción. Cubre 0, 1, 3 y más de 10 actividades,
63 combinaciones de tema y anchura, flechas, teclado, swipe táctil real, carga de más
páginas, reintentos, audiencias, comentarios y enlaces. Las capturas quedan en
`artifacts/mural-carousels/desktop.png` y `mobile.png`.
También verifica los bloques recuperados de Git, el saludo, los enlaces laterales,
la columna de 280 px, el apilado responsive y el formulario original con permisos de
administrador dentro de la columna izquierda, sin desbordamiento entre 320 y 1440 px.

La prueba general preexistente `test:navigation` tiene comprobaciones desactualizadas
fuera de este cambio: espera `.settings-page .account-details`, mientras la pantalla
actual monta `.account-page`. Al comprobar temporalmente ese selector también falla
una expectativa de cabecera privilegiada. No se cambiaron esas pantallas ni se dejaron
modificaciones en esa prueba. Lint conserva una advertencia previa en `Layout.jsx`;
la compilación conserva el aviso de tamaño del bundle.

## Pendiente

“Nuevos libros” no se muestra: requiere autorización explícita y un registro de
incorporación compartida en la Etapa 2. No se publican comprobantes históricos ni
bibliotecas privadas. Las correcciones y abandonos no crean categorías nuevas en
esta entrega; se conserva su historial y su política de visibilidad.
