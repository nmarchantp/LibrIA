# Registro progresivo e identidad literaria

## Resultado funcional

El registro empieza con una sola tarjeta «Crea tu cuenta», centrada. Tras crear la cuenta, la misma tarjeta se desplaza a la izquierda durante 650 ms, muestra los datos registrados y aparece la pregunta de géneros a la derecha. En escritorio el resumen acompaña las preguntas siguientes; en el último paso se oculta para ampliar el resultado. En pantallas de hasta 800 px se muestra únicamente el formulario del paso actual, con transiciones entre preguntas. Todo ocurre en `/register`, sobre el fondo de biblioteca existente y sin volver a crear la cuenta.

Los cambios de pregunta se animan durante 380 ms, invierten la dirección al retroceder y respetan movimiento reducido. Solo la cuenta y la pregunta actual son accesibles; los otros paneles son `inert`. Todas las tarjetas del registro tienen 708 px de alto, con los botones al pie. En móvil se compactan los espacios y se reduce la cantidad de opciones y resultados por página para conservar esa altura. El fondo permanece fijo al viewport. Los géneros tienen búsqueda y páginas de 18 opciones; los elementos narrativos reutilizan ese mismo selector con 15 opciones por página. La selección se mantiene entre páginas. Los resultados de búsqueda muestran dos libros por página en escritorio y uno en móvil. Sus filas tienen ancho limitado, títulos de hasta dos líneas y autores truncados visualmente; los controles permanecen dentro de la tarjeta de 708 px. Los favoritos seleccionados aparecen con portadas grandes superpuestas bajo la cuenta, separados del buscador, y cada portada tiene su propio botón para quitarla. En móvil la colección se muestra después de los resultados y la cuenta sigue compacta. Se reutiliza BookCover para manejar portadas disponibles y su alternativa cuando falta una imagen. Los controles no heredan las dimensiones del footer general.

La primera pulsación de Siguiente crea la cuenta utilizando el registro actual. Un bloqueo sincrónico impide envíos repetidos; después se desmontan las contraseñas. Retroceder muestra los datos de la cuenta ya creada, sin volver a registrar ni conservar credenciales. La unicidad del correo sigue siendo la protección transaccional ante reintentos cuya respuesta se pierde.

Las respuestas y el paso se guardan al navegar y mediante guardado progresivo. Las escrituras del navegador se serializan y se descartan si cambia la sesión. Una recarga reanuda el cuestionario. Las ediciones posteriores se guardan como borrador y solo regeneran la interpretación al confirmar. La finalización es independiente del éxito de Gemini.

## Auditoría y componentes reutilizados

| Área existente | Integración |
| --- | --- |
| React, AuthContext, SessionGate y AuthJourney | Se conserva la sesión, navegación de acceso y escena original. Solo cambia el contenido de la tarjeta durante las preguntas. |
| Registro y AuthRepository | Se inicializa onboarding únicamente en cuentas nuevas; no hay proceso de alta alternativo. |
| Google vinculado y verificado | Continúa siendo un mecanismo de ingreso de cuentas vinculadas. Un lector pendiente entra al mismo wizard sin contraseña. No se agregó alta automática por Google porque el servicio actual la rechaza. |
| Preferencias, Genre, Trope, FavoriteGenre y FavoriteTrope | El cuestionario consulta las taxonomías activas y sincroniza los gustos declarados al finalizar. |
| Catálogo canónico y buscador local | Favoritos con UUID de obra canónica; se deduplican también las redirecciones. No se importan ediciones ni se crean lecturas. |
| ThemeContext y ThemeSelector | Temas gratuitos `lavanda` y `dark` en el wizard; todos los universos actuales siguen disponibles en Configuración. La preferencia se restaura desde la cuenta al ingresar. |
| `ia.jobs`, `ia.analyses`, `ia.evidence`, ledger y worker Gemini | Se extienden con el tipo de trabajo `onboarding`; se reutilizan proveedor, validación estructurada, presupuestos, límites, leases, reintentos y backoff. |
| Mis análisis y Sobre mí | Presentación del ADN inicial, origen declarado, fecha, actualización y consentimiento explícito. La proyección pública excluye respuestas, favoritos, trabajos y recomendaciones. |
| Recuperación y ciclo de vida de cuentas | Las reglas de recuperación permanecen. Al anonimizar se limpian las preferencias nuevas y sus asociaciones de favoritos. |

La revisión partió de la migración `0097_literary_characters`. No existía un onboarding anterior que pudiera convertirse visualmente, por lo que fue necesario implementar su persistencia sobre estos componentes existentes.

## Persistencia y permisos

`app.usuarios.onboarding` contiene versión, obligación, estado, paso, respuestas normalizadas, fechas, consentimiento, huella de evidencia y referencia al trabajo vigente. El estado del cuestionario es `pending`, `in_progress` o `completed`. El estado de IA se lee directamente de la cola: `pending`, `processing`, `completed` o `failed`.

`app.usuarios.visual_theme` guarda el universo seleccionado. `app.onboarding_favoritos` conserva la relación con obras mediante claves foráneas, clave compuesta e índice de obra. No hay una columna por preferencia.

Los usuarios anteriores reciben `{}` y no quedan bloqueados. Solo se exige completar a nuevos lectores con la marca explícita de obligatoriedad. Otros roles siguen utilizando sus permisos actuales. El backend controla el acceso desde la dependencia común de autenticación; siguen disponibles autenticación, recuperación/cuenta, roles, onboarding, catálogos de preferencias y consulta bibliográfica. SessionGate incorpora la misma regla al navegar.

Endpoints añadidos al router de perfiles:

| Método | Ruta, bajo `/api` | Uso |
| --- | --- | --- |
| GET | `/profiles/me/onboarding` | Estado, opciones, respuestas, ADN y recomendaciones del titular. |
| PATCH | `/profiles/me/onboarding` | Guardado parcial, borradores o confirmación. |
| PATCH | `/profiles/me/onboarding/sharing` | Consentimiento independiente para publicar/ocultar ADN. |
| PATCH | `/profiles/me/onboarding/theme` | Preferencia visual de cuenta. |
| GET | `/profiles/{profile_id}/literary-dna` | Proyección pública restringida, con consentimiento y acceso al perfil. |

Los contratos de usuario de registro, login, renovación y `/auth/me` incorporan `onboarding_required` y `visual_theme`.

## Gemini, recomendaciones y evolución

«Confirmar y finalizar» guarda la finalización y ejecuta Gemini dentro de esa misma petición HTTP. La respuesta incluye el ADN y las recomendaciones generadas; no requiere ETL, scheduler ni worker en ejecución. Se reutiliza un trabajo persistente exclusivamente para la idempotencia, el control de concurrencia, la contabilidad y los reintentos. La ejecución se limita al titular y a la versión exacta que confirmó: nunca consume trabajos ajenos. Si otro proceso ya está generando esa versión, se comparte su resultado con una espera acotada. No se repite una llamada cuando la interpretación ya está disponible.

El timeout interactivo es `ONBOARDING_AI_TIMEOUT_SECONDS`, de 45 segundos por defecto. Se conservan las autorizaciones de Gemini, el ledger, los límites y el backoff; el modo interactivo no espera turnos ni agrega la pausa artificial de espaciado del worker. Si falta configuración, el proveedor está ocupado, se agota el presupuesto o falla Gemini, la cuenta permanece habilitada y se devuelven recomendaciones deterministas del catálogo. Los análisis individuales y sus demoras no cambian.

Durante la petición, el botón muestra «Consultando Gemini…». Al responder se presentan el perfil y las primeras recomendaciones en la misma tarjeta, identificando si su origen es Gemini o el fallback del catálogo. La interpretación ampliada se puede desplegar y los libros se recorren en un carrusel compacto. Los trabajos pendientes obsoletos se cancelan; volver a preferencias anteriores reutiliza su trabajo sin reiniciar el presupuesto de intentos. Antes de publicar se vuelven a comprobar la cuenta, la evidencia vigente y el lease.

El contexto solo contiene géneros, tropos, emociones, hábito, metadatos disponibles de favoritos y candidatos reales. No incluye nombre, correo, contraseñas ni tokens. Un contrato Pydantic valida el ADN y las recomendaciones. Las etiquetas de afinidad deben pertenecer a las preferencias declaradas; los UUID recomendados deben pertenecer a los candidatos enviados y ser únicos. Los títulos, autores y portadas que se muestran provienen del catálogo, nunca de Gemini.

Se reutiliza la recuperación de candidatos del worker. El ranking prioriza coincidencias de género y excluye favoritos y obras de la biblioteca; si faltan coincidencias exactas, amplía el conjunto con obras reales del catálogo, identificadas como opciones de exploración. La IA recibe hasta veinte candidatos y el prompt exige entre cinco y diez recomendaciones distintas. El esquema y la validación del servidor exigen al menos `min(5, candidatos disponibles)`: una respuesta de una sola obra se rechaza si había cinco candidatos. Si el catálogo elegible completo tiene menos de cinco, se utilizan todos los disponibles sin inventar ni repetir obras. El fallback muestra hasta diez obras y descarta resultados históricos de IA que ya no cumplan el mínimo frente al catálogo actual, sin repetir consultas de pago al abrir la pantalla. Añadir una recomendación utiliza `LibraryContext.addBook` y su comando idempotente habitual.

La interfaz consulta el estado automáticamente durante aproximadamente un minuto. Cuando hay resultados no muestra mensajes de búsqueda ni un botón de actualización. Ingresar siempre está disponible al terminar el cuestionario. Se conserva la interpretación anterior mientras llega una nueva.

El ADN de onboarding representa preferencias **declaradas**. El ADN continuo existente conserva la evidencia de lecturas, reseñas, reflexiones, notas y correcciones, con sus políticas actuales. No se fabrican categorías ausentes, los favoritos pendientes no generan eventos de lectura ni se utilizan como actividad observada. Las correcciones y evidencia observada siguen siendo responsabilidad del proceso existente; editar las preferencias actualiza el punto de partida declarado. Los análisis individuales mantienen su scheduler y sus reglas de consolidación.

## Validación y reproducción

Se validó toda la cadena de migraciones en PostgreSQL 17 temporal, incluida la migración de una cuenta real de prueba creada antes de 0098: se conservó y su onboarding permaneció opcional. No se migró ninguna base de producción o de desarrollo existente.

El ejecutor `apps/backend/scripts/test_onboarding.py` exige una base loopback llamada `libria_nightly_test_*`, excluye `.env` local y habilita las suites optativas con proveedores simulados. Incluye onboarding, registro, Google, cuenta/recuperación, preferencias, géneros, proveedor Gemini, worker, presupuestos, reintentos y análisis nocturnos/individuales. Las suites originales truncan datos: utilizar exclusivamente una base desechable migrada a head.

```powershell
# Desde apps/backend, con DATABASE_URL apuntando a esa base aislada:
.\.venv\Scripts\python.exe -m alembic upgrade head
.\.venv\Scripts\python.exe -m scripts.test_onboarding
```

En frontend:

```powershell
npm run lint
npm run build
npm run test:auth-journey
npm run test:themes
node --experimental-websocket tests/theme-mode.mjs
# API de prueba en 8012, Vite en 5173 y Chrome CDP en 9224:
$env:LIBRIA_LIVE_ONBOARDING_TEST='1'
npm run test:onboarding-live
```

El test real usa un contexto de navegador aislado y redirige las peticiones exclusivamente a la API temporal. Verifica registro, permisos de backend, recarga y restauración del paso, cinco preguntas, favoritos vacíos, finalización sin Gemini, biblioteca sin alteraciones y restauración del tema de cuenta. La prueba de AuthJourney cubre además las ocho etapas sin cambio de URL, retroceso, una sola creación de cuenta, transiciones, movimiento reducido y siete resoluciones. Las pruebas de temas cubren los 24 universos existentes.

Lint termina sin errores, con siete advertencias anteriores de Fast Refresh. La compilación termina correctamente y conserva la advertencia de tamaño del bundle. La suite aislada aprobó **202 pruebas sin omisiones** en 93,932 segundos, incluidas 17 de onboarding y siete nuevas de ejecución directa. Estas últimas verifican la respuesta con recomendaciones sin ETL ni worker, la idempotencia, la selección exclusiva del trabajo del titular, el timeout, el backoff, los IDs falsos y la indisponibilidad del proveedor. Pasaron también las pruebas de navegador, incluidas «Consultando Gemini…» y la presentación de los resultados en la misma vista. Se realizó además una única consulta real a Gemini con preferencias ficticias y tres obras de dominio público en una base temporal: devolvió ADN y tres recomendaciones válidas, con una llamada registrada y cero ejecuciones de ETL. No se enviaron datos de la cuenta del usuario ni se alteraron autorizaciones de pago. Durante la exploración, ejecutar pruebas antiguas directamente con `.env` local produjo incompatibilidades de fixtures frente a los flags de catálogo y versiones de prompts; se reprodujeron sus contratos en el ejecutor aislado, sin cambiar las reglas funcionales. La ejecución global inicial se interrumpió por transacciones abiertas de esas pruebas; no se presenta como una ejecución completa del repositorio.

Las capturas del flujo real están en `artifacts/onboarding-wizard/`.

## Archivos principales

Nuevos: `RegistrationWizard.jsx/.css`, `InitialLiteraryDNA.jsx`, `PublicLiteraryDNA.jsx`, `onboardingService.js`, `users/onboarding.py`, migración `0098_literary_onboarding.py`, `tests/test_onboarding.py`, `tests/onboarding_support.py`, `scripts/test_onboarding.py`, `tests/onboarding-live.mjs` y este documento.

Extendidos en backend: `analytics/gemini_worker.py`, `analytics/models.py`; `auth/dependencies.py`, `repository.py`, `router.py`, `service.py`; `users/models.py`, `schemas.py`, `preference_models.py`, `preferences_router.py`, `account_lifecycle.py`.

Extendidos en frontend: `RegisterPage`, `SessionGate`, `ThemeSelector`, `AuthContext`, `LibraryContext`, `ThemeContext`, `ProfilePage`, `CommunityProfilePage`, `SettingsPage` y `package.json`. Se actualizaron los fixtures de preferencias/géneros/worker para representar cuentas existentes, AuthJourney para recorrer el wizard y las medidas de temas para contemplar la densidad de escritorio existente.

## Despliegue y límites

1. Respaldar la base y aplicar 0098 con el procedimiento Alembic habitual antes de iniciar esta versión de la API.
2. Construir y distribuir API y frontend; reiniciar el worker para que reconozca `onboarding`.
3. Conservar las autorizaciones y configuración actuales de Gemini. No se habilitaron consultas de pago ni se cambiaron sus presupuestos. El onboarding consulta directamente a Gemini aunque el worker esté apagado, siempre que el proveedor esté configurado y autorizado. El worker solo es necesario para recuperar reintentos diferidos; el ingreso no depende de él.
4. Comprobar registro, reanudación, tema, consentimiento y un trabajo de prueba en el entorno de despliegue.

La migración es aditiva y no altera migraciones anteriores. Su downgrade se rechaza para evitar borrar preferencias: una reversión de esquema requiere un procedimiento explícito con respaldo. La selección inicial está limitada al catálogo local y al máximo de candidatos del motor existente; la calidad depende de sus metadatos y de las categorías disponibles. La velocidad de respuesta depende de Gemini y se acota con el timeout indicado. Las pruebas automatizadas usan proveedores simulados; la prueba remota fue independiente y utilizó exclusivamente datos de prueba. El alta autónoma por Google no existe en la arquitectura actual y no fue introducida por este cambio.

No se realizó commit ni despliegue.

## Guía del primer ingreso

La primera finalización del cuestionario de un lector crea `onboarding.guide` en estado `analysis`. Ingresar desde el registro lleva a `/profile?tab=analysis`; si cierra la sesión antes de entrar, el siguiente ingreso retoma ese paso. Los registros completados antes de esta función no se interrumpen automáticamente. Pueden iniciar o repetir la guía desde «Conocer LibrIAverse» en Mis análisis.

El recorrido muestra el resumen del cuestionario y acompaña ocho pasos: análisis, búsqueda, elección de resultado, incorporación del libro, biblioteca del perfil, estado de lectura, progreso y cuaderno. La búsqueda y el alta se realizan con las pantallas y comandos existentes; la guía no crea libros de ejemplo ni cambia estados o páginas. Solo avanza al confirmar una búsqueda con resultados y una incorporación exitosa. Las lecturas ya existentes también pueden utilizarse.

`PATCH /profiles/me/onboarding/guide` guarda el paso y la referencia del libro para el titular autenticado. Requiere un cuestionario completado, conserva el progreso entre ingresos y permite omitir o terminar sin reiniciar la guía al reenviar el cuestionario. No requiere migración porque utiliza el JSON de onboarding existente. «Omitir guía» deja la navegación disponible y el recorrido puede reiniciarse manualmente.

Validación: `npm run test:welcome-guide` recorre las pantallas reales de catálogo, ficha, biblioteca y lectura usando peticiones aisladas; verifica el resumen, el alta como Pendiente, la reanudación, móvil, finalización y omisión. `test:auth-journey` verifica que el primer ingreso después del registro vaya a Mis análisis. Las pruebas de backend verifican persistencia y protección de la guía, sin llamadas a Gemini.

Los favoritos conservan sus portadas durante la elección del tema, la confirmación y el resultado. Al finalizar se guardan automáticamente en la biblioteca como Pendiente, dentro de la transacción del cuestionario. Se conserva cualquier estado, progreso o archivo preexistente de la misma obra canónica. Abrir un resultado anterior sincroniza sus favoritos mediante `POST /profiles/me/onboarding/library`; repetir la operación no duplica entradas ni reinicia lecturas. Las obras se guardan sin inventar ediciones o páginas. El contexto de biblioteca se recarga al terminar la sincronización.

El último paso oculta la tarjeta de cuenta y utiliza el ancho disponible. Las recomendaciones se presentan en un carrusel compacto con autor, motivo y acción para añadir el libro a la biblioteca. Avanza cada cinco segundos, continúa con el cursor encima y ofrece pausa y reproducción explícitas, incluso si las animaciones generales están desactivadas. Mi ADN literario identifica esta primera selección como resultado del cuestionario y reserva los análisis profundos de biblioteca completa y por lectura para una etapa posterior.
