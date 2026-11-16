# Refinamiento de Reino de Sombras y Jardín de Macarons

Implementado el 15 de noviembre de 2026. Complementa el informe inicial; sus tablas describen el estado anterior.

## Alcance y conservación

Los ajustes se limitan a `dark` y `lavanda`, dentro de la interfaz autenticada y los modales compartidos de perfil y contenido. Se conservan nombres, identificadores, tema predeterminado, `ThemeContext`, acceso rápido, clave `libria_theme`, preferencias guardadas y sincronización entre pestañas. Los otros siete temas mantienen sus estilos.

Se conservan los doce colores base:

| Variable | Reino de Sombras | Jardín de Macarons |
|---|---|---|
| `--paper` | `#181721` | `#F4EFF9` |
| `--surface` | `#292535` | `#FFFCFF` |
| `--primary` | `#C2A4F3` | `#7856A4` |
| `--secondary` | `#453854` | `#DFD1EF` |
| `--accent` | `#9776CF` | `#B38BCD` |
| `--ink` | `#F6F0FC` | `#332743` |

## Colores de componentes

Estos valores se aplican mediante tokens locales en `refinements.css`, sin reemplazar la paleta raíz.

| Función | Oscuro | Claro | Justificación |
|---|---|---|---|
| Superficie elevada | `#302A3D` | `#FFFCFF` | Separar navegación y diálogos del fondo |
| Fondo de campos | `#211E2C` | `#F9F5FC` | Identificar áreas editables |
| Borde interactivo | `#9484A4` | `#8B789E` | Hacer visibles los controles |
| Borde de panel | `#544961` | `#D4C8DF` | Delimitar tarjetas sin brillo excesivo |
| Botón neutro | `#362E43` | `#F1E9F8` | Unificar acciones secundarias |
| Hover neutro | `#453854` | `#E8DCEF` | Respuesta visual consistente |

El botón neutro claro pasa de crema `#F7EEE0` a lavanda `#F1E9F8` en los controles ordinarios alcanzados. Se respetan variaciones especiales, incluidas clases explícitas de crema. Los botones principales conservan `--primary` y `--on-primary`, sin nuevos degradados. Acciones destructivas usan los colores semánticos de error existentes.

## Componentes y ambientación

- Foco visible consistente, campos de 16 px, metadatos seleccionados de al menos 12 px y mejor interlineado del contenido.
- Bordes de panel discretos, navegación elevada y controles de archivos y modales adaptados al tema.
- Ajuste del ancho del logo en la cabecera compacta para evitar colisiones con acciones.
- Estrellas interiores menos densas y brillantes, sin gradiente ambiental ni capa de estrellas grandes. Sin paisajes nuevos.
- Movimiento interior desactivado por defecto para estos dos temas cuando no existe elección guardada. Se conservan el interruptor, las preferencias explícitas y `prefers-reduced-motion`.
- DM Sans y DM Serif Display permanecen. Login, registro y transiciones conservan sus identidades propias.
- Consolidación de reglas duplicadas de botones/selects que ya estaban sobrescritas. Corrección de claves React repetidas entre tres componentes hermanos del perfil.

## Validación

Pruebas con componentes reales y respuestas API simuladas: mural, perfil, biblioteca, lectura, catálogo, eventos, recomendaciones, configuración y administración. Se verifican seis tamaños: 1440×1000, 1024×768, 768×1024, 390×844, 320×568 y 844×390. La suite ampliada pasó en Edge; previamente se verificaron escritorio, tablet y celular en Chrome. Safari y Firefox no se comprobaron.

Sin excepciones de ejecución ni desplazamiento horizontal en las vistas probadas. Se comprobaron apertura de modal, foco y preferencias. Las verificaciones de paletas, selector, persistencia y fondo estelar también pasan. Login y transiciones de autenticación pasan sus pruebas de regresión.

| Par medido | Oscuro | Claro |
|---|---|---|
| Texto de botón principal | 8,36:1 | 5,73:1 |
| Texto de botón neutro | 11,54:1 | 11,74:1 |
| Texto de acción destructiva | 8,10:1 | 6,40:1 |
| Texto de campo | 14,60:1 | 12,89:1 |
| Borde neutro / relleno | 3,74:1 | 3,36:1 |
| Borde de campo / relleno | 4,74:1 | 3,69:1 |

Las muestras cumplen los umbrales aplicables de [contraste de texto](https://www.w3.org/WAI/WCAG22/Understanding/contrast-minimum.html) y [contraste no textual](https://www.w3.org/WAI/WCAG22/Understanding/non-text-contrast.html). No constituye una certificación WCAG de toda la aplicación; contenidos de usuarios, imágenes y estados no cubiertos requieren evaluación contextual.

`npm run lint`: sin errores, cinco advertencias de Fast Refresh en fixtures existentes. `npm run build`: correcto, con advertencia de tamaño de bundle. Ejecución específica: `npm run test:theme-refinements` con navegador CDP disponible.

Capturas de referencia: `artifacts/theme-refinements/`.
