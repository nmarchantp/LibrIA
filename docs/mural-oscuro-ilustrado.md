# Mural oscuro basado en la referencia ilustrada

## Fondo superior y sidebar completados

La nebulosa superior reutiliza la parte alta del recurso existente, con desvanecimiento y oscurecimiento para preservar los iconos y el saludo. No añade descargas ni animaciones. La sidebar incorpora iluminación violeta, trayectorias junto al logo, selección activa redondeada, farol de mayor tamaño y separadores de cuenta. [Comparación específica](comparacion-fondo-sidebar.html).

Se corrigió también el aislamiento de capas de la columna principal en celular para `dark` y `lavanda`: antes impedía que los controles superiores recibieran clics por encima de la barra lateral. La suite de identidad ahora comprueba apertura real del menú mediante puntero. La prueba dedicada de navegación usa el fixture actualizado y acepta superficies elevadas del tema como encabezado opaco. El escenario de 320 px de `otono` sigue mostrando un ajuste de ancho pendiente en la suite completa; no se modificó esa paleta.

La captura del usuario define esta dirección, sustituyendo la restricción anterior de no usar paisajes en el mural. El cambio continúa limitado al mural de `dark`; no se extiende a otras pantallas ni a otras paletas.

## Implementación

- Hero ilustrado con libro abierto, nube violeta y estrella luminosa. Borde redondeado y capa oscura localizada para proteger la lectura.
- Tu rincón con paisaje de castillo, luna y enlace delimitado. El saludo y el texto siguen siendo HTML real; se mantiene su funcionalidad.
- Sidebar con libros y farol transparente en el espacio disponible entre navegación y cuenta; se oculta en la navegación compacta para no interferir con sus controles.
- Estado activo violeta, navegación del mural elevada y separadores estelares en encabezados de categorías. Las tarjetas no reciben ilustraciones ni efectos encima de su contenido.
- Se evita superponer la estrella CSS del hero al recurso ilustrado, que ya contiene una estrella. Las ilustraciones son estáticas y decorativas.
- En celular se oscurece y reencuadra el hero; el libro permanece visible, el texto se adapta y los carruseles conservan su interacción.

## Recursos

Se utilizó la habilidad [imagegen](C:/Users/nikoo/.codex/skills/.system/imagegen/SKILL.md), mediante la herramienta integrada, sin API/CLI. Los tres WebP finales y los prompts completos se encuentran en [mural-universe](../apps/web/public/images/mural-universe/README.md). Total de las ilustraciones públicas: 413 074 bytes (aproximadamente 403 KiB). Los PNG fuente permanecen fuera de los recursos públicos de producción.

## Comparación y pruebas

[Comparación antes/después](comparacion-mural-ilustrado.html) a 1440 y 390 px, en oscuro. Para que pueda evaluarse el protagonismo del contenido, ambas capturas utilizan el mismo escenario simulado con actividades de lectura. Son fixtures aislados: no se agregaron publicaciones, libros ni cuentas a la aplicación real.

La suite de identidad recorre nueve vistas, dos temas y seis tamaños; no detecta excepciones ni desbordamiento horizontal. Comprueba contraste de controles normales/hover, límites, foco y modal. La suite de temas conserva paletas, preferencias y variantes ajenas. Lint sin errores, con cinco advertencias existentes de Fast Refresh en fixtures. Build correcto, con advertencia de tamaño de bundle. Las imágenes están separadas de ese bundle de JavaScript.

La revisión visual se realizó con capturas reales de Chrome. No se afirma una certificación completa WCAG ni cobertura de Safari/Firefox. El contenido de producción seguirá utilizando sus propias portadas y datos.

Para regenerar las capturas en PowerShell, con el navegador CDP disponible:

```powershell
$env:MURAL_SCENE='1'
$env:CAPTURE_FOLDER='mural-reference-after'
npm run test:interior-identity
```
