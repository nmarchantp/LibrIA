# Algodón de azúcar: identidad rosa compartida

El tema existente `rosa-antiguo` utiliza ahora la lámina de ilustraciones adjunta por el usuario. `CottonInterior.css`, importado por `Layout`, comparte fondo, sidebar, superficies, controles y encabezados entre todas las rutas autenticadas.

El mural conserva título transparente y fondo continuo. La escena de libros, lazos y dulces queda centrada antes de Tu rincón. El panel lateral muestra el cupcake; el sidebar utiliza el adorno de libros, piruleta y frasco. Los bordes de la ambientación se desvanecen para evitar recuadros. En celular se reencuadra la escena y se oculta el adorno del menú para proteger su interacción.

El banner automático del perfil comparte la escena panorámica. Los avatares, las portadas, datos, enlaces y permisos permanecen. Administración conserva superficies limpias. Autenticación no recibe estos estilos.

## Paleta local

La paleta raíz de `themes.js` permanece; las superficies interiores usan fondo `#FFF2F8`, tarjeta `#FFFAFD`, tinta `#301331`, texto secundario `#68445E`, acción principal `#AD2869`, hover `#8E1855`, borde interactivo `#A65C82` y neutro `#FBE1EF`. Nombre, ID, preferencias y sincronización se conservan.

Se reutilizan [las ilustraciones suministradas](../apps/web/public/images/cotton-universe/README.md) mediante un atlas CSS: un solo WebP de 73 952 bytes. No hay nuevas dependencias ni generación de imágenes.

## Revisión

- [Galería de páginas](galeria-algodon-azucar.html).
- [Antes/después](comparacion-algodon-azucar.html).

Capturas reales de navegador con API simulada, a 1440 y 390 px. Pruebas de identidad en nueve rutas y seis resoluciones, sin excepciones ni desbordamiento, con foco, modal y menú móvil. Texto del botón principal: 6,39:1; hover: 8,71:1; texto neutro: 13,55:1; borde neutro: 3,83:1; texto de campo: 15,90:1 y borde: 4,49:1.

Navegación: siete tamaños, áreas de 44 px, cierres, Escape, scroll y movimiento reducido. Suite de temas: nueve selecciones, preferencias y banners; los cambios de apariencia y banner de `rosa-antiguo` se consideran intencionales. ESLint sin errores y con cinco advertencias existentes en fixtures; compilación correcta, con advertencia de tamaño del bundle.

Revisión visual en Chrome; Safari y Firefox pendientes. Las muestras no constituyen certificación completa WCAG.

## Corrección adicional solicitada

El hover de navegación de Pacto de Sangre elimina el halo del pseudo-elemento que producía líneas visibles arriba y abajo. Las opciones inactivas utilizan un fondo burdeos uniforme, sin sombra; el estado activo mantiene su identificación roja.
