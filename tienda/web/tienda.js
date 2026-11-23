/* Tienda: catálogo + carrito + compra, para pegar en CUALQUIER página.
 *
 * Uso (una sola línea donde quieras que aparezcan los productos):
 *   <script src="https://TU-SERVIDOR/tienda.js" defer></script>
 *
 * Opciones (atributos del <script>):
 *   data-cabecera="no"     sin nombre/logo de la tienda (si tu página ya tiene el suyo); quedan el buscador y el carrito
 *   data-donde="#mi-div"   dónde dibujar la tienda (si no, aparece justo donde está el <script>)
 *   data-servidor="https://..."  dirección del servidor (si no, la misma de donde se carga este archivo)
 *   data-color="#141414"   color de los botones del carrito (si no, el que se elige en el panel)
 *   data-modo="carrito"    solo el carrito y la compra (para un diseño propio que dibuja sus productos).
 *                          El diseño usa window.Tienda: Tienda.listo (promesa con {productos, config, pagos}),
 *                          Tienda.agregar(id, cantidad), Tienda.abrirCarrito(), Tienda.cantidad(), Tienda.whatsapp(texto)
 *                          y el evento window "tienda:carrito" cada vez que cambia el carrito.
 *
 * Tu página tiene que estar en TIENDA_ORIGENES del servidor (ver docs/PASOS.md).
 * El público solo ve productos, carrito y su pedido. Las ventas y los datos de clientes están en /panel, con clave.
 */
(() => {
'use strict';
const SCRIPT = document.currentScript;
const PAGINA = SCRIPT && SCRIPT.dataset.pagina === 'si';   // la página propia de la tienda (index.html)
const URL_SCRIPT = new URL(SCRIPT ? SCRIPT.src : location.href, location.href);
const SRV_ = ((SCRIPT && SCRIPT.dataset.servidor) || (window.TIENDA_SERVIDOR || '') || (URL_SCRIPT.origin === location.origin ? '' : URL_SCRIPT.origin)).replace(/\/$/, '');
// Sin servidor (GitHub Pages o archivo suelto) funciona en MODO DEMO.
const DEMO_ = !(SCRIPT && SCRIPT.dataset.servidor) && !window.TIENDA_SERVIDOR && (URL_SCRIPT.protocol === 'file:' || /\.github\.io$/.test(URL_SCRIPT.hostname));

let HOST = SCRIPT && SCRIPT.dataset.donde ? document.querySelector(SCRIPT.dataset.donde) : null;
if (!HOST) { HOST = document.createElement('div'); SCRIPT && SCRIPT.parentNode ? SCRIPT.parentNode.insertBefore(HOST, SCRIPT) : document.body.appendChild(HOST); }
HOST.classList.add('tienda-online');
const R = HOST.attachShadow({ mode: 'open' });
R.innerHTML = '<style>' + "\n:host{\n  --marca:#6c4cf1; --marca-tx:#fff;\n  --bg:#f6f5f2; --card:#fff; --tx:#1c1b22; --mut:#6b6a75; --line:#e6e3dc; --soft:#efede8;\n  --ok:#1f8a5b; --ok-soft:#e3f4ec; --bad:#c23b3b; --bad-soft:#fbe7e7; --warn:#9a6400; --warn-soft:#fdf1d8;\n  --r:14px; --sombra:0 1px 2px rgba(20,18,30,.05),0 8px 24px -14px rgba(20,18,30,.18);\n  --sans:system-ui,-apple-system,\"Segoe UI\",Roboto,\"Helvetica Neue\",Arial,sans-serif;\n  color-scheme:light;\n}\n@media (prefers-color-scheme:dark){:host{\n  --bg:#121216; --card:#1b1b21; --tx:#efeef3; --mut:#a3a2ad; --line:#2c2c35; --soft:#24242b;\n  --ok:#5fd39a; --ok-soft:#173327; --bad:#ff8c8c; --bad-soft:#3a1d1f; --warn:#f3c15e; --warn-soft:#382c12; color-scheme:dark;\n}}\n*{box-sizing:border-box}\n:host{display:block;background:var(--bg);color:var(--tx);font:16px/1.5 var(--sans);-webkit-font-smoothing:antialiased;text-align:left}\n.raiz{min-height:200px}\nbutton,input,select,textarea{font:inherit;color:inherit}\nbutton{cursor:pointer}\na{color:inherit}\nimg{max-width:100%;display:block}\n[hidden]{display:none!important}\n.wrap{max-width:1180px;margin:0 auto;padding:0 16px}\n.vis{position:absolute;width:1px;height:1px;overflow:hidden;clip:rect(0 0 0 0)}\n\n/* aviso y cabecera */\n#aviso{background:var(--marca);color:var(--marca-tx);text-align:center;font-size:14px;padding:7px 16px}\n#prueba{background:var(--warn-soft);color:var(--warn);text-align:center;font-size:14px;padding:7px 16px;font-weight:600}\nheader{position:sticky;top:0;z-index:20;background:color-mix(in srgb,var(--bg) 88%,transparent);backdrop-filter:blur(10px);border-bottom:1px solid var(--line)}\nheader .wrap{display:flex;align-items:center;gap:14px;height:68px}\n.marca{display:flex;align-items:center;gap:10px;text-decoration:none;min-width:0}\n.marca .ini{width:40px;height:40px;border-radius:12px;background:var(--marca);color:var(--marca-tx);display:grid;place-items:center;font-weight:800;font-size:19px;flex:none}\n.marca b{display:block;font-size:19px;line-height:1.1;letter-spacing:-.01em;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}\n.marca small{display:block;color:var(--mut);font-size:13px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}\n.buscar{flex:1;max-width:420px;margin-left:auto;position:relative}\n.buscar input{width:100%;height:42px;border-radius:999px;border:1px solid var(--line);background:var(--card);padding:0 16px 0 40px}\n.buscar svg{position:absolute;left:14px;top:12px;width:18px;height:18px;color:var(--mut)}\n.btn-carrito{position:relative;height:42px;border-radius:999px;border:0;background:var(--tx);color:var(--bg);padding:0 16px;display:flex;align-items:center;gap:8px;font-weight:600;flex:none}\n.btn-carrito svg{width:20px;height:20px}\n.btn-carrito .n{background:var(--marca);color:var(--marca-tx);border-radius:999px;min-width:22px;height:22px;display:grid;place-items:center;font-size:13px;padding:0 6px}\n@media (max-width:640px){\n  header .wrap{flex-wrap:wrap;height:auto;padding-top:10px;padding-bottom:10px;gap:10px}\n  .buscar{order:3;max-width:none;flex-basis:100%}\n  .btn-carrito{margin-left:auto}\n  .btn-carrito .txt{display:none}\n}\n\n/* categor\u00edas */\n.chips{display:flex;gap:8px;overflow-x:auto;padding:16px 0 6px;scrollbar-width:none}\n.chips::-webkit-scrollbar{display:none}\n.chip{border:1px solid var(--line);background:var(--card);border-radius:999px;padding:7px 14px;white-space:nowrap;font-size:14px}\n.chip[aria-pressed=\"true\"]{background:var(--tx);color:var(--bg);border-color:var(--tx)}\n\n/* productos */\n.grilla{display:grid;grid-template-columns:repeat(auto-fill,minmax(210px,1fr));gap:16px;padding:12px 0 40px}\n@media (max-width:480px){.grilla{grid-template-columns:repeat(2,minmax(0,1fr));gap:10px}}\n.prod{background:var(--card);border-radius:var(--r);box-shadow:var(--sombra);overflow:hidden;display:flex;flex-direction:column;border:1px solid var(--line)}\n.prod .foto{aspect-ratio:1/1;background:var(--soft);position:relative;border:0;padding:0;width:100%}\n.prod .foto img{width:100%;height:100%;object-fit:cover}\n.sinfoto{width:100%;height:100%;display:grid;place-items:center;font-size:42px;font-weight:800;color:color-mix(in srgb,var(--marca) 70%,var(--tx));background:linear-gradient(135deg,color-mix(in srgb,var(--marca) 16%,var(--soft)),var(--soft))}\n.etq{position:absolute;left:10px;top:10px;display:flex;flex-direction:column;gap:5px;align-items:flex-start}\n.tag{font-size:12px;font-weight:700;border-radius:999px;padding:3px 9px;background:var(--card);color:var(--tx)}\n.tag.of{background:var(--marca);color:var(--marca-tx)}\n.tag.bad{background:var(--bad-soft);color:var(--bad)}\n.tag.warn{background:var(--warn-soft);color:var(--warn)}\n.prod .info{padding:12px 14px 14px;display:flex;flex-direction:column;gap:6px;flex:1}\n.prod h3{margin:0;font-size:15px;font-weight:600;line-height:1.3}\n.prod h3 button{all:unset;cursor:pointer}\n.precio{display:flex;align-items:baseline;gap:8px;flex-wrap:wrap;margin-top:auto}\n.precio b{font-size:19px;font-variant-numeric:tabular-nums}\n.precio s{color:var(--mut);font-size:14px}\n.agregar{height:40px;border-radius:10px;border:0;background:var(--marca);color:var(--marca-tx);font-weight:600}\n.agregar:disabled{background:var(--soft);color:var(--mut);cursor:not-allowed}\n.vacio{text-align:center;color:var(--mut);padding:60px 16px}\n\n/* paneles laterales y ventanas */\n.velo{position:fixed;inset:0;background:rgba(10,10,15,.45);z-index:40}\n.lado{position:fixed;top:0;right:0;bottom:0;width:min(440px,100%);background:var(--bg);z-index:41;display:flex;flex-direction:column;box-shadow:-10px 0 40px rgba(0,0,0,.2)}\n.lado .cab{display:flex;align-items:center;justify-content:space-between;padding:16px 18px;border-bottom:1px solid var(--line)}\n.lado .cab h2{margin:0;font-size:19px}\n.cerrar{width:38px;height:38px;border-radius:999px;border:1px solid var(--line);background:var(--card);font-size:20px;line-height:1}\n.lado .cuerpo{flex:1;overflow:auto;padding:16px 18px}\n.lado .pie{border-top:1px solid var(--line);padding:16px 18px;background:var(--card)}\n.linea{display:grid;grid-template-columns:64px 1fr auto;gap:12px;align-items:center;padding:10px 0;border-bottom:1px solid var(--line)}\n.linea .mini{width:64px;height:64px;border-radius:10px;overflow:hidden;background:var(--soft)}\n.linea .mini img{width:100%;height:100%;object-fit:cover}\n.linea .mini .sinfoto{font-size:22px}\n.linea b{display:block;font-size:15px;font-weight:600;line-height:1.3}\n.cant{display:inline-flex;align-items:center;border:1px solid var(--line);border-radius:999px;background:var(--card);margin-top:6px}\n.cant button{width:32px;height:32px;border:0;background:none;font-size:18px}\n.cant span{min-width:26px;text-align:center;font-variant-numeric:tabular-nums}\n.quitar{border:0;background:none;color:var(--mut);font-size:13px;text-decoration:underline;padding:0;margin-left:10px}\n.fila{display:flex;justify-content:space-between;gap:10px;padding:3px 0}\n.fila.total{font-size:19px;font-weight:700;padding-top:8px}\n.num{font-variant-numeric:tabular-nums}\n.btn{width:100%;height:50px;border-radius:12px;border:0;background:var(--marca);color:var(--marca-tx);font-weight:700;font-size:16px;margin-top:12px}\n.btn.sec{background:var(--card);color:var(--tx);border:1px solid var(--line);font-weight:600}\n.btn:disabled{opacity:.6;cursor:wait}\nform label{display:block;font-size:14px;font-weight:600;margin:12px 0 0}\nform input,form textarea{width:100%;margin-top:5px;border:1px solid var(--line);background:var(--card);border-radius:10px;padding:11px 12px;font-weight:400}\nform textarea{min-height:70px;resize:vertical}\n.opc{display:flex;gap:10px;align-items:flex-start;border:1px solid var(--line);background:var(--card);border-radius:12px;padding:12px;margin-top:8px;font-weight:400;cursor:pointer}\n.opc:has(input:checked){border-color:var(--marca);box-shadow:0 0 0 1px var(--marca)}\n.opc input{width:auto;margin:3px 0 0}\n.opc small{display:block;color:var(--mut)}\n.opc .num{margin-left:auto;font-weight:600;white-space:nowrap}\n.error{background:var(--bad-soft);color:var(--bad);border-radius:10px;padding:10px 12px;margin-top:12px;font-size:14px}\n.nota{background:var(--soft);border-radius:10px;padding:10px 12px;font-size:14px;color:var(--mut);margin-top:12px}\n.ventana{position:fixed;z-index:41;inset:auto 0 0 0;max-height:92vh;background:var(--bg);border-radius:18px 18px 0 0;overflow:auto;box-shadow:0 -10px 40px rgba(0,0,0,.25)}\n@media (min-width:760px){.ventana{inset:50% auto auto 50%;transform:translate(-50%,-50%);width:min(880px,94vw);border-radius:18px}}\n.detalle{display:grid;gap:22px;padding:18px}\n@media (min-width:760px){.detalle{grid-template-columns:1fr 1fr;padding:24px}}\n.galeria .grande{aspect-ratio:1/1;border-radius:14px;overflow:hidden;background:var(--soft)}\n.galeria .grande img{width:100%;height:100%;object-fit:cover}\n.galeria .minis{display:flex;gap:8px;margin-top:8px;overflow-x:auto}\n.galeria .minis button{width:58px;height:58px;padding:0;border-radius:8px;overflow:hidden;border:2px solid transparent;flex:none;background:var(--soft)}\n.galeria .minis button[aria-pressed=\"true\"]{border-color:var(--marca)}\n.galeria .minis img{width:100%;height:100%;object-fit:cover}\n.detalle h2{margin:0 0 6px;font-size:24px;line-height:1.2}\n.detalle .desc{white-space:pre-wrap;color:var(--mut);margin:14px 0}\n.detalle .precio b{font-size:26px}\n.resultado{max-width:560px;margin:40px auto;background:var(--card);border-radius:18px;box-shadow:var(--sombra);padding:26px 22px;border:1px solid var(--line)}\n.resultado h1{margin:8px 0 4px;font-size:26px;line-height:1.2}\n.icono{width:56px;height:56px;border-radius:999px;display:grid;place-items:center;font-size:28px}\n.icono.ok{background:var(--ok-soft);color:var(--ok)} .icono.esp{background:var(--warn-soft);color:var(--warn)} .icono.bad{background:var(--bad-soft);color:var(--bad)}\n.pago-prueba{max-width:420px;margin:0 auto;padding:24px}\n.pago-prueba .caja{border:2px dashed var(--warn);border-radius:14px;padding:18px;background:var(--warn-soft);color:var(--warn);font-size:14px}\nfooter{border-top:1px solid var(--line);color:var(--mut);font-size:14px;padding:26px 0 40px}\nfooter .wrap{display:flex;flex-wrap:wrap;gap:12px 24px;justify-content:space-between}\nfooter a{color:var(--mut)}\n.wsp{position:fixed;right:16px;bottom:16px;z-index:30;width:56px;height:56px;border-radius:999px;background:#25d366;color:#fff;display:grid;place-items:center;box-shadow:0 8px 24px -8px rgba(0,0,0,.4)}\n.wsp svg{width:30px;height:30px}\n#toast{position:fixed;left:50%;bottom:24px;transform:translateX(-50%);background:var(--tx);color:var(--bg);padding:10px 18px;border-radius:999px;z-index:60;font-size:15px;box-shadow:var(--sombra)}\n.cargando{padding:80px 0;text-align:center;color:var(--mut)}\n.solo #principal{position:fixed;inset:0;z-index:45;background:rgba(10,10,15,.5);overflow:auto;padding:16px;max-width:none}\n.solo #principal .cargando{color:#fff}\n.solo #principal .resultado{margin:6vh auto}\n@media (prefers-reduced-motion:no-preference){.lado{animation:entra .22s ease-out}@keyframes entra{from{transform:translateX(30px);opacity:.4}}}\n" + '</style><div class="raiz">' + "<div id=\"prueba\" hidden></div>\n<div id=\"aviso\" hidden></div>\n<header id=\"cabecera\">\n  <div class=\"wrap\">\n    <a class=\"marca\" href=\"\" id=\"marca\"><span class=\"ini\" id=\"ini\">\u00b7</span><span><b id=\"nombre\">Tienda</b><small id=\"lema\"></small></span></a>\n    <label class=\"buscar\"><span class=\"vis\">Buscar productos</span><svg viewBox=\"0 0 24 24\" fill=\"none\" stroke=\"currentColor\" stroke-width=\"2\" aria-hidden=\"true\"><circle cx=\"11\" cy=\"11\" r=\"7\"/><path d=\"m20 20-3.5-3.5\"/></svg><input id=\"q\" type=\"search\" placeholder=\"Buscar productos\" autocomplete=\"off\"></label>\n    <button class=\"btn-carrito\" id=\"abrirCarrito\" aria-label=\"Ver carrito\"><svg viewBox=\"0 0 24 24\" fill=\"none\" stroke=\"currentColor\" stroke-width=\"2\" aria-hidden=\"true\"><path d=\"M3 4h2l2.4 11.2a2 2 0 0 0 2 1.6h7.7a2 2 0 0 0 2-1.5L21 8H6.2\"/><circle cx=\"10\" cy=\"20\" r=\"1.4\"/><circle cx=\"17\" cy=\"20\" r=\"1.4\"/></svg><span class=\"txt\">Carrito</span><span class=\"n\" id=\"nCarrito\">0</span></button>\n  </div>\n</header>\n<main class=\"wrap\" id=\"principal\"><div class=\"cargando\">Cargando productos\u2026</div></main>\n<footer><div class=\"wrap\" id=\"pie\"></div></footer>\n<div id=\"capa\"></div>\n<div id=\"toast\" hidden></div>" + '</div>';
if (SCRIPT && SCRIPT.dataset.cabecera === 'no') R.querySelector('#marca').hidden = true;
const SOLO_CARRITO = !!(SCRIPT && SCRIPT.dataset.modo === 'carrito');
if (SOLO_CARRITO) R.querySelector('.raiz').classList.add('solo');
if (SOLO_CARRITO) ['#cabecera', 'footer', '#aviso', '#prueba', '#principal'].forEach(s => { R.querySelector(s).hidden = true; });

'use strict';
const $ = s => R.querySelector(s);
const esc = s => String(s ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
const plata = n => '$ ' + (Math.round((Number(n) || 0) * 100) / 100).toLocaleString('es-AR', { minimumFractionDigits: 0, maximumFractionDigits: 2 });
const toast = m => { const t = $('#toast'); t.textContent = m; t.hidden = false; clearTimeout(toast.h); toast.h = setTimeout(() => t.hidden = true, 2600); };
const guardar = (k, v) => { try { localStorage.setItem(k, JSON.stringify(v)); } catch (e) {} };
const leer = (k, d) => { try { const v = JSON.parse(localStorage.getItem(k) || 'null'); return v ?? d; } catch (e) { return d; } };

// ---------------------------------------------------------------- conexión con el servidor
// Sin servidor (por ejemplo, abierta desde GitHub Pages o como archivo) la tienda funciona en MODO DEMO:
// muestra los productos cargados en Milenium 2 en este navegador (o unos de ejemplo) y el pago es de prueba.
const SRV = SRV_;
const DEMO = DEMO_;

async function api(metodo, ruta, datos) {
  if (DEMO) return demo(metodo, ruta, datos);
  let r;
  try { r = await fetch(SRV + ruta, { method: metodo, headers: datos ? { 'Content-Type': 'application/json' } : {}, body: datos ? JSON.stringify(datos) : undefined }); }
  catch (e) { throw new Error('No hay conexión. Revisá internet y probá de nuevo.'); }
  let j = null; try { j = await r.json(); } catch (e) {}
  if (!r.ok) throw new Error(j && typeof j.detail === 'string' ? j.detail : 'Revisá los datos e intentá de nuevo.');
  return j;
}

// ---------------------------------------------------------------- modo demo (sin servidor)
function demo(metodo, ruta, datos) {
  const ped = leer('tienda-demo-pedidos', {});
  const mil = leer('mostrador-datos-v1', null);   // datos de Milenium 2 en este mismo navegador
  let prods = Array.isArray(window.TIENDA_DEMO_PRODUCTOS) ? window.TIENDA_DEMO_PRODUCTOS.map(p => ({ descripcion: '', categoria: '', precio_antes: 0, controla_stock: true, fotos: [], destacado: false, ...p })) : [];
  if (!prods.length && mil && mil.productos) prods = Object.entries(mil.productos).filter(([, p]) => p.activo !== false && Number(p.precio) > 0)
    .map(([id, p]) => ({ id, codigo: (p.codigos || [])[0] || '', nombre: p.nombre, descripcion: '', categoria: p.rubro || '', precio: Number(p.precio), precio_antes: 0,
      disponible: p.controlaStock === false ? null : Math.max(0, Math.floor(p.stock || 0)), controla_stock: p.controlaStock !== false, fotos: [], destacado: false }));
  if (!prods.length) prods = [['Agua mineral 500 ml', 'Bebidas', 800, 48], ['Gaseosa cola 1,5 L', 'Bebidas', 2600, 24], ['Alfajor triple chocolate', 'Golosinas', 1100, 60], ['Cargador de celular USB-C', 'Accesorios', 9500, 8], ['Hielo en bolsa 2 kg', 'Varios', 1800, 15]]
    .map(([nombre, categoria, precio, disponible], i) => ({ id: 'ej' + (i + 1), codigo: '779000100' + String(i + 1).padStart(4, '0'), nombre, descripcion: 'Producto de ejemplo.', categoria, precio, precio_antes: 0, disponible, controla_stock: true, fotos: [], destacado: false }));
  const config = { nombre: 'Tienda de prueba', lema: 'Así se ve tu tienda', aviso: '', whatsapp: '', instagram: '', email: '', color: '#6c4cf1', instrucciones_pago: '',
    envios: [{ id: 'retiro', nombre: 'Retiro en el local', precio: 0, pide_direccion: false, detalle: '' }, { id: 'domicilio', nombre: 'Envío a domicilio', precio: 0, pide_direccion: true, detalle: 'Costo a coordinar' }] };
  const vista = p => ({ numero: p.numero, ts: p.ts, estado: p.estado, items: p.items, subtotal: p.subtotal, envio: p.envio, envio_nombre: p.envio_nombre, total: p.total, pago_medio: p.pago_medio });
  return new Promise((ok, mal) => setTimeout(() => {
    if (ruta === '/api/tienda') return ok({ config, productos: prods, pagos: 'simulado' });
    if (metodo === 'POST' && ruta === '/api/pedidos') {
      const items = datos.items.map(i => { const p = prods.find(x => x.id === i.producto_id); return p && { producto_id: p.id, codigo: p.codigo, nombre: p.nombre, precio: p.precio, cantidad: i.cantidad }; });
      if (items.some(i => !i)) return mal(new Error('Un producto del carrito ya no está a la venta.'));
      const env = config.envios.find(e => e.id === datos.envio_id);
      const subtotal = items.reduce((s, i) => s + i.precio * i.cantidad, 0);
      const numero = 'DEMO-' + Date.now().toString(36).toUpperCase(), t = Math.random().toString(36).slice(2) + Math.random().toString(36).slice(2);
      ped[numero] = { numero, t, ts: Date.now(), estado: 'esperando_pago', items, subtotal, envio: env.precio, envio_nombre: env.nombre, total: subtotal + env.precio, cliente: datos.cliente, pago_medio: '' };
      guardar('tienda-demo-pedidos', ped);
      return ok({ numero, t, total: subtotal + env.precio, pagar_url: null, pagos: 'simulado' });
    }
    const m = ruta.match(/^\/api\/pedidos\/([^/?]+)(\/pago-simulado)?/);
    const p = m && ped[m[1]];
    if (!p) return mal(new Error('No existe ese pedido'));
    if (m[2] && p.estado === 'esperando_pago') {
      p.estado = 'pagado'; p.pago_medio = 'Mercado Pago (simulado)'; p.pago_ts = Date.now();
      guardar('tienda-demo-pedidos', ped);
      // Si Milenium 2 está en este navegador, le deja el pedido para que lo registre como venta y descuente stock.
      if (mil) { const cola = leer('milenium-tienda-demo', []); cola.push({ pedido_id: p.numero, fecha_ms: p.pago_ts, items: p.items.map(i => ({ codigo: i.codigo, nombre: i.nombre, cantidad: i.cantidad, precio: i.precio })), envio: p.envio, descuento: 0, total: p.total, medio_pago: p.pago_medio, cliente: { nombre: p.cliente.nombre, email: p.cliente.email, telefono: p.cliente.telefono } }); guardar('milenium-tienda-demo', cola); }
    }
    ok(vista(p));
  }, 250));
}

// ---------------------------------------------------------------- estado
const E = { cfg: null, prods: [], pagos: 'simulado', cat: '', q: '', carrito: leer('tienda-carrito', []), envio: '', error: '', enviando: false };
const prod = id => E.prods.find(p => String(p.id) === String(id));
const enCarrito = () => E.carrito.reduce((s, l) => s + l.cantidad, 0);
const lineas = () => E.carrito.map(l => ({ ...l, p: prod(l.id) })).filter(l => l.p);
const subtotal = () => lineas().reduce((s, l) => s + l.p.precio * l.cantidad, 0);
const maximo = p => p.controla_stock ? Math.max(0, Math.floor(p.disponible || 0)) : 999;
const guardarCarrito = () => { guardar('tienda-carrito', E.carrito); $('#nCarrito').textContent = enCarrito(); window.dispatchEvent(new CustomEvent('tienda:carrito', { detail: { cantidad: enCarrito() } })); };
const iniciales = s => String(s || '?').trim().split(/\s+/).slice(0, 2).map(w => w[0]).join('').toUpperCase();
const foto = (p, alt) => p.fotos && p.fotos[0] ? `<img src="${esc(urlFoto(p.fotos[0]))}" alt="${esc(alt ?? p.nombre)}" loading="lazy">` : `<div class="sinfoto" aria-hidden="true">${esc(iniciales(p.nombre))}</div>`;
const urlFoto = u => /^https?:\/\//.test(u) ? u : SRV + u;
const pctOff = p => p.precio_antes > p.precio ? Math.round((1 - p.precio / p.precio_antes) * 100) : 0;

function agregar(id, n = 1) {
  const p = prod(id); if (!p) return;
  const l = E.carrito.find(x => String(x.id) === String(id));
  const ya = l ? l.cantidad : 0;
  if (ya + n > maximo(p)) return toast(maximo(p) ? `Hay ${maximo(p)} disponibles` : 'Sin stock');
  if (l) l.cantidad += n; else E.carrito.push({ id: p.id, cantidad: n });
  guardarCarrito(); toast('Agregado al carrito');
}

// ---------------------------------------------------------------- vistas
function vCatalogo() {
  const cats = [...new Set(E.prods.map(p => p.categoria).filter(Boolean))].sort((a, b) => a.localeCompare(b, 'es'));
  const q = E.q.trim().toLowerCase();
  const lista = E.prods.filter(p => (!E.cat || p.categoria === E.cat) && (!q || (p.nombre + ' ' + p.categoria + ' ' + p.descripcion).toLowerCase().includes(q)));
  $('#principal').innerHTML = `${cats.length > 1 ? `<div class="chips" role="group" aria-label="Categorías"><button class="chip" data-cat="" aria-pressed="${!E.cat}">Todo</button>${cats.map(c => `<button class="chip" data-cat="${esc(c)}" aria-pressed="${E.cat === c}">${esc(c)}</button>`).join('')}</div>` : '<div style="height:10px"></div>'}
  ${lista.length ? `<div class="grilla">${lista.map(p => { const max = maximo(p), off = pctOff(p); return `<article class="prod">
    <button class="foto" data-ver="${esc(p.id)}" aria-label="Ver ${esc(p.nombre)}">${foto(p, '')}<span class="etq">${off ? `<span class="tag of">${off}% OFF</span>` : ''}${!max ? '<span class="tag bad">Sin stock</span>' : (p.controla_stock && max <= 3 ? `<span class="tag warn">${max === 1 ? 'Última unidad' : 'Últimas ' + max}</span>` : '')}</span></button>
    <div class="info"><h3><button data-ver="${esc(p.id)}">${esc(p.nombre)}</button></h3>
    <div class="precio"><b>${plata(p.precio)}</b>${off ? `<s>${plata(p.precio_antes)}</s>` : ''}</div>
    <button class="agregar" data-agregar="${esc(p.id)}" ${max ? '' : 'disabled'}>${max ? 'Agregar' : 'Sin stock'}</button></div></article>`; }).join('')}</div>`
    : `<div class="vacio">${E.prods.length ? 'No encontramos productos con esa búsqueda.' : 'Todavía no hay productos a la venta.'}</div>`}`;
}

function vDetalle(id, fi = 0) {
  const p = prod(id); if (!p) return;
  const max = maximo(p), off = pctOff(p);
  const fotos = p.fotos || [];
  abrir(`<div class="velo" data-cerrar></div><div class="ventana" role="dialog" aria-modal="true" aria-label="${esc(p.nombre)}">
    <div style="display:flex;justify-content:flex-end;padding:12px 12px 0"><button class="cerrar" data-cerrar aria-label="Cerrar">×</button></div>
    <div class="detalle" style="padding-top:4px"><div class="galeria"><div class="grande">${fotos.length ? `<img src="${esc(urlFoto(fotos[fi]))}" alt="${esc(p.nombre)}">` : foto(p)}</div>
      ${fotos.length > 1 ? `<div class="minis">${fotos.map((f, i) => `<button data-foto="${i}" data-de="${esc(p.id)}" aria-pressed="${i === fi}" aria-label="Foto ${i + 1}"><img src="${esc(urlFoto(f))}" alt=""></button>`).join('')}</div>` : ''}</div>
    <div>${p.categoria ? `<div class="nota" style="display:inline-block;margin:0 0 8px;padding:3px 10px">${esc(p.categoria)}</div>` : ''}<h2>${esc(p.nombre)}</h2>
      <div class="precio"><b>${plata(p.precio)}</b>${off ? `<s>${plata(p.precio_antes)}</s> <span class="tag of">${off}% OFF</span>` : ''}</div>
      ${p.descripcion ? `<p class="desc">${esc(p.descripcion)}</p>` : '<div style="height:12px"></div>'}
      ${max ? `<div style="display:flex;gap:10px;align-items:center"><div class="cant"><button data-dcant="-1" aria-label="Menos">−</button><span id="dcant">1</span><button data-dcant="1" aria-label="Más">+</button></div>
        <span class="nota" style="margin:0">${p.controla_stock ? (max === 1 ? 'Última unidad' : max + ' disponibles') : 'Disponible'}</span></div>
        <button class="btn" data-dagregar="${esc(p.id)}">Agregar al carrito</button>` : '<div class="error">Sin stock por ahora.</div>'}
    </div></div></div>`);
}

function vCarrito() {
  const ls = lineas();
  abrir(`<div class="velo" data-cerrar></div><aside class="lado" role="dialog" aria-modal="true" aria-label="Carrito">
    <div class="cab"><h2>Tu carrito</h2><button class="cerrar" data-cerrar aria-label="Cerrar">×</button></div>
    <div class="cuerpo">${ls.length ? ls.map(l => `<div class="linea"><div class="mini">${foto(l.p, '')}</div><div><b>${esc(l.p.nombre)}</b><span class="num" style="color:var(--mut);font-size:14px">${plata(l.p.precio)} c/u</span><br>
      <span class="cant"><button data-cant="-1" data-id="${esc(l.id)}" aria-label="Menos">−</button><span>${l.cantidad}</span><button data-cant="1" data-id="${esc(l.id)}" aria-label="Más">+</button></span><button class="quitar" data-quitar="${esc(l.id)}">Quitar</button></div>
      <div class="num" style="font-weight:600">${plata(l.p.precio * l.cantidad)}</div></div>`).join('') : '<div class="vacio" style="padding:40px 0">Tu carrito está vacío.</div>'}</div>
    ${ls.length ? `<div class="pie"><div class="fila total"><span>Subtotal</span><span class="num">${plata(subtotal())}</span></div><p style="margin:2px 0 0;color:var(--mut);font-size:14px">El envío se elige en el paso siguiente.</p><button class="btn" data-comprar>Finalizar compra</button></div>` : ''}
  </aside>`);
}

function vCheckout() {
  const ls = lineas();
  if (!ls.length) return vCarrito();
  const d = leer('tienda-datos', {});
  const envs = E.cfg.envios || [];
  if (!envs.some(e => e.id === E.envio)) E.envio = envs[0] && envs[0].id;
  const env = envs.find(e => e.id === E.envio) || { precio: 0 };
  const boton = E.pagos === 'mercadopago' ? 'Pagar con Mercado Pago' : E.pagos === 'simulado' ? 'Ir a pagar (prueba)' : 'Confirmar pedido';
  abrir(`<div class="velo" data-cerrar></div><aside class="lado" role="dialog" aria-modal="true" aria-label="Finalizar compra">
    <div class="cab"><h2>Finalizar compra</h2><button class="cerrar" data-cerrar aria-label="Cerrar">×</button></div>
    <form class="cuerpo" id="fCompra" novalidate>
      <b>Tus datos</b>
      <label>Nombre y apellido<input name="nombre" required autocomplete="name" value="${esc(d.nombre)}"></label>
      <label>Email<input name="email" type="email" required autocomplete="email" value="${esc(d.email)}"></label>
      <label>Teléfono / WhatsApp<input name="telefono" type="tel" required autocomplete="tel" value="${esc(d.telefono)}"></label>
      <div style="margin-top:18px"><b>¿Cómo lo recibís?</b></div>
      ${envs.map(e => `<label class="opc"><input type="radio" name="envio" value="${esc(e.id)}" ${e.id === E.envio ? 'checked' : ''}><span>${esc(e.nombre)}${e.detalle ? `<small>${esc(e.detalle)}</small>` : ''}</span><span class="num">${e.precio ? plata(e.precio) : 'Gratis'}</span></label>`).join('')}
      ${env.pide_direccion ? `<label>Dirección de entrega<input name="direccion" required autocomplete="street-address" placeholder="Calle, número, departamento, ciudad" value="${esc(d.direccion)}"></label>` : ''}
      <label>Notas (opcional)<textarea name="notas" placeholder="Horario, referencias, regalo…"></textarea></label>
      ${E.error ? `<div class="error" role="alert">${esc(E.error)}</div>` : ''}
    </form>
    <div class="pie">${ls.map(l => `<div class="fila" style="font-size:14px"><span>${l.cantidad} × ${esc(l.p.nombre)}</span><span class="num">${plata(l.p.precio * l.cantidad)}</span></div>`).join('')}
      <div class="fila"><span>Envío</span><span class="num">${env.precio ? plata(env.precio) : 'Gratis'}</span></div>
      <div class="fila total"><span>Total</span><span class="num">${plata(subtotal() + (env.precio || 0))}</span></div>
      <button class="btn" form="fCompra" type="submit" ${E.enviando ? 'disabled' : ''}>${E.enviando ? 'Un momento…' : boton}</button>
      <button class="btn sec" data-volver type="button">Volver al carrito</button></div>
  </aside>`);
}

async function confirmarCompra(f) {
  const v = n => (f.elements[n] ? f.elements[n].value.trim() : '');
  const cli = { nombre: v('nombre'), email: v('email'), telefono: v('telefono'), direccion: v('direccion'), notas: v('notas') };
  if (cli.nombre.length < 2) E.error = 'Escribí tu nombre.';
  else if (!/^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(cli.email)) E.error = 'Revisá el email.';
  else if (cli.telefono.replace(/\D/g, '').length < 6) E.error = 'Escribí un teléfono para avisarte.';
  else if (f.elements.direccion && cli.direccion.length < 5) E.error = 'Escribí la dirección de entrega.';
  else E.error = '';
  guardar('tienda-datos', { nombre: cli.nombre, email: cli.email, telefono: cli.telefono, direccion: cli.direccion });
  if (E.error) return vCheckout();
  E.enviando = true; vCheckout();
  try {
    const r = await api('POST', '/api/pedidos', { volver: location.origin + location.pathname, items: lineas().map(l => ({ producto_id: l.p.id, cantidad: l.cantidad })), envio_id: E.envio, cliente: cli });
    E.carrito = []; guardarCarrito(); E.enviando = false;
    if (r.pagar_url) { location.href = r.pagar_url; return; }
    history.pushState(null, '', `?pedido=${encodeURIComponent(r.numero)}&t=${encodeURIComponent(r.t)}`);
    cerrar();
    if (r.pagos === 'simulado') vPagoPrueba(r); else vResultado();
  } catch (e) { E.enviando = false; E.error = e.message; vCheckout(); await cargar(true); }
}

function vPagoPrueba(r) {
  abrir(`<div class="velo"></div><div class="ventana" role="dialog" aria-modal="true" aria-label="Pago de prueba"><div class="pago-prueba">
    <h2 style="margin:0 0 6px">Pago de prueba</h2><p style="margin:0 0 14px;color:var(--mut)">Pedido ${esc(r.numero)} · <b class="num" style="color:var(--tx)">${plata(r.total)}</b></p>
    <div class="caja">Esta tienda todavía no tiene Mercado Pago conectado. <b>No se cobra nada.</b> Acá, con la cuenta conectada, el cliente pagaría con tarjeta, dinero en cuenta o efectivo.</div>
    <button class="btn" data-simular="aprobar">Simular pago aprobado</button><button class="btn sec" data-simular="no">Cancelar</button></div></div>`);
  E.simulando = r;
}

async function vResultado() {
  const u = new URLSearchParams(location.search);
  const numero = u.get('pedido'), t = u.get('t') || '', pid = u.get('payment_id') || u.get('collection_id') || '';
  $('#principal').hidden = false;
  $('#principal').innerHTML = '<div class="cargando">Buscando tu pedido…</div>';
  let p;
  try { p = await api('GET', `/api/pedidos/${encodeURIComponent(numero)}?t=${encodeURIComponent(t)}${pid ? '&payment_id=' + encodeURIComponent(pid) : ''}`); }
  catch (e) { $('#principal').innerHTML = `<div class="resultado"><div class="icono bad">!</div><h1>No encontramos el pedido</h1><p>${esc(e.message)}</p><a class="btn sec" style="display:grid;place-items:center;text-decoration:none" href="${esc(location.pathname)}">Volver a la tienda</a></div>`; return; }
  const pagado = ['pagado', 'enviado', 'entregado'].includes(p.estado);
  const wsp = E.cfg.whatsapp ? `https://wa.me/${E.cfg.whatsapp}?text=${encodeURIComponent('Hola! Hice el pedido ' + p.numero + ' en la tienda.')}` : '';
  let titulo, texto, ic;
  if (pagado) { ic = '<div class="icono ok">✓</div>'; titulo = '¡Gracias por tu compra!'; texto = `Tu pago entró. Te escribimos para coordinar la entrega.`; }
  else if (p.estado === 'cancelado') { ic = '<div class="icono bad">×</div>'; titulo = 'Pedido cancelado'; texto = 'Si fue un error, escribinos.'; }
  else if (E.pagos === 'manual') { ic = '<div class="icono esp">…</div>'; titulo = 'Recibimos tu pedido'; texto = 'Falta el pago. ' + (E.cfg.instrucciones_pago ? '' : 'Te escribimos para coordinarlo.'); }
  else { ic = '<div class="icono esp">…</div>'; titulo = 'Estamos esperando la confirmación del pago'; texto = 'Si ya pagaste, en unos segundos se actualiza solo.'; }
  $('#principal').innerHTML = `<div class="resultado">${ic}<h1>${titulo}</h1><p style="color:var(--mut);margin:0 0 14px">Pedido <b style="color:var(--tx)">${esc(p.numero)}</b>. ${texto}</p>
    ${!pagado && E.pagos === 'manual' && E.cfg.instrucciones_pago ? `<div class="nota" style="white-space:pre-wrap;color:var(--tx)">${esc(E.cfg.instrucciones_pago)}</div>` : ''}
    <div style="margin-top:14px">${p.items.map(i => `<div class="fila"><span>${i.cantidad} × ${esc(i.nombre)}</span><span class="num">${plata(i.precio * i.cantidad)}</span></div>`).join('')}
    <div class="fila"><span>${esc(p.envio_nombre || 'Envío')}</span><span class="num">${p.envio ? plata(p.envio) : 'Gratis'}</span></div>
    <div class="fila total"><span>Total</span><span class="num">${plata(p.total)}</span></div>${p.pago_medio ? `<p style="margin:4px 0 0;color:var(--mut);font-size:14px">Pagado con ${esc(p.pago_medio)}</p>` : ''}</div>
    ${wsp ? `<a class="btn" style="display:grid;place-items:center;text-decoration:none;background:#25d366;color:#fff" href="${wsp}" target="_blank" rel="noopener">Escribirnos por WhatsApp</a>` : ''}
    <a class="btn sec" style="display:grid;place-items:center;text-decoration:none" href="${esc(location.pathname)}">Seguir comprando</a></div>`;
  if (p.estado === 'esperando_pago' && E.pagos === 'mercadopago' && (vResultado.n = (vResultado.n || 0) + 1) < 20) setTimeout(vResultado, 4000);
}

function vPie() {
  const c = E.cfg;
  const redes = [c.whatsapp && `<a href="https://wa.me/${esc(c.whatsapp)}" target="_blank" rel="noopener">WhatsApp</a>`, c.instagram && `<a href="https://instagram.com/${esc(c.instagram.replace(/^@/, ''))}" target="_blank" rel="noopener">Instagram</a>`, c.email && `<a href="mailto:${esc(c.email)}">${esc(c.email)}</a>`].filter(Boolean);
  $('#pie').innerHTML = `<span>© ${new Date().getFullYear()} ${esc(c.nombre)}</span><span>${redes.join(' · ')}</span><span>${E.pagos === 'mercadopago' ? 'Pagos seguros con Mercado Pago' : ''}</span>`;
  R.querySelector('.wsp') || (c.whatsapp && R.querySelector('.raiz').insertAdjacentHTML('beforeend', `<a class="wsp" href="https://wa.me/${esc(c.whatsapp)}" target="_blank" rel="noopener" aria-label="Escribinos por WhatsApp"><svg viewBox="0 0 24 24" fill="currentColor" aria-hidden="true"><path d="M12 2a10 10 0 0 0-8.6 15.1L2 22l5-1.3A10 10 0 1 0 12 2Zm0 18.2a8.2 8.2 0 0 1-4.2-1.1l-.3-.2-3 .8.8-2.9-.2-.3A8.2 8.2 0 1 1 12 20.2Zm4.5-6.1c-.2-.1-1.5-.7-1.7-.8-.2-.1-.4-.1-.6.1l-.8 1c-.1.2-.3.2-.5.1a6.7 6.7 0 0 1-3.3-2.9c-.3-.4.3-.4.7-1.3.1-.2 0-.3 0-.4l-.8-1.8c-.2-.5-.4-.4-.6-.4h-.5a1 1 0 0 0-.7.3 3 3 0 0 0-.9 2.2 5.2 5.2 0 0 0 1.1 2.7 11.8 11.8 0 0 0 4.5 4c1.7.7 2.3.8 3.2.6.5-.1 1.5-.6 1.7-1.2.2-.6.2-1.1.2-1.2-.1-.1-.2-.2-.4-.3Z"/></svg></a>`));
}

// ---------------------------------------------------------------- ventanas
function abrir(html) { $('#capa').innerHTML = html; document.body.style.overflow = 'hidden'; const f = $('#capa [data-cerrar].cerrar, #capa .btn'); f && f.focus({ preventScroll: true }); }
function cerrar() { $('#capa').innerHTML = ''; document.body.style.overflow = ''; E.error = ''; }

R.addEventListener('click', async e => {
  const b = e.target.closest('button,[data-cerrar]'); if (!b) return;
  const d = b.dataset;
  if (d.cerrar !== undefined) cerrar();
  else if (d.cat !== undefined) { E.cat = d.cat; vCatalogo(); }
  else if (d.ver) vDetalle(d.ver);
  else if (d.foto) vDetalle(d.de, Number(d.foto));
  else if (d.agregar) agregar(d.agregar);
  else if (d.dcant) { const s = $('#dcant'); const p = prod($('[data-dagregar]').dataset.dagregar); s.textContent = Math.min(maximo(p), Math.max(1, Number(s.textContent) + Number(d.dcant))); }
  else if (d.dagregar) { agregar(d.dagregar, Number($('#dcant').textContent)); cerrar(); }
  else if (d.cant) { const l = E.carrito.find(x => String(x.id) === d.id); const p = prod(d.id); l.cantidad = Math.min(maximo(p), l.cantidad + Number(d.cant)); if (l.cantidad < 1) E.carrito = E.carrito.filter(x => x !== l); guardarCarrito(); vCarrito(); }
  else if (d.quitar) { E.carrito = E.carrito.filter(x => String(x.id) !== d.quitar); guardarCarrito(); vCarrito(); }
  else if (d.comprar !== undefined) vCheckout();
  else if (d.volver !== undefined) vCarrito();
  else if (b.id === 'abrirCarrito') vCarrito();
  else if (d.simular) {
    const r = E.simulando; cerrar();
    if (d.simular === 'aprobar') { try { await api('POST', `/api/pedidos/${encodeURIComponent(r.numero)}/pago-simulado`, { t: r.t }); } catch (er) { toast(er.message); } }
    vResultado();
  }
});
R.addEventListener('change', e => { if (e.target.name === 'envio') { const f = $('#fCompra'); const keep = {}; ['nombre', 'email', 'telefono', 'direccion', 'notas'].forEach(n => f.elements[n] && (keep[n] = f.elements[n].value)); guardar('tienda-datos', { ...leer('tienda-datos', {}), ...keep }); E.envio = e.target.value; vCheckout(); } });
R.addEventListener('submit', e => { if (e.target.id === 'fCompra') { e.preventDefault(); confirmarCompra(e.target); } });
document.addEventListener('keydown', e => { if (e.key === 'Escape' && $('#capa').innerHTML && !E.enviando) cerrar(); });
$('#q').addEventListener('input', e => { E.q = e.target.value; if (!new URLSearchParams(location.search).get('pedido')) vCatalogo(); });
window.addEventListener('popstate', () => { cerrar(); new URLSearchParams(location.search).get('pedido') ? vResultado() : vCatalogo(); });

// ---------------------------------------------------------------- arranque
async function cargar(callado) {
  try {
    const d = await api('GET', '/api/tienda');
    E.cfg = d.config; E.prods = d.productos; E.pagos = d.pagos;
  } catch (e) {
    if (!callado) $('#principal').innerHTML = `<div class="vacio">No se pudo cargar la tienda. ${esc(e.message)}</div>`;
    return false;
  }
  const c = E.cfg;
  if (PAGINA) document.title = c.nombre;
  $('#nombre').textContent = c.nombre; $('#lema').textContent = c.lema || ''; $('#ini').textContent = iniciales(c.nombre).slice(0, 1);
  const color = (SCRIPT && SCRIPT.dataset.color) || c.color || '#6c4cf1';   // data-color: el color del diseño manda
  HOST.style.setProperty('--marca', color);
  const hex = color.replace('#', ''), lum = (0.299 * parseInt(hex.slice(0, 2), 16) + 0.587 * parseInt(hex.slice(2, 4), 16) + 0.114 * parseInt(hex.slice(4, 6), 16)) / 255;
  HOST.style.setProperty('--marca-tx', lum > 0.62 ? '#1c1b22' : '#fff');
  $('#aviso').hidden = !c.aviso; $('#aviso').textContent = c.aviso || '';
  const prueba = DEMO ? 'Tienda de demostración: los productos y pagos son de prueba.' : E.pagos === 'simulado' ? 'Modo prueba: los pagos son simulados, no se cobra nada.' : '';
  $('#prueba').hidden = !prueba; $('#prueba').textContent = prueba;
  // el carrito solo guarda lo que sigue a la venta
  E.carrito = E.carrito.filter(l => prod(l.id)).map(l => ({ ...l, cantidad: Math.min(l.cantidad, maximo(prod(l.id))) })).filter(l => l.cantidad > 0);
  guardarCarrito(); if (!SOLO_CARRITO) vPie();
  return true;
}
// Para un diseño propio (data-modo="carrito"): dibuja sus productos y usa esto.
let avisarListo;
window.Tienda = {
  listo: new Promise(r => { avisarListo = r; }),
  productos: () => E.prods.slice(),
  config: () => E.cfg,
  agregar: (id, n) => agregar(id, Math.max(1, Math.floor(n || 1))),
  abrirCarrito: () => vCarrito(),
  cantidad: () => enCarrito(),
  disponible: id => { const p = prod(id); return p ? maximo(p) : 0; },
  whatsapp: texto => E.cfg && E.cfg.whatsapp ? `https://wa.me/${E.cfg.whatsapp}?text=${encodeURIComponent(texto || '')}` : '',
};
(async () => {
  if (!(await cargar())) { avisarListo({ productos: [], config: null, pagos: '', error: true }); return; }
  avisarListo({ productos: E.prods.slice(), config: E.cfg, pagos: E.pagos });
  if (new URLSearchParams(location.search).get('pedido')) vResultado(); else if (!SOLO_CARRITO) vCatalogo();
})();
})();
