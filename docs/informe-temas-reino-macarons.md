# Informe de temas visuales de LibrIAverse

Revisión del código local, 15 de noviembre de 2026. Informe de evaluación: no modifica las paletas ni los componentes de la aplicación.

## 1. Identidad y comportamiento

| Aspecto | Reino de Sombras | Jardín de Macarons |
|---|---|---|
| Identificador interno | `dark` | `lavanda` |
| Modo | Oscuro | Claro |
| Intención visual | Noche, índigo y lavanda luminosa | Lavanda pastel, superficies casi blancas y violeta |
| Papel actual | Tema predeterminado sin preferencia válida guardada | Alternativa clara del acceso rápido |
| Banner de perfil | `/images/profile-banners/dark.webp` | `/images/profile-banners/lavender.webp` |

El botón junto a Mensajes alterna entre estos dos temas. La selección se guarda en `localStorage`, clave `libria_theme`, y se sincroniza entre pestañas. Pertenece al navegador, no a la cuenta del usuario. Una elección guardada prevalece sobre el valor predeterminado. Los demás temas siguen disponibles en Configuración / Personalización.

## 2. Paleta y función de cada color

Las seis primeras filas son colores exactos declarados. Los derivados con `color-mix(in srgb,?)` se muestran aproximados al hexadecimal de 8 bits más cercano; el navegador puede mantener canales fraccionarios.

| Uso | Variable CSS | Reino de Sombras | Jardín de Macarons |
|---|---|---|---|
| Fondo general | `--paper` | `#181721` | `#F4EFF9` |
| Tarjetas y paneles | `--surface` | `#292535` | `#FFFCFF` |
| Acción principal y foco | `--primary` | `#C2A4F3` | `#7856A4` |
| Lavanda de apoyo | `--secondary` | `#453854` | `#DFD1EF` |
| Acento decorativo | `--accent` | `#9776CF` | `#B38BCD` |
| Texto principal | `--ink` | `#F6F0FC` | `#332743` |
| Texto secundario | `--muted` | `#C9C3D0` | `#60566C` |
| Bordes y separadores | `--line` | `#666271` | `#C2BCC7` |
| Superficie suave | `--soft` | `#362E43` | `#F1E9F8` |
| Texto sobre botón principal | `--on-primary` | `#181721` | `#FFFFFF` |
| Enlaces y acentos legibles | `--accent-text` | `#C2A4F3` | `#523C6F` |
| Hover principal | `--primary-hover` | `#CBB2F5` | `#6E4F95` |
| Fondo de botón neutro | `--neutral-button-bg` | `#362E43` | `#F7EEE0` |

Reglas principales:

- `--muted`: 78 % texto + 22 % superficie.
- `--line`: 30 % texto + 70 % superficie.
- `--soft`: 45 % secundario + 55 % superficie.
- El foco usa `--primary`.
- En oscuro, `--accent-text` coincide con el principal y el hover mezcla 85 % principal con 15 % blanco.
- En claro, `--accent-text` mezcla 45 % principal con 55 % texto; el hover mezcla 85 % principal con 15 % texto.
- Los botones neutros claros usan el crema `#F7EEE0` solicitado; los oscuros usan la superficie suave.
- Las reglas de cada componente pueden sobrescribir estos valores. No todos los botones están obligados a usar el fondo neutro.

## 3. Colores funcionales

Estos colores comunican estados, independientemente del acento violeta.

| Estado | Texto oscuro | Fondo oscuro | Texto claro | Fondo claro |
|---|---|---|---|---|
| Éxito | `#A8E2BF` | `#203B30` | `#245644` | `#EFF8F3` |
| Error | `#FFC0B8` | `#482B30` | `#923E34` | `#FFF0ED` |
| Advertencia | `#F4D391` | `#403522` | `#71501F` | `#FFF4DD` |
| Información | `#BED9FF` | `#27374D` | `#294B71` | `#F0F5FC` |
| Valoraciones | `#F4BF45` | / | `#946500` | / |

Bordes de estado: Éxito `#638B74` / `#B6CFC5`; error `#A7676E` / `#E4B5A8`; información `#6F8EB4` / `#BECFE4` (oscuro / claro).

## 4. Tipografía, superficies y efectos

- Texto y controles: **DM Sans**. Los pesos y tamaños dependen del componente.
- Títulos editoriales: **DM Serif Display**; existen títulos de formularios que usan DM Sans.
- Radio general `--radius`: **18 px**. Hay botones de 12 px y tarjetas con radios propios.
- Sombra general: `0 8px 28px var(--shadow-color)`.
- Oscuro: sombra negra al 30 %. Claro: texto principal mezclado al 12 % con transparencia.
- Superficie de vidrio: 96 % superficie y 4 % transparencia.
- Capa de oscurecimiento: `rgb(12 10 18 / 72%)` en ambos temas.
- Los efectos de estrellas y su movimiento tienen preferencias independientes del tema.
- Las portadas de libros y las ilustraciones contienen sus propios colores; no se recolorean por cambiar la paleta.

## 5. Contraste calculado de pares base

Cálculo sRGB sobre colores sólidos, con derivados redondeados. Orienta la evaluación, pero no reemplaza comprobar el CSS efectivo, la transparencia, los fondos ilustrados, el tamaño del texto y los estados de cada componente.

| Par | Reino de Sombras | Jardín de Macarons |
|---|---|---|
| Texto / fondo | 15.88:1 | 12.28:1 |
| Texto / tarjeta | 13.32:1 | 13.64:1 |
| Texto secundario / tarjeta | 8.65:1 | 6.77:1 |
| Enlace principal / tarjeta | 7.02:1 | 5.63:1 |
| Texto / botón principal | 8.36:1 | 5.73:1 |
| Texto / botón neutro | 11.54:1 | 12.08:1 |
| Borde / tarjeta | 2.52:1 | 1.82:1 |

Una relación menor entre tarjeta y fondo o entre borde y superficie puede ser intencional. Conviene evaluar si la jerarquía y los límites de los controles siguen siendo claros en el contexto real. Esta tabla no es una certificación de accesibilidad de toda la interfaz.

## 6. Aspectos que conviene evaluar antes de modificar

1. **Consistencia de botones:** hay estilos globales, estilos por componente y colores fijos. Conviene acordar tres roles: principal, secundario y peligro. Cambiar solo `--primary` no alcanza para uniformar todos los botones.
2. **Acento decorativo frente a texto:** `--accent` no tiene la misma función que `--accent-text`. Usar el decorativo para texto pequeño puede reducir la legibilidad.
3. **Separación de superficies oscuras:** fondo `#181721`, tarjeta `#292535` y suave `#362E43` son cercanos. Si se percibe poca jerarquía, conviene probar primero bordes o superficie, sin aclarar toda la página.
4. **Contraste de campos claros:** el fondo lavanda y los paneles casi blancos dan un aspecto suave; si los inputs se confunden con las tarjetas, ajustar el borde y el foco antes que aumentar sombras.
5. **Crema en el tema claro:** `#F7EEE0` introduce un matiz cálido que se aparta del lavanda. Evaluar si debe quedar para acciones secundarias o convertirse en un tono lavanda consistente.
6. **Login y registro:** conservan fondos ilustrados y colores propios en `LoginPage.css` y `AuthJourney.css`. No reproducen todos los colores del tema seleccionado. Definir si esta identidad fija debe mantenerse.
7. **Colores fijos:** existen fondos como `#EEE7F7` en estilos globales de fechas e iconos de notificaciones, además de colores propios en componentes. Conviene revisar su apariencia en oscuro y convertirlos a variables cuando corresponda.
8. **CSS acumulado:** algunas clases, como `.button.primary`, se declaran varias veces. El resultado depende del orden y la especificidad. Antes de rediseñar, conviene consolidar reglas para evitar que una pantalla responda distinto.
9. **Preferencias:** cambiar el tema por defecto no reemplaza una preferencia válida ya guardada. Para evaluar el valor inicial, probar en un navegador sin esa selección.

## 7. Orden sugerido de evaluación

- Elegir si se conserva el violeta como color principal de ambos temas.
- Ajustar fondo, tarjetas y bordes para definir profundidad.
- Acordar botones principales/secundarios y el uso del crema.
- Revisar texto secundario, enlaces y foco con esos fondos.
- Revisar estados de Éxito/error y después ilustraciones/efectos.
- Comprobar una muestra representativa: mural, perfil, catálogo, formularios y administración, en escritorio y celular.

## 8. Fuentes del proyecto

- `apps/web/src/theme/themes.js`: seis colores base, nombres, IDs y valor predeterminado.
- `apps/web/src/theme/themes.css`: derivados, estados y reglas de contraste.
- `apps/web/src/context/ThemeContext.jsx`: persistencia y sincronización.
- `apps/web/src/components/ThemeModeToggle.jsx`: alternancia rápida.
- `apps/web/src/theme/profileBanners.js`: ilustraciones por tema.
- `apps/web/src/styles.css`: tipografías, radios, botones y excepciones.
- `apps/web/src/pages/LoginPage.css` y `apps/web/src/components/AuthJourney.css`: identidad de autenticación.

La comparación visual adjunta muestra muestras y componentes ilustrativos basados en estas variables; no es una captura ni un cambio de la aplicación.
