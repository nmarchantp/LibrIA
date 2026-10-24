# Fondo mágico global

El fondo aprobado vive en `apps/web/src/components/MagicalBackground.jsx` y
`MagicalBackground.css`. Layout monta una sola instancia dentro de
`.social-page-column`, detrás del main y del encabezado transparente. Conserva
las mismas tres capas, posiciones, colores semánticos, opacidades (0,28/0,4/0,55),
patrones de 600 px, dirección descendente y duraciones (50/100/150 segundos).
El sidebar queda fuera de su contenedor. No hay fondo en login ni en pantallas
ajenas al layout autenticado. No se han modificado las paletas ni los banners.

La prueba específica de ProfilePage se retiró. Navegar no vuelve a montar el
fondo ni reinicia sus animaciones. Apagarlo desmonta todo el árbol decorativo y
retira su atributo de activación, sin capas o animaciones ocultas residuales.

## Preferencia e interfaz

`ThemeContext` comparte `magicalBackground` y `setMagicalBackground` de forma
independiente al estado del tema. El lector y la clave están en
`src/theme/visualPreferences.js`. La clave es:

`libriaverse-magical-background`

Se guarda `true` o `false` en localStorage. Sin preferencia, con un valor inválido
o sin acceso al almacenamiento, el fondo está activado por defecto. El apagado
persiste al recargar el documento y la preferencia se sincroniza entre pestañas.
La clave existente `libria_theme` no cambia. Es una preferencia por navegador,
no una nueva preferencia almacenada por cuenta en PostgreSQL.

El interruptor está en **Configuración → Personalización → Efectos visuales**,
debajo del selector de temas. Lo renderiza `VisualEffectsSettings.jsx`, con estilos
en `ThemeSelector.css`. Usa un checkbox nativo con `role="switch"`, etiqueta,
descripción asociada, manejo de teclado y foco visible. No se añaden dependencias.

## Accesibilidad y validación

Todas las capas decorativas son `aria-hidden` y `pointer-events:none`, recortadas
al área principal y sin modificar la distribución de las páginas. La preferencia
`prefers-reduced-motion:reduce` mantiene las estrellas estáticas, como antes.

`npm run test:magical-background` usa la fixture autenticada aislada y el mismo
navegador CDP de las pruebas existentes. Comprueba:

- Activación predeterminada y parámetros visuales/animación originales.
- Doce rutas y pestañas autenticadas con la misma instancia DOM y animación.
- Encendido/apagado inmediato y sin animaciones residuales al desactivar.
- Persistencia de ambos estados en los nueve temas, sin modificar su selección.
- Teclado, ausencia de desbordamiento en escritorio/tablet/móvil y capas sin clics.
- Movimiento reducido, interacción con el editor real y exclusión de login.

También se ejecutan lint, build, navegación, temas y modales del perfil. La prueba
de temas conserva la referencia de paletas originales; excluye solo el fondo
histórico opaco del encabezado, reemplazado por transparencia en un cambio previo.

La licencia MIT y atribución de amir_6539 se conservan en
`docs/licenses/uiverse-profile-starfield-MIT.txt`, enlazadas desde el CSS.
