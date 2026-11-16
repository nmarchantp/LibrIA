# Renovación de imágenes de siete temas

16 de noviembre de 2026. Se regeneraron **21 ilustraciones** con el acabado de la colección reciente: panorama, composición lateral y Tu rincón para cada uno de estos temas.

| Tema | Identificador | Motivos conservados |
|---|---|---|
| Jardín de Macarons | `lavanda` | Lavanda pastel, libro luminoso, castillo, pluma y farol |
| Reino de Sombras | `dark` | Noche violeta, libro mágico, castillo, estrellas y farol |
| Tintas del Equinoccio | `otono` | Biblioteca de explorador, mapas, brújula, telescopio y barco |
| Alas de Cristal | `invierno` | Dragón de hielo, castillo nevado, cristales y farol plateado |
| Algodón de azúcar | `rosa-antiguo` | Libros rosas, lazos, dulces, algodón, flores y farol |
| Bosque feérico | `bosque` | Árbol biblioteca, puente, cascada, hada, hongos y farol |
| Biblioteca de Medianoche | `dark-dorado` | Biblioteca azul nocturna, ventana gótica, luna, libros y luz dorada |

## Recursos e integración

Archivos finales en `apps/web/public/images/theme-refresh-v1/<identificador>/`:

- `banner.webp`: 1800×600, composición panorámica con zona tranquila para títulos.
- `sidebar-decoration.webp`: 600×900, transparencia real y composición de libros, iluminación y elementos temáticos.
- `corner.webp`: 600×750, detalles hacia abajo/derecha para conservar espacio de lectura.

Los 21 WebP suman **2,93 MB**. No se eliminan las imágenes anteriores. Los tamaños conservan la proporción generada; el panorama no se comprime a una altura fija para rellenar la pantalla.

La nueva capa `apps/web/src/components/RefreshedThemeArtwork.css` aplica exclusivamente estas imágenes a los siete identificadores. Mantiene el fondo continuo del mural, fundido inferior, espacio reservado para la columna derecha y escalado proporcional; en celular adapta el encuadre. Las laterales quedan inmediatamente encima de la cuenta y Tu rincón usa una imagen propia, sin depender de la decoración lateral. No se añaden hojas encima del logo de Bosque feérico.

`Layout.jsx` importa la capa después de los estilos anteriores. `profileBanners.js` usa los panoramas nuevos en los perfiles correspondientes. `refreshedThemeAssets.json` registra dimensiones, peso y transparencia de los recursos.

Las paletas base, identificadores, preferencias, controles, puntos mágicos y autenticación se conservan. En Alas de Cristal los textos sobre la nueva escena clara usan el azul existente `#173B66`, en lugar del blanco de la escena anterior. Las ilustraciones anteriores de login/registro no cambian.

## Generación

Se usó la herramienta integrada conforme a [imagegen](C:/Users/nikoo/.codex/skills/.system/imagegen/SKILL.md). Prompts: `artifacts/seven-theme-refresh-prompts.json`. Tres ediciones posteriores retiraron halos opacos de las laterales oscuras: `artifacts/seven-theme-cleanup-prompts.json`.

Originales seleccionados en `artifacts/theme-generation/originals/refresh-<identificador>/`, ignorados por Git. Optimización local: `artifacts/seven-theme-optimize.mjs`; verifica transparencia y escala proporcionalmente. Los archivos consumidos por la aplicación están dentro del proyecto. **No hay recursos pendientes.**

## Revisión

[Galería de los siete temas](galeria-renovacion-siete-temas.html), con nueve pantallas y vistas de escritorio/celular. Capturas reales con API simulada en `artifacts/seven-theme-refresh/`. No se modificaron cuentas ni datos reales.

Pruebas: mural, perfil, biblioteca, lectura, catálogo, eventos, recomendaciones, configuración y administración; siete tamaños (1440×1000, 1024×768, 768×1024, 390×844, 320×568, 844×390 y 1920×1080). Se comprueban las nuevas rutas de imágenes, proporciones, ausencia de desbordamientos/excepciones, controles, modal, foco y menú móvil. Capturas de escritorio, celular y escritorio amplio: 189 imágenes.

El selector y la persistencia siguen funcionando en los 24 temas. La suite del fondo mágico verifica preferencias y movimiento reducido; la de decoración lateral comprueba la posición sobre la cuenta. Texto de las muestras de controles ≥4,5:1 y bordes de campos/controles neutros ≥3:1. No se afirma una certificación WCAG completa de todos los fondos ilustrados y contenidos de usuarios.

ESLint: cero errores y cinco advertencias existentes de Fast Refresh en fixtures. Compilación correcta con advertencia existente de tamaño del bundle. Registros de ejecución: `artifacts/seven-theme-refresh-*.log`. Navegador verificado: Chrome/CDP; no se afirma cobertura Safari/Firefox. No se realizó commit.
