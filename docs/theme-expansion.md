# Ampliación de temas de LibrIAverse

Se extiende el catálogo existente a cinco claros y cuatro oscuros. No se cambia
ThemeContext, autenticación, rutas, navegación, endpoints ni base de datos.

| Grupo | Nombre visible | ID persistido |
| --- | --- | --- |
| Claro | Jardín de Macarons | `lavanda` |
| Claro | Tintas del Equinoccio | `otono` |
| Claro | Alas de Cristal | `invierno` |
| Claro | Algodón de azúcar | `rosa-antiguo` |
| Claro | Bosque feérico | `bosque` |
| Oscuro | Reino de Sombras | `dark` |
| Oscuro | Rosas y Espinas | `dark-rosado` |
| Oscuro | Pacto de Sangre | `dark-blood` |
| Oscuro | Biblioteca de Medianoche | `dark-dorado` |

La clave `localStorage.libria_theme` y sus seis IDs originales permanecen intactos.
El catálogo ampliado permite guardar los tres nuevos sin migrar preferencias.
Se conservan la sincronización entre pestañas y el respaldo Jardín de Macarons ante IDs inválidos.

Los cinco claros y Dark original conservan sus colores, variables derivadas,
estados funcionales y banners. Solo cambian los nombres visibles de Bosque y Dark.
Las variantes nuevas reciben variables semánticas para toda la aplicación y
reutilizan temporalmente el recurso y encuadre de Dark, sin modificar los archivos
de imágenes ni la lógica de carga/fallback de ProfileBanner.

Pacto de Sangre mantiene fondos negros y superficies neutras. El rojo `#89001F` se usa
en botones con texto claro; `#EE7893` es la variante legible para texto pequeño,
contornos SVG y foco. `#C4183D` se mantiene como acento y hover. Los estados de
error, éxito, advertencia e información son independientes de la identidad decorativa.

## Archivos

- `apps/web/src/theme/themes.js`: catálogo, grupos y rol accesible opcional.
- `apps/web/src/theme/themes.css`: variantes oscuras y contraste de controles.
- `apps/web/src/theme/profileBanners.js`: reutilización de Dark para variantes nuevas.
- `apps/web/src/pages/ProfilePage.css`: atenuación del banner para los nuevos oscuros.
- `apps/web/src/components/ThemeSelector.jsx` y `.css`: dos grupos, nueve opciones,
  misma presentación de tarjetas y distribución responsive 4/2/1.
- `apps/web/package.json`: comando `test:themes` sin dependencias adicionales.
- `apps/web/tests/themes.mjs` y `fixtures/original-theme-appearance.json`: pruebas
  de regresión de paletas originales, persistencia, banners, contraste y selector.
- `apps/web/tests/main-navigation.mjs` y `profile-edit-modals.mjs`: cobertura de
  las nueve paletas en navegación y editores reales del perfil.
- `apps/web/src/theme/README.md` y este documento: arquitectura y entrega.
- `artifacts/themes/`: capturas de las tres variantes nuevas en Configuración y
  del perfil con Pacto de Sangre, obtenidas con datos de prueba aislados.

## Validación

Pruebas de navegador con el fixture autenticado aislado y Edge vía CDP; sin
escrituras en backend ni uso de datos reales de usuarios:

- Comparación exacta de las seis paletas previas: variables, esquema de color,
  colores/sombras representativos y configuración de banners.
- Nueve opciones únicas, grupos de cinco y cuatro, una selección activa.
- Aplicación inmediata y recuperación de cada ID tras recrear el documento.
- Carga y decodificación correctas de los banners de los nueve IDs.
- Diez pares de texto/controles/estados por tema nuevo con contraste mínimo 4,5:1.
- Renderizado de mural, explorar, eventos, recomendaciones, mensajes,
  notificaciones, configuración, biblioteca y análisis con cada nuevo tema.
- Selector a 1440/768/390/320 px con cuatro/dos/una/una columnas, sin desbordamiento.
- Navegación y cuatro modales en nueve temas; permisos comunitarios conservados.
- Sin errores de consola ni excepciones del navegador en la prueba de temas.
- ESLint y build de producción.

## Límites y colores fijos existentes

- Faltan banners exclusivos para los tres nuevos temas, por decisión de producto.
- `LibraryContext.jsx` y `BookCover.jsx` conservan colores de portadas de contenido
  y su respaldo; no se recolorean como superficies de la interfaz.
- Hay valores fijos históricos en `AdminEtlPage.css` (cabecera de tabla) y
  `styles.css` (fechas/iconos de notificación). Ya tienen reglas semánticas que
  los sobrescriben en los estilos globales; no se rediseñan en esta ampliación.
- `CommunityDashboard.css` conserva un color de respaldo dentro de
  `var(--accent, …)`; la variable está definida en las nueve paletas.
- Los colores funcionales fijos de éxito/error/advertencia/información son roles
  intencionales con variantes oscuras, no preferencias decorativas.
- Las verificaciones cubren roles y vistas con respuestas simuladas. No sustituyen
  una revisión manual de todas las combinaciones de datos y permisos en producción.
