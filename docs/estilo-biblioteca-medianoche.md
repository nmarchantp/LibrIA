# Biblioteca de Medianoche: azul nocturno y oro

El tema existente `dark-dorado` sigue la referencia adjunta mediante `MidnightInterior.css`, importado por `Layout`. Se comparte en todas las rutas autenticadas, sin modificar nombre, identificador, preferencias ni sincronización.

## Composición

- Fondo continuo de biblioteca nocturna, luna y libro, visible hasta el inicio de las pestañas. La altura sigue la posición real del menú del mural, también al cambiar de resolución.
- Entorno azul profundo, tipografía crema y acentos dorados. Sidebar con farol, libros, ventana e hiedra de la imagen proporcionada.
- Tu rincón incorpora la misma escena con un encuadre de farol y libros; textos y enlace siguen siendo elementos reales de la aplicación.
- Publicaciones, formularios, catálogo, eventos, configuración y administración comparten superficies azules con bordes dorados discretos. No se añaden efectos sobre portadas o publicaciones.
- El perfil recibe un banner automático de la biblioteca suministrada. Los avatares y datos no se alteran.

Los roles locales usan fondo `#070D1D`, superficie `#121A2C`, elevada `#1C263B`, texto `#FFF5D9`, secundario `#D8CFBC`, acento `#E2C17A`, borde interactivo `#9C895B` y campo `#0C1425`. La paleta raíz de `themes.js` permanece. Autenticación y las otras ocho paletas no reciben estos estilos.

El hover de navegación usa azul uniforme y texto crema, sin sombras que creen líneas. El activo conserva el borde y brillo dorados de la referencia. Las ilustraciones son estáticas; se conservan las preferencias de ambientación y movimiento reducido.

## Recursos y comparación

Se reutilizó [la imagen original adjunta](../apps/web/public/images/midnight-universe/README.md) mediante encuadres CSS. Un único WebP de 314 550 bytes, sin generación de imágenes ni dependencias nuevas.

- [Galería de páginas](galeria-biblioteca-medianoche.html).
- [Comparación antes/después](comparacion-biblioteca-medianoche.html).

Capturas reales de Chrome con datos simulados a 1440 y 390 px.

## Validación

- Nueve rutas y seis resoluciones, sin excepciones ni desbordamiento horizontal; paleta y sidebar consistentes, foco, modal y apertura del menú móvil.
- Texto del botón principal 10,64:1; hover 12,62:1; texto de botón neutro 13,90:1 y borde 4,42:1; texto de campo 16,91:1 y borde 5,38:1.
- Navegación: siete tamaños, áreas de 44 px, foco, Escape, cierres, scroll y movimiento reducido.
- Suite de temas: nueve selecciones, preferencias, paletas raíz y banners verificados.
- ESLint sin errores, con cinco advertencias existentes en fixtures; compilación correcta, con advertencia de tamaño del bundle.

No se modificó backend, permisos ni autenticación. Safari y Firefox no se comprobaron; las muestras de contraste no constituyen certificación completa WCAG.
