# Navegación principal

El layout compartido mantiene exactamente cinco enlaces en el sidebar, en orden:
Mural, Mi perfil, Explorar libros, Eventos y Recomendaciones IA. El bloque de
cuenta y Cerrar sesión permanece debajo. En móvil se muestra al final del menú
desplegado, que se cierra al navegar o con Escape.

Los accesos definitivos del perfil son:

- Biblioteca: **Mi perfil → Mi biblioteca** (`/profile?tab=library`). La ruta
  anterior `/library` conserva su redirección existente.
- Tu ADN lector: **Mi perfil → Mis análisis** (`/profile?tab=analysis`). No se
  añadió ninguna sección o acceso alternativo a este análisis.

Mensajes (`/messages`) y Notificaciones (`/notifications`) se enlazan desde dos
iconos en un único encabezado compartido. Tienen nombres accesibles, tooltips
visibles con hover/foco y resaltado de ruta activa. En móvil se alinean en la
misma fila visual del logo y el botón de menú, sin añadir otro encabezado.

Las páginas existentes de mensajes y notificaciones siguen siendo demostrativas.
No había un contador global real de pendientes, por lo que no se muestran
contadores inventados en el encabezado. Sus contenidos no se modificaron.

Para conservar los accesos condicionales sin añadir opciones al sidebar,
«LibrIA Insights», «Gestionar perfiles» y «Carga de datos» se encuentran en el
menú Herramientas del encabezado. Mantienen las mismas condiciones anteriores:
respuesta `group` de `/analytics/access` para Insights y rol `admin` para las
herramientas administrativas. Las rutas y sus controles de autorización no
cambiaron.

## Archivos y validación

La implementación está en `Layout.jsx` y `LayoutNavigation.css`; no cambia las
páginas, backend, permisos, autenticación, preferencias, banner ni temas.
El logo y el bloque de usuario usan enlaces normales para evitar marcarlos como
segundas opciones activas junto al enlace principal.

Con Vite y el navegador CDP aislado descrito en `profile-edit-modals.md`:

```powershell
npm run test:navigation --prefix apps/web
npm run test:profile-modals --prefix apps/web
npm run lint --prefix apps/web
npm run build --prefix apps/web
```

La suite de navegación usa servicios sustituidos en una fixture de prueba,
sin escrituras al backend. Comprueba el orden exacto y una sola ruta activa,
mensajes/notificaciones, las seis pestañas del perfil, biblioteca/análisis,
los seis temas a 1440/768/390/320 px, menú móvil, cuenta y cierre de sesión,
condiciones de las herramientas administrativas y tooltips con ratón/teclado.
Las capturas de `artifacts/navigation/` usan datos de prueba y no se cargan como
recursos de la aplicación.
