# Bosque feérico: bosque profundo, niebla y marfil

El tema existente `bosque` sigue la referencia suministrada mediante `ForestInterior.css`, importado por `Layout`. Se comparte en todas las rutas autenticadas, sin modificar nombre, ID, preferencias, grupo del selector ni sincronización.

## Composición

La biblioteca del árbol ocupa el fondo continuo del mural hasta el inicio real de las pestañas. La escena se centra antes de Tu rincón y se desvanece hacia un área de lectura verde niebla. Las tarjetas marfil conservan el protagonismo de portadas y actividades.

El sidebar mantiene verde profundo, selección verde y dorada, y el farol y el hada del lado izquierdo de la imagen. Tu rincón utiliza un encuadre de luna, bosque y setas. Los bordes se integran con máscaras y veladuras. Un detalle inferior de follaje de baja opacidad comparte el recurso original. La ambientación principal respeta el interruptor de fondo mágico.

La cabecera y navegación compacta usan iconos dorados sobre verde. El menú móvil conserva su apertura, foco, Escape, cierres y scroll. Administración recibe superficies limpias; las portadas, avatares, datos y funcionalidades permanecen. El banner automático del perfil utiliza la biblioteca suministrada.

## Roles locales

Fondo `#D5DFBC`, tarjeta `#F6F3E5`, superficie elevada `#FCFAEE`, texto `#182C20`, secundario `#40573D`, acción principal `#426638`, hover `#34552C`, borde interactivo `#6F8058` y campo `#FFFCF0`. Sidebar y Tu rincón declaran texto crema y acentos dorados propios para no heredar tinta oscura sobre verde profundo.

La paleta raíz permanece en `themes.js`; estos roles se limitan al interior de `bosque`. Autenticación y las otras ocho paletas quedan fuera de estos estilos. Se conservan estados semánticos, preferencias de movimiento y movimiento reducido; no se animan las ilustraciones.

## Recursos y revisión

Se reutilizó [la imagen original adjunta](../apps/web/public/images/forest-universe/README.md). Un único WebP de 227 928 bytes, sin generación de imágenes ni dependencias nuevas.

- [Galería de páginas](galeria-bosque-feerico.html).
- [Antes/después](comparacion-bosque-feerico.html).

Capturas reales de Chrome con datos simulados a 1440 y 390 px. Identidad comprobada en nueve rutas y seis resoluciones, sin excepciones ni desbordamiento horizontal; paleta y sidebar compartidos, encabezado transparente, foco, modal y menú móvil.

Contraste de muestras: texto principal de botón 6,25:1; hover 8,04:1; texto neutro 12,68:1; borde neutro 3,67:1; texto de campo 14,39:1 y borde 4,17:1. No constituye una certificación completa de accesibilidad.

Navegación comprobada en siete tamaños; suite de temas verifica nueve selecciones, paletas raíz, preferencias y banners. Lint sin errores y con cinco advertencias existentes en fixtures. Build correcto, con advertencia de tamaño del bundle. Safari y Firefox pendientes.
