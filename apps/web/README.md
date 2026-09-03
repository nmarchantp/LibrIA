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

La persistencia, autenticación real, catálogo externo, ETL e integración de IA se incorporarán en las siguientes etapas.
