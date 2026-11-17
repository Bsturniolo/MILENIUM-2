# ⚠️ FALTA LA PARTE FÍSICA

> **Estado al 17/11/2026:** el software está hecho y probado (servidor, código del módulo y simulador). **Todavía no se armó ni se probó ningún módulo físico.** Nada de esto está conectado a una máquina real. Antes de usarlo con clientes hay que completar esta lista.

## Lista de pendientes

- [ ] Comprar los materiales de la prueba de mesa (abajo)
- [ ] Armar la prueba de mesa con un foquito y probar el firmware en una placa real
- [ ] Subir el servidor a internet con HTTPS (ya está preparado: ver `docs/SUBIR-A-LA-NUBE.md`) y pegar su certificado raíz en el firmware (`CA_RAIZ`)
- [ ] Elegir la primera máquina real y ver cómo se habilita (si alcanza con darle corriente o si necesita un pulso de arranque)
- [ ] Armar el primer módulo en una caja cerrada, con un electricista matriculado para la parte de 220 V
- [ ] Probar 1 semana en una sola máquina antes de instalar más
- [ ] Conectar Mercado Pago de verdad (hoy el pago con QR está simulado)
- [x] Conectar la app (pestaña Equipos) con el servidor: vincular con código, ver si el módulo responde, encender al cobrar y detener

## Cómo se cobra y se habilita una máquina

En Argentina se paga con **QR de Mercado Pago, en pesos**. No usamos monedero ni fichas.

1. El cliente escanea el QR de la máquina y paga.
2. Mercado Pago le avisa al servidor que el pago entró (hoy está simulado).
3. El servidor le manda una orden firmada al módulo de esa máquina.
4. El módulo la habilita y la corta solo cuando termina el tiempo pagado.

Para habilitar la máquina hay dos variantes. En el firmware se eligen con `salida rele` o `salida pulso`:

| Variante | Cuándo | Cómo funciona | Riesgo |
| --- | --- | --- | --- |
| **Relé** (la normal) | Casi todas: aspiradoras, hidrolavadoras, lavarropas, cafeteras | El módulo da corriente a la máquina con un relé o un relé de estado sólido (SSR) del tamaño correcto para su consumo, y la corta al terminar | Alto: es 220 V. Lo instala un electricista matriculado, con térmica y disyuntor |
| **Pulso** (opcional) | Máquinas que quedan con corriente y arrancan con un botón o contacto de inicio | El módulo cierra un instante ese contacto, con un optoacoplador, en lugar del botón | Bajo: solo cables de señal, pero hay que conocer bien la máquina |

## Materiales

Los precios en pesos cambian seguido: buscarlos en MercadoLibre al momento de comprar y anotarlos acá.

### Prueba de mesa (una sola vez, sin 220 V)

| Material | Para qué | Precio ($) |
| --- | --- | --- |
| ESP32 DevKit V1 (38 pines) | El cerebro del módulo, con Wi-Fi |  |
| Módulo relé de 1 canal, 5 V, optoacoplado | Prender el foquito como si fuera la máquina |  |
| Foquito o LED de 5 V y protoboard con cables dupont | Ver que enciende y apaga a tiempo |  |
| Pulsador | Simular "la máquina está funcionando" (entrada de uso) |  |
| Microswitch | Simular "abrieron la caja" |  |
| Cable USB de datos | Cargar el firmware desde la compu |  |

### Por cada máquina real

| Material | Para qué | Precio ($) |
| --- | --- | --- |
| ESP32 DevKit V1 | Cerebro del módulo |  |
| Relé o SSR del amperaje de la máquina (o optoacoplador PC817 + resistencias para la variante pulso) | Salida a la máquina |  |
| Módulo detector de 220 V optoacoplado | Saber si la máquina está funcionando (alerta de uso sin pago) |  |
| Fuente 220 V → 5 V chica (tipo HLK-PM01) | Alimentar el módulo |  |
| Fusible con portafusible | Protección |  |
| Caja estanca IP54 o IP65 con tornillos | Que no se pueda tocar ni mojar |  |
| Microswitch en la tapa | Avisar si alguien abre la caja |  |
| Borneras y precintos | Conexiones firmes |  |

**Total por máquina: a completar**, más la mano de obra de instalación.

## Conexiones (pines del firmware)

| Pin ESP32 | Va a | Detalle |
| --- | --- | --- |
| GPIO 26 | Entrada del relé, o LED del optoacoplador con resistencia de 330 Ω | Salida a la máquina |
| GPIO 27 | Salida del detector de 220 V | LOW = la máquina está funcionando |
| GPIO 14 | Microswitch de la tapa (a GND) | LOW = caja cerrada; si se abre, avisa |
| GPIO 2 | LED de la placa | Encendido mientras la máquina está habilitada |
| 5V y GND | Fuente de 5 V | Alimentación |

El módulo **siempre arranca apagado**: si se corta la luz a la mitad de un uso, al volver no enciende la máquina solo.

## Cómo hacer la prueba de mesa

1. Instalar Arduino IDE, agregar el soporte para ESP32 (Espressif, versión 2.0 o mayor) y la biblioteca **ArduinoJson** versión 7.
2. Abrir `modulos/firmware/modulo_milenium/modulo_milenium.ino` y cargarlo en la placa.
3. Correr el servidor en la compu (ver `modulos/README.md`). Para esta prueba, el servidor tiene que tener HTTPS o, solo en la mesa, usar un túnel con certificado (por ejemplo Cloudflare Tunnel).
4. En el monitor serie escribir: `wifi <red> <clave>`, `servidor https://...`, `salida rele`.
5. Pedirle al servidor un código de vinculación para un equipo y escribir `vincular <código>`.
6. Cobrar un uso desde el servidor. El foquito tiene que prenderse y apagarse justo al terminar el tiempo.
7. Probar las protecciones: desconectar el Wi-Fi a la mitad (el foquito igual tiene que apagarse a tiempo), mantener apretado el pulsador sin pago (llega la alerta de "uso sin pago") y abrir el microswitch (llega "caja abierta").

## Seguridad que ya trae el software

- Cada módulo tiene su propia clave, que se entrega una sola vez al vincularlo con un código de 6 dígitos que vence en 10 minutos.
- Cada pedido del módulo va firmado; el servidor rechaza firmas falsas y pedidos repetidos, y los anota como alerta.
- Cada orden del servidor va firmada; el módulo ignora órdenes alteradas, vencidas o repetidas.
- El mismo pago no puede activar una máquina dos veces.
- El tiempo lo cuenta la placa, con un tope de 4 horas por uso.

## Lo que no hay que hacer

- No conectar nada a 220 V sin un electricista matriculado.
- No usar `setInsecure()` en el firmware: deja la conexión sin verificar.
- No cambiar la máquina por dentro (placas originales, cableado de motor): el módulo solo maneja la corriente de entrada o el contacto de arranque.
- No instalar en muchas máquinas antes de probar una sola durante una semana.
