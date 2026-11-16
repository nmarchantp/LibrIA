# Recurso de Bosque feérico

`fairy-library-v1.webp` reutiliza directamente la segunda imagen proporcionada por el usuario: biblioteca en un árbol, puente, luna, cascada, hada, farol y setas luminosas. No se generó una variante ni se incorporaron textos de la captura de interfaz.

La imagen recibida mide 2048 × 683 px. El PNG se conserva en `artifacts/forest-universe-sources/fairy-library-v1.png`. Se codificó a WebP, calidad 0,86 y mismas dimensiones: 227 928 bytes, aproximadamente 223 KiB.

`ForestInterior.css` comparte una sola descarga mediante diferentes encuadres:

- Fondo continuo del mural desde arriba hasta las pestañas, reservando el espacio de Tu rincón.
- Sidebar: lado izquierdo de la imagen con farol y hada, suavizado en el perímetro.
- Tu rincón: lado derecho con luna, bosque y setas, con veladura verde para proteger el texto.
- Banner automático del perfil: escena original de la biblioteca.
- Ambientación inferior: borde de follaje con baja opacidad al final del contenido.

Los recortes y las máscaras son CSS. El archivo de imagen conserva su composición; las ilustraciones no se animan ni capturan clics.

## Motivos separados

El encabezado usa el 75 % derecho de la escena mediante un encuadre CSS ampliado al 133,333 %: muestra el ?rbol y excluye el hada y el farol del extremo izquierdo. La sidebar usa el extremo izquierdo con hada y farol, sin la biblioteca. Se conserva el archivo original; no se generan ilustraciones nuevas.

Colores de interfaz: niebla `#D5DFBC`, marfil `#F6F3E5`, texto `#182C20`, verde principal `#426638`, sidebar `#254B36` y oro `#E8D58C`.

## Sidebar transparente

`fairy-lantern-transparent-v1.png`: variante con alfa creada con la herramienta integrada image_gen a partir de la escena original. Incluye hada lectora, farol, tronco curvo, hojas y flores; excluye paisaje y biblioteca. Se muestra completa con `contain`, sin m?scara rectangular, sobre un resplandor CSS suave.

Prompt: extraer la vi?eta izquierda del hada y farol en composici?n vertical, conservar hojas y flores completas, retirar el fondo verde, lago, biblioteca, puente y luna; transparencia real y halos c?lidos suaves, sin texto ni interfaz.

## Fondo completo definitivo de sidebar

`sidebar-fairy-full-v1.png` es la imagen vertical enviada por el usuario, sin modificaciones. Sustituye los recortes y el follaje generado: se aplica como fondo de la sidebar completa y del men? desplegable de celular, detr?s del logo, enlaces y cuenta. Se muestra con `100% 100%` para conservar todos los extremos de la composici?n.

## ?rbol superior

`tree-library-transparent-v1.png` conserva la nueva imagen enviada por el usuario. Reemplaza exclusivamente la ilustraci?n superior del mural; el fondo completo de la sidebar permanece intacto. El ?rbol se alinea a la derecha y se adapta a la altura del encabezado, manteniendo sus proporciones.

## Composici?n de cuatro piezas (versi?n actual)

Extra?das directamente del atlas suministrado por el usuario, sin generaci?n ni cambio de estilo:

- `sidebar-leaves-v2.png`: follaje superior, detr?s del logo.
- `sidebar-fairy-v2.png`: hada y vegetaci?n en el espacio inferior del men?; transparencia original.
- `tree-header-v2.png`: ?rbol y biblioteca en la cabecera continua del mural.
- `reader-corner-v2.png`: setas y hojas para Tu rinc?n.

El atlas original se conserva en `artifacts/forest-universe-sources/four-pieces-atlas.png`. Sustituyen los recursos anteriores en la interfaz del tema. Los archivos anteriores se conservan como hist?rico.

La nueva referencia cambia la direcci?n de claro a verde profundo: fondo `#073B2B`, superficie `#174D3B`, superficie elevada `#205C46`, texto marfil `#FFF9E6`, texto secundario `#D9E5CB`, acento oro `#F0D974`, borde de panel `#8D9B60` y borde interactivo `#A3AD75`. Tonos elegidos para aproximar la referencia y preservar contraste. Nombres, IDs, preferencias y dem?s temas permanecen sin cambios.

## ?rbol sin recorte

`tree-header-v3.png`: variante generada mediante image_gen integrado a partir de `tree-header-v2.png`. Prompt: recomponer el ?rbol-biblioteca como vi?eta compacta con copa completa, ra?ces, puente y cascada, transparencia y margen alrededor, sin marco ni texto. Se muestra con `contain` a la derecha y conserva proporciones; sustituye el uso de `cover` que cortaba la copa.

## Sustituci?n del hada

`sidebar-fairy-v3.png` conserva directamente la nueva imagen transparente enviada por el usuario (hada lectora, tronco, flores y luces). Sustituye `sidebar-fairy-v2.png` en la decoraci?n inferior de la sidebar, alineada a la izquierda y al pie, con proporciones originales. No se gener? ni se edit? la ilustraci?n.

## Paisaje superior actual

`tree-landscape-v4.png` es el paisaje panor?mico enviado por el usuario, sin modificaciones. Sustituye el ?rbol aislado en la cabecera del mural, ocupando toda su ?rea hasta las pesta?as; mantiene la zona despejada a la izquierda y la biblioteca a la derecha. La sidebar y Tu rinc?n conservan sus recursos independientes.

## Tu rinc?n actual

`reader-corner-v3.png` conserva la imagen vertical de hojas y setas luminosas enviada por el usuario. Sustituye el recorte anterior en Tu rinc?n; el texto se mantiene en la zona superior izquierda despejada.
