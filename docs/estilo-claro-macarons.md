# Jardín de Macarons: estilo claro compartido

La referencia proporcionada guía una identidad de amanecer lavanda, aplicada a todas las rutas autenticadas de `lavanda` mediante `LightInterior.css`, importado por `Layout`. Funciona al entrar directamente a cualquier página.

## Cambios

- Cielo pastel superior, superficies casi blancas, bordes lavanda y sombras violetas suaves.
- Sidebar con selección violeta clara, trayectorias alrededor del logo, farol pastel y halo cálido. La ilustración se desvanece en sus bordes y se oculta en la navegación compacta.
- Hero del mural con libro abierto luminoso y castillo al horizonte. Tu rincón recibe una ilustración propia de pluma, libros y farol.
- Tarjetas, calendario, paneles, configuración y encabezados comparten superficies; administración conserva paneles limpios.
- Textos, portadas, datos, enlaces y controles siguen siendo componentes reales de la aplicación.

Los seis colores base de `lavanda`, su identificador, preferencias y sincronización se conservan. Tampoco se modifican el tema oscuro, las otras siete paletas ni las pantallas de autenticación. Los banners personalizados del perfil se mantienen.

Las ilustraciones fueron recreadas con la herramienta integrada de imagegen a partir de la dirección visual de la captura, sin recortar textos o controles de ella. [Recursos y prompts completos](../apps/web/public/images/macaron-universe/README.md). Los tres WebP suman 497 168 bytes.

## Revisión

- [Antes/después del mural y páginas](comparacion-macarons.html).
- [Galería de páginas claras](galeria-estilo-claro.html).

Capturas de Chrome a 1440 y 390 px con el mismo fixture simulado. La suite de identidad comprueba nueve rutas, dos temas y seis resoluciones, sin excepciones ni desbordamiento; confirma la paleta clara y el farol compartido, contraste de controles normales/hover, foco y apertura del menú móvil.

La suite de navegación pasa 14 combinaciones de oscuro/claro, incluidos Escape, foco, scroll y movimiento reducido. La suite de temas conserva variantes y preferencias. ESLint sin errores, con cinco advertencias existentes en fixtures. Build correcto, con la advertencia existente de tamaño del bundle.

No se modificaron datos reales ni backend. Safari y Firefox no se comprobaron. Las muestras de contraste no constituyen una certificación completa de accesibilidad.
