# Base de datos local y pgAdmin

LibrIA usa PostgreSQL. pgAdmin 4 está instalado en este equipo junto con PostgreSQL 17. Este administrador permite explorar tablas, consultar registros y generar un diagrama de relaciones.

## Aplicar el esquema

En otro computador, ejecutar primero `setup.cmd` desde la raíz. Si el entorno ya existe, desde `apps/backend`:

```powershell
.\.venv\Scripts\python.exe -m alembic upgrade head
.\.venv\Scripts\python.exe -m alembic current
```

La revisión de esta primera etapa es `0003_catalogo_lecturas`. La migración 0002 renombra las tablas originales y conserva sus registros. La 0003 agrega catálogo y lecturas, y elimina una restricción de correo redundante manteniendo el índice único. Reiniciar el backend si estaba abierto al aplicar el cambio de nombres.

## Conectar pgAdmin

1. Abrir **pgAdmin 4** desde el menú Inicio de Windows.
2. En **Servers**, usar **Register → Server** y asignar el nombre `LibrIA local`.
3. En **Connection**, ingresar los valores de `DATABASE_URL` de `apps/backend/.env`: Host, Port, Maintenance database, Username y Password. La configuración local habitual es host `localhost`, puerto `5432`, base `libria` y usuario `libria`; prevalecen siempre los valores del archivo local. No compartir la contraseña ni incorporarla a este documento.
4. Guardar y abrir **Databases → libria → Schemas → app → Tables**. Si el servidor ya estaba registrado, actualizar el árbol con **Refresh**.
5. Sobre una tabla, abrir **View/Edit Data → All Rows** para consultar sus registros. Las tablas nuevas comienzan vacías.
6. Para ver relaciones, usar **ERD For Database** desde el menú contextual de la base, o **ERD For Schema** si la versión instalada ofrece esa opción. Seleccionar el esquema `app` cuando corresponda. El diagrama se construye a partir de las claves foráneas reales.

Tablas de esta etapa: `usuarios`, `cuentas_autenticacion`, `autores`, `obras`, `obras_autores`, `ediciones`, `fuentes_catalogo`, `entradas_biblioteca`, `lecturas` y `progreso_lectura`. Los esquemas `analytics` y `ai` todavía no tienen tablas.

## Consultas de lectura

En **Query Tool**, listar las tablas:

```sql
SELECT table_name
FROM information_schema.tables
WHERE table_schema = 'app'
ORDER BY table_name;
```

Consultar los intentos de lectura y su porcentaje calculado:

```sql
SELECT l.id, u.display_name AS lector, o.title AS obra,
       e.language AS idioma, e.edition_label AS edicion,
       l.status AS estado, l.current_page AS pagina_actual,
       l.total_pages AS paginas_totales,
       round(100.0 * l.current_page / nullif(l.total_pages, 0), 2) AS porcentaje,
       l.abandonment_reason AS motivo_abandono
FROM app.lecturas l
JOIN app.entradas_biblioteca b ON b.id = l.library_entry_id
JOIN app.usuarios u ON u.id = b.user_id
JOIN app.obras o ON o.id = l.work_id
JOIN app.ediciones e ON e.id = l.edition_id
ORDER BY l.created_at DESC;
```

## Alcance y verificación

Esta etapa implementa el esquema y los modelos ORM. La interfaz todavía usa su catálogo simulado: faltan endpoints y servicios de catálogo y biblioteca, importación externa y conexión del frontend. La copia del total de páginas al iniciar, las transiciones de estado y el registro automático de progreso se implementarán en esos servicios. Las restricciones de base ya impiden páginas inválidas, estados incoherentes, abandono sin motivo y ediciones de otra obra.

Las pruebas usan transacciones revertidas y no dejan datos de ejemplo:

```powershell
# Desde apps/backend
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
.\.venv\Scripts\python.exe -m alembic check
```

No ejecutar downgrade sobre datos que se quieran conservar: la reversión de la etapa de catálogo elimina sus tablas.
