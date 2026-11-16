# Vela de Pacto de Sangre

La ilustraci?n original permanece intacta. `SidebarCandle.jsx` la muestra en un SVG proporcional de 1200?1300, ocultando ?nicamente la llama impresa mediante una m?scara. Una llama vectorial independiente, anclada a la mecha, cambia de inclinaci?n, curvatura y escala. Su opacidad permanece en 1 para evitar el efecto de encendido y apagado.

Una zona transparente alrededor de la llama recibe el puntero. Al acercarlo se intensifica el balanceo y reacciona el halo; al retirarlo vuelve al movimiento suave. La ilustraci?n no captura clics fuera de esa zona ni agrega controles al recorrido de teclado.

Solo se monta en Pacto de Sangre; en celular se oculta junto con la decoraci?n lateral existente. Sin fondo m?gico la llama permanece est?tica, sin halo animado. La opci?n expl?cita ?Mover los puntitos? tambi?n controla la vela: encendida prevalece sobre la regla global de movimiento reducido, igual que el fondo de part?culas; apagada mantiene llama y halo est?ticos. La descripci?n del control lo explica en Pacto de Sangre. El resto de temas conserva sus im?genes.

Verificaci?n: `node --experimental-websocket apps/web/tests/blood-candlelight.mjs` comprueba movimiento de geometr?a con opacidad constante, hover real, retirada del cursor, halo, movimiento reducido y fondo m?gico. `sidebar-artwork-position.mjs` comprueba posici?n de las ilustraciones en ocho temas y tres tama?os. Captura de escritorio en `artifacts/blood-candlelight/desktop.png`.

Se corrigi? la causa del bloqueo observado: la regla global de movimiento reducido anulaba las animaciones. La prueba ahora se ejecuta con esa preferencia activada y compara transformaciones antes y despu?s de 350 ms reales, sin adelantar el reloj de la animaci?n, adem?s de probar hover y pausa.
