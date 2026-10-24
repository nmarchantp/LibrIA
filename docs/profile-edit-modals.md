# Edición de Sobre mí mediante modales

`ProfileEditModal` usa un `dialog` nativo abierto con `showModal()` y montado
mediante un portal en `document.body`. La capa superior del navegador lo sitúa
por encima de banners y menús y vuelve inerte el fondo. No requiere dependencias.

Los editores de historia, géneros, tropos y gustos conservan sus estados de
borrador, catálogos, validaciones y llamadas existentes a `onSave`. Sus tarjetas
permanecen montadas con los datos guardados, sin clases de edición ni formularios
inline. El modal tiene encabezado, cuerpo desplazable y pie de acciones fijo.

- Guardar cierra únicamente después de una respuesta exitosa y actualiza la
  tarjeta mediante el flujo existente. Los errores conservan el borrador.
- Durante el guardado se deshabilitan los controles de cierre.
- Cancelar, X, Escape y clic en el overlay solicitan confirmación si hay cambios.
  «Seguir editando» conserva el borrador; «Descartar cambios» cierra sin guardar.
- Los cambios del buscador no cuentan como preferencias pendientes de guardar.
- El foco entra en el diálogo, se mantiene dentro, se recupera si la carga de un
  catálogo desmonta el selector enfocado y vuelve al botón Editar al cerrar.
- El scroll del fondo se bloquea conservando el espacio de la barra de scroll.
- Las preferencias públicas conservan la vista de lectura sin controles Editar.

«Otros intereses» permanece retirado de la interfaz, como en la versión anterior.
Este cambio no modifica backend, base de datos, endpoints, permisos ni el sistema
de temas, y no afecta biblioteca u otras pestañas.

## Pruebas de navegador sin dependencias adicionales

Ejecutar Vite en `http://127.0.0.1:5173` y un Edge/Chromium aislado con depuración
remota. Por ejemplo, en PowerShell sobre Windows:

```powershell
Start-Process -FilePath 'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe' -ArgumentList '--headless=new','--disable-gpu','--no-first-run','--remote-debugging-port=9224',"--user-data-dir=$env:TEMP/libria-about-modal-qa",'about:blank' -WindowStyle Hidden
npm run test:profile-modals --prefix apps/web
```

Se pueden configurar `CDP_URL` y `VITE_URL`. El script abre y cierra su propia
pestaña de prueba. La fixture usa servicios sustituidos y datos claramente de
prueba; no envía escrituras al backend ni se importa desde la aplicación.

La suite comprueba geometría de las cinco tarjetas antes y durante la edición,
scroll y foco, ciclo Tab/Shift+Tab, fondo inerte, confirmación al cerrar, cancelación,
contador de 200 caracteres, errores/reintentos, guardado pendiente, los cuatro
contratos de actualización, límite de géneros, cinco categorías y un destacado,
los seis temas a 1440/768/390/320 px, pantallas de poca altura y perfil comunitario.
