# Profundidad del mural oscuro

## Cambios aplicados

La figura angular se eliminó del componente y se sustituyó por `MuralBrandStar`, que reutiliza la máscara de cuatro puntas del logo. El hero oscuro solo conserva esa estrella: se retiran las partículas adicionales de su fondo y se profundiza el degradado violeta, con luz lavanda localizada. No hay animación ni efectos sobre el contenido.

La paleta propuesta se aplica mediante variables locales de `.social-shell[data-mural="true"]` en `dark`. No se modifica `themes.js`, identificadores, preferencias ni colores de las demás rutas. La única corrección compartida con el mural claro es la eliminación de la figura angular; su paleta y jerarquía permanecen.

| Nivel | Color aplicado |
|---|---|
| Fondo | `#171421` |
| Sidebar | `#211B2E` |
| Tarjeta | `#2B2338` |
| Panel elevado | `#342A45` |
| Hero base | `#2A1F3D` |
| Glow violeta / lavanda | `#6D4FA3` / `#A98AE8`, mezclados con transparencia |
| Texto / secundario | `#F7F1FF` / `#CBBFDA` |
| Borde general / interactivo | `#514564` / `#9580BA` |
| Principal / hover | `#7E57C2` / `#7248B4` |
| Secundario | `#3A304A` |

Dos desviaciones de la propuesta responden al contraste: el borde `#7C68A0` no alcanzaba 3:1 sobre el botón neutro, por lo que se aclara a `#9580BA` (3,57:1). El hover `#9168DA` daba 3,65:1 con el texto claro; se oscurece a `#7248B4`. El botón principal normal alcanza 4,71:1. Se conservan los colores semánticos de estados.

«Tu rincón» usa un degradado más rico, una estrella pequeña y separación clara del enlace. Se elimina la órbita secundaria del panel. Publicaciones y portadas conservan su composición, sin adornos nuevos. El panel de lectura se distingue mediante la superficie elevada.

## Comparación y validación

[Comparar antes/después](comparacion-profundidad-mural.html) en oscuro a 1440 y 390 px. Capturas en `artifacts/mural-depth-before/` y `artifacts/mural-depth-after/`, con el mismo fixture y resolución. La diferencia se aprecia en el bloque superior, sidebar y paneles; el contenido permanece sobre fondo limpio. Las capturas simuladas incluyen categorías vacías, por lo que no representan todos los contenidos reales.

Pruebas de identidad: nueve vistas, seis resoluciones, sin errores de ejecución ni desbordamiento horizontal. Se evalúan controles del mural, incluidos principal normal y hover, bordes, modal y foco. La suite de temas comprueba persistencia y variantes ajenas. ESLint sin errores, con cinco advertencias existentes en fixtures. Build correcto, con advertencia de tamaño de bundle. Revisión visual en Chrome, sin afirmar certificación completa WCAG ni pruebas de Safari/Firefox.

## Dirección preparada para siguientes pantallas

La jerarquía propuesta queda documentada aquí, sin activarla fuera del mural:

- **Mi perfil:** fondo base y paneles elevados; conservar banner personalizado y portadas.
- **Explorar:** resultados en superficie de tarjeta, herramientas en superficie elevada; sin efectos en portadas.
- **Eventos:** misma separación entre agenda, filtros y detalles.
- **Recomendaciones IA:** resultados limpios y estados semánticos, con marca solo en encabezado.
- **Configuración:** formularios sobre tarjeta y grupos auxiliares elevados, sin hero ilustrado.

Tras la validación visual del mural, estos tokens pueden extraerse a un alcance compartido explícito. Administración permanece fuera de esta propuesta y conserva su tratamiento actual.
