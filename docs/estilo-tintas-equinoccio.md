# Tintas del Equinoccio: cuero, pergamino y exploración

El tema existente `otono` adopta la dirección visual de la referencia mediante `EquinoxInterior.css`, importado por `Layout`. Se aplica a las rutas autenticadas sin depender de visitar antes el mural. Nombre, identificador, grupo del selector, preferencias y sincronización permanecen.

## Composición

- Fondo continuo con biblioteca marítima, mapa, telescopio y barco. Mantiene el encuadre centrado antes de Tu rincón y el desvanecimiento hacia el fondo normal.
- Entorno oscuro de cuero marrón, encabezados crema, acentos y selección dorados.
- Publicaciones, resultados, formularios y paneles sobre pergamino claro con tinta marrón; sin ilustraciones superpuestas a las portadas.
- Tu rincón como cubierta de cuero con brújula y libros. Sidebar con brújula de bolsillo, diario y cuerda, transparente y difuminado; se oculta el adorno en navegación compacta.
- Banner automático del perfil utiliza la escena de exploración. No se modifican avatares ni datos.

La paleta raíz de `themes.js` permanece como referencia histórica; los roles locales del interior cambian para seguir el ejemplo. Se usan fondo `#26190F`, panel oscuro `#3A2618`, texto crema `#F7E8CB`, oro `#F2C36D` y pergamino entre `#F7E7C9` y `#EED5A9`. Los paneles claros declaran tinta `#2D1A0E`, secundario `#63472C` y acciones marrones `#8A4A17`, para no heredar texto crema sobre pergamino. El borde interactivo se oscureció a `#8C632D` tras comprobar contraste.

Las otras ocho paletas, autenticación, backend, permisos y navegación funcional no cambian. Los estados semánticos conservan su tratamiento. Se respetan preferencias de movimiento y movimiento reducido; las ilustraciones no se animan.

## Recursos y comparación

Generación mediante la herramienta integrada de imagegen. [Archivos finales y prompts](../apps/web/public/images/equinox-universe/README.md). Los tres WebP suman 904 294 bytes.

- [Galería de páginas](galeria-tintas-equinoccio.html).
- [Comparación antes/después](comparacion-tintas-equinoccio.html).

Capturas de navegador con API simulada a 1440 y 390 px. El fixture de identidad sincroniza el tema con ThemeProvider y espera la carga del banner, para que la captura represente también el contenido dependiente del contexto, no solo las variables CSS.

## Validación

- Identidad: cuatro temas, nueve rutas y seis resoluciones, sin excepciones ni desbordamiento horizontal; menú móvil, foco y modal conservados.
- Contraste evaluado en entorno oscuro y tarjetas claras: texto de botón principal 11,89:1; hover 13,64:1; botón principal sobre tarjeta 6,17:1; borde de botón neutro sobre tarjeta 3,65:1; texto de campo 15,07:1 y borde 4,84:1.
- Navegación de `otono`: siete tamaños, áreas de 44 px, foco, Escape, cierres, scroll y movimiento reducido. También corrige la anterior falta de espacio del logo a 320 px dentro de este tema.
- Suite de temas: colores raíz originales y preferencias preservados; el cambio de banner y componentes de `otono` es intencional y se verifica con el nuevo estilo.
- ESLint sin errores y con cinco advertencias existentes en fixtures; compilación correcta, con advertencia de tamaño del bundle.

Revisión visual en Chrome. Safari y Firefox pendientes; las muestras no constituyen una certificación completa WCAG.
