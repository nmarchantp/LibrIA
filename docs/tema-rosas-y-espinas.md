# Rosas y Espinas

El identificador existente `dark-rosado` mantiene sus seis colores ra?z, nombre, selecci?n y persistencia. El refinamiento se aplica a las rutas autenticadas y los modales compartidos de perfil y contenido. Login, registro y otros temas no cambian.

## Componentes

Fondo ciruela `#25151F`, tarjetas `#3B2431`, superficie elevada `#482C3B`, texto `#F9E9EF`, secundario `#D9BEC9`, acento rosa `#F0A5C5`, bordes de panel `#805366` y bordes interactivos `#B37D95`. Estos tokens locales distinguen las superficies y acercan los componentes a la referencia sin alterar la paleta ra?z ni las preferencias.

El mural usa jard?n, arco y luna como fondo continuo, con proporciones conservadas y difuminado inferior. La sidebar muestra ramas y rosas justo antes del usuario. Tu rinc?n usa una ilustraci?n independiente con farol. Una reutilizaci?n discreta de las rosas ambienta el borde inferior del contenido. El perfil recibe un banner autom?tico del jard?n.

Se conservan las tres capas de puntitos y los controles Fondo m?gico y Mover los puntitos. La nueva decoraci?n es est?tica y no captura clics. No se a?ade movimiento de p?talos ni interacciones nuevas.

[Galer?a de escritorio y celular](galeria-estilo-rosas.html), con nueve p?ginas a 1920, 1440 y 390 px. Capturas de Chrome con API simulada, sin datos reales.

## Verificaci?n

Suite de identidad: nueve vistas y siete tama?os (1920?1080, 1440?1000, 1024?768, 768?1024, 390?844, 320?568, 844?390). Comprueba proporciones de ilustraciones, ausencia de errores y desbordamiento horizontal, foco, modales y navegaci?n m?vil. Muestras de contraste: bot?n principal 8,76:1, secundario 10,93:1, campos 14,10:1; borde secundario 3,83:1 y de campo 4,94:1. No constituye una certificaci?n WCAG completa. Safari y Firefox no comprobados.

Se verifican adem?s selector, preferencias y puntitos en los nueve temas. ESLint sin errores, con cinco advertencias existentes de fixtures. Compilaci?n correcta con advertencia existente de tama?o del bundle.

Recursos y prompts: `apps/web/public/images/rose-universe/README.md`.
