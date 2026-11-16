# Canto de Sirenas, Ecos de las Sombras y Aquelarre de Medianoche

## Estado

Los tres temas están incorporados a **Configuración → Personalización**, junto a los 21 anteriores. **Ambientación completada el 16 de noviembre de 2026:** los nueve recursos reales están integrados, con transparencia lateral, fundidos y escalado proporcional. No quedan ilustraciones pendientes.

## Paletas

Orden: fondo, tarjetas, principal, secundario, acento y texto. Se mantienen los 18 colores solicitados sin modificaciones.

| Tema | Identificador | Colores |
|---|---|---|
| Canto de Sirenas | `canto-sirenas` | `#071E2A #103440 #83D1D3 #24515C #E8BCA4 #EFFBFC` |
| Ecos de las Sombras | `ecos-sombras` | `#090A0C #1B1D20 #C4C9CE #30343A #8A929C #F0F1F2` |
| Aquelarre de Medianoche | `aquelarre-medianoche` | `#171020 #291D36 #C391E5 #493052 #E2B976 #F7EEFC` |

La capa compartida deriva bordes, campos, texto secundario y estados hover legibles. Los botones principales usan texto casi negro sobre los acentos claros; las acciones destructivas conservan los roles semánticos de error. Se añaden reflejos azulados, niebla gris o resplandor ciruela discretos mediante degradados estáticos. Los puntos y sus preferencias siguen funcionando; no se añaden animaciones ni capturas de puntero decorativas.

## Recursos integrados

Para **cada uno de los tres identificadores** se incorporaron:

| Recurso final | Medidas previstas | Integración |
|---|---|---|
| `sidebar-decoration.webp` | 600 × 900 | Transparencia real; libros, fuente de luz y motivos propios; encima del usuario |
| `banner.webp` | 1800 × 600 | Zona izquierda tranquila para texto, escena hacia centro/derecha; distinto del fondo general |
| `corner.webp` | 600 × 750 | Zona superior izquierda tranquila; decoración de Tu rincón |

Directorios finales: `apps/web/public/images/themes/canto-sirenas/`, `apps/web/public/images/themes/ecos-sombras/` y `apps/web/public/images/themes/aquelarre-medianoche/`. Dimensiones, transparencia y peso registrados en `literaryThemeAssets.json`. El panorama generado tiene proporción 3:1, conservada sin comprimirlo a la altura orientativa de 500 px. Las laterales son 600×900 y Tu rincón 600×750. Los nueve WebP suman 1,20 MB.

- **Canto de Sirenas:** lateral con libros/farol náutico/conchas/perlas/coral/estrellas de mar; banner con sirena, océano nocturno, luna, olas luminosas y castillo costero; rincón con concha y perla luminosa.
- **Ecos de las Sombras:** lateral con libros oscuros/farol gótico/velas/fantasmas/arañas/telarañas; banner de castillo abandonado, luna, árboles secos y niebla; rincón de biblioteca embrujada.
- **Aquelarre de Medianoche:** lateral con grimorios/gato negro/farol/velas/pociones/cristales; banner de bruja leyendo bajo la luna con castillo distante; rincón con caldero, vapor violeta y libros de hechizos.

El mural muestra su escena propia con transición inferior; la decoración lateral queda encima del usuario, sin fondo rectangular, y Tu rincón conserva una zona de lectura tranquila sobre su imagen. El perfil usa ahora el panorama específico de cada tema. Los fondos generales discretos y los controles del fondo mágico permanecen.

Se usó la herramienta integrada de generación de imágenes, siguiendo [imagegen](C:/Users/nikoo/.codex/skills/.system/imagegen/SKILL.md). Prompts completos: `artifacts/three-theme-prompts.json`. Originales PNG en `artifacts/theme-generation/originals/<identificador>/`, ignorados por Git; WebP finales en los directorios anteriores. Optimización proporcional y verificación de transparencia: `artifacts/three-theme-optimize.mjs`.

[Galería de las tres ambientaciones](galeria-sirenas-sombras-aquelarre.html), con escritorio y celular por pantalla. Capturas finales: `artifacts/three-themes-illustrated/`.

## Archivos y conservación

- `apps/web/src/theme/literaryThemes.json`: tres registros adicionales y descripciones del arte previsto.
- `literaryThemes.js`: registra las ilustraciones disponibles desde el manifiesto; conserva la alternativa segura si faltan recursos futuros.
- `literaryThemeAssets.json`: incorpora metadatos reales de las nueve ilustraciones nuevas sin sustituir los anteriores.
- `profileBanners.js`: solo registra banners temáticos disponibles.
- `apps/web/src/components/LiteraryThemePack.css`: reutiliza controles/superficies y añade tres fondos sutiles, limitados a sus identificadores.
- Pruebas del selector, fondo mágico, navegación, decoración lateral e identidad interior: reconocen las 24 opciones y verifican sus recursos.

Los temas anteriores y sus recursos permanecen. No se cambia `ThemeContext`, `libria_theme`, el predeterminado, acceso rápido, autenticación, navegación ni estructura funcional.

## Verificación

Pruebas con API simulada en Chrome/CDP, sin modificar datos reales:

- `test:interior-identity` con los tres identificadores: mural, perfil, biblioteca, lectura, catálogo, eventos, recomendaciones, configuración y administración. Siete resoluciones: 1440×1000, 1024×768, 768×1024, 390×844, 320×568, 844×390 y 1920×1080. Sin desbordamiento horizontal ni excepciones; comprueba modal, foco, menú móvil, recursos propios y escalado proporcional.
- `test:themes`: las 24 selecciones aplican y persisten al recargar; paletas anteriores conservadas.
- `test:magical-background`: preferencias, teclado, movimiento reducido y visibilidad en los 24 temas.
- `sidebar-artwork-position.mjs`: arte integrado en los 24 temas inmediatamente encima del usuario.
- Muestras de texto de controles ≥4,5:1 y bordes de campos/controles neutros ≥3:1. No equivale a certificación WCAG completa de la aplicación.
- ESLint sin errores; cinco advertencias previas de Fast Refresh en fixtures. Compilación correcta, con advertencia existente de tamaño del bundle.

Capturas anteriores sin ilustraciones: `artifacts/three-new-themes/`. Capturas finales: `artifacts/three-themes-illustrated/`. Registros finales: `artifacts/three-themes-illustrated-*.log`. Revisión visual de las nueve ilustraciones y capturas de escritorio/celular. No se afirma validación de Safari/Firefox. No se realizó commit.
