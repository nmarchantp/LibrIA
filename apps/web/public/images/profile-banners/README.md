# Banners de Mi perfil

Las seis ilustraciones se generaron individualmente con la habilidad imagegen y
la herramienta integrada, editando siempre el banner original sin gato
`/images/profile-reading-nook.png`. La cuadrícula adjunta se utilizó únicamente
como inspiración para los ambientes. Los WebP actuales sustituyen los recortes
anteriores; no proceden de recortar la cuadrícula ni de imágenes externas.

| Tema existente en ThemeContext | Archivo | Ambiente esperado |
| --- | --- | --- |
| `lavanda` | `lavender.webp` | Paisaje mágico lavanda |
| `otono` | `autumn.webp` | Paisaje otoñal cálido |
| `invierno` | `winter.webp` | Paisaje invernal nevado |
| `dark` | `dark.webp` | Paisaje mágico nocturno |
| `bosque` | `forest.webp` | Bosque feérico encantado |
| `rosa-antiguo` | `rose.webp` | Primavera con flores rosadas |

Los nombres ingleses son archivos de recursos; no cambian los identificadores de
tema ni las preferencias ya guardadas. La configuración visual está centralizada
en `src/theme/profileBanners.js`. Cada entrada admite `position` y `mobilePosition`
para ajustar el encuadre de cada ilustración.

Conservar una composición panorámica consistente, con la ventana y los elementos
importantes en una zona que tolere los recortes. El contenedor mantiene sus
proporciones actuales: 4.3 en escritorio, 3.8 en tablet y 2.7 en móvil, con
`object-fit: cover`. Se recomienda WebP comprimido y dimensiones suficientes para
el ancho de escritorio; no es necesario incrustar textos en las ilustraciones.

ProfileBanner consume exclusivamente ThemeContext. Conserva la imagen anterior
hasta decodificar la siguiente, reutiliza las cargas correctas y descarta respuestas
de selecciones anteriores. Ante errores HTTP o archivos inválidos, decodifica el
respaldo. No hay fundidos ni animaciones. Si también falla el respaldo, no entra
en un ciclo de reintentos. Tras añadir o reemplazar archivos en este directorio,
recargar el navegador para descartar recursos previamente almacenados en caché.

Exportación: 2172 × 724 px, WebP calidad 90, sin redimensionar ni recortar las
imágenes generadas. La habitación, ventana, libros, cortina, repisa y manta se
mantienen como referencia común. No contienen gatos, personas ni etiquetas.

Actualización de Invierno: `winter.webp` fue reemplazado por la ilustración
aportada «Castillo Nevado tras la Ventana.png», sin generar contenido nuevo.
Se eliminaron los márgenes exteriores (recorte de origen: x=19, y=87, hasta
x=2151, y=590) y se exportó a WebP calidad 90, 2132 × 503 px, 296782 bytes.
El fondo exterior de las esquinas redondeadas se hizo transparente; se conserva
la ilustración fría original. No fue necesario modificar el encuadre configurado.
Verificado a 1440, 900 y 390 px: carga correcta, sin desbordamientos ni errores de
JavaScript, con las proporciones y bordes existentes. Los otros cinco WebP no
se modificaron.

Encuadre: `center 35%` en escritorio y tablet para proteger las torres y la luna;
`center 52%` en móvil, manteniendo el comportamiento y dimensiones del contenedor.

## Prompts de generación

Cada llamada usó las mismas dos referencias (banner original como escena fija y
cuadrícula como inspiración) y el siguiente prompt común, reemplazando
`{environment}` por una de las variantes enumeradas debajo:

> Use case: lighting-weather / identity-preserve illustration edit. Input 1 is the ORIGINAL ROOM to preserve, input 2 is ONLY atmosphere inspiration (six-panel sheet). Produce ONE standalone high resolution panoramic banner, same 3:1 aspect ratio as input 1, never a grid. Preserve EXACTLY input 1's room geometry, camera position, perspective, wooden window frames and central mullion, books and potted plants on left, stacked books on right, tied-back right curtain, lower wooden sill and blanket, all object positions and scale. Change ONLY the world seen through the glass and coherent interior light/reflections. Environment: {environment} Keep the same elegant hand-painted literary fantasy style, fine ink outlines, rich painterly detail and cozy room. Interior objects must remain clearly recognizable, not silhouetted. NO cats or animals, NO people, NO text or theme names, NO labels or UI, NO watermark. Do not crop or reproduce any panel from input 2; transform the original room in input 1. Lock the composition; do not move, replace or add furniture or decorative objects.

- `lavender`: Magical lavender landscape with the same distant castle, enchanted lavender sky and soft glowing lights.
- `autumn`: Warm autumn landscape with copper trees, golden foliage and golden late afternoon sunlight.
- `winter`: Snowy winter landscape, snow-covered fir trees, distant mountains and a pale winter sky.
- `dark`: Magical nighttime landscape with moon and stars, an illuminated distant castle, deep midnight blue and violet.
- `forest`: Enchanted fairy forest of ancient trees, abundant vegetation, glowing mushrooms and magical firefly lights outside the window.
- `rose`: Delicate spring landscape with pink flowers, cherry trees in blossom and soft rosy daylight.

Integración inicial verificada en Edge a 1440, 900 y 390 px para los seis temas, usando
respuestas de imagen interceptadas con el banner existente (sin crear recursos
provisionales). Se comprobaron rutas, imágenes decodificadas, ausencia de
desbordamientos, proporciones y bordes originales, respaldo ante archivos ausentes
o inválidos, conservación del banner durante la carga y cambios rápidos con una
respuesta anterior retrasada. No se registraron excepciones de JavaScript.

Validación final con los seis WebP generados reales: 18 combinaciones de tema y
viewport (1440, 900 y 390 px). Todas las imágenes se cargaron y decodificaron a
resolución completa, con `object-fit: cover`, sin desbordamientos ni cambios de
proporciones o bordes. Se revisaron capturas de los encuadres de cada ambiente,
y se volvió a comprobar el fallback mediante un error HTTP simulado. Cero
excepciones de JavaScript. ESLint y build de producción aprobados.
