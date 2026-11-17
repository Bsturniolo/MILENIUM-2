# Propuesta: sistema nuevo de mercadería

Sistema enfocado en la mercadería (productos, stock, compras, ventas, caja y cuentas corrientes), tomando como referencia cómo resolvía cada tema un sistema de gestión de estaciones de servicio hecho en Visual Basic 6.

## Lo que se toma del sistema viejo

| Tema | Idea | En el sistema nuevo |
| --- | --- | --- |
| Productos | Rubro, categoría, costo, precio, IVA, varios códigos de barra, opciones (controla stock, precio editable, por peso) | Igual, más variantes (talle, color) |
| Ventas | Cabecera + renglones que guardan precio y costo del momento | Igual: ganancia real por venta |
| Comprobantes | Factura A/B, nota de crédito, remito | Una sola tabla de comprobantes con campo tipo |
| Stock | Kardex: cada movimiento con su comprobante y saldo | Igual, con avisos de reposición |
| Compras y pagos | Facturas de proveedor, órdenes de pago | Igual, con vencimientos |
| Caja por turno | Apertura, rendición por vendedor, cierre | Igual, diferencia calculada sola |
| Cuentas corrientes | Remito, luego factura y cobro | Igual, con límite de crédito |
| Auditoría | Quién cambió qué, valor anterior y nuevo | Igual, para precios y stock |

## Lo que se corrige

- Un programa web en vez de 15 ejecutables.
- Una sola base de datos en vez de SQL Server, DBF y Access mezclados.
- Fechas como fechas, importes en decimal exacto, claves y relaciones reales.
- Stock con una sola fuente de verdad.
- Sin contraseñas escritas en archivos de configuración.

## Etapas

1. Productos, stock con kardex, ventas en mostrador y caja por turno (primera versión en este repo).
2. Compras, proveedores y pagos; cuentas corrientes con remitos.
3. Factura electrónica, tarjetas y Mercado Pago, reportes y libros de IVA.
4. Importar los datos del sistema viejo.
5. Más adelante, opcional: surtidores (controlador de surtidores, ventas por manguera, stock por tanque, GNC).
