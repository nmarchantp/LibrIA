# Pacto de Sangre: identidad gótica compartida

El tema existente `dark-blood` recibe una identidad inspirada en la referencia: burdeos, rosas, luz de vela, ventana gótica y luna roja. `BloodInterior.css`, importado por `Layout`, aplica el estilo a las rutas autenticadas sin depender de visitar antes el mural.

## Alcance

- Sidebar con logo carmesí, selección burdeos, libros antiguos, rosas y vela. Difuminado periférico y halo cálido estático.
- Fondo superior gótico que se desvanece antes de las áreas de lectura.
- Hero con libro y cáliz; Tu rincón con castillo y luna roja, solo en el mural.
- Tarjetas, campos, botones, modales compartidos, encabezados y paneles coordinados en las demás páginas. Administración conserva superficies limpias.
- Banner automático del perfil de este tema reutiliza la nueva escena gótica; deja de usar el banner violeta genérico. No se modifican avatares ni datos de usuarios.

Nombres, ID, preferencias y paleta raíz permanecen. Las superficies locales usan fondo `#10090D`, tarjeta `#21171D`, elevada `#291B22`, texto crema `#F5E9E2`, secundario `#CFBAB8`, borde interactivo `#A17D87`, botón vino `#89001F` y hover `#C4183D`. Los estados conservan sus colores semánticos. Los otros ocho temas y autenticación quedan fuera de estos selectores.

Se preservan las preferencias de movimiento; las ilustraciones no se animan. Las partículas existentes se atenúan y se respeta movimiento reducido. Los gráficos decorativos no capturan clics ni agregan contenido a lectores de pantalla.

## Recursos y revisión

Generación mediante la herramienta integrada de imagegen. [Archivos y prompts completos](../apps/web/public/images/blood-universe/README.md). Tres WebP: 454 666 bytes en total.

- [Galería de páginas](galeria-pacto-sangre.html).
- [Antes/después](comparacion-pacto-sangre.html).

Capturas de navegador con API simulada a 1440 y 390 px. La suite de identidad se amplió a `dark-blood`: nueve rutas, seis resoluciones, ausencia de excepciones/desbordamiento, paleta y sidebar persistentes, foco, modal y menú móvil. También se verificaron Reino de Sombras y Jardín de Macarons.

Muestras del mural: texto principal de botón 8,76:1; hover 5,15:1; neutro 13,74:1; borde neutro 4,52:1; texto de campo 15,52:1 y borde 5,10:1. No representan una certificación completa WCAG.

La suite de navegación pasa 21 combinaciones de los tres temas, incluidos foco, Escape, scroll y movimiento reducido. La suite de temas verifica todas las paletas, preferencias y banners. Lint sin errores, con cinco advertencias existentes de Fast Refresh en fixtures; compilación correcta, con advertencia de tamaño del bundle.

No se modificó backend, base de datos, permisos ni lógica de autenticación. Revisión visual en Chrome; Safari y Firefox pendientes.
