# Historias de usuarios

Todos los roles de cuentas personales, incluidos lectores, pueden publicar imágenes desde **Tu historia** en Mural → Contactos o desde el botón **+** de su foto de perfil. Se aceptan JPEG, PNG y WebP de hasta 5 MB y 25 megapíxeles. La vista previa conserva la imagen completa sobre un lienzo vertical 9:16. El servidor verifica y convierte la imagen a JPEG 1080 × 1920, sin metadatos. No incluye videos en esta versión.

Las historias duran exactamente 24 horas desde su publicación, con un máximo de 20 activas por perfil. Un aro luminoso con polvo dorado y un destello que recorre lentamente su contorno indica que queda alguna historia sin ver. Cuando todas se vieron, el mismo aro queda plateado y estático. Por solicitud de diseño, la animación del aro dorado permanece activa incluso con la regla global de movimiento reducido: el destello completa una vuelta cada ocho segundos. El plateado no tiene animación. El estado se guarda por usuario e historia en el servidor cuando la imagen termina de cargar en el visor visible. Una historia nueva vuelve a activar el aro dorado.

Contactos muestra una sola foto propia, con el aro si hay historias y un botón «+» independiente para publicar. Tocar la foto abre las historias propias, o el formulario si todavía no hay ninguna. Las fotos de personas seguidas aparecen después. La sección se ubica antes de «Entre páginas». Desde un perfil se abre su primera historia y se puede continuar por los demás perfiles visibles. El visor avanza cada siete segundos y permite clic a ambos lados, flechas del teclado y deslizamientos horizontales; incluye pausa, cierre con Escape y eliminación con confirmación para el propietario.

Las imágenes se solicitan con Bearer y se muestran con una URL de objeto temporal; no existen enlaces públicos a los archivos. Tanto el listado como cada descarga verifican la vigencia, el estado de la cuenta y la privacidad actual del perfil. Un perfil privado admite las personas a quienes sigue su propietario, igual que el resto del perfil. No se comparten historias de cuentas suspendidas o inactivas. Los listados se actualizan cada minuto, al recuperar foco y después de publicar o eliminar.

Migración: `0089_user_stories`, posterior a `0088_profile_privacy`. Las historias vencidas dejan de estar disponibles inmediatamente. `scripts.run_scheduler` elimina sus archivos en lotes de 200 cada minuto mediante el proceso de mantenimiento existente; la caducidad funciona aunque el scheduler esté detenido. Una nueva publicación también retira las historias vencidas de su autor.

API autenticada:

- `GET /api/stories?audience=contacts|community`, filtro opcional `profile_id`.
- `POST /api/stories`, cuerpo binario de imagen.
- `GET /api/stories/{id}/image`, con `Cache-Control: private, no-store`.
- `DELETE /api/stories/{id}`, exclusivo del propietario.
- `PUT /api/stories/{id}/view`, confirmación idempotente para el usuario autenticado, respetando privacidad y vencimiento. Requiere la migración `0090_story_views`; los registros se eliminan junto con la historia.

Pruebas backend: `python -m unittest tests.test_user_stories`. Pruebas de navegador aisladas: `npm run test:stories`; no publican contenido en la base real.
