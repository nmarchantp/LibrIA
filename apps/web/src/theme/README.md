# Temas visuales

`themes.js` es el catálogo de nueve paletas: cada entrada tiene un identificador estable,
nombre visible independiente, grupo (`light`/`dark`) y seis colores en orden fondo,
superficie, principal, secundario, acento y texto. Opcionalmente, `roles` define
variantes accesibles de esos colores sin cambiar las muestras de referencia.
`applyTheme` asigna esos roles a `<html data-theme="…">` y actualiza el
color del navegador. `main.jsx` lo ejecuta antes de montar React.

`themes.css` deriva los roles de contraste, bordes, superficies suaves y controles.
Mantiene los nombres CSS existentes para que las páginas compartan la paleta sin
cambiar sus dimensiones o distribución. `--accent-text` permite usar un tono
legible en texto pequeño sin alterar el acento original. Algodón de azúcar necesita
`--button-bg` algo más oscuro para texto blanco; Dark usa texto oscuro sobre el
principal claro.

Los estados de éxito, error, advertencia e información tienen roles independientes
con variantes claras/oscuras. No deben reemplazarse por colores decorativos de la
paleta. Las portadas y sus colores propios son contenido y se conservan.

`ThemeProvider` conserva la selección en `localStorage` (`libria_theme`), sincroniza
otras pestañas y tolera almacenamiento bloqueado o identificadores inválidos.
La preferencia pertenece al navegador; no se guarda en el servidor ni por cuenta.
`ThemeSelector` se muestra únicamente en **Configuración → Personalización**, con
botones nativos y `aria-pressed` para indicar la selección. No existe un acceso
de Apariencia en la navegación lateral ni móvil.

Para añadir una paleta, agregar una entrada al catálogo y comprobar contraste.
Los identificadores y `data-theme` también permiten vincular futuros recursos o
decoraciones, sin incorporarlos a la lógica de negocio ni al contexto de sesión.
El perfil utiliza una ilustración de portada independiente y sin texto superpuesto.
Las superficies y textos siguen las variables semánticas; Dark atenúa la ilustración.
Se requieren navegadores modernos con soporte de `color-mix()`.

`profileBanners.js` relaciona los identificadores originales con las seis rutas de
ilustraciones en `public/images/profile-banners/`. `ProfileBanner` consume el tema
activo del mismo contexto y cambia de imagen después de cargarla y decodificarla;
no tiene una segunda preferencia ni modifica la lógica de sesión o biblioteca.
El banner actual sin gato es el respaldo de recursos ausentes o inválidos.
Los nombres, ambientes y ajustes de encuadre se documentan en
`public/images/profile-banners/README.md`. Las seis ilustraciones se generaron
individualmente a partir del banner original sin gato, conservando su habitación
y variando el paisaje. Se guardaron en WebP a 2172 × 724 px.

## Ampliación a nueve temas

Los claros conservan sus IDs y paletas: `lavanda`, `otono`, `invierno`,
`rosa-antiguo`, `bosque` (nombre visible: Bosque feérico).
`dark` conserva exactamente su paleta y roles; se presenta como Reino de Sombras.
Los nuevos son `dark-rosado`, `dark-blood` y `dark-dorado`.
El selector muestra cinco claros y cuatro oscuros, en hasta cuatro columnas,
dos en tablet y una en móvil. No hay migraciones de preferencias.

Los nuevos temas heredan los roles funcionales oscuros de éxito/error/advertencia/
información. Sus diferencias visuales están limitadas a sus propios selectores.
Pacto de Sangre utiliza negro `#050507`, superficies `#1D1D24`, botones `#89001F`,
hover `#C4183D` y un rojo luminoso `#EE7893` en el rol `--primary` para texto,
foco e iconos pequeños. El rojo principal de referencia se conserva en las
muestras y en `--button-bg`. Así no se fuerza texto pequeño de bajo contraste.

Las tres variantes nuevas devuelven la configuración de `profileBanners.dark`,
incluido su encuadre, y reutilizan la atenuación oscura. No hay imágenes nuevas.
Los seis recursos originales no se modifican.

`npm run test:themes` verifica las nueve selecciones y su persistencia al recrear
el documento, banners decodificados, agrupación y columnas responsive, y contraste
de diez pares de roles por variante nueva (mínimo 4,5:1). Usa el mismo navegador
CDP y fixture aislado que las pruebas de navegación, sin llamadas reales de escritura.
La referencia `tests/fixtures/original-theme-appearance.json` fue capturada antes
de ampliar el catálogo: compara todos los roles originales y estilos representativos
del sidebar, encabezado, tarjetas, etiquetas y SVG. No contiene datos personales.
Las propiedades transitorias heredadas que los SVG no utilizan para pintarse se
excluyen; sus `fill` y `stroke` sí se comparan.

Detalles de validación, límites y archivos: [ampliación de temas](../../../../docs/theme-expansion.md).

Validación inicial realizada con Edge sin ventana y una página temporal que montó los
componentes reales ThemeProvider/ThemeSelector junto con estilos compartidos:

- Seis temas en 1440 y 375 píxeles: selección, colores exactos, persistencia de cada
  tema al recargar y ausencia de desbordamiento del selector.
- Cierre con Escape y recuperación de Jardín de Macarons ante un valor guardado inválido.
- Contraste de texto principal/secundario, botón, tarjeta destacada, etiqueta,
  estados de error/éxito y opción seleccionada: mínimo medido 4,78:1.
- Formulario real `/login` con Dark: superficie y controles adaptados.
- ESLint y compilación de producción.

Estas comprobaciones no sustituyen una revisión manual completa de las pantallas
autenticadas con datos y permisos de cada rol.

Tras integrar el selector en el perfil se verificaron las cinco pestañas, los cinco
filtros, retirada y cambio de estado con respuestas API interceptadas en un perfil
de navegador aislado, sin mutaciones reales. Se comprobaron las seis paletas en
1536, 1280, 1024, 768, 390 y 320 px, persistencia, estados vacíos y errores de carga.
