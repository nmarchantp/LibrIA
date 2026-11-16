# Puntitos y controles del fondo m?gico

Se restauran las tres capas originales de puntitos en los nueve temas. Se eliminan las excepciones de las hojas de tema que ocultaban la capa grande, reduc?an casi a cero las dem?s o sustitu?an su densidad. Las part?culas se dibujan por encima de las ilustraciones de fondo y debajo del contenido.

El componente MagicalBackground vuelve a ser la fuente com?n de densidad, opacidad y tiempos: fino 0,28/50 s, medio 0,40/100 s y grande 0,55/150 s. Usa el color principal del tema.

- Fondo m?gico desactivado: el componente se desmonta.
- Fondo m?gico activado: se muestran las tres capas.
- Mover los puntitos desactivado: las capas siguen visibles, con movimiento pausado.
- Mover los puntitos activado: se reanuda la animaci?n compartida.

Se mantienen las claves de almacenamiento, las preferencias guardadas, su sincronizaci?n y los valores predeterminados existentes. No se modifican login ni registro. Las indicaciones hist?ricas de otros informes sobre capas ocultas quedan reemplazadas por este comportamiento.

La suite magical-background comprueba en los nueve temas las tres capas visibles, pausa/reanudaci?n desde los controles reales y persistencia. Tambi?n prueba doce rutas autenticadas, teclado, cuatro tama?os, movimiento reducido seg?n la pol?tica expl?cita existente y exclusi?n del login. ESLint sin errores (cinco advertencias existentes); compilaci?n correcta con advertencia existente de tama?o de bundle.
