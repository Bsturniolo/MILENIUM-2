# Tienda online propia

Una tienda online con **carrito y cobro con Mercado Pago**, más un **panel** para cargar productos con fotos, manejar el stock y los pedidos. Es la alternativa casera a Tiendanube: no se paga plan mensual ni comisión a la plataforma, solo el servidor y lo que cobra Mercado Pago.

**Funciona sola.** Si se quiere, se conecta con [Milenium 2](../README.md) (u otro sistema) para que cada venta quede registrada allá y descuente stock.

👉 **Probala ya:** https://bsturniolo.github.io/MILENIUM-2/tienda/ (versión de demostración: productos y pagos de prueba)

## Qué tiene

| Parte | Qué hace |
| --- | --- |
| Tienda (`/`) | Productos con fotos, ofertas (precio tachado), categorías, buscador, "últimas unidades", carrito que se guarda, compra con datos del cliente y forma de entrega (retiro, envío con precio), botón de WhatsApp. Se ve bien en el celular |
| Cobro | **Mercado Pago** (tarjetas, dinero en cuenta, efectivo). Sin cuenta configurada: **modo prueba** (pago simulado) o **pago a coordinar** (transferencia: el pedido queda esperando y se marca pagado a mano) |
| Seguridad del cobro | El precio y el total los calcula el servidor (no se puede "tocar" desde el navegador). El aviso de Mercado Pago no se cree a ciegas: se le pregunta a Mercado Pago por el pago y solo se acepta si está aprobado y el monto coincide. El mismo pago nunca cuenta dos veces |
| Stock | Se descuenta al pagar. Un pedido sin pagar aparta el stock 30 minutos (48 horas en "pago a coordinar"), así dos personas no compran la última unidad. Cancelar un pedido pagado devuelve el stock |
| Panel (`/panel`) | Inicio (vendido hoy y en 30 días, pedidos para preparar), pedidos (datos del cliente, dirección, marcar enviado/entregado/cancelado, WhatsApp al cliente), productos (fotos que se achican solas, precio, oferta, stock con motivo, visible/destacado) y configuración (nombre, color, cartel, WhatsApp, Instagram, formas de entrega, cómo pagar sin Mercado Pago) |
| Conexión (opcional) | Cada pedido pagado se manda firmado a Milenium 2 (`/tienda/pedido`). Si no responde, reintenta solo cada minuto. También recibe precios y stock desde otro sistema (`PUT /api/panel/sincronizar`) |

## Pegarla en otra página

El público solo ve productos y carrito; las ventas y los datos de clientes quedan en `/panel`, con clave. Para poner los productos y el carrito dentro de una página que ya tenés, alcanza con una línea:

```html
<script src="https://mitienda.com.ar/tienda.js" data-cabecera="no" defer></script>
```

Detalle en [docs/PASOS.md](docs/PASOS.md#poner-el-carrito-en-tu-propia-página).

**Con un diseño propio** (la página dibuja sus productos a su manera y usa solo nuestro carrito y compra): `data-modo="carrito"`. Ejemplo armado con la propuesta ganadora: [`ejemplos/propuesta-b/`](ejemplos/propuesta-b/index.html) · [verla funcionando](https://bsturniolo.github.io/MILENIUM-2/tienda/ejemplos/propuesta-b/).

## Probarla en la compu

1. Instalar **Python** 3.12 o 3.13 (en Windows, tildar "Add python.exe to PATH").
2. Bajar el código (en GitHub: botón verde **Code → Download ZIP**, y descomprimir).
3. Entrar a la carpeta `tienda` y hacer doble clic en **`iniciar.bat`** (Windows) o correr `./iniciar.sh` (Linux/Mac).
4. Se abre el panel. La **clave** aparece en la ventana negra. Cargá productos, después abrí http://localhost:8000 y comprá.

Viene en **modo prueba**: los pagos son simulados. Para publicarla de verdad y cobrar: [docs/PASOS.md](docs/PASOS.md) (incluye cuánto cuesta).

## Copiarla para otro proyecto

Copiá la carpeta `tienda/` entera. No depende del resto del repo (salvo una prueba que verifica que el formato sea compatible con Milenium 2: si no está, esa prueba se saltea). Nombre, color, WhatsApp y formas de entrega se cambian desde el panel, sin tocar código.

## Estructura

| Archivo | Para qué |
| --- | --- |
| `servidor/app.py` | Servidor: tienda, pedidos, stock, panel y conexión con otro sistema |
| `servidor/mercadopago.py` | Todo lo que habla con Mercado Pago |
| `web/tienda.js` | La tienda entera (catálogo, carrito, compra), sin dependencias. Se pega en cualquier página. Sin servidor funciona en modo demostración |
| `web/index.html` | La página propia de la tienda (solo carga `tienda.js`) |
| `web/panel.html` | El panel |
| `tests/` | Pruebas con un Mercado Pago falso y Milenium 2 de verdad |
| `Dockerfile` · `deploy/` | Para subirla a un servidor con HTTPS |
| `iniciar.bat` · `iniciar.sh` | Para usarla en la compu |

Pruebas: `pip install -r requirements-dev.txt && python -m pytest -q tests`

## Lo que todavía no tiene

- Variantes (talle, color) dentro de un mismo producto: hoy cada variante se carga como un producto aparte.
- Cupones de descuento, cálculo de envío por código postal (Correo Argentino / Andreani), factura electrónica.
- Emails automáticos al cliente (hoy se avisa por WhatsApp desde el panel).
