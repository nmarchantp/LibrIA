# Ilustraciones de Algodón de azúcar

`candy-atlas-v1.webp` reutiliza directamente la segunda imagen adjunta por el usuario: una lámina con sidebar, escena panorámica y panel de cupcake. No se generaron variantes ni se incorporaron textos de la captura de la interfaz.

La lámina recibida mide 2048 × 683 px. Se codificó a WebP con calidad 0,86: 73 952 bytes. El PNG recibido permanece en `artifacts/cotton-universe-sources/candy-atlas-v1.png`.

`CottonInterior.css` presenta las tres regiones mediante posiciones y tamaños de fondo CSS, sin producir copias de los dibujos:

| Región | Rectángulo de referencia, en píxeles |
|---|---|
| Escena panorámica | x=252, y=190, ancho=1386, alto=262 |
| Adorno del sidebar | x=20, y=310, ancho=204, alto=320 |
| Cupcake de Tu rincón | x=1664, y=112, ancho=370, alto=444 |

Las máscaras CSS suavizan el perímetro del fondo y del sidebar. La misma escena panorámica se utiliza como banner automático de perfil. El navegador comparte una sola descarga entre todas las regiones.

## Recursos independientes

Se reemplaza el uso directo del atlas por tres recortes del original: `candy-landscape-v2.png`, `candy-sidebar-v2.png` y `candy-corner-v2.png`. As? ninguna resoluci?n puede revelar las piezas vecinas ni las separaciones de la l?mina en Configuraci?n, otras cabeceras, sidebar o Tu rinc?n. Se preservan proporciones con cover y se conservan las m?scaras de difuminado. El banner autom?tico de perfil tambi?n usa solo el paisaje.
