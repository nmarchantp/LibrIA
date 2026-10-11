# Acceso al ADN lector y a Recomendaciones IA

Ambas funciones personales requieren al menos diez obras distintas registradas en la biblioteca del titular. Cuentan los estados pendiente, leyendo, terminado y abandonado. Las relecturas no incrementan el total y las entradas archivadas no cuentan. Los libros de otras personas no cuentan. El acceso grupal de profesionales conserva sus reglas anteriores.

`GET /analytics/me/insights` y `GET /analytics/me/recommendations` devuelven `status=locked`, `book_count`, `minimum_books` y `missing_books` cuando el mínimo no se cumple, sin acceder a evidencia privada, resultados guardados ni Ollama. Sus pantallas explican el requisito y enlazan a Explorar. Los POST de interpretación y recomendaciones se rechazan con HTTP 403 y `detail.code=minimum_reader_books`, antes de consultar el modelo o el caché. `GET /analytics/access` informa también la elegibilidad personal.

Al incorporar la décima obra, ambas funciones quedan habilitadas sin esperar al ETL. Los indicadores y reflexiones del ADN siguen requiriendo una carga analítica para aparecer. Si la biblioteca vuelve a quedar por debajo del mínimo, los resultados anteriores dejan de estar accesibles desde estas rutas, aunque el historial guardado se conserva.

Pruebas: `python -m unittest discover -s tests -p test_reader_eligibility.py`. Cubren nueve frente a diez obras, aislamiento por titular, rechazo antes de usar modelo o caché y revocación al archivar.
