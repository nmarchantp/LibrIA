# Temas visuales

`themes.js` es el catálogo de paletas: cada entrada tiene un identificador estable,
nombre y seis colores en orden fondo, superficie, principal, secundario, acento y
texto. `applyTheme` asigna esos roles a `<html data-theme="…">` y actualiza el
color del navegador. `main.jsx` lo ejecuta antes de montar React.

`themes.css` deriva los roles de contraste, bordes, superficies suaves y controles.
Mantiene los nombres CSS existentes para que las páginas compartan la paleta sin
cambiar sus dimensiones o distribución. `--accent-text` permite usar un tono
legible en texto pequeño sin alterar el acento original. Rosa antiguo necesita
`--button-bg` algo más oscuro para texto blanco; Dark usa texto oscuro sobre el
principal claro.

Los estados de éxito, error, advertencia e información tienen roles independientes
con variantes claras/oscuras. No deben reemplazarse por colores decorativos de la
paleta. Las portadas y sus colores propios son contenido y se conservan.

`ThemeProvider` conserva la selección en `localStorage` (`libria_theme`), sincroniza
otras pestañas y tolera almacenamiento bloqueado o identificadores inválidos.
La preferencia pertenece al navegador; no se guarda en el servidor ni por cuenta.
`ThemeSelector` se muestra únicamente en **Mi perfil → Personalización**, con
botones nativos y `aria-pressed` para indicar la selección. No existe un acceso
de Apariencia en la navegación lateral ni móvil.

Para añadir una paleta, agregar una entrada al catálogo y comprobar contraste.
Los identificadores y `data-theme` también permiten vincular futuros recursos o
decoraciones, sin incorporarlos a la lógica de negocio ni al contexto de sesión.
El perfil utiliza una ilustración de portada independiente y sin texto superpuesto.
Las superficies y textos siguen las variables semánticas; Dark atenúa la ilustración.
Se requieren navegadores modernos con soporte de `color-mix()`.

`profileBanners.js` relaciona los identificadores existentes con las seis rutas de
ilustraciones en `public/images/profile-banners/`. `ProfileBanner` consume el tema
activo del mismo contexto y cambia de imagen después de cargarla y decodificarla;
no tiene una segunda preferencia ni modifica la lógica de sesión o biblioteca.
El banner actual sin gato es el respaldo de recursos ausentes o inválidos.
Los nombres, ambientes y ajustes de encuadre se documentan en
`public/images/profile-banners/README.md`. Las seis ilustraciones se generaron
individualmente a partir del banner original sin gato, conservando su habitación
y variando el paisaje. Se guardaron en WebP a 2172 × 724 px.

Validación inicial realizada con Edge sin ventana y una página temporal que montó los
componentes reales ThemeProvider/ThemeSelector junto con estilos compartidos:

- Seis temas en 1440 y 375 píxeles: selección, colores exactos, persistencia de cada
  tema al recargar y ausencia de desbordamiento del selector.
- Cierre con Escape y recuperación de Lavanda ante un valor guardado inválido.
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
