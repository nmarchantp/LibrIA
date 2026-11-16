# Identidad visual interior de LibrIAverse

> Informe de una fase anterior. El estado actual del tema oscuro y su extensión a todas las páginas se documenta en [Estilo oscuro unificado](estilo-oscuro-unificado.md).

Implementación del 15 de noviembre de 2026, posterior al refinamiento de temas.

## Recursos y decisiones

Se revisaron `BrandLogo`, las escenas exteriores del login y la biblioteca del registro, `MagicalBackground`, los banners por tema y los encabezados existentes. Se reutiliza la silueta de cuatro puntas del logo en una pequeña máscara SVG compartida; no se crean nuevas ilustraciones ni dependencias.

`LiteraryAtmosphere` aporta un resplandor superior y dos estrellas estáticas. La intensidad es menor en Jardín de Macarons. Usa exclusivamente variables actuales de cada tema; no cambia colores base, persistencia ni configuración. Se oculta al desactivar el fondo mágico y no se monta en administración. No tiene animaciones, eventos ni semántica accesible.

`LiteraryIdentity.css` define un único patrón de marca editorial para encabezados principales, incluida Mi biblioteca y Recomendaciones IA. Mantiene textos, tipografías y controles existentes. La sidebar recibe un separador bajo el logo y un indicador discreto para la ruta activa. En celular se reduce la decoración y el indicador se adapta a la navegación compacta.

Los banners de perfil, las portadas y los estados vacíos con iconos de libro abierto ya existentes se conservan. No se adornan publicaciones, resultados, tablas ni portadas individualmente. No se incorporan escenas ilustradas interiores. Login y registro permanecen intactos. Los selectores visuales nuevos solo se activan en `dark` y `lavanda`; los otros siete temas no reciben los efectos.

## Comparación

Abrir [la comparación antes/después](comparacion-identidad-interior.html), con selectores de tema, pantalla y tamaño. Incluye mural, perfil, biblioteca, recomendaciones y administración en oscuro y claro, a 1440 y 390 px. Capturas reales de navegador con API simulada, disponibles en `artifacts/interior-identity-before/` y `artifacts/interior-identity-after/`.

La comparación muestra una marca recurrente en los encabezados y navegación, manteniendo las superficies de contenido limpias y los banners existentes. La biblioteca conserva las portadas sin marcos nuevos. Administración no recibe el resplandor ambiental.

## Verificación

- `npm run test:interior-identity`: nueve vistas, dos temas y seis resoluciones (1440×1000, 1024×768, 768×1024, 390×844, 320×568 y 844×390). Sin excepciones ni desbordamiento horizontal; conserva pruebas de contraste, modal y foco. Verifica decoración estática, `aria-hidden`, ausencia de captura de puntero y exclusión de administración.
- Pruebas `themes.mjs` y `magical-background.mjs`: paletas y preferencias conservadas, otras variantes sin regresiones detectadas, teclado, movimiento reducido y exclusión de autenticación.
- ESLint: cero errores, cinco advertencias existentes de Fast Refresh en fixtures.
- Compilación correcta, con la advertencia existente de tamaño del bundle.

Validación automatizada en Chrome; revisión visual de capturas de escritorio y celular. No se afirma cobertura de Safari o Firefox ni certificación completa de accesibilidad. Las pruebas usan datos simulados; no modifican cuentas ni datos reales.
