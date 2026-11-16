# Revisi?n de proporciones de im?genes

Se revisan los nueve temas existentes, sin cambios de paleta, preferencias, navegaci?n ni autenticaci?n.

| Tema | Resultado |
|---|---|
| Reino de Sombras | Fondo y decoraciones ya usan escalado proporcional; se conservan. |
| Jard?n de Macarons | Fondo y Tu rinc?n ya conservan proporciones; se conservan. |
| Pacto de Sangre | Fondo y paneles ya usan alto autom?tico o cover; se conservan. |
| Tintas del Equinoccio | Fondo y paneles ya usan alto autom?tico o cover; se conservan. |
| Algod?n de az?car | Se corrigen las dos dimensiones independientes del atlas en ambientaci?n, sidebar y Tu rinc?n: ahora una dimensi?n es autom?tica. El fondo principal ya era proporcional. |
| Biblioteca de Medianoche | Cover y contain conservan proporciones; se mantienen. |
| Bosque fe?rico | Se elimina el escalado independiente en el paisaje y Tu rinc?n. Paisaje con ancho al 100 % y alto autom?tico; en escritorio puede continuar hacia abajo, con difuminado. Tu rinc?n usa cover. |
| Alas de cristal | Se mantiene la correcci?n proporcional de escritorio y se retira el valor deformante de la regla base. |
| Rosas y Espinas | Sin ilustraciones espec?ficas deformadas; se conserva el comportamiento actual. |

`cover` puede recortar los extremos para llenar una tarjeta, pero mantiene la relaci?n entre ancho y alto. `contain` muestra la pieza completa. Los degradados y fondos de carga no son ilustraciones y no requieren la proporci?n de un archivo.

[Galer?a de revisi?n](galeria-proporciones-temas.html): nueve temas, nueve p?ginas, capturas a 1920, 1440 y 390 px, con datos simulados.

La suite de identidad incorpora una comprobaci?n de las capas de imagen del mural, sidebar, ambientaci?n y Tu rinc?n: cada recurso debe usar cover, contain o al menos una dimensi?n autom?tica. Se ampl?a a 1920?1080 para todos los temas, adem?s de 1440?1000, 1024?768, 768?1024, 390?844, 320?568 y 844?390. Comprueba tambi?n contraste de muestras, modal, foco, navegaci?n m?vil, errores y desbordamiento horizontal.

ESLint: cero errores y cinco advertencias existentes. Compilaci?n correcta con la advertencia existente de tama?o del bundle. Navegador de validaci?n: Chrome; no se afirma cobertura de Safari o Firefox.
