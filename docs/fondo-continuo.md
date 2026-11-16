# Fondo continuo del mural

En Reino de Sombras (`dark`), Jardín de Macarons (`lavanda`) y Pacto de Sangre (`dark-blood`), el encabezado deja de ser una tarjeta frontal. Su fondo es transparente, sin borde, radio ni sombra. El título conserva sus textos, tipografía y funcionalidad.

`ContinuousMural.css` comparte este comportamiento y selecciona la imagen existente de cada tema. Una sola capa superior se extiende desde la barra de saludo hasta el comienzo del contenido, con veladura lateral para proteger el texto y desvanecimiento hacia el fondo normal. No se descargan ilustraciones nuevas ni se añaden animaciones.

En escritorio, la escena reserva el espacio de la columna lateral y se escala completa, con un ancho máximo de 1000 px. Así el libro permanece junto al título y no queda oculto detrás de Tu rincón. Los bordes laterales e inferior se desvanecen para evitar que reaparezca un recuadro.

En celular se reencuadra la misma imagen y se adapta su veladura. El fondo respeta el interruptor existente de ambientación; los controles permanecen encima y las tarjetas conservan sus superficies. Los paneles de Tu rincón y sidebar se mantienen. Los otros temas y las demás rutas conservan sus diseños.

[Galería de los tres temas, escritorio y celular](galeria-fondo-continuo.html). Capturas reales con API simulada, a 1440 y 390 px.

Verificación: tres temas, nueve rutas y seis tamaños sin desbordamiento ni excepciones. La suite comprueba el encabezado sin fondo, borde ni sombra, además de contraste, foco y menú móvil. Lint sin errores, con cinco advertencias existentes en fixtures; compilación correcta, con advertencia de tamaño del bundle. Revisión visual en Chrome; Safari y Firefox pendientes.
