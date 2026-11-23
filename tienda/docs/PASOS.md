# Pasos para publicar la tienda y cobrar de verdad

> **Nada de esto está contratado.** Esta guía es para cuando decidas publicarla. Mientras tanto se prueba gratis en la compu (`iniciar.bat`) o en la [demostración](https://bsturniolo.github.io/MILENIUM-2/tienda/).

## Cuánto cuesta (aproximado, noviembre 2026)

| Qué | Para qué | Costo aproximado | Dónde |
| --- | --- | --- | --- |
| **Servidor** (VPS chico: 2 CPU, 2 a 4 GB) | Que la tienda esté prendida las 24 horas | Unos **US$ 5 a 8 por mes**. Ej.: Hetzner CPX22 figura a € 6,49/mes; DigitalOcean y Vultr tienen planes parecidos | [hetzner.com/cloud](https://www.hetzner.com/cloud) |
| **Dominio** `.com.ar` | La dirección (ej. `mitienda.com.ar`) | Pago **anual en pesos**, barato. El precio lo fija NIC Argentina y cambia: mirarlo al momento | [nic.ar](https://nic.ar) |
| **Mercado Pago** | Cobrar con tarjeta, dinero en cuenta o efectivo | Sin costo fijo. Cobra una **comisión por cada venta**, que depende de en cuántos días querés la plata (al instante es más cara). Ver la tabla vigente en tu cuenta | [Checkout de Mercado Pago](https://www.mercadopago.com.ar/herramientas-para-vender/check-out) |
| Certificado HTTPS (candado) | Que el navegador muestre "seguro" | **Gratis** (lo saca solo el servidor con Let's Encrypt) | — |

Comparado con Tiendanube: ahí se paga plan mensual y, en algunos planes, un costo por cada venta además de Mercado Pago. Acá solo pagás el servidor y el dominio. Lo que perdés: el soporte de Tiendanube y algunas cosas que todavía no tiene esta tienda (ver el README). Precios de referencia de Tiendanube: [tiendanube.com/planes-y-precios](https://www.tiendanube.com/planes-y-precios?c=AR).

Un mismo servidor alcanza para la tienda **y** el servidor de Milenium 2 (o varias tiendas), así que el costo no se multiplica.

## 1. Crear la cuenta de Mercado Pago para cobrar 👤

La cuenta tiene que ser **de quien recibe la plata** (la clienta, si la tienda es de ella).

1. Entrar a [mercadopago.com.ar/developers/panel](https://www.mercadopago.com.ar/developers/panel) con esa cuenta.
2. **Crear aplicación** → nombre (ej. "Tienda") → tipo de pago: **Pagos online** → **Checkout Pro**.
3. En la aplicación, entrar a **Credenciales de prueba** y copiar el **Access Token** (empieza con `TEST-` o `APP_USR-`). Con esto se prueba con tarjetas de prueba, sin plata real.
4. Cuando todo ande, en **Credenciales de producción** activar y copiar el **Access Token de producción**. Ese es el que cobra de verdad. **No se comparte con nadie ni se sube a GitHub.**
5. (Recomendado) En **Webhooks**: URL `https://TU-DOMINIO/mp/aviso`, evento **Pagos**. Copiar la **clave secreta** que muestra.

## 2. Contratar el servidor y el dominio 👤

1. Comprar el dominio en [nic.ar](https://nic.ar) (con Clave Fiscal).
2. Crear un servidor con **Ubuntu 24.04** en Hetzner (o similar). Anotar la **IP** que te da.
3. En nic.ar → tu dominio → **Delegar** a los DNS del proveedor, o crear un registro **A** que apunte el dominio a la IP del servidor. Puede tardar unas horas en tomar.

## 3. Subir la tienda al servidor

Desde la consola del servidor (el proveedor tiene una en la web):

```bash
# instalar Docker
curl -fsSL https://get.docker.com | sh
# bajar el código
git clone https://github.com/Bsturniolo/MILENIUM-2.git
cd MILENIUM-2/tienda/deploy
cp .env.ejemplo .env
nano .env        # completar (ver abajo) y guardar con Ctrl+O, Enter, Ctrl+X
docker compose up -d --build
```

En el `.env`:

| Dato | Qué poner |
| --- | --- |
| `DOMINIO` | `mitienda.com.ar` (sin https) |
| `TIENDA_URL` | `https://mitienda.com.ar` |
| `TIENDA_ADMIN_TOKEN` | Una clave larga. Generarla con `openssl rand -hex 24` y guardarla: es la del panel |
| `MP_ACCESS_TOKEN` | El Access Token de Mercado Pago (primero el de prueba, después el de producción) |
| `MP_WEBHOOK_SECRETO` | La clave secreta de Webhooks (opcional) |
| `TIENDA_PRUEBA` | `0` |

Listo: la tienda queda en `https://mitienda.com.ar` y el panel en `https://mitienda.com.ar/panel`.

Para actualizar cuando haya cambios: `cd MILENIUM-2 && git pull && cd tienda/deploy && docker compose up -d --build`. Los productos, fotos y pedidos están en un volumen aparte y **no se borran**.

**Copias de seguridad:** activá los "backups" del proveedor (en Hetzner suma un 20 % al precio del servidor), o bajá de vez en cuando el archivo de la base: `docker compose cp tienda:/datos ./copia`.

## 4. Probar un cobro

1. Con el Access Token **de prueba**, comprá algo en la tienda. Mercado Pago muestra su página de pago: usá una tarjeta de prueba (están en la [documentación de Mercado Pago](https://www.mercadopago.com.ar/developers/es/docs), buscando "tarjetas de prueba").
2. Al volver, la tienda dice "¡Gracias por tu compra!" y en el panel el pedido aparece **Pagado · preparar**, con el stock descontado.
3. Cambiá al Access Token **de producción** en el `.env` y corré `docker compose up -d`. Desde ahí cobra de verdad.

## Poner el carrito en tu propia página

La tienda se puede usar de dos maneras:

- **Página propia de la tienda:** `https://mitienda.com.ar` (no hace falta nada más).
- **Pegada en una página que ya tenés** (hecha a mano, con WordPress, Wix con código, etc.): ahí aparecen los productos y el carrito, con el diseño de tu página arriba y abajo.

Para pegarla, en el lugar de tu página donde quieras los productos, agregá **una línea**:

```html
<script src="https://mitienda.com.ar/tienda.js" data-cabecera="no" defer></script>
```

- `data-cabecera="no"` saca el nombre y logo de la tienda (porque tu página ya tiene los suyos). Quedan el buscador y el botón del carrito.
- En el `.env` del servidor, poné la dirección de tu página en `TIENDA_ORIGENES` (ej. `https://www.mipagina.com.ar`) y reiniciá con `docker compose up -d`. Sin eso, el navegador no deja que tu página hable con la tienda.
- Después de pagar en Mercado Pago, el cliente **vuelve a tu página** y ve "¡Gracias por tu compra!".

**Qué ve cada uno:**

| Quién | Qué ve |
| --- | --- |
| El público (en la tienda o en tu página) | Productos, precios, carrito, su compra y su propio pedido. Nada más |
| Vos, en `https://mitienda.com.ar/panel` con la clave | Ventas, pedidos, datos de los clientes (nombre, email, teléfono, dirección), productos, stock y configuración |

El panel no aparece enlazado en ningún lado de la tienda, no lo indexa Google, y sin la clave no muestra nada: el servidor no entrega ventas ni datos de clientes sin ella. Cada cliente solo puede ver su propio pedido, con un código secreto que se le da al comprar.

## 5. (Opcional) Conectar con Milenium 2

Así cada venta de la tienda queda también en Milenium 2, en la pestaña **Ventas**, y descuenta el stock allá.

1. Tener el servidor de Milenium 2 andando (guía: [docs/SUBIR-A-LA-NUBE.md](../../docs/SUBIR-A-LA-NUBE.md)). Puede ser el mismo servidor que la tienda, con otro subdominio.
2. Generar una clave compartida: `openssl rand -hex 32`.
3. En el `.env` de **Milenium 2**: `MILENIUM_TIENDA_SECRETO=<esa clave>`.
4. En el `.env` de **la tienda**: `CONECTAR_URL=https://<servidor de Milenium 2>/tienda/pedido` y `CONECTAR_CLAVE=<la misma clave>`.
5. Reiniciar los dos (`docker compose up -d`).
6. Cargar los productos con **el mismo código / SKU** en los dos lados. Si un código no coincide, la venta igual entra a Milenium 2 pero marcada "revisar".

En el panel de la tienda, **Conexión** muestra si está conectado y si quedó algún pedido sin pasar (se reintenta solo cada minuto, o a mano con "Reintentar ahora").

Para mandar precios y stock **desde** otro sistema a la tienda existe `PUT /api/panel/sincronizar` (con la clave del panel):

```json
{ "productos": [ { "codigo": "7790001000011", "nombre": "Agua 500 ml", "precio": 800, "stock": 40 } ] }
```

Actualiza los que coinciden por código y crea los nuevos **ocultos**, para revisarlos y ponerles foto antes de mostrarlos.

**Sin servidor, para mostrar cómo funciona:** abrí Milenium 2 desde GitHub (https://bsturniolo.github.io/MILENIUM-2/) y, en la misma compu y navegador, la [tienda de demostración](https://bsturniolo.github.io/MILENIUM-2/tienda/). La demo muestra los productos cargados en Milenium 2, y lo que compres aparece solo en **Ventas** y descuenta el stock.

## Conectar Ecomers (Tiendanube) con Milenium 2

Se puede, y es poco trabajo, porque Milenium 2 ya recibe pedidos en el mismo formato que usa esta tienda:

1. En Ecomers, cuando registra una venta web de Tiendanube (`registrar_venta_web` en `conector/app.py`), agregar un aviso firmado a `https://<servidor de Milenium 2>/tienda/pedido` con: número de pedido, productos (SKU, nombre, cantidad, precio), envío, descuento, total, medio de pago y cliente. El formato y un ejemplo están en [docs/TIENDA-WEB.md](../../docs/TIENDA-WEB.md).
2. Guardar el aviso para reintentar si Milenium 2 no responde (Ecomers ya tiene ese mecanismo para los avisos de Tiendanube).
3. Configurar la misma clave en los dos lados (`MILENIUM_TIENDA_SECRETO` en Milenium 2).

Ojo: si Ecomers ya descuenta stock y Milenium 2 también, conviene decidir **cuál es el que manda** con el stock, para no llevar dos inventarios distintos.
