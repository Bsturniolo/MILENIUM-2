# Milenium 2

### 👉 [Abrir la app](https://bsturniolo.github.io/MILENIUM-2/)

https://bsturniolo.github.io/MILENIUM-2/ · Si ves una versión vieja, recargá con Ctrl + F5. La versión aparece abajo de todo en la app.

Sistema de gestión de mercadería para comercios: productos, ventas en mostrador, stock, equipos automáticos que se cobran por uso, caja por turno y reportes.

Toma las ideas de un sistema de gestión de estaciones de servicio de los años 2000 (ventas con foto de precio y costo, kardex de stock, caja por turno, auditoría de cambios) y las rehace como una aplicación web simple.

## Qué hace hoy

| Sección | Qué se puede hacer |
| --- | --- |
| Vender | Buscar por nombre o escanear código de barras, armar el ticket, elegir medio de pago (efectivo con vuelto, débito, crédito, transferencia, QR Mercado Pago) y cobrar. Elegir cliente, guardar presupuesto o hacer remito a cuenta corriente |
| Ventas | Todas las ventas (mostrador, tienda web y equipos) con total pagado, detalle por venta y filtros. Las ventas de la tienda web entran solas y descuentan stock (ver [docs/TIENDA-WEB.md](docs/TIENDA-WEB.md)) |
| Productos | Alta, edición y baja; varios códigos de barra por producto, rubro, costo, precio, IVA, stock mínimo, venta por peso |
| Stock | Ajustes de inventario con motivo, productos para reponer y kardex de movimientos |
| Clientes | Clientes con CUIT/DNI y límite de crédito; cuenta corriente (remitos suman, pagos restan); presupuestos (pasan al ticket) y remitos, con impresión y anulación |
| Compras | Proveedores con cuenta corriente; compras de varios productos (suman stock, actualizan costo) pagadas al contado o a cuenta; pagos a proveedores |
| Equipos | Alta de máquinas (lavarropas, cafeteras, aspiradoras, etc.) con precio por uso o por minuto; cobrar y activar (el pago con QR de Mercado Pago está simulado), cuenta regresiva, detener, fuera de servicio, usos y recaudación del día |
| Caja | Apertura de turno con efectivo inicial, gastos y retiros, cobros de cuenta corriente y pagos a proveedores en efectivo, cierre con efectivo contado y diferencia calculada |
| Reportes | Ventas, facturado, ganancia y ticket promedio por día, semana o mes; productos más vendidos; anulación de ventas (devuelve el stock) |

## Cómo usarlo

Entrá a https://bsturniolo.github.io/MILENIUM-2/, o descargá `index.html` y abrilo en el navegador. Es un solo archivo, no necesita instalar nada.

- Fuera de Claude, los datos se guardan en el navegador (localStorage) de esa computadora. Arranca con 5 productos de ejemplo.
- Publicado como Artifact en Claude, usa la base de datos compartida del Artifact.

## Tienda online propia

En [`tienda/`](tienda/README.md) hay una tienda online con carrito, cobro con Mercado Pago y panel para cargar productos con fotos y manejar pedidos. Funciona sola, o conectada a Milenium 2 para que cada venta web quede registrada acá. Es la alternativa casera a Tiendanube.

👉 [Demostración](https://bsturniolo.github.io/MILENIUM-2/tienda/) · Costos y pasos para publicarla: [tienda/docs/PASOS.md](tienda/docs/PASOS.md)

## Módulos para las máquinas

En `modulos/` está el sistema propio para encender las máquinas solo cuando se pagó: servidor, código para la placa ESP32 y un simulador.

> ⚠️ **Falta la parte física**: todavía no se armó ninguna placa. Materiales, conexiones y pendientes en [modulos/FALTA-PARTE-FISICA.md](modulos/FALTA-PARTE-FISICA.md).

El servidor está listo para subirse a la nube, pero todavía no se subió: pasos en [docs/SUBIR-A-LA-NUBE.md](docs/SUBIR-A-LA-NUBE.md).

## Estructura

| Archivo | Para qué |
| --- | --- |
| `mostrador.src.html` | Código fuente de la app (HTML, CSS y JavaScript sin dependencias) |
| `index.html` | Versión lista para abrir, generada con `python3 scripts/build.py` |
| `docs/propuesta.md` | Plan del sistema y etapas |
| `modulos/` | Servidor, firmware y simulador de los módulos para máquinas |
| `Dockerfile` · `deploy/` | Todo lo necesario para subir el servidor a la nube |
| `docs/SUBIR-A-LA-NUBE.md` | Guía paso a paso para subirlo |
| `tienda/` | Tienda online propia (carrito, Mercado Pago, panel); se copia sola a otro proyecto |

## Próximas etapas

1. Base de datos propia en un servidor, para usarlo desde varias computadoras y vendérselo a otros comercios.
2. Compras y proveedores con pagos, cuentas corrientes de clientes con remitos.
3. Factura electrónica (ARCA), tarjetas y Mercado Pago, libros de IVA.
4. Importador de datos desde el sistema viejo.
5. Conectar los equipos de verdad: Mercado Pago avisa al servidor cuando entra el pago y el servidor enciende la máquina con una placa (por ejemplo ESP32 con relé). El mismo esquema sirve para surtidores de combustible.
