# Doce nuevos temas literarios

Implementación del 15 de noviembre de 2026. Acceso: **Configuración → Personalización**. El selector contiene los nueve temas anteriores y los doce nuevos.

## Paletas conservadas

Se mantienen exactamente los seis colores solicitados, en orden fondo, superficie, principal, secundario, acento y texto:

| Tema / identificador | Colores base |
|---|---|
| Crónicas del Tiempo / `cronicas-tiempo` | `#211C19 #332923 #D1A15E #5B4030 #C77942 #F5E9D6` |
| Reino Celestial / `reino-celestial` | `#F0F1F8 #FFFFFF #8A70BB #DAD9F0 #C69B52 #34324A` |
| Arenas del Destino / `arenas-destino` | `#EEE2CC #FFF8EA #A87530 #D4BD94 #218B8A #473624` |
| Susurros de Sakura / `susurros-sakura` | `#F7EDF0 #FFFAFB #A85D7A #EACDD8 #C48D9C #49333E` |
| Archivo Galáctico / `archivo-galactico` | `#0B1021 #171F36 #7B9EF5 #26365B #61D7E8 #EDF4FF` |
| Olimpo Eterno / `olimpo-eterno` | `#F0EBDF #FFFCF5 #92743F #DCD0B7 #477A91 #343A40` |
| Otoño Encantado / `otono-encantado` | `#F3E6D6 #FFF8EE #A75D34 #DFC3A3 #B18A3D #463326` |
| Oráculo de la Luna / `oraculo-luna` | `#18152B #29233F #C2A0DF #43365F #D6B56D #F5EDFF` |
| Runas del Norte / `runas-norte` | `#25313A #35444D #B7C9D1 #52646D #C7A477 #F0F3F2` |
| Reino de los Hongos / `reino-hongos` | `#E7E9D8 #FAF9ED #66815D #C5D0AC #BE8067 #344635` |
| Catedral de Cristal / `catedral-cristal` | `#202333 #303449 #A8B5DE #454963 #D4A96F #F3F0F7` |
| Las Mil y Una Historias / `mil-una-historias` | `#102B36 #1D4050 #D7AD72 #2B5964 #46A7A1 #FFF1D9` |

Los colores derivados identifican campos, bordes, enlaces y estados. El texto principal de botones se elige blanco, casi negro o negro según contraste; Olimpo Eterno necesita negro para superar 4,5:1 sin cambiar su dorado. Los enlaces se ajustan hacia el texto de cada paleta cuando el principal resulta insuficiente. Los colores semánticos de éxito, error, información y advertencia reutilizan los roles claros/oscuros existentes.

## Implementación y archivos

- `apps/web/src/theme/literaryThemes.json`: especificaciones e identidad de los doce temas.
- `literaryThemes.js`: registro, recursos y aplicación/limpieza de tokens. Al volver a un tema anterior se retiran todos los derivados nuevos.
- `themeColorRoles.js`: cálculo compartido de contraste, superficies y controles.
- `literaryThemeAssets.json`: dimensiones, transparencia y peso de los recursos finales.
- `themes.js`, `themes.css`, `profileBanners.js`: integración con el sistema actual y banners de perfil.
- `apps/web/src/components/LiteraryThemePack.css`: una sola capa de componentes, limitada a los doce temas mediante `data-theme-pack="literary"`.
- `Layout.jsx`: importa esa capa. Se conservan estructura, navegación y controles funcionales.
- Pruebas `themes.mjs`, `magical-background.mjs`, `interior-identity.mjs`, `sidebar-artwork-position.mjs` y conteo del selector en `main-navigation.mjs`.
- `.gitignore`: excluye únicamente los PNG originales generados de este trabajo; los WebP finales permanecen disponibles para versionar.

No se cambia `ThemeContext`, la clave `libria_theme`, la sincronización, los identificadores anteriores ni el tema predeterminado. El acceso rápido mantiene su comportamiento. Login, registro y sus transiciones no reciben la nueva capa. Los puntos del fondo mágico conservan sus controles de visibilidad y movimiento. No se incorporan nuevas animaciones decorativas.

## Ilustraciones reales

Cada tema contiene tres recursos propios en `apps/web/public/images/themes/<identificador>/`: `banner.webp`, `sidebar-decoration.webp` y `corner.webp`. Son 36 WebP, **4,17 MB en total**, entre 44 y 191 KB por imagen; solo las imágenes referenciadas por el tema activo se solicitan.

Generadas mediante la herramienta de imágenes integrada siguiendo la habilidad imagegen. Prompts completos: `artifacts/theme-generation/prompts.json`. Originales de trabajo ignorados: `artifacts/theme-generation/originals/`. Conversión proporcional: `artifacts/theme-generation-optimize.mjs`.

Banners de 1800×600, tarjetas de 600×750 y decoraciones de hasta 576×720. Se conserva la proporción original; no se fuerza la altura de las ilustraciones para rellenar el ancho. Los fondos del mural tienen una transición inferior suave; la ilustración lateral tiene transparencia real y queda inmediatamente encima del usuario. Las portadas de libros siguen siendo contenido independiente.

**Recursos gráficos pendientes: ninguno.**

## Revisión visual y validación

[Galería de los doce temas](galeria-nuevos-temas.html), con selector de pantalla y comparación escritorio/celular. Capturas reales con API simulada en `artifacts/literary-theme-pack/`; no se modifican cuentas reales.

Las pruebas cubren mural, perfil, biblioteca, lectura, explorar, eventos, recomendaciones, configuración y administración, a 1440×1000, 1024×768, 768×1024, 390×844, 320×568, 844×390 y 1920×1080. Comprueban renderizado, desbordamiento, modal, foco, menú táctil, recursos y proporciones; las muestras de texto requieren 4,5:1 y los bordes de campo/botón neutro 3:1.

Navegador disponible: Chrome mediante CDP. No se afirma validación en Safari o Firefox ni certificación WCAG completa de contenidos e imágenes de usuarios.

Resultados finales:

- `test:interior-identity`: correcto en los doce temas, nueve vistas y siete tamaños; sin excepciones ni desbordamiento horizontal. Genera 324 capturas (tres tamaños por vista y tema).
- `test:themes`: paletas anteriores conservadas; 21 selecciones aplican inmediatamente, sobreviven a recarga y cargan su banner.
- `test:magical-background`: correcto en los 21 temas; preferencias independientes, teclado, movimiento reducido y exclusión del login.
- `sidebar-artwork-position.mjs`: correcto en los 21 temas a tres tamaños; decoración inmediatamente encima de la cuenta, navegación sin comprimir.
- Optimización: 36 archivos reales, proporciones conservadas y transparencia lateral verificada.
- ESLint: cero errores y cinco advertencias previas de Fast Refresh en fixtures.
- Compilación correcta con la advertencia existente de tamaño del bundle.

Registros en `artifacts/literary-validation.log`, `artifacts/literary-themes-test.log` y `artifacts/literary-particles-test.log`. No se realizó commit.
