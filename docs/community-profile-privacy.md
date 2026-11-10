# Perfiles de la comunidad

Los nombres y avatares de las publicaciones enlazan a `/profiles/:profileId`.
En Mi perfil, los contadores entre la fecha de ingreso y las pestañas abren
modales de seguidores y seguidos. Libros leídos cuenta obras distintas con al
menos una lectura terminada, sin duplicar relecturas. Las
notificaciones de seguimiento también enlazan al perfil de quien te sigue.

Debajo de los contadores, Editar privacidad abre las mismas opciones de
Configuración; se guardan al instante. Compartir perfil genera un QR localmente
con `qrcode` y permite copiar el enlace. El enlace abre el perfil con una
invitación a seguirlo, conservando el destino durante login, registro y acceso
con Google. Escanear el QR no ejecuta un seguimiento sin pulsar Seguir.

El QR usa puntos redondeados, marcadores con esquinas suaves y un libro con
destello central. Su degradado sigue la paleta activa; las tintas se oscurecen
cuando hace falta para conservar contraste sobre blanco. Se conserva el margen
de lectura y se usa corrección H. El nombre real de la cuenta aparece debajo.
La prueba de navegador decodifica el PNG con `jsqr` en las nueve paletas y
comprueba que el contenido sea exactamente el enlace al perfil compartido.
Los puntos de control tienen bordes redondeados y los marcadores pequeños de
alineación conservan sus anillos. El libro crece dos veces un 15% (32,25%
acumulado), con un margen blanco adicional de 0,9 módulos por lado. También se
comprueban URLs con UUID a 320 y 240 píxeles.

Descubrir personas abre tarjetas con avatar, nombre y botón Seguir. La búsqueda
por nombre excluye la cuenta propia, personas ya seguidas y cuentas inactivas o
suspendidas. La API solo entrega nombre, avatar e ID comunitario. El contador
de seguidos se actualiza al seguir o dejar de seguir desde las tarjetas.

En Configuración → Mi cuenta → Privacidad de mi perfil se puede elegir público
o privado y seleccionar biografía, géneros, temáticas, gustos, intereses y citas.
Las secciones desactivadas no se devuelven en la respuesta de la API.

Un perfil privado se desbloquea cuando su dueño sigue al visitante. Seguir al
dueño no lo desbloquea. Sin acceso solo se muestran el banner existente, nombre,
foto, estado y controles de seguimiento, junto con la explicación de acceso.
El dueño siempre puede abrir su propia vista comunitaria. Los perfiles públicos
son accesibles a usuarios autenticados. La biblioteca y los análisis personales
no se incluyen en la proyección comunitaria.

Los eventos conservan sus controles privado/contactos/público; además, el bloqueo
general de un perfil privado también protege los endpoints de su agenda.

El seguimiento crea una notificación persistente dentro de la misma transacción.
Hay como máximo una por pareja de usuarios, para evitar spam al dejar de seguir
y volver a seguir. La bandeja permite paginar y marcar como leída; únicamente su
destinatario puede consultarla o modificarla. No se envían correos.

Las listas personales de seguidores/seguidos y las notificaciones se paginan en
la API. Se excluyen cuentas suspendidas o inactivas.

Migración: `0088_profile_privacy`, posterior a `0087_demo_mode`. Conserva como
públicos los campos comunitarios anteriormente visibles. Las citas requieren
activación explícita. El banner conserva el componente visual existente.

Validación:

```sh
cd apps/backend
python -m unittest tests.test_community_profiles tests.test_profile_events tests.test_literary_preferences
cd ../web
node tests/community-profile-render.mjs
npm run test:profile-social
npm run build
```
