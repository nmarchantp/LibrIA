# Modo demostración

La migración `0087_demo_mode` agrega un interruptor persistente, desactivado de
forma predeterminada. Aplicar con el procedimiento habitual de respaldo y
migración explícita; reiniciar el backend con el código actualizado.

En **Administración > Configuración > Modo demostración**, un administrador
puede activar o desactivar la generación sin reiniciar. Necesita
`CATALOG_DISCOVERY_ENABLED=true` y `LIBRIA_DEMO_PASSWORD` de al menos ocho
caracteres. La contraseña permite iniciar únicamente las cuentas propias de
esta demo; el servicio no cambia contraseñas de cuentas existentes.

La selección está limitada a los doce títulos y autores aprobados en
`app/modules/demo/curated_books.json`. Se reutilizan ediciones verificadas del
catálogo y se buscan las pendientes en Google Books u Open Library. Las
importaciones usan el servicio canónico y registran al administrador y su motivo.
No se sustituyen libros pendientes por títulos ajenos a la lista. El panel muestra
los títulos preparados y los que aún no se han conseguido con portada.

Las portadas originales se descargan, se valida que sean imágenes de tamaño
adecuado y se guardan en `apps/backend/var/demo-covers/` (fuera de Git). Se sirven
desde `/api/demo/covers/{edition_id}`. Cuando el proveedor no trae imagen, se
busca por el ISBN verificado de la edición; una excepción curada puede indicar
la imagen de una ficha de librería con exactamente ese ISBN y guardar su fuente.
La imagen no se inventa ni se asigna solo por coincidencia de título. Conserva
esta carpeta como almacenamiento persistente al desplegar la demo.

La nueva selección reemplaza los libros demo anteriores en las consultas del
mural, sin eliminar su actividad histórica ni filtrar la de usuarios reales. Un
cambio de selección retoma en el siguiente ciclo completo y mantiene las claves
de actividad ya utilizadas. No necesita otra migración.

Para preparar o volver a intentar los pendientes con la demo apagada, sin cambiar
su interruptor: `python -m scripts.prepare_demo_catalog`. Necesita la autorización
administrativa previamente guardada al configurar la demo y acceso a Internet.

Ocho perfiles ficticios identificados con «Demo» usan las APIs de autenticación,
biblioteca, lectura, reseñas, publicaciones, eventos e interacciones. Las
actividades van a sus tablas correspondientes; no se duplican como posts.
Se generan inicios, avances, finales, reseñas, notas, teorías, publicaciones,
promociones, novedades, lanzamientos, eventos fechados, seguimientos,
comentarios, me gusta, visualizaciones y asistencias. Solo se generan
interacciones con contenido de las cuentas demo.

Las acciones se mezclan con aleatoriedad reproducible: cada bloque de 32 incluye
actividad de lectura, todos los tipos de publicaciones e interacciones. Los
siete perfiles lectores se turnan en orden barajado, cada uno conserva su propio
intento activo y empieza con una asignación distinta cuando hay suficientes
libros. Los avances tienen incrementos variables, los finales solo ocurren sobre
intentos iniciados y generan una reseña. Las publicaciones eligen otros libros,
textos y actores independientemente de esa lectura. La librería no recibe
lecturas personales. La mezcla no completa primero todos los pasos de una misma
persona y un mismo libro. No necesita migraciones adicionales.

Los primeros 32 pasos se preparan a intervalos de dos segundos; después se usa
el intervalo elegido (10–3600 segundos). Un bloqueo asesor PostgreSQL evita
productores simultáneos entre procesos de API. El estado y el progreso
sobreviven a reinicios. Las escrituras sociales usan claves de idempotencia;
las lecturas revisan su estado antes de avanzar. La procedencia demo de las
lecturas, reseñas y publicaciones queda registrada para los consumidores de
analítica que distinguen datos simulados.

Desactivar detiene nuevas operaciones. Una operación ya iniciada puede acabar.
No elimina contenido ni vacía el catálogo; reactivar continúa desde el progreso
guardado. No hay llamadas directas a Gemini en el generador.

La CLI anterior ahora controla el mismo interruptor, no inicia otro productor:

```powershell
python -m scripts.generate_posts --enable --interval 30
python -m scripts.generate_posts --disable
python -m scripts.generate_posts
```

Usa por defecto `demo.admin@example.com` y `LIBRIA_DEMO_PASSWORD` para
autenticarse. Para otras cuentas, usa el panel con su sesión administradora.
`run-local.ps1 -DemoPosts` activa este mismo modo después de esperar a la API.
No se necesita mantener otra ventana de generador abierta.

## Validación desde una base vacía

Desde `apps/backend`: `python -m scripts.validate_demo_fresh_database`.
El validador crea su propio clúster PostgreSQL 17 en un puerto aleatorio y nunca
acepta una URL de base de datos de aplicación. Aplica todas las migraciones,
ejecuta `migrate_and_seed`, repite la semilla para comprobar idempotencia y exige
que el catálogo y la caché de portadas estén inicialmente vacíos. Luego usa los
proveedores reales, el importador canónico y las APIs de la aplicación.

Comprueba doce ediciones con sus doce portadas, las ocho personas ficticias,
actividad intercalada con lecturas coherentes, todas las categorías del mural,
retomar el progreso y activar/desactivar. Las llamadas Gemini y los schedulers
quedan deshabilitados en esa validación. Necesita PostgreSQL local y acceso a los
proveedores de catálogo e imágenes. El servidor privado se detiene al terminar;
sus registros se conservan en el directorio temporal indicado por la ejecución.
El resultado se guarda en `artifacts/demo-fresh-database/last-result.json`.

La validación del 9 de noviembre de 2026 pasó hasta `0087_demo_mode`: doce libros
y portadas importados desde cero, 97 pasos, 60 eventos de lectura sobre ocho
obras distintas, 21 publicaciones y doce reseñas antes de la prueba de reanudación.
La base configurada de la aplicación no fue utilizada ni modificada.
