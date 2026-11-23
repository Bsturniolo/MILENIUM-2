"""Tienda online propia: catálogo, carrito, cobro con Mercado Pago y panel para manejarla.

Qué hace:
- Muestra la tienda en "/" (productos con fotos, buscador, carrito y compra).
- Panel en "/panel" (con clave) para cargar productos, fotos, precios y stock, ver pedidos y configurar la tienda.
- Cobra con Mercado Pago (Checkout Pro). Sin cuenta configurada, el pago es SIMULADO para poder probar todo.
- Cuando un pedido queda pagado, descuenta el stock y, si está configurado, avisa a otro sistema
  (por ejemplo Milenium 2) para que lo registre como venta. Si ese sistema no responde, reintenta solo.

Funciona sola: la conexión con otro sistema es opcional.

Cómo se corre (desarrollo):
    pip install -r requirements.txt
    TIENDA_ADMIN_TOKEN=una-clave-larga-de-prueba uvicorn app:app --reload
    (tienda en http://localhost:8000 · panel en http://localhost:8000/panel)
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import logging
import os
import pathlib
import re
import secrets
import sqlite3
import threading
import time
import urllib.error
import urllib.request
from typing import Callable, Optional

from fastapi import BackgroundTasks, Depends, FastAPI, Header, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

try:  # funciona como paquete (tests) y como script (uvicorn app:app)
    from . import mercadopago as mp_mod
except ImportError:  # pragma: no cover
    import mercadopago as mp_mod

log = logging.getLogger("tienda")
AQUI = pathlib.Path(__file__).resolve().parent
WEB = AQUI.parent / "web"
MINUTOS_RESERVA = 30        # un pedido sin pagar "aparta" el stock durante 30 minutos
MAX_INTENTOS_AVISO = 20     # avisos al otro sistema: después de 20 intentos queda en "error"
SEGUNDOS_REINTENTO = 60
MAX_FOTO_BYTES = 3_000_000
ESTADOS = ("esperando_pago", "pagado", "enviado", "entregado", "cancelado")


def ahora_ms() -> int:
    return int(time.time() * 1000)


def r2(x) -> float:
    return round(float(x or 0) + 0.0, 2)


ESQUEMA = """
CREATE TABLE IF NOT EXISTS config (
  clave TEXT PRIMARY KEY,
  valor TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS productos (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  codigo TEXT NOT NULL DEFAULT '',            -- SKU o código de barras (sirve para conectar con otro sistema)
  nombre TEXT NOT NULL,
  descripcion TEXT NOT NULL DEFAULT '',
  categoria TEXT NOT NULL DEFAULT '',
  precio REAL NOT NULL,
  precio_antes REAL NOT NULL DEFAULT 0,       -- precio tachado (oferta); 0 = sin oferta
  stock REAL NOT NULL DEFAULT 0,
  controla_stock INTEGER NOT NULL DEFAULT 1,
  fotos TEXT NOT NULL DEFAULT '[]',           -- JSON: lista de direcciones
  visible INTEGER NOT NULL DEFAULT 1,
  destacado INTEGER NOT NULL DEFAULT 0,
  activo INTEGER NOT NULL DEFAULT 1,
  modificado INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS productos_codigo ON productos (codigo);
CREATE TABLE IF NOT EXISTS pedidos (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  numero TEXT UNIQUE,
  token TEXT NOT NULL,                        -- para que solo quien compró vea su pedido
  ts INTEGER NOT NULL,
  estado TEXT NOT NULL DEFAULT 'esperando_pago',
  items TEXT NOT NULL,                        -- JSON
  subtotal REAL NOT NULL,
  envio REAL NOT NULL DEFAULT 0,
  envio_nombre TEXT NOT NULL DEFAULT '',
  total REAL NOT NULL,
  cliente TEXT NOT NULL DEFAULT '{}',         -- JSON
  pago_id TEXT NOT NULL DEFAULT '',
  pago_medio TEXT NOT NULL DEFAULT '',
  pago_ts INTEGER,
  mp_preferencia TEXT NOT NULL DEFAULT '',
  aviso_estado TEXT NOT NULL DEFAULT 'no',    -- no | pendiente | ok | error (aviso al otro sistema)
  aviso_intentos INTEGER NOT NULL DEFAULT 0,
  aviso_error TEXT NOT NULL DEFAULT '',
  modificado INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS pedidos_estado ON pedidos (estado);
CREATE TABLE IF NOT EXISTS movimientos (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  ts INTEGER NOT NULL,
  producto_id INTEGER NOT NULL REFERENCES productos(id),
  cantidad REAL NOT NULL,
  motivo TEXT NOT NULL,
  saldo REAL NOT NULL
);
"""

CONFIG_INICIAL = {
    "nombre": "Mi tienda",
    "lema": "",
    "whatsapp": "",           # con código de país, solo números (ej: 5492611234567)
    "instagram": "",
    "email": "",
    "aviso": "",              # cartel arriba de todo (ej: "Envíos a todo Mendoza")
    "color": "#6c4cf1",
    "instrucciones_pago": "",  # sin Mercado Pago: cómo pagar (alias, CBU, efectivo al retirar)
    "envios": [{"id": "retiro", "nombre": "Retiro en el local", "precio": 0, "pide_direccion": False, "detalle": ""}],
}


class Base:
    def __init__(self, ruta: str):
        self.con = sqlite3.connect(ruta, check_same_thread=False, isolation_level=None)
        self.con.row_factory = sqlite3.Row
        self.con.execute("PRAGMA foreign_keys = ON")
        self.con.executescript(ESQUEMA)
        self.lock = threading.RLock()

    def q(self, sql: str, args=()):
        with self.lock:
            return self.con.execute(sql, args).fetchall()

    def uno(self, sql: str, args=()):
        f = self.q(sql, args)
        return f[0] if f else None

    def ejec(self, sql: str, args=()):
        with self.lock:
            return self.con.execute(sql, args)


# ---------------------------------------------------------------- modelos
class Envio(BaseModel):
    id: str = Field(min_length=1, max_length=30, pattern=r"^[a-z0-9_-]+$")
    nombre: str = Field(min_length=1, max_length=80)
    precio: float = Field(ge=0)
    pide_direccion: bool = False
    detalle: str = Field(default="", max_length=200)


class Config(BaseModel):
    nombre: str = Field(min_length=1, max_length=80)
    lema: str = Field(default="", max_length=160)
    whatsapp: str = Field(default="", max_length=20, pattern=r"^\d*$")
    instagram: str = Field(default="", max_length=60)
    email: str = Field(default="", max_length=120)
    aviso: str = Field(default="", max_length=200)
    color: str = Field(default="#6c4cf1", pattern=r"^#[0-9a-fA-F]{6}$")
    instrucciones_pago: str = Field(default="", max_length=600)
    envios: list[Envio] = Field(min_length=1, max_length=10)


class Producto(BaseModel):
    codigo: str = Field(default="", max_length=60)
    nombre: str = Field(min_length=1, max_length=160)
    descripcion: str = Field(default="", max_length=4000)
    categoria: str = Field(default="", max_length=60)
    precio: float = Field(gt=0)
    precio_antes: float = Field(default=0, ge=0)
    stock: float = Field(default=0, ge=0)
    controla_stock: bool = True
    fotos: list[str] = Field(default_factory=list, max_length=8)
    visible: bool = True
    destacado: bool = False


class CambiosProducto(BaseModel):
    codigo: Optional[str] = Field(default=None, max_length=60)
    nombre: Optional[str] = Field(default=None, min_length=1, max_length=160)
    descripcion: Optional[str] = Field(default=None, max_length=4000)
    categoria: Optional[str] = Field(default=None, max_length=60)
    precio: Optional[float] = Field(default=None, gt=0)
    precio_antes: Optional[float] = Field(default=None, ge=0)
    controla_stock: Optional[bool] = None
    fotos: Optional[list[str]] = Field(default=None, max_length=8)
    visible: Optional[bool] = None
    destacado: Optional[bool] = None


class AjusteStock(BaseModel):
    cantidad: float                               # positivo suma, negativo resta
    motivo: str = Field(min_length=1, max_length=120)


class ProductoSync(BaseModel):
    codigo: str = Field(min_length=1, max_length=60)
    nombre: str = Field(min_length=1, max_length=160)
    precio: float = Field(gt=0)
    stock: Optional[float] = Field(default=None, ge=0)
    categoria: Optional[str] = Field(default=None, max_length=60)


class Sincronizar(BaseModel):
    productos: list[ProductoSync] = Field(max_length=5000)
    crear_nuevos: bool = True                     # los que no existen se crean ocultos, para revisarlos


class Foto(BaseModel):
    data_url: str = Field(max_length=MAX_FOTO_BYTES * 2)


class ItemCompra(BaseModel):
    producto_id: int
    cantidad: int = Field(ge=1, le=999)


class Cliente(BaseModel):
    nombre: str = Field(min_length=2, max_length=120)
    email: str = Field(min_length=5, max_length=160, pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
    telefono: str = Field(min_length=6, max_length=40)
    direccion: str = Field(default="", max_length=300)
    notas: str = Field(default="", max_length=500)


class Compra(BaseModel):
    volver: str = Field(default="", max_length=300)   # página desde donde se compró (si el carrito está pegado en otra página)
    items: list[ItemCompra] = Field(min_length=1, max_length=100)
    envio_id: str = Field(min_length=1, max_length=30)
    cliente: Cliente


class Token(BaseModel):
    t: str = Field(min_length=10, max_length=80)


class CambioEstado(BaseModel):
    estado: str = Field(pattern="^(pagado|enviado|entregado|cancelado)$")


# ---------------------------------------------------------------- aviso a otro sistema (Milenium 2, etc.)
def enviar_aviso_http(url: str, clave: str, cuerpo: bytes) -> None:
    """Manda el pedido firmado (HMAC-SHA256 del cuerpo, en X-Firma). Formato de docs/TIENDA-WEB.md de Milenium 2."""
    firma = hmac.new(clave.encode(), cuerpo, hashlib.sha256).hexdigest()
    req = urllib.request.Request(url, data=cuerpo, method="POST",
                                 headers={"Content-Type": "application/json", "X-Firma": firma})
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            r.read()
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"El sistema respondió {e.code}")
    except (urllib.error.URLError, TimeoutError) as e:
        raise RuntimeError(f"No se pudo conectar: {e}")


# ---------------------------------------------------------------- app
def crear_app(ruta_base: str | None = None, *, admin_token: str | None = None, mp=None,
              enviar_aviso: Callable[[str, str, bytes], None] | None = None,
              carpeta_fotos: str | None = None, reintentos_en_fondo: bool = True,
              prueba: bool | None = None, conectar: tuple[str, str] | None = None) -> FastAPI:
    base = Base(ruta_base or os.environ.get("TIENDA_DB", "tienda.db"))
    token = admin_token or os.environ.get("TIENDA_ADMIN_TOKEN", "")
    if len(token) < 16:
        raise RuntimeError("Definí TIENDA_ADMIN_TOKEN con al menos 16 caracteres")
    if mp is None and os.environ.get("MP_ACCESS_TOKEN"):
        mp = mp_mod.MercadoPago(os.environ["MP_ACCESS_TOKEN"])
    mp_secreto = os.environ.get("MP_WEBHOOK_SECRETO", "")
    # Cómo se cobra: "mercadopago" (con cuenta), "simulado" (solo para probar: TIENDA_PRUEBA=1)
    # o "manual" (sin Mercado Pago: el pedido queda esperando y se marca pagado a mano, ej. transferencia).
    modo_pago = "mercadopago" if mp else ("simulado" if (prueba if prueba is not None else os.environ.get("TIENDA_PRUEBA") == "1") else "manual")
    minutos_reserva = MINUTOS_RESERVA if modo_pago != "manual" else 48 * 60
    url_publica = os.environ.get("TIENDA_URL", "").rstrip("/")
    prefijo = re.sub(r"[^A-Za-z0-9]", "", os.environ.get("TIENDA_PREFIJO", "W"))[:6] or "W"
    conectar_url, conectar_clave = conectar or (os.environ.get("CONECTAR_URL", "").strip(), os.environ.get("CONECTAR_CLAVE", "").strip())
    conectado = bool(conectar_url and len(conectar_clave) >= 16)
    mandar = enviar_aviso or enviar_aviso_http
    fotos_dir = pathlib.Path(carpeta_fotos or os.environ.get("TIENDA_FOTOS",
                             str(pathlib.Path(ruta_base or os.environ.get("TIENDA_DB", "tienda.db")).resolve().parent / "fotos")))
    fotos_dir.mkdir(parents=True, exist_ok=True)

    app = FastAPI(title="Tienda")
    app.state.base = base

    # Si la página de la tienda se publica en otro lado (ej. GitHub Pages), agregar ese origen acá.
    origenes = [o.strip() for o in os.environ.get("TIENDA_ORIGENES", "").split(",") if o.strip()]
    if origenes:
        app.add_middleware(CORSMiddleware, allow_origins=origenes, allow_methods=["GET", "POST"],
                           allow_headers=["Content-Type"])

    # ---------- utilidades
    def admin(authorization: str = Header(default="")):
        if not hmac.compare_digest(authorization or "", f"Bearer {token}"):
            raise HTTPException(401, "Falta la clave del panel o es incorrecta")

    def config() -> dict:
        f = base.uno("SELECT valor FROM config WHERE clave = 'tienda'")
        return {**CONFIG_INICIAL, **(json.loads(f["valor"]) if f else {})}

    def vista_producto(p, reservado: float = 0) -> dict:
        disp = max(0.0, p["stock"] - reservado) if p["controla_stock"] else None
        return {"id": p["id"], "codigo": p["codigo"], "nombre": p["nombre"], "descripcion": p["descripcion"],
                "categoria": p["categoria"], "precio": p["precio"], "precio_antes": p["precio_antes"],
                "stock": p["stock"], "disponible": disp, "controla_stock": bool(p["controla_stock"]),
                "fotos": json.loads(p["fotos"]), "visible": bool(p["visible"]), "destacado": bool(p["destacado"]),
                "activo": bool(p["activo"]), "modificado": p["modificado"]}

    def vista_pedido(p, privado: bool = True) -> dict:
        d = {"numero": p["numero"], "ts": p["ts"], "estado": p["estado"], "items": json.loads(p["items"]),
             "subtotal": p["subtotal"], "envio": p["envio"], "envio_nombre": p["envio_nombre"], "total": p["total"],
             "pago_medio": p["pago_medio"], "pago_ts": p["pago_ts"]}
        if privado:
            d.update({"id": p["id"], "cliente": json.loads(p["cliente"]), "pago_id": p["pago_id"],
                      "aviso_estado": p["aviso_estado"], "aviso_intentos": p["aviso_intentos"],
                      "aviso_error": p["aviso_error"], "modificado": p["modificado"]})
        return d

    def reservas() -> dict[int, float]:
        """Unidades apartadas por pedidos sin pagar de los últimos 30 minutos."""
        desde = ahora_ms() - minutos_reserva * 60_000
        r: dict[int, float] = {}
        for p in base.q("SELECT items FROM pedidos WHERE estado = 'esperando_pago' AND ts > ?", (desde,)):
            for i in json.loads(p["items"]):
                r[i["producto_id"]] = r.get(i["producto_id"], 0) + i["cantidad"]
        return r

    def mover_stock(producto_id: int, cantidad: float, motivo: str) -> None:
        p = base.uno("SELECT stock, controla_stock FROM productos WHERE id = ?", (producto_id,))
        if not p or not p["controla_stock"] or not cantidad:
            return
        saldo = round(p["stock"] + cantidad, 3)
        base.ejec("UPDATE productos SET stock = ?, modificado = ? WHERE id = ?", (saldo, ahora_ms(), producto_id))
        base.ejec("INSERT INTO movimientos (ts, producto_id, cantidad, motivo, saldo) VALUES (?,?,?,?,?)",
                  (ahora_ms(), producto_id, cantidad, motivo, saldo))

    def pedido_o_404(numero: str):
        p = base.uno("SELECT * FROM pedidos WHERE numero = ?", (numero,))
        if not p:
            raise HTTPException(404, "No existe ese pedido")
        return p

    def pedido_con_token(numero: str, t: str):
        p = pedido_o_404(numero)
        if not hmac.compare_digest(p["token"], t or ""):
            raise HTTPException(404, "No existe ese pedido")
        return p

    # ---------- pago aprobado: descuenta stock y avisa al otro sistema
    def marcar_pagado(numero: str, pago_id: str, medio: str) -> bool:
        with base.lock:
            cur = base.ejec("UPDATE pedidos SET estado = 'pagado', pago_id = ?, pago_medio = ?, pago_ts = ?, modificado = ?,"
                            " aviso_estado = ? WHERE numero = ? AND estado = 'esperando_pago'",
                            (pago_id, medio, ahora_ms(), ahora_ms(), "pendiente" if conectado else "no", numero))
            if cur.rowcount == 0:
                return False  # ya estaba pagado (aviso repetido) o cancelado
            p = pedido_o_404(numero)
            for i in json.loads(p["items"]):
                mover_stock(i["producto_id"], -i["cantidad"], f"Venta web {numero}")
        return True

    def avisar(numero: str) -> None:
        p = base.uno("SELECT * FROM pedidos WHERE numero = ?", (numero,))
        if not p or p["aviso_estado"] not in ("pendiente", "error") or not conectado:
            return
        c = json.loads(p["cliente"])
        cuerpo = json.dumps({
            "pedido_id": p["numero"], "fecha_ms": p["pago_ts"] or p["ts"],
            "items": [{"codigo": i["codigo"], "nombre": i["nombre"], "cantidad": i["cantidad"], "precio": i["precio"]}
                      for i in json.loads(p["items"])],
            "envio": p["envio"], "descuento": 0, "total": p["total"], "medio_pago": p["pago_medio"] or "Tienda web",
            "cliente": {"nombre": c.get("nombre", ""), "email": c.get("email", ""), "telefono": c.get("telefono", "")},
        }, ensure_ascii=False).encode()
        try:
            mandar(conectar_url, conectar_clave, cuerpo)
            base.ejec("UPDATE pedidos SET aviso_estado = 'ok', aviso_error = '', aviso_intentos = aviso_intentos + 1 WHERE id = ?", (p["id"],))
        except Exception as e:  # queda para reintentar
            intentos = p["aviso_intentos"] + 1
            estado = "error" if intentos >= MAX_INTENTOS_AVISO else "pendiente"
            base.ejec("UPDATE pedidos SET aviso_estado = ?, aviso_error = ?, aviso_intentos = ? WHERE id = ?",
                      (estado, str(e)[:300], intentos, p["id"]))
            log.warning("No se pudo avisar el pedido %s: %s", numero, e)

    def reintentar_avisos() -> None:
        for p in base.q("SELECT numero FROM pedidos WHERE aviso_estado = 'pendiente' ORDER BY id LIMIT 50"):
            avisar(p["numero"])

    app.state.reintentar_avisos = reintentar_avisos

    if reintentos_en_fondo and conectado:
        def bucle():
            while True:
                time.sleep(SEGUNDOS_REINTENTO)
                try:
                    reintentar_avisos()
                except Exception:  # pragma: no cover
                    log.exception("Error reintentando avisos")
        threading.Thread(target=bucle, daemon=True).start()

    def aplicar_pago_mp(pago_id: str) -> str:
        """Pregunta a Mercado Pago por el pago y, si está aprobado y coincide, marca el pedido pagado."""
        if not mp:
            raise HTTPException(409, "Mercado Pago no está configurado")
        try:
            pago = mp.pago(pago_id)
        except mp_mod.ErrorMP as e:
            log.warning("No se pudo consultar el pago %s: %s", pago_id, e)
            raise HTTPException(502, str(e))
        numero = str(pago.get("external_reference") or "")
        p = base.uno("SELECT * FROM pedidos WHERE numero = ?", (numero,))
        if not p:
            return "pedido_desconocido"
        if pago.get("status") != "approved":
            return "no_aprobado"
        if pago.get("currency_id", "ARS") != "ARS" or abs(float(pago.get("transaction_amount") or 0) - p["total"]) > 0.01:
            log.warning("El pago %s no coincide con el pedido %s", pago_id, numero)
            return "monto_distinto"
        medio = {"credit_card": "Tarjeta de crédito", "debit_card": "Tarjeta de débito", "account_money": "Dinero en Mercado Pago",
                 "ticket": "Efectivo (Pago Fácil / Rapipago)", "bank_transfer": "Transferencia"}.get(pago.get("payment_type_id"), "")
        if marcar_pagado(numero, str(pago_id), "Mercado Pago" + (f" · {medio}" if medio else "")):
            avisar(numero)
            return "pagado"
        return "ya_estaba"

    # ---------- páginas
    @app.get("/salud", include_in_schema=False)
    def salud():
        base.uno("SELECT 1")
        return {"ok": True}

    @app.get("/", include_in_schema=False)
    def tienda():
        return FileResponse(WEB / "index.html", media_type="text/html")

    @app.get("/tienda.js", include_in_schema=False)
    def tienda_js():
        return FileResponse(WEB / "tienda.js", media_type="text/javascript", headers={"Cache-Control": "no-cache"})

    @app.get("/panel", include_in_schema=False)
    def panel():
        return FileResponse(WEB / "panel.html", media_type="text/html")

    @app.get("/fotos/{nombre}", include_in_schema=False)
    def foto(nombre: str):
        if not re.fullmatch(r"[a-f0-9]{24}\.(jpg|png|webp)", nombre):
            raise HTTPException(404)
        ruta = fotos_dir / nombre
        if not ruta.exists():
            raise HTTPException(404)
        return FileResponse(ruta, headers={"Cache-Control": "public, max-age=31536000, immutable"})

    # ---------- lo que ve el público
    @app.get("/api/tienda")
    def datos_tienda():
        res = reservas()
        prods = [vista_producto(p, res.get(p["id"], 0)) for p in
                 base.q("SELECT * FROM productos WHERE activo = 1 AND visible = 1 ORDER BY destacado DESC, nombre")]
        for p in prods:
            for k in ("stock", "visible", "activo", "modificado"):
                p.pop(k)
        return {"config": config(), "productos": prods, "pagos": modo_pago}

    @app.post("/api/pedidos")
    def comprar(d: Compra, request: Request):
        cfg = config()
        envio = next((e for e in cfg["envios"] if e["id"] == d.envio_id), None)
        if not envio:
            raise HTTPException(422, "Elegí cómo recibir el pedido")
        if envio.get("pide_direccion") and len(d.cliente.direccion.strip()) < 5:
            raise HTTPException(422, "Falta la dirección de entrega")
        cant: dict[int, int] = {}
        for i in d.items:
            cant[i.producto_id] = cant.get(i.producto_id, 0) + i.cantidad
        with base.lock:  # para que dos compras al mismo tiempo no se lleven el mismo stock
            res = reservas()
            items = []
            for pid, n in cant.items():
                p = base.uno("SELECT * FROM productos WHERE id = ? AND activo = 1 AND visible = 1", (pid,))
                if not p:
                    raise HTTPException(409, "Un producto del carrito ya no está a la venta. Actualizá la página.")
                if p["controla_stock"] and n > p["stock"] - res.get(pid, 0):
                    disp = max(0, int(p["stock"] - res.get(pid, 0)))
                    raise HTTPException(409, f"De \"{p['nombre']}\" quedan {disp}." if disp else f"\"{p['nombre']}\" se agotó.")
                items.append({"producto_id": pid, "codigo": p["codigo"], "nombre": p["nombre"], "precio": r2(p["precio"]), "cantidad": n})
            subtotal = r2(sum(i["precio"] * i["cantidad"] for i in items))
            total = r2(subtotal + envio["precio"])
            tk = secrets.token_urlsafe(18)
            cliente = d.cliente.model_dump()
            cliente = {k: v.strip() for k, v in cliente.items()}
            cur = base.ejec("INSERT INTO pedidos (token, ts, items, subtotal, envio, envio_nombre, total, cliente, modificado)"
                            " VALUES (?,?,?,?,?,?,?,?,?)",
                            (tk, ahora_ms(), json.dumps(items, ensure_ascii=False), subtotal, r2(envio["precio"]),
                             envio["nombre"], total, json.dumps(cliente, ensure_ascii=False), ahora_ms()))
            numero = f"{prefijo}-{cur.lastrowid:05d}"
            base.ejec("UPDATE pedidos SET numero = ? WHERE id = ?", (numero, cur.lastrowid))
        pedido = {"numero": numero, "token": tk, "items": items, "envio": r2(envio["precio"]), "envio_nombre": envio["nombre"],
                  "total": total, "cliente": cliente}
        url_tienda = (url_publica or str(request.base_url).rstrip("/")) + "/"
        # Si el carrito está pegado en otra página (autorizada en TIENDA_ORIGENES), después de pagar se vuelve ahí.
        m = re.match(r"(https?://[^/?#]+)(/[^?#]*)?", d.volver.strip())
        url_volver = (m.group(1) + (m.group(2) or "/")) if m and m.group(1) in origenes else url_tienda
        if mp:
            try:
                pref = mp.crear_preferencia(pedido, url_volver, url_tienda + "mp/aviso")
            except mp_mod.ErrorMP as e:
                base.ejec("UPDATE pedidos SET estado = 'cancelado', modificado = ? WHERE numero = ?", (ahora_ms(), numero))
                log.error("No se pudo crear el cobro del pedido %s: %s", numero, e)
                raise HTTPException(502, "No se pudo iniciar el pago con Mercado Pago. Probá de nuevo en un rato.")
            base.ejec("UPDATE pedidos SET mp_preferencia = ? WHERE numero = ?", (pref["id"], numero))
            return {"numero": numero, "t": tk, "total": total, "pagar_url": pref["url"], "pagos": "mercadopago"}
        return {"numero": numero, "t": tk, "total": total, "pagar_url": None, "pagos": modo_pago}

    @app.get("/api/pedidos/{numero}")
    def ver_pedido(numero: str, t: str = "", payment_id: str = ""):
        p = pedido_con_token(numero, t)
        # Al volver de Mercado Pago: si el aviso todavía no llegó, se confirma preguntando por el pago.
        if p["estado"] == "esperando_pago" and payment_id and mp:
            try:
                aplicar_pago_mp(payment_id)
            except HTTPException:
                pass
            p = pedido_o_404(numero)
        return vista_pedido(p, privado=False)

    @app.post("/api/pedidos/{numero}/pago-simulado")
    def pago_simulado(numero: str, d: Token, fondo: BackgroundTasks):
        """Solo existe mientras no se configure Mercado Pago: hace lo mismo que un pago aprobado."""
        if modo_pago != "simulado":
            raise HTTPException(404, "Esta tienda no acepta pagos de prueba")
        p = pedido_con_token(numero, d.t)
        if p["estado"] == "esperando_pago":
            marcar_pagado(numero, "SIM-" + secrets.token_hex(4), "Mercado Pago (simulado)")
            fondo.add_task(avisar, numero)
        return vista_pedido(pedido_o_404(numero), privado=False)

    @app.post("/mp/aviso")
    async def aviso_mp(request: Request, fondo: BackgroundTasks):
        """Mercado Pago avisa acá cada cambio de un pago. Se confirma siempre consultando el pago."""
        qs = request.query_params
        try:
            cuerpo = json.loads((await request.body()) or b"{}")
        except ValueError:
            cuerpo = {}
        tipo = cuerpo.get("type") or cuerpo.get("topic") or qs.get("type") or qs.get("topic") or ""
        pago_id = str((cuerpo.get("data") or {}).get("id") or qs.get("data.id") or qs.get("id") or "")
        if tipo != "payment" or not pago_id:
            return {"ok": True, "ignorado": True}
        if mp_secreto and not mp_mod.firma_aviso_valida(mp_secreto, request.headers.get("x-signature", ""),
                                                        request.headers.get("x-request-id", ""), qs.get("data.id") or pago_id):
            raise HTTPException(401, "Firma inválida")
        fondo.add_task(lambda: _seguro(aplicar_pago_mp, pago_id))
        return {"ok": True}

    def _seguro(f, *a):
        try:
            f(*a)
        except Exception as e:  # pragma: no cover
            log.warning("Aviso de Mercado Pago: %s", e)

    # ---------- panel (con clave)
    @app.get("/api/panel/resumen", dependencies=[Depends(admin)])
    def resumen():
        ini_dia = ahora_ms() - (ahora_ms() + 3 * 3600_000) % 86_400_000   # medianoche de Argentina (UTC-3)
        def tot(desde):
            f = base.uno("SELECT COUNT(*) n, COALESCE(SUM(total),0) t FROM pedidos WHERE estado IN ('pagado','enviado','entregado') AND pago_ts >= ?", (desde,))
            return {"pedidos": f["n"], "total": r2(f["t"])}
        return {
            "hoy": tot(ini_dia), "ultimos_30": tot(ahora_ms() - 30 * 86_400_000),
            "para_preparar": base.uno("SELECT COUNT(*) n FROM pedidos WHERE estado = 'pagado'")["n"],
            "sin_stock": base.uno("SELECT COUNT(*) n FROM productos WHERE activo = 1 AND visible = 1 AND controla_stock = 1 AND stock <= 0")["n"],
            "pagos": modo_pago,
            "conexion": {"activa": conectado, "url": conectar_url,
                         "pendientes": base.uno("SELECT COUNT(*) n FROM pedidos WHERE aviso_estado = 'pendiente'")["n"],
                         "errores": base.uno("SELECT COUNT(*) n FROM pedidos WHERE aviso_estado = 'error'")["n"]},
        }

    @app.get("/api/panel/config", dependencies=[Depends(admin)])
    def leer_config():
        return config()

    @app.put("/api/panel/config", dependencies=[Depends(admin)])
    def guardar_config(d: Config):
        if len({e.id for e in d.envios}) != len(d.envios):
            raise HTTPException(422, "Hay dos formas de entrega con el mismo código")
        base.ejec("INSERT INTO config (clave, valor) VALUES ('tienda', ?) ON CONFLICT(clave) DO UPDATE SET valor = excluded.valor",
                  (json.dumps(d.model_dump(), ensure_ascii=False),))
        return config()

    @app.get("/api/panel/productos", dependencies=[Depends(admin)])
    def productos():
        res = reservas()
        return [vista_producto(p, res.get(p["id"], 0)) for p in base.q("SELECT * FROM productos WHERE activo = 1 ORDER BY nombre")]

    def codigo_libre(codigo: str, salvo: int = 0):
        if codigo and base.uno("SELECT 1 FROM productos WHERE codigo = ? AND activo = 1 AND id != ?", (codigo, salvo)):
            raise HTTPException(409, f"El código {codigo} ya está en otro producto")

    @app.post("/api/panel/productos", dependencies=[Depends(admin)])
    def crear_producto(d: Producto):
        codigo_libre(d.codigo.strip())
        cur = base.ejec("INSERT INTO productos (codigo, nombre, descripcion, categoria, precio, precio_antes, stock, controla_stock, fotos, visible, destacado, modificado)"
                        " VALUES (?,?,?,?,?,?,0,?,?,?,?,?)",
                        (d.codigo.strip(), d.nombre.strip(), d.descripcion, d.categoria.strip(), r2(d.precio), r2(d.precio_antes),
                         int(d.controla_stock), json.dumps(d.fotos), int(d.visible), int(d.destacado), ahora_ms()))
        if d.stock:
            mover_stock(cur.lastrowid, d.stock, "Stock inicial")
        return vista_producto(base.uno("SELECT * FROM productos WHERE id = ?", (cur.lastrowid,)))

    def producto_o_404(pid: int):
        p = base.uno("SELECT * FROM productos WHERE id = ? AND activo = 1", (pid,))
        if not p:
            raise HTTPException(404, "No existe ese producto")
        return p

    @app.patch("/api/panel/productos/{pid}", dependencies=[Depends(admin)])
    def cambiar_producto(pid: int, d: CambiosProducto):
        producto_o_404(pid)
        nuevo = {k: v for k, v in d.model_dump().items() if v is not None}
        if "codigo" in nuevo:
            nuevo["codigo"] = nuevo["codigo"].strip()
            codigo_libre(nuevo["codigo"], pid)
        if "fotos" in nuevo:
            nuevo["fotos"] = json.dumps(nuevo["fotos"])
        for k in ("controla_stock", "visible", "destacado"):
            if k in nuevo:
                nuevo[k] = int(nuevo[k])
        if nuevo:
            campos = ", ".join(f"{k} = ?" for k in nuevo)  # claves fijas del modelo
            base.ejec(f"UPDATE productos SET {campos}, modificado = ? WHERE id = ?", (*nuevo.values(), ahora_ms(), pid))
        return vista_producto(producto_o_404(pid))

    @app.delete("/api/panel/productos/{pid}", dependencies=[Depends(admin)])
    def borrar_producto(pid: int):
        producto_o_404(pid)
        base.ejec("UPDATE productos SET activo = 0, modificado = ? WHERE id = ?", (ahora_ms(), pid))  # los pedidos viejos no cambian
        return {"ok": True}

    @app.post("/api/panel/productos/{pid}/stock", dependencies=[Depends(admin)])
    def ajustar_stock(pid: int, d: AjusteStock):
        p = producto_o_404(pid)
        if p["stock"] + d.cantidad < 0:
            raise HTTPException(422, "El stock no puede quedar negativo")
        mover_stock(pid, d.cantidad, d.motivo)
        return vista_producto(producto_o_404(pid))

    @app.get("/api/panel/productos/{pid}/movimientos", dependencies=[Depends(admin)])
    def movimientos(pid: int):
        return [dict(m) for m in base.q("SELECT * FROM movimientos WHERE producto_id = ? ORDER BY id DESC LIMIT 100", (pid,))]

    @app.post("/api/panel/fotos", dependencies=[Depends(admin)])
    def subir_foto(d: Foto):
        m = re.fullmatch(r"data:image/(jpeg|png|webp);base64,([A-Za-z0-9+/=]+)", d.data_url)
        if not m:
            raise HTTPException(422, "La foto tiene que ser JPG, PNG o WEBP")
        datos = base64.b64decode(m.group(2))
        if len(datos) > MAX_FOTO_BYTES:
            raise HTTPException(413, "La foto es muy pesada (máximo 3 MB)")
        firmas = {"jpeg": b"\xff\xd8", "png": b"\x89PNG", "webp": b"RIFF"}
        if not datos.startswith(firmas[m.group(1)]):
            raise HTTPException(422, "El archivo no es una imagen válida")
        nombre = secrets.token_hex(12) + "." + {"jpeg": "jpg"}.get(m.group(1), m.group(1))
        (fotos_dir / nombre).write_bytes(datos)
        return {"url": "/fotos/" + nombre}

    @app.put("/api/panel/sincronizar", dependencies=[Depends(admin)])
    def sincronizar(d: Sincronizar):
        """Para otro sistema (Milenium 2 u otro): actualiza precio y stock por código. Los nuevos se crean ocultos."""
        actualizados = creados = 0
        with base.lock:
            for s in d.productos:
                p = base.uno("SELECT * FROM productos WHERE codigo = ? AND activo = 1", (s.codigo,))
                if p:
                    base.ejec("UPDATE productos SET precio = ?, categoria = COALESCE(?, categoria), modificado = ? WHERE id = ?",
                              (r2(s.precio), s.categoria, ahora_ms(), p["id"]))
                    if s.stock is not None and p["controla_stock"] and round(s.stock - p["stock"], 3):
                        mover_stock(p["id"], round(s.stock - p["stock"], 3), "Sincronizado desde el sistema")
                    actualizados += 1
                elif d.crear_nuevos:
                    cur = base.ejec("INSERT INTO productos (codigo, nombre, categoria, precio, visible, modificado) VALUES (?,?,?,?,0,?)",
                                    (s.codigo, s.nombre, s.categoria or "", r2(s.precio), ahora_ms()))
                    if s.stock:
                        mover_stock(cur.lastrowid, s.stock, "Sincronizado desde el sistema")
                    creados += 1
        return {"actualizados": actualizados, "creados": creados}

    @app.get("/api/panel/pedidos", dependencies=[Depends(admin)])
    def pedidos(estado: Optional[str] = None, limite: int = 300):
        if estado and estado not in ESTADOS:
            raise HTTPException(422, "Estado inválido")
        sql = "SELECT * FROM pedidos WHERE numero IS NOT NULL" + (" AND estado = ?" if estado else "") + " ORDER BY id DESC LIMIT ?"
        return [vista_pedido(p) for p in base.q(sql, ((estado,) if estado else ()) + (min(max(limite, 1), 2000),))]

    @app.post("/api/panel/pedidos/{numero}/estado", dependencies=[Depends(admin)])
    def cambiar_estado(numero: str, d: CambioEstado, fondo: BackgroundTasks):
        p = pedido_o_404(numero)
        if p["estado"] == d.estado:
            return vista_pedido(p)
        if p["estado"] == "cancelado":
            raise HTTPException(409, "El pedido está cancelado")
        if d.estado == "pagado":
            # Pago cobrado por fuera (transferencia, efectivo): se marca a mano.
            if p["estado"] != "esperando_pago":
                raise HTTPException(409, "El pedido ya estaba pagado")
            marcar_pagado(numero, "", "Marcado a mano")
            fondo.add_task(avisar, numero)
        elif d.estado == "cancelado":
            with base.lock:
                if p["estado"] != "esperando_pago":  # estaba pagado: devuelve el stock
                    for i in json.loads(p["items"]):
                        mover_stock(i["producto_id"], i["cantidad"], f"Pedido {numero} cancelado")
                base.ejec("UPDATE pedidos SET estado = 'cancelado', modificado = ? WHERE id = ?", (ahora_ms(), p["id"]))
        else:
            if p["estado"] == "esperando_pago":
                raise HTTPException(409, "El pedido todavía no está pagado")
            base.ejec("UPDATE pedidos SET estado = ?, modificado = ? WHERE id = ?", (d.estado, ahora_ms(), p["id"]))
        return vista_pedido(pedido_o_404(numero))

    @app.post("/api/panel/pedidos/{numero}/reavisar", dependencies=[Depends(admin)])
    def reavisar(numero: str):
        p = pedido_o_404(numero)
        if not conectado:
            raise HTTPException(409, "No hay ningún sistema conectado")
        if p["aviso_estado"] in ("pendiente", "error"):
            base.ejec("UPDATE pedidos SET aviso_estado = 'pendiente', aviso_intentos = 0 WHERE id = ?", (p["id"],))
            avisar(numero)
        return vista_pedido(pedido_o_404(numero))

    return app


if os.environ.get("TIENDA_ADMIN_TOKEN"):  # para `uvicorn app:app`
    logging.basicConfig(level=logging.INFO)
    app = crear_app()
