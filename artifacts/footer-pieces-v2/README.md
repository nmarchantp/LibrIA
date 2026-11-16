# Footers de dos piezas para los 24 temas

Cada footer combina dos imágenes independientes: una esquina detallada y una franja horizontal repetible. La esquina conserva su proporción; la franja ocupa el borde inferior sin estirar el dibujo de la esquina.

Los 45 recursos nuevos se generaron con ImageGen y se guardaron como WebP con transparencia. Canto de Sirenas conserva sus dos imágenes aprobadas; Aquelarre conserva su esquina del caldero y recibe una franja nueva.

- Archivos finales de cada tema: [manifest.json](./manifest.json).
- Prompts completos y referencias de generación: [jobs.json](./jobs.json).
- Selector de recursos: `apps/web/src/theme/themeFooters.js`.
- Composición y suavizado compartidos: `apps/web/src/components/ThemeFooters.css`.

La suavidad aprobada se comparte entre los temas: opacidad 0,55 en escritorio y 0,45 en móvil; saturación 0,72; brillo 0,86; desenfoque de 0,6 px. El efecto solo se aplica al footer.

La prueba `apps/web/tests/theme-footers.mjs` revisa los 24 temas a 1920, 1280 y 390 px: carga de las dos imágenes, transparencia, resolución, escala proporcional, repetición horizontal, suavizado y ausencia de desbordamiento. Guarda capturas de las esquinas en escritorio y de la vista móvil para revisión.

Verificación completada: las 72 combinaciones de tema y ancho pasaron, al igual que la compilación de producción y la prueba de alineación, contracción de barra y efectos de luz de los 24 temas. Revisión visual conjunta en [contact-desktop.png](./contact-desktop.png).
