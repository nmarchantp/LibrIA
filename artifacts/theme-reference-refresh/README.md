# Ajuste de Canto de Sirenas y Aquelarre de Medianoche

Ilustraciones recreadas con ImageGen a partir de la composición y los motivos de las referencias del usuario. Las cabeceras muestran a los personajes de lejos; los laterales usan faroles colgantes y las esquinas contienen la concha o el caldero. Las imágenes laterales y las esquinas conservan transparencia real.

## Archivos finales

- Canto de Sirenas: `apps/web/public/images/themes/canto-sirenas/banner-v2.png`, `sidebar-decoration-v2.png`, `corner-v2.png`.
- Aquelarre de Medianoche: `apps/web/public/images/themes/aquelarre-medianoche/banner-v2.png`, `sidebar-decoration-v3.png`, `corner-v2.png`.

Las instrucciones completas de generación están en [prompts.json](./prompts.json). Los efectos de luz se mantienen separados de las imágenes; las dos velas exteriores de Aquelarre utilizan la llama compartida de Pacto de Sangre.

## Canto de Sirenas: rincón y footer separados

- Imagen exclusiva de “Tu rincón”: `apps/web/public/images/themes/canto-sirenas/welcome-nook-v1.png`, con un libro y una ventana al mar.
- Esquina del footer: `apps/web/public/images/themes/canto-sirenas/corner-v2.png`, conservada con su calidad original.
- Camino horizontal del footer: `apps/web/public/images/themes/canto-sirenas/footer-strip-v1.png`, una ilustración transparente independiente que se repite horizontalmente sin estirar la esquina.

Las dos imágenes nuevas se generaron con ImageGen. Instrucciones completas en [sirenas-footer-prompts.json](./sirenas-footer-prompts.json). Ambas piezas del footer se componen como capas separadas en CSS; el resto de los temas mantiene sus imágenes.

## Verificación

Compilación de producción correcta. Comprobación de navegación y efectos de los 24 temas; carga de los seis recursos y capturas de ambos temas en escritorio (1920 px) y móvil (390 px), sin desbordamiento horizontal.
