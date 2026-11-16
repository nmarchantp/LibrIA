# Alas de cristal

El tema existente `invierno` incorpora una identidad de hielo y cristal en las rutas autenticadas y los modales compartidos de perfil y contenido. Conserva nombre, identificador, seis colores ra?z, preferencias, selector y sincronizaci?n. Login, registro y dem?s temas permanecen sin cambios.

Los componentes usan fondo `#D9EAF7`, tarjetas `#EEF6FF`, superficie elevada `#E3F0FC`, texto azul `#173B66`, texto secundario `#36587B`, principal `#326A9D` con texto blanco y bordes interactivos `#6386A5`. El mural conserva texto blanco sobre la parte oscura del paisaje; los accesos sobre el ?rea clara usan azul profundo. La pesta?a activa es azul con borde blanco y brillo cian.

Tres ilustraciones creadas con image_gen a partir de la referencia, descritas en `apps/web/public/images/crystal-universe/README.md`. El banner autom?tico de perfil utiliza el paisaje del drag?n. Decoraci?n est?tica, sin captura de puntero; se mantienen preferencias de fondo y movimiento.

[Galer?a de escritorio y celular](galeria-estilo-cristal.html). Capturas reales con API simulada, sin modificar datos de usuarios.

Validaci?n en Chrome: nueve vistas y seis resoluciones (1440?1000, 1024?768, 768?1024, 390?844, 320?568, 844?390), foco, modal, navegaci?n t?ctil, paleta, recursos, contraste de muestras y ausencia de desbordamiento horizontal. Texto de bot?n principal 5,70:1; secundario 9,78:1; campos 10,81:1; bordes de bot?n secundario 3,31:1 y campo 3,65:1. No constituye certificaci?n WCAG completa. Safari y Firefox no comprobados.

ESLint sin errores y cinco advertencias existentes de fixtures. Compilaci?n correcta con advertencia existente de tama?o del bundle.

## Proporciones del paisaje en escritorio

Se elimina `background-size:100% 100%` en pantallas desde 701 px. El paisaje mantiene ancho al 100 % y alto autom?tico, con una capa de proporci?n 3:1 y altura m?nima de cabecera. En pantallas anchas puede extenderse por debajo de las pesta?as; una m?scara progresiva difumina el tramo inferior. El encuadre de celular permanece igual. Prueba adicional a 1920?1080 que comprueba alto autom?tico y proporci?n del contenedor.
