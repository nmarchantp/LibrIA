# Accesos demo por perfil

| Perfil exclusivo | Correo | Variable de contraseña |
| --- | --- | --- |
| Administrador | demo.admin@example.com | LIBRIA_DEMO_ADMIN_PASSWORD |
| Lector | demo.lector@example.com | LIBRIA_DEMO_LECTOR_PASSWORD |
| Influencer | demo.influencer@example.com | LIBRIA_DEMO_INFLUENCER_PASSWORD |
| Autor | demo.autor@example.com | LIBRIA_DEMO_AUTOR_PASSWORD |
| Librería | demo.libreria@example.com | LIBRIA_DEMO_LIBRERIA_PASSWORD |
| Editorial | demo.editorial@example.com | LIBRIA_DEMO_EDITORIAL_PASSWORD |

Las contraseñas se configuran en `apps/backend/.env`, excluido de Git. No se imprimen en consola ni se guardan en este documento. Si una variable individual está vacía, se usa `LIBRIA_DEMO_PASSWORD` por compatibilidad. En esta instalación se configuraron seis contraseñas distintas: la de administrador conserva su valor anterior y las otras cinco se generaron de forma aleatoria.

## Preparar o sincronizar las cuentas

Desde `apps/backend`, una vez aplicadas las migraciones autorizadas:

```powershell
./.venv/Scripts/python.exe -m scripts.seed_demo
```

Para sincronizar solamente una cuenta:

```powershell
./.venv/Scripts/python.exe -m scripts.seed_demo --role influencer
```

El comando solo admite el entorno `development`. Usa UUID y correos estables: no crea duplicados ni añade libros, reseñas o publicaciones. La sincronización fija los roles demo indicados y ajusta sus capacidades; no modifica personas ajenas al manifiesto. Las colisiones de correo con otra identidad se rechazan. No reactiva cuentas suspendidas ni borra sus datos. Si cambia una contraseña o un rol, invalida las sesiones antiguas de esa cuenta.

Las cuentas existentes de Librería y Editorial que eran lectores responsables de organizaciones pasan a sus tipos exclusivos conservando usuario, perfil, relaciones e historial. Las organizaciones históricas no se eliminan. No se crean organizaciones nuevas como sustituto del tipo de cuenta.

`seed_default_admin` y los comandos demo que usan credenciales administrativas respetan la contraseña específica del administrador. Los generadores de escenarios reciben también las contraseñas por perfil, sin restablecerlas a la común.

## Editorial

La migración aditiva `0093_editorial_account` permite `editorial` en las cuentas y solicitudes profesionales. El tipo ya existía en los contratos de publicaciones y eventos. Se incorporó a las etiquetas de navegación/cuentas y a la gestión administrativa, manteniendo la aprobación necesaria para cambios profesionales fuera de las cuentas ficticias. El registro público sigue creando lectores.

No se modifica el contenido histórico al ampliar las restricciones de base de datos. El downgrade falla si todavía existen cuentas o solicitudes editoriales, en lugar de convertirlas o eliminarlas.

## Validación

En PostgreSQL temporal aislado:

```powershell
docker compose -f compose.influencer-test.yaml build test
docker compose -f compose.influencer-test.yaml run --rm test python -m alembic upgrade head
docker compose -f compose.influencer-test.yaml run --rm test python -m unittest tests.test_demo_profile_accounts tests.test_default_admin_seed tests.test_account_management tests.test_influencer_access tests.test_generate_posts
```

Resultado: 59 pruebas correctas. Incluyen seis inicios de sesión con claves distintas, rol real, permisos de publicación y administración, claves incorrectas, repetibilidad, conservación de lecturas, rotación de claves e invalidación de sesiones, colisiones de identidad y compatibilidad del administrador. ESLint y compilación frontend correctos.

En la instalación local se respaldó `libria`, se aplicó 0093 y se sincronizaron las seis identidades. Se verificaron roles, estado activo y hashes de las seis contraseñas mediante consultas de solo lectura. Se conservaron los totales de usuarios, lecturas, reseñas, publicaciones y biblioteca. El respaldo está en `backups/before-demo-profiles-20261111-191722.dump`; existe además una copia anterior de `.env` con sufijo `.backup-demo-profiles-20261111-191722`.
