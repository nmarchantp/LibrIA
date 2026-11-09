# Corrección del acceso a Moderación de contenido

## Causa raíz

La entrega de etapa 4 montó `ModerationSection` en `AdminEnvironmentPage`, ruta
`/admin/environment`, accesible como «Configurar aplicación». Sin embargo, la opción
«Configuración» del menú existente abre `/settings`, renderizada por `SettingsPage`.
Esta última no importaba ni montaba la moderación. La importación del componente
era correcta, pero estaba en una ruta distinta a la que el usuario utilizaba.

La prueba anterior usaba directamente `/admin/environment`; por ello pasó sin
detectar el fallo de integración en la navegación real. No era un problema de roles
ni del backend. No se modificaron permisos, cuentas, modelos ni endpoints.

## Corrección

- `apps/web/src/pages/SettingsPage.jsx`: agrega el acceso **Moderación de contenido**
  dentro de Configuración, únicamente cuando `AuthContext` confirma `access.admin`
  y ha terminado de consultar los permisos. Monta el componente existente al
  seleccionar `/settings?tab=moderation`.
- `apps/web/src/pages/SettingsPage.css`: permite ajustar las opciones al ancho móvil.
- `apps/web/src/components/ModerationSection.jsx`: admite abrir directamente su
  contenido al entrar desde la pestaña, sin un segundo paso de expansión.
- `apps/web/src/pages/AdminEnvironmentPage.jsx`: sustituye el montaje anterior por
  un enlace al acceso canónico; no duplica la gestión ni cambia los formularios de
  Backend y Web.
- `apps/web/tests/fixtures/moderation.jsx`, `tests/moderation-ui.mjs`: la prueba
  recorre ahora el enlace real «Configuración» del menú y selecciona su nueva
  opción, en lugar de dar por válido el montaje en la otra ruta.

Ubicación: **Configuración → Moderación de contenido**, URL
`/settings?tab=moderation`. Muestra Pendientes de aprobación, Reportes de usuarios
e Historial. No se agregó una entrada independiente en el menú principal.

## Pruebas realizadas

- `npm run test:moderation`: correcto, incluyendo navegación desde el menú real,
  tres pestañas, decisiones, comparación, recuperación ante 409 y ausencia de
  excepciones JavaScript. Nueve temas a 360, 768 y 1440 px sin desbordamiento.
- La prueba comprueba también que un usuario sin acceso administrativo no ve el
  enlace y no puede montar el componente mediante la URL directa.
- `tests.test_moderation_administration`: 19 pruebas PostgreSQL correctas,
  incluyendo permisos reales, denegaciones y operaciones administrativas.
- `npm run lint`: sin errores, una advertencia previa de `Layout.jsx`.
- `npm run build`: correcto; advertencia de tamaño del bundle de Vite.
- `git diff --check`: sin errores.

## Verificación visual: alcance y pendiente

La navegación y el diseño se verificaron en navegador con respuestas aisladas de
prueba. **Esto no equivale a iniciar sesión con una cuenta administrativa real.**

Se comprobó que existe una cuenta con permiso administrativo real en PostgreSQL,
pero no hay credenciales locales de prueba configuradas ni una sesión real
autenticada disponible en el navegador conectado. No se crearon cuentas, no se
cambiaron contraseñas y no se concedieron permisos para eludir esta limitación.

La primera instancia conectada resultó ser headless, separada del Edge habitual.
Se abrió después una ventana visible y aislada, conectada al puerto 9225, en
`/login` de la aplicación real, sin interceptar su API ni solicitar contraseñas.
Aunque el usuario indicó haber iniciado sesión, la comprobación de esa ventana
seguía mostrando `/login` y ausencia de token. No se accedió a credenciales ni a
datos del perfil habitual de Edge para eludir esta limitación.

**La validación visual con cuenta real queda pendiente**; no se declara completada.
El resultado observado se registra sin credenciales en
`artifacts/moderation-access-fix/real-session-verification.json`. La captura
`configuration-fixture.png` corresponde exclusivamente a la prueba aislada.
