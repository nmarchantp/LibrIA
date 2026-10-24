# Sobre mí: composición y jerarquía visual

Esta etapa modifica exclusivamente la presentación del frontend. No cambia
persistencia, permisos, endpoints, selección del gusto destacado, biblioteca,
otras pestañas, encabezado, banners ni navegación.

`ProfileAboutSection.css` define dos columnas explícitas mediante áreas:

```text
history     genres
tropes      featured
statistics  quotes
```

El área `quotes` está reservada: no tiene tarjeta, texto de ejemplo ni controles.
Con un contenedor de 660 px o menos, las cinco tarjetas pasan a una sola columna.
La vista comunitaria mantiene sus cuatro tarjetas públicas y no reserva una
fila de estadísticas privadas.

Se reutilizan los cuatro editores existentes y sus contratos PATCH. El texto de
biografía tiene más tamaño e interlineado; las etiquetas usan fondos derivados
del tema; el indicador destacado conserva cinco iconos y solo una categoría;
las barras mantienen los porcentajes recibidos por el servicio existente.
Las notas sobre asignaciones y redondeo siguen disponibles en un `details`
accesible, cerrado inicialmente. Los selectores del editor no tienen superficies
de tarjeta anidadas.

## Decoración y recursos pendientes

Se revisaron `public/images/profile-reading-nook.png` y los seis banners. Son
escenas panorámicas, no ilustraciones independientes adecuadas para las esquinas
del mockup. No se recortaron ni se reutilizaron como fondos de tarjetas.

Los pequeños detalles lineales de libros y plantas reutilizan Lucide. Son
decorativos, se ocultan a lectores de pantalla y no interceptan eventos.
Para completar la parte ilustrada del mockup faltan recursos transparentes:

- Libros apilados con velas y flores, para el extremo derecho de Mi historia.
- Un pequeño conjunto de libros y flores para géneros y tropos.
- Un compañero lector, como el gatito negro sobre libros, para el gusto destacado.

Las ubicaciones están identificadas con `data-decoration-slot`; no hay imágenes
aleatorias ni botones sin acción. Cualquier recurso posterior debe respetar el
texto, los botones y los seis temas, y reducirse u ocultarse en móvil.

## Validación

- Lint y build del frontend.
- Composición exacta de filas en escritorio, una columna en anchos reducidos.
- Seis paletas reales mediante `applyTheme`, con anchos de 1800, 1440, 1024,
  768, 390 y 320 px, sin desbordamiento horizontal.
- Contraste de texto secundario, etiquetas, biografía y descripción del indicador:
  mínimo medido 5,43:1 en las combinaciones comprobadas.
- Apertura, guardado y cancelación de los cuatro editores con los campos PATCH
  anteriores; cinco gustos siguen disponibles al editar y solo uno al visualizar.
- Estados vacíos, notas de cálculo accesibles y perfil comunitario sin edición
  ni estadísticas privadas.

Las pruebas de navegador usaron servicios sustituidos solamente en fixtures
temporales, sin escribir en la base de datos. Esas fixtures se eliminaron.
Las capturas de `artifacts/profile-about/` son vistas de prueba, no datos de
usuarios ni recursos cargados por la aplicación.
