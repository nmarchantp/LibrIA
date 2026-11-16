# Mural: identidad visual perceptible

15 de noviembre de 2026. Iteración limitada al mural de `dark` y `lavanda`.

## Resultado

El encabezado deja de depender de detalles diminutos: ahora ocupa una región delimitada con profundidad violeta, nubes de luz lavanda, estrellas irregulares y un libro dibujado como constelación. El degradado termina antes de la navegación del mural; no se aplica detrás de las publicaciones. El título y descripción usan los colores de texto actuales.

La cabecera del logo recibe una iluminación violeta y una trayectoria curva. La selección activa de navegación conserva su estructura y añade profundidad. Estos cambios de sidebar solo se activan mientras se está en el mural.

«Tu rincón» tiene una estrella de marca, degradado, saludo editorial, separación del mensaje y enlace claramente delimitado. Mantiene el destino al perfil y su ubicación; no se fuerza a aparecer en celular si el layout actual lo oculta.

Se mantienen las doce bases de color. La noche usa mezclas de secundario, papel, acento y principal; el amanecer claro usa las mismas variables de su propia paleta, con superficies luminosas. No se introducen colores fijos en los estilos del mural ni nuevas dependencias.

## Integración y alcance

`MuralIdentity.css` centraliza los cambios. `LiteraryConstellation` aporta el pequeño dibujo vectorial decorativo, oculto de la semántica accesible. `LiteraryAtmosphere` se conserva para otras vistas; su capa tenue se oculta en el mural para evitar duplicarla con el nuevo encabezado. `LiteraryIdentity` sigue vigente, retirando en este encabezado la estrella pequeña anterior.

Perfil, biblioteca, recomendaciones, administración, login y registro no reciben este rediseño. Tampoco cambian backend, datos, permisos, rutas ni autenticación. Los otros siete temas conservan su apariencia; el dibujo nuevo queda oculto en ellos.

## Comparación visual

[Abrir antes/después del mural](comparacion-identidad-mural.html): capturas de 1440 y 390 px en ambos temas. Los archivos anteriores provienen de la fase inmediatamente anterior y los posteriores se generaron con el mismo fixture y resolución.

1. **Identidad más fuerte:** el área violeta delimitada y el panel editorial se distinguen a tamaño de pantalla completa.
2. **Continuidad con login:** cielo, iluminación lavanda, estrella de marca y constelación literaria, sin trasladar castillos ni paisajes.
3. **Protagonismo del contenido:** los efectos terminan en la cabecera; las tarjetas, portadas y actividades conservan sus estilos. Las capturas usan datos simulados y varias categorías vacías, por lo que no representan todas las publicaciones reales.
4. **Tu rincón:** separación entre símbolo, saludo, texto y enlace; intensidad coordinada con el encabezado.
5. **Legibilidad:** texto de los temas actuales sobre superficies de su propia paleta, sin animaciones ni capas que intercepten controles.
6. **Celular:** constelación reducida, título legible y cabecera de navegación compacta; no se agregan paneles nuevos al flujo móvil.

## Validación

- Suite de identidad interior: nueve vistas, dos temas, seis resoluciones, sin excepciones ni desbordamiento horizontal; contraste base, foco y modal conservados.
- Suite de temas: paletas, persistencia, selector y estilos de los temas ajenos sin regresiones detectadas.
- ESLint: cero errores y cinco advertencias existentes en fixtures.
- Build correcto, con advertencia de tamaño de bundle.
- Revisión visual de capturas reales en Chrome de ambos temas y tamaños solicitados. Safari y Firefox pendientes.

Para regenerar en PowerShell: `$env:CAPTURE_FOLDER='mural-identity-after'` y `npm run test:interior-identity`, con navegador CDP disponible. La comparación visual complementa las pruebas; no representa una certificación completa de accesibilidad.
