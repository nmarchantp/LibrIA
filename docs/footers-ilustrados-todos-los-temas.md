# Bordes ilustrados de los 24 temas

16 de noviembre de 2026. Se extendió a todos los temas el acabado aprobado en Reino de Sombras: franja inferior fina, detalle vertical a la derecha, transparencia real y color suave. El recurso aprobado de `dark` se conserva sin regenerarlo.

## Implementación

- **23 ilustraciones nuevas**, una por cada tema restante. Archivos finales: `apps/web/public/images/theme-footers-v1/<identificador>/footer.webp`.
- Reino de Sombras sigue usando `apps/web/public/images/theme-refresh-v1/dark/footer-v2.webp`.
- Todas son 1800×600 y conservan proporción 3:1. Los archivos nuevos suman **2,30 MB**, entre 64 y 124 KB cada uno. No se cargan las 24 imágenes simultáneamente: el CSS referencia el recurso del tema activo.
- `apps/web/src/components/ThemeFooters.css`: mapa de ilustraciones y colocación compartida. Sustituye el CSS de la prueba `ThemeFooterPreview.css`; `Layout.jsx` importa ahora la capa general.
- `apps/web/src/theme/themeFooterAssets.json`: metadatos de las 23 imágenes nuevas.

El borde queda dentro de la capa de fondo fija y detrás del contenido. Rebasa unos píxeles el recorte del fondo para ocultar márgenes transparentes inferiores y laterales, como en la prueba aprobada. Opacidad 78 % en escritorio y 72 % en celular. No captura eventos ni incorpora animaciones. Los antiguos acentos inferiores de Bosque, Cristal y Rosas se sustituyen por este único recurso para evitar decoración duplicada.

No cambian las paletas, identificadores, preferencias, navegación, estructura de los módulos, banners, Tu rincón, login ni registro. El interruptor de fondo mágico sigue desmontando el fondo con su decoración; los puntos y sus preferencias de movimiento permanecen.

## Identidad

Cada borde conserva motivos propios: lavanda, exploración náutica, hielo, dulces, bosque feérico, biblioteca nocturna, rosas, fantasía gótica, mecanismos de reloj, nubes celestiales, papiros, sakura, galaxias, laurel, otoño, astrología, runas, hongos, vitrales, mosaicos, corales, fantasmas y brujería. Los objetos se concentran en el borde inferior y extremo derecho para conservar el espacio de lectura.

## Recursos y generación

Generación mediante la herramienta integrada, conforme a [imagegen](C:/Users/nikoo/.codex/skills/.system/imagegen/SKILL.md). Prompts completos: `artifacts/all-theme-footer-prompts.json`. Originales seleccionados: `artifacts/theme-generation/originals/footer-<identificador>/footer.png`, ignorados por Git. Optimización proporcional y verificación de alfa: `artifacts/all-theme-footer-optimize.mjs`.

**Recursos pendientes: ninguno.** No se eliminan los originales ni las versiones anteriores aprobadas.

## Verificación y capturas

[Galería de los 24 temas](galeria-footers-temas.html), con capturas del mural en escritorio y celular. [Vista conjunta de las 24 ilustraciones](../artifacts/theme-footers/contact-sheet.png). Capturas adicionales a 1920 px en `artifacts/theme-footers/`.

- `footer-contact-sheet.mjs`: las 24 URLs responden como WebP; todas las imágenes decodifican, conservan la proporción 3:1 y tienen transparencia en la zona de lectura.
- `test:interior-identity`: **24 temas × nueve vistas × siete resoluciones**. Comprueba recurso específico del tema, decoración estática sin captura de puntero, fondo fijo, contenido desplazable, ausencia de desbordamientos y excepciones, modal, foco, menú móvil y controles. Texto de las muestras ≥4,5:1 y bordes de campos/controles neutros ≥3:1.
- Resoluciones: 1440×1000, 1024×768, 768×1024, 390×844, 320×568, 844×390 y 1920×1080. Se guardan 72 capturas del mural para no duplicar cientos de capturas de módulos que mantienen su estructura.
- `test:magical-background`: preferencias y visibilidad en los 24 temas, teclado, movimiento reducido y exclusión del login.
- ESLint sin errores, con cinco advertencias previas de Fast Refresh en fixtures. Compilación correcta con advertencia existente de tamaño del bundle.

Validación en Chrome/CDP con API simulada; no se alteran datos reales. No se afirma cobertura de Safari/Firefox ni certificación completa de accesibilidad. Registros: `artifacts/theme-footers-group-1.log`, `group-2.log`, `group-3.log` y `theme-footers-particles.log` en el mismo directorio. Sin commit.
