# Conectar la tienda web con Milenium 2

> **Estado al 17/11/2026:** la conexión está hecha y probada con pedidos simulados. La tienda todavía no existe (la vamos a armar nosotros) y el servidor todavía no está en la nube.

## Cómo funciona

1. Un cliente compra en la tienda web y **paga**.
2. La tienda le avisa al servidor de Milenium 2 con el pedido (qué productos, cuántos, a qué precio y el total pagado).
3. La app de Milenium 2 revisa el servidor cada 5 segundos, registra la venta en la pestaña **Ventas**, descuenta el stock y deja anotado el total pagado.

- Si la tienda manda el mismo pedido dos veces (por ejemplo, porque reintenta), **cuenta una sola vez**.
- Si hay dos computadoras con la app abierta, **solo una** registra cada venta.
- Si la tienda vende un producto que no está cargado en la app, la venta igual se registra, pero queda marcada para revisar (ese stock no se descuenta).
- Los productos se reconocen por el **código** (de barras o SKU). Tiene que ser el mismo en la tienda y en la app.

## Lo que tiene que hacer la tienda

Cuando un pedido queda **pagado**, mandar:

```
POST https://<servidor>/tienda/pedido
Content-Type: application/json
X-Firma: <HMAC-SHA256 en hex del cuerpo, con la clave de la tienda>
```

Cuerpo:

```json
{
  "pedido_id": "W-1001",
  "fecha_ms": 1795000000000,
  "items": [
    { "codigo": "7790001000011", "nombre": "Agua mineral 500 ml", "cantidad": 3, "precio": 800 }
  ],
  "envio": 4000,
  "descuento": 0,
  "total": 6400,
  "medio_pago": "Mercado Pago",
  "cliente": { "nombre": "Ana Gómez", "email": "ana@ejemplo.com", "telefono": "" }
}
```

| Campo | Obligatorio | Qué es |
| --- | --- | --- |
| `pedido_id` | Sí | Número de pedido de la tienda, único (letras, números, `-`, `_`, `.`, `:`) |
| `items` | Sí | Productos: `codigo` (igual que en la app), `nombre`, `cantidad`, `precio` unitario cobrado |
| `total` | Sí | Lo que pagó el cliente, con envío y descuentos |
| `envio`, `descuento` | No | Para verlos separados en el detalle |
| `medio_pago` | No | Por defecto "Tienda web" |
| `fecha_ms` | No | Fecha del pago en milisegundos; si falta, se usa la hora en que llega |
| `cliente` | No | Nombre, email y teléfono |

Respuestas: `200` (recibido; `"repetido": true` si ya había llegado), `401` (firma incorrecta), `422` (datos mal armados), `503` (falta configurar la clave en el servidor).

### Ejemplo en JavaScript (Node)

```js
import crypto from "node:crypto";

async function avisarMilenium(pedido) {
  const cuerpo = JSON.stringify(pedido);
  const firma = crypto.createHmac("sha256", process.env.MILENIUM_TIENDA_SECRETO).update(cuerpo).digest("hex");
  const r = await fetch(process.env.MILENIUM_URL + "/tienda/pedido", {
    method: "POST",
    headers: { "Content-Type": "application/json", "X-Firma": firma },
    body: cuerpo,
  });
  if (!r.ok) throw new Error("Milenium respondió " + r.status);  // reintentar más tarde: no se duplica
}
```

La clave **nunca** va en el navegador del cliente: el aviso lo manda el servidor de la tienda, después de confirmar el pago con Mercado Pago.

## Configurar

1. Generar una clave: `openssl rand -hex 32`.
2. Ponerla en el servidor de Milenium 2 como `MILENIUM_TIENDA_SECRETO` (en `deploy/.env`) y en la tienda.
3. En la app: **Equipos → Servidor**, poner la dirección del servidor y la clave de administrador. La pestaña **Ventas** dice "Conectado con la tienda web".

## Probar sin tienda

En **Ventas** está el botón **Simular venta web**: manda un pedido de prueba con productos cargados.

## Pendiente

- Armar la tienda.
- Que la tienda lea el stock y los precios de Milenium 2 (para no vender lo que no hay).
- Hoy los datos de la app quedan en cada navegador. Si van a usarla varias computadoras, conviene pasar también los datos de la app al servidor.
