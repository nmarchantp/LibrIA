# Estilo oscuro unificado

El estilo aprobado del mural se comparte ahora mediante `components/DarkInterior.css`, importado directamente por `Layout`. Se aplica en cualquier ruta autenticada de `dark`, incluso al abrir una URL directamente, sin pasar primero por el mural.

## Alcance

- Fondo superior con nebulosa, estrellas y transición al fondo de lectura.
- Sidebar con logo, trayectorias, selección violeta, farol con halo cálido y bordes difuminados.
- Misma paleta de fondo, superficies, texto, bordes y botones en perfil, biblioteca, lectura, catálogo, eventos, recomendaciones, configuración, mensajes, notificaciones y administración.
- Tarjetas y formularios con niveles de superficie consistentes. Los modales compartidos de perfil y contenido reciben los mismos tokens.
- Encabezados editoriales coordinados; administración conserva paneles sin paisajes interiores adicionales.

El hero del libro y el paisaje de Tu rincón permanecen en el mural. Los banners personalizados del perfil, las portadas y los datos no se alteran. Login y registro conservan su identidad. Los estilos no se activan en los otros temas.

La paleta local mantiene los valores aprobados: fondo `#171421`, tarjeta `#2B2338`, superficie elevada `#342A45`, texto `#F7F1FF`, secundario `#CBBFDA`, botón principal `#7E57C2`, hover `#7248B4` y borde interactivo `#9580BA`. Los identificadores y preferencias no cambian.

## Arquitectura

Se extrajeron los estilos comunes de `MuralIdentity.css`; ese archivo conserva los tratamientos propios del mural. `data-interior-style="literary"` delimita la interfaz autenticada. Se conservan los ajustes de capas para que los controles móviles aparezcan por encima de la cabecera y reciban clics.

## Verificación

[Galería de páginas](galeria-estilo-oscuro.html), con capturas reales y datos simulados a 1440 y 390 px.

La suite de identidad comprueba nueve rutas en seis tamaños, consistencia de la paleta oscura y presencia del farol en navegación de escritorio; también verifica contraste, foco, modal, menú móvil y ausencia de desbordamiento. La suite de navegación pasa 14 combinaciones de `dark`/`lavanda`, con foco, Escape, cierres, scroll y movimiento reducido. La suite de temas conserva las otras variantes y preferencias.

ESLint sin errores y con cinco advertencias existentes de fixtures. Build correcto, con advertencia de tamaño de bundle. No se realizaron escrituras al backend ni a datos reales. Safari y Firefox no fueron comprobados.
