# LibrIA Web

Primera aplicación web del MVP de LibrIA. Está construida con React, JavaScript y Vite.

## Ejecución recomendada

Desde la raíz `Libria`, usa Docker para mantener el mismo entorno en todos los computadores:

```bash
docker compose up --build
```

Consulta el `README.md` de la raíz para conocer el flujo completo del equipo.

## Ejecución local alternativa

Solo si necesitas trabajar sin Docker, instala Node.js 20.19 o superior:

```bash
npm install
npm run dev
```

La aplicación queda disponible en `http://localhost:5173`.

## Verificaciones

```bash
npm run lint
npm run build
```

## Alcance actual

- Inicio y navegación adaptable para escritorio y móvil.
- Exploración y búsqueda local de libros.
- Biblioteca con filtros y actualización local del estado de lectura.
- Vista demostrativa de patrones y emociones.
- Rutas reales para login, registro, perfil, catálogo, detalle, biblioteca, experiencia e insights.
- Código separado en páginas, componentes, contexto, servicios y cliente API.
- Datos simulados aislados en `src/data.js` para reemplazarlos después por la API.

La autenticación está conectada a FastAPI. La persistencia de biblioteca, el catálogo externo, las publicaciones sociales, el ETL y la integración de IA siguen pendientes de conexión en la interfaz.

## Navegación social actual

- `/login` y `/register`: acceso a la cuenta; al autenticarse se abre el mural.
- `/`: mural con filtros Para ti, Reseñas, Lecturas y Comunidad. Las publicaciones son ficticias y están identificadas como ejemplos.
- `/books` y `/books/:id`: exploración y detalle del catálogo demostrativo.
- `/profile`: perfil de la cuenta autenticada, con biblioteca, análisis y actividad.
- `/profile?tab=library` y `/profile?tab=analysis`: enlaces directos a cada sección. Las rutas anteriores `/library` y `/insights` redirigen a estas secciones.
- `/reading/:id`: formulario de experiencia existente, todavía sin persistencia.

La sesión se recupera mediante `/api/auth/me` al recargar. Las pantallas interiores requieren autenticación; los errores de conexión permiten reintentar sin borrar la sesión, y el menú permite cerrarla. La biblioteca y los análisis siguen usando datos simulados. La actividad personal muestra un estado vacío hasta implementar publicaciones reales. Esta vista es el espacio propio autenticado; las rutas públicas de otros lectores, autores y organizaciones todavía no están implementadas.

La navegación usa una barra lateral en escritorio y un menú inferior en móvil. El mural aún no permite publicar, comentar ni seguir perfiles.
