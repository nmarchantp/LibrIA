# ADN Lector 2.0

## Arquitectura y alcance

El ETL existente (`analytics/etl.py` y `recommendation_profiles.py`) ya consolida reseñas, valoraciones, reflexiones, cuadernos, notas y teorías en `ia.reader_profile_versions`. `gemini_context.py` crea unidades de evidencia trazables. El worker procesa el ADN antes de generar recomendaciones y reutiliza `ia.reader_dna` mediante la huella de evidencia, modelo y versión del prompt.

El evolutivo amplía ese mismo ADN global. No cambia la elegibilidad del ETL, no incorpora otro motor ni modifica el contrato del análisis individual por libro. Los libros disponibles siguen siendo los elegibles del ETL existente: no se añaden nuevas fuentes de abandono al perfil global en este cambio.

## Generación y validación

`ReaderDnaInterpretation` conserva obligatoriamente las siete dimensiones y añade `schema_version=2`, `reader_essence` y `evolution`. Los contratos antiguos siguen siendo legibles y conservan su presentación. `DNA_SYSTEM` establece profundidad, segunda persona, jerarquía de evidencia y prohibición de atribuciones psicológicas, diagnósticos, experiencias inventadas y características sensibles.

La esencia suficiente exige un arquetipo, 3–5 rasgos literarios y 120–180 palabras en 2–3 párrafos. Se valida la presencia de segunda persona, el formato, las referencias y el nivel máximo de evidencia. El juicio semántico sigue correspondiendo a Gemini: una referencia válida no prueba por sí sola que una interpretación sea verdadera. Los textos del usuario se tratan como datos no confiables, nunca como instrucciones.

El límite determinista de evidencia utiliza solo valores de textos personales; excluye metadatos, números y claves JSON. Un registro expresivo requiere al menos 12 palabras. Para habilitar una esencia completa hacen falta al menos dos obras con textos expresivos y 180 palabras acumuladas. Una única obra queda como máximo en `partial`. Sin texto expresivo, el resultado es `insufficient`, sin arquetipo, narrativa profunda ni rasgos. Gemini debe reducir el nivel cuando el texto sea solo argumento, teoría o no exprese preferencias; estos umbrales son un máximo estructural, no una clasificación automática de su significado.

Con evidencia parcial solo se muestran tendencias preliminares, sin identidad completa. Las citas de una esencia suficiente deben incluir textos expresivos de al menos dos obras. No se aceptan dimensiones omitidas ni evidencias inventadas.

## Evolución e historial

Se reutilizan los registros persistentes de `ia.reader_dna` y `ia.analyses`, sin tabla nueva. Cada versión conserva identificador, titular, fecha, modelo, prompt, esquema, contenido, nivel de evidencia y referencia al perfil fuente. `ia.evidence` mantiene la procedencia de los hallazgos. No se añaden copias de reseñas o textos fuente.

La comparación es combinada: Gemini interpreta diferencias semánticas entre las siete dimensiones; el backend valida la referencia anterior, las citas de ambos resultados y la presencia de evidencia personal nueva o modificada. Para calcular esa novedad se comparan huellas de textos y valoraciones, excluyendo metadatos bibliográficos. Las correcciones de título, cambios de redacción o un nuevo nombre de arquetipo por sí solos no autorizan un cambio significativo. El prompt prohíbe interpretar ausencia de menciones como pérdida de interés.

Solo dos esencias suficientes permiten comparar evolución. Cada hallazgo emergente o cambiante debe citar evidencia personal nueva/modificada y evidencia de la versión de referencia. Sin cambios respaldados se indica estabilidad; sin versiones comparables se indica que la evolución está en construcción. Las comparaciones históricas seleccionadas por el usuario muestran los hallazgos guardados de ambas versiones; no ejecutan otra interpretación de IA ni etiquetan diferencias de texto como evolución.

La restricción existente `(owner_id,source_hash,model,prompt_version)` y la caché impiden repetir versiones idénticas. Un bloqueo por titular serializa la generación del ADN para no crear ramas de referencia entre workers. Antes de publicar se verifica que el perfil fuente siga siendo vigente. Una revisión del modelo/prompt puede crear una versión técnica relevante, sin marcarla automáticamente como cambio de preferencias.

`GET /api/me/ai/profile/history` utiliza una secuencia cronológica global, no el número que se reiniciaba por tarea. Devuelve solo resultados válidos de ADN y versiones legadas del perfil; excluye resultados de recomendaciones que duplicaban el ADN. Conserva paginación mediante `before` y filtros por titular. Consultar el perfil/historial no genera trabajos ni llama a Gemini.

## Privacidad y fallos

El historial y la esencia global solo están disponibles por las rutas privadas del usuario autenticado, con `Cache-Control: no-store`. La proyección pública del cuestionario permanece separada y no expone `reader_essence`, evolución ni historial. Regenerar no modifica los permisos ni activa compartir.

La lectura del perfil conserva el último ADN válido si cambia la evidencia, el modelo o el prompt, o si la siguiente generación falla. La solicitud de actualización distingue esa lectura de respaldo del resultado vigente para poder encolar la actualización. Resultados incompletos no sustituyen los válidos. Los límites de contexto y presupuesto existentes siguen vigentes: un perfil que no quepa puede fallar de manera controlada; no se recorta evidencia silenciosamente ni se amplían límites de gasto.

## Llamadas y consumo

- Un fragmento que cabe con esquema y referencia: una sola llamada global, ahora con esencia y evolución.
- Varios fragmentos o contexto directo demasiado grande: procesamiento/reducciones existentes más una síntesis final necesaria para relacionar dimensiones. Esa síntesis usa los resúmenes y una proyección de la versión anterior, sin volver a enviar su narrativa personal completa.
- Se reutilizan los fragmentos y las síntesis válidas por caché; el ADN ya persistido evita repetir la generación con la misma identidad.
- Las recomendaciones reciben las siete dimensiones anteriores, sin reenviarles innecesariamente la esencia o el historial.
- Cada llamada sigue registrada en `ia.call_ledger`, con reservas, límites, reintentos y contabilidad existentes. No se realizan llamadas desde las consultas del perfil ni desde la comparación visual.
- La respuesta global es más larga; puede consumir más tokens aunque el número de llamadas de un perfil pequeño no cambie. Las pruebas utilizan proveedores simulados y no miden calidad ni coste real de Gemini.

## Interfaz y archivos

Dentro del detalle existente se muestran, en orden: `ReaderEssence`, las siete dimensiones de `DnaProfileSections` y `ReaderDnaEvolution`. Se añadieron línea de tiempo, detalle de versiones y comparación de dimensiones. Los estados antiguo, parcial e insuficiente tienen mensajes específicos. Se usan variables del tema y comparación en una columna en móvil, sin puntuaciones ni gráficos inventados.

Archivos de backend: `app/core/config.py`, `analytics/gemini_contracts.py`, `gemini_prompts.py`, `gemini_worker.py`, `reader_dna.py`, `adaptive_router.py`.

Archivos de frontend: `ReaderDna.jsx`, `ReaderDna.css`, `ReaderEssence.jsx`, `ReaderDnaEvolution.jsx`. `DnaProfileSections` se reutiliza sin alterar sus siete dimensiones.

Pruebas: `tests/test_reader_dna_v2.py`, adaptación del proveedor simulado de `test_stage5_gemini_worker.py`, ejecutor `scripts/test_reader_dna_v2.py`, fixture web `tests/fixtures/reader-dna-v2.{html,jsx}` y prueba de navegador `tests/reader-dna-v2.mjs`.

## Activación y migraciones

No hay migraciones nuevas ni pendientes: los campos se guardan en JSONB y el historial utiliza las tablas existentes. No se ejecutaron migraciones contra desarrollo o producción; las pruebas aplican las migraciones ya existentes únicamente a una base temporal desechable.

El prompt predeterminado pasa a `reader-dna-v2.1-deep-second-history-es`. Si un despliegue define `READER_DNA_PROMPT_VERSION`, debe actualizarlo a ese valor; después se reinician API y worker mediante el procedimiento habitual. La nueva esencia aparecerá en la siguiente generación global autorizada; no se fuerza una regeneración masiva ni se llama a Gemini al abrir el perfil. Las versiones previas continúan visibles hasta que exista una nueva válida.

### Ajustes comprobados con la solicitud real del 18 de noviembre

Se detectó un worker iniciado antes del despliegue y una cola extensa de análisis individuales. Los trabajos de ADN global solicitados ahora se priorizan entre tareas ya vencidas, conservando fechas de disponibilidad, locks, cuotas e intentos. El worker requiere reinicio para cargar el código y el prompt actuales.

La reducción comprueba el tamaño del sobre completo de la síntesis: instrucciones, esquema, resúmenes, evaluación y referencia anterior. Si no cabe, vuelve a reducir con caché y un máximo de cuatro rondas, sin ampliar el contexto configurado. Se compactó el esquema enviado al proveedor eliminando límites combinatorios de arrays y textos; Pydantic sigue aplicando esos límites localmente.

La primera respuesta real de síntesis que llegó a generarse terminó con `MAX_TOKENS` en el límite antiguo de 2048 tokens y se descartó. El contrato v2.1 añade `READER_DNA_OUTPUT_TOKEN_BUDGET=4096`, usado exclusivamente para la síntesis global; fragmentos y análisis individuales conservan `AI_OUTPUT_TOKEN_BUDGET`. Los límites mensuales, por trabajo y de intentos no se aumentan. Las siete dimensiones se solicitan concisas y la esencia cita 2–6 fuentes expresivas relevantes. Los intentos agotados del contrato anterior no se reinician; una nueva ejecución corresponde al contrato corregido y necesita la autorización del usuario.

## Validación

Desde `apps/backend`:

```powershell
.\.venv\Scripts\python.exe scripts/test_reader_dna_v2.py
```

El ejecutor crea y elimina un PostgreSQL temporal de loopback, excluye las sobrescrituras de `.env`, aplica las migraciones existentes y usa exclusivamente proveedores simulados. Las suites originales truncan sus datos: no deben ejecutarse con banderas de integración contra una base real.

Desde `apps/web`:

```powershell
node --experimental-websocket tests/reader-dna-v2.mjs
npx eslint src/components/ReaderDna.jsx src/components/ReaderEssence.jsx src/components/ReaderDnaEvolution.jsx
npm run build
```

La prueba web comprueba las siete dimensiones, historial bajo demanda, selección de versión anterior, comparación, estados legado/insuficiente y ausencia de desbordamiento en 1440/390 px, temas lavanda/oscuro. Capturas: `artifacts/reader-dna-v2/`.

Resultado de la verificación: 107 pruebas backend aprobadas (15 del ADN 2.0, 28 de optimización/contabilidad, 24 del worker, 32 de análisis nocturno/individual y 8 de consultas privadas). La prueba de navegador, ESLint de los componentes modificados y la compilación frontend también aprobaron. Se inspeccionó visualmente la captura móvil oscura. La compilación mantiene el aviso de tamaño del paquete principal; no hay errores de compilación. No se realizaron llamadas reales a Gemini.
