# Sobre mí y Mis gustos literarios

Las preferencias son declaraciones explícitas de la cuenta, no inferencias de
la biblioteca. La biografía sigue en `app.usuarios.biography`. Los géneros y los
tropos se almacenan en catálogos y relaciones independientes; no se incorporan
todavía al algoritmo IA ni al ETL.

## Base de datos y migración

`0043_literary_preferences` depende de `0042_google_email_verification` y crea:

- `app.catalogo_generos`: 15 opciones iniciales, con ID estable, nombre, orden y activo.
- `app.catalogo_tropos`: 15 temáticas/tropos iniciales, con los mismos metadatos.
- `app.gustos_generos`: cuenta, género y posición de 1 a 5.
- `app.gustos_tropos`: cuenta y temática/tropo.

Las claves compuestas evitan duplicados y las claves foráneas validan la identidad
del catálogo. Los cinco puestos posibles y su unicidad por cuenta impiden también
en PostgreSQL almacenar un sexto género. No se rellenan preferencias de cuentas
existentes. Las cuentas nuevas empiezan igualmente con listas vacías.

Antes de aplicar la migración se inspeccionaron las tablas de la base local: no
había equivalentes, la biografía era TEXT y la revisión era 0042. La migración
rechaza nombres de tabla ya existentes en lugar de asumir compatibilidad.
Se aplicó solo en la base **local de desarrollo** `libria`, comprobando entorno y
host previamente. No se migró producción. La reversión y reaplicación se probaron
dentro de una transacción que fue revertida, restaurando los datos anteriores.

Los catálogos se amplían con una migración de datos que agregue identificadores
estables; no se requiere editar el frontend. Se recomienda desactivar opciones
en lugar de borrarlas: las selecciones anteriores siguen visibles y pueden
mantenerse o retirarse, pero una opción inactiva no puede seleccionarse de nuevo.
No se incluye un mantenedor administrativo de catálogos en este alcance.

Actualización: `0044_trope_catalog_groups` amplía las temáticas a 51 y agrega cinco
grupos. El selector incluye búsqueda y conserva todas las selecciones anteriores.
Las etiquetas de géneros favoritos se muestran ahora en Sobre mí. La tarjeta inferior
presenta estadísticas personales de géneros leídos, independientes de las preferencias.
Ver [fórmula, cobertura y validación](reading-genres.md).

## API

Todas las rutas requieren el token de la sesión existente. «Público» significa
visible para toda la comunidad autenticada, sin controles adicionales de privacidad.

| Método | Ruta bajo `/api` | Uso |
| --- | --- | --- |
| GET | `/profiles/preference-catalogs` | Catálogos activos separados: `genres`, `tropes` |
| GET | `/profiles/me/literary-preferences` | Preferencias y biografía propias |
| PATCH | `/profiles/me/literary-preferences` | Actualización personal parcial |
| GET | `/profiles/{profile_id}` | Proyección comunitaria de un perfil personal |

El PATCH no admite identificadores de propietario: siempre toma la cuenta desde
la sesión. Rechaza campos extra, identificadores desconocidos o del catálogo
equivocado, duplicados y más de cinco géneros. Bloquea la fila de cuenta al guardar
para serializar ediciones simultáneas y hace una única transacción; cualquier fallo
revierte tanto biografía como selecciones.

```json
{
  "biography": "Me gustan los mundos imaginarios.",
  "genre_ids": ["fantasia", "romance"],
  "trope_ids": ["magia", "romance-lento"]
}
```

Un campo **omitido** permanece sin cambios. `genre_ids: []` y `trope_ids: []`
eliminan exclusivamente su selección. No admiten `null`. `biography: null`, una
cadena vacía o de espacios borran la biografía. La edición personal permite 200
caracteres Unicode, sin truncar automáticamente valores anteriores.

La edición administrativa existente conserva su contrato y límite de 1000
caracteres. No se cambia ni se evade su autorización. Si un administrador guardó
una biografía de más de 200, se muestra completa; el propietario debe acortarla
para guardar una nueva biografía, pero puede guardar gustos sin modificarla.

La consulta comunitaria usa el ID de `app.perfiles`, no el de `app.usuarios`.
Devuelve únicamente `id`, `display_name`, `avatar_url`, `biography`, `genres` y
`tropes`. No devuelve correo, roles, membresías, estadísticas, biblioteca, análisis
ni otros campos privados. Los perfiles inexistentes o de organización responden
404: este MVP presenta gustos de cuentas personales.

## Frontend

La ruta `/profile` conserva biblioteca, actividad, análisis, cuenta y personalización.
Las tarjetas mantienen su diseño y utilizan las variables de los seis temas.
«Sobre mí» tiene contador, guardar, cancelar, estado de guardado y error. «Mis gustos
literarios» permite editar por separado géneros y tropos, mostrando las selecciones
guardadas como etiquetas y estados vacíos explícitos.

La ruta `/profiles/:profileId` reutiliza `ProfileHeader`, `ProfilePersonalColumn`,
`ProfileAboutCard` y `ProfileTastesCard`, sin edición ni secciones privadas.
El perfil propio incluye «Ver mi perfil comunitario» para obtener la dirección
compartible. No se añade todavía un directorio de personas ni se cambian los enlaces
del mural. El almacenamiento es PostgreSQL; localStorage solo sigue usándose para
el token y el sistema de temas preexistentes, no para las preferencias.

`profileService` centraliza las consultas y `useLiteraryPreferences` administra
carga, errores, reintentos y guardado. La biografía actualizada también se refleja
en Mi cuenta sin modificar el contexto o el mecanismo de autenticación.

## Verificación

- 10 pruebas nuevas con PostgreSQL: catálogos, round trip, proyección pública,
  campos omitidos/vacíos, biografía, permisos, catálogos inactivos, restricciones de
  base de datos y rollback ante fallo de commit. Cada prueba revierte sus cuentas.
- 13 pruebas existentes de roles e interacciones: aprobadas, incluida edición
  administrativa, biblioteca e interacciones sociales.
- Prueba de navegador con una API temporal sobre una transacción reversible:
  guardar/cancelar, contador 201/200 y bloqueo de guardado, fallo de conexión y
  reintento, fallo de catálogo y reintento, máximo cinco géneros, selección separada
  de tropos, persistencia al recargar, vista pública de solo lectura y 404.
- Seis temas en 1440, 900, 390 y 320 px (24 combinaciones), incluidos los editores
  abiertos sin desbordamiento horizontal. Sin excepciones JavaScript.
- Se detuvo la API temporal y se revirtieron todos sus datos. La API normal local
  se reinició para servir las nuevas rutas. ESLint y compilación de producción.

Ejecutar los tests únicamente con una configuración de desarrollo o prueba:

```powershell
cd apps/backend
.\.venv\Scripts\python.exe -m unittest tests.test_literary_preferences tests.test_user_roles tests.test_post_interactions -v
```

## Archivos de esta implementación

Backend creados:

- `apps/backend/app/modules/users/preference_models.py`
- `apps/backend/app/modules/users/preference_schemas.py`
- `apps/backend/app/modules/users/preferences_router.py`
- `apps/backend/migrations/versions/0043_literary_preferences.py`
- `apps/backend/tests/test_literary_preferences.py`

Backend modificados: `apps/backend/app/main.py` y `apps/backend/migrations/env.py`.
Los endpoints y formularios administrativos no se modificaron.

Frontend creados:

- `apps/web/src/services/profileService.js`
- `apps/web/src/hooks/useLiteraryPreferences.js`
- `apps/web/src/components/ProfileAboutCard.jsx`
- `apps/web/src/components/ProfileTastesCard.jsx`
- `apps/web/src/components/ProfilePreferences.css`
- `apps/web/src/pages/CommunityProfilePage.jsx`

Frontend modificados:

- `apps/web/src/App.jsx`
- `apps/web/src/pages/ProfilePage.jsx`
- `apps/web/src/pages/AccountPage.jsx`
- `apps/web/src/components/ProfileHeader.jsx`
- `apps/web/src/components/ProfilePersonalColumn.jsx`

Documentación creada: `docs/literary-preferences.md` (este documento).


## Genre catalog expansion

Migration `0045_genre_catalog_groups` adds ten genre groups and the requested catalog entries, retaining all existing IDs and saved preferences. The development catalog contains 70 entries (55 additions). Both genre editors share `GenreSelector`, with accent-insensitive search and a five-selection limit across filtered results. Downgrade removes grouping only, preserving additive records and user selections.


## Profile identity tab

`/profile` opens the `about` tab by default; explicit existing tab query links remain valid. `ProfileAboutSection` reuses the biography/genre editor, trope editor and private reading statistics in a responsive grid. Each editor PATCHes only its own field. The community route shares the public cards without edit controls; reading statistics remain private because the existing public API does not authorize them. No preferred spicy level is shown without persistence. The complementary reading challenge stays in the sidebar.
