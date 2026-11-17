"""Servidor de Milenium 2 para los módulos que controlan las máquinas.

Qué hace:
- Guarda los equipos (lavarropas, cafeteras, etc.) y su estado.
- Vincula cada módulo físico a un equipo con un código de 6 dígitos que vence.
- Cuando se cobra un uso, deja una orden firmada para el módulo de ese equipo.
- Recibe del módulo latidos, inicio y fin de uso, y alertas (uso sin pago, tapa abierta).

Cómo se corre (desarrollo):
    pip install -r requirements.txt
    MILENIUM_ADMIN_TOKEN=un-token-largo uvicorn app:app --reload

En producción tiene que ir detrás de HTTPS.
"""
from __future__ import annotations

import json
import os
import secrets
import sqlite3
import threading
import time
from typing import Optional

from fastapi import Depends, FastAPI, Header, HTTPException, Request
from pydantic import BaseModel, Field

try:  # funciona como paquete (tests) y como script (uvicorn app:app)
    from . import firmas
except ImportError:  # pragma: no cover
    import firmas

# ---------------------------------------------------------------- configuración
SEGUNDOS_CONECTADO = 90          # sin latido en este tiempo, el módulo figura desconectado
VIGENCIA_CODIGO_MS = 10 * 60_000  # el código de vinculación dura 10 minutos
VIGENCIA_ORDEN_MS = 60_000        # una orden que el módulo no tomó en 1 minuto ya no sirve
DESFASE_MAX_MS = 120_000          # tolerancia de reloj entre módulo y servidor
MAX_SEGUNDOS_USO = 4 * 3600       # tope de seguridad por uso


def ahora_ms() -> int:
    return int(time.time() * 1000)


# ---------------------------------------------------------------- base de datos
ESQUEMA = """
CREATE TABLE IF NOT EXISTS equipos (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  nombre TEXT NOT NULL,
  modo TEXT NOT NULL CHECK (modo IN ('uso','minuto')),
  precio REAL NOT NULL,
  minutos INTEGER NOT NULL DEFAULT 30,
  estado TEXT NOT NULL DEFAULT 'libre' CHECK (estado IN ('libre','en_uso','fuera')),
  fin_ms INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS modulos (
  id TEXT PRIMARY KEY,
  equipo_id INTEGER NOT NULL UNIQUE REFERENCES equipos(id),
  secreto TEXT NOT NULL,
  ultimo_ts INTEGER NOT NULL DEFAULT 0,
  ultimo_contacto INTEGER NOT NULL DEFAULT 0,
  firmware TEXT
);
CREATE TABLE IF NOT EXISTS codigos (
  codigo TEXT PRIMARY KEY,
  equipo_id INTEGER NOT NULL REFERENCES equipos(id),
  expira_ms INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS ordenes (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  modulo_id TEXT NOT NULL REFERENCES modulos(id),
  accion TEXT NOT NULL CHECK (accion IN ('activar','detener')),
  segundos INTEGER NOT NULL DEFAULT 0,
  expira_ms INTEGER NOT NULL,
  entregada INTEGER NOT NULL DEFAULT 0,
  confirmada INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS pagos (
  ref TEXT PRIMARY KEY,
  equipo_id INTEGER NOT NULL REFERENCES equipos(id),
  medio TEXT NOT NULL,
  monto REAL NOT NULL,
  segundos INTEGER NOT NULL,
  ts INTEGER NOT NULL,
  orden_id INTEGER REFERENCES ordenes(id)
);
CREATE TABLE IF NOT EXISTS eventos (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  ts INTEGER NOT NULL,
  equipo_id INTEGER REFERENCES equipos(id),
  tipo TEXT NOT NULL,
  detalle TEXT NOT NULL DEFAULT '',
  alerta INTEGER NOT NULL DEFAULT 0
);
"""


class Base:
    def __init__(self, ruta: str):
        self.con = sqlite3.connect(ruta, check_same_thread=False, isolation_level=None)
        self.con.row_factory = sqlite3.Row
        self.con.execute("PRAGMA foreign_keys = ON")
        self.con.executescript(ESQUEMA)
        self.lock = threading.Lock()

    def q(self, sql: str, args=()):
        with self.lock:
            return self.con.execute(sql, args).fetchall()

    def uno(self, sql: str, args=()):
        filas = self.q(sql, args)
        return filas[0] if filas else None

    def ejec(self, sql: str, args=()) -> int:
        with self.lock:
            return self.con.execute(sql, args).lastrowid

    def evento(self, equipo_id, tipo, detalle="", alerta=False):
        self.ejec("INSERT INTO eventos (ts, equipo_id, tipo, detalle, alerta) VALUES (?,?,?,?,?)",
                  (ahora_ms(), equipo_id, tipo, detalle, 1 if alerta else 0))


# ---------------------------------------------------------------- modelos
class EquipoNuevo(BaseModel):
    nombre: str = Field(min_length=1, max_length=80)
    modo: str = Field(pattern="^(uso|minuto)$")
    precio: float = Field(gt=0)
    minutos: int = Field(default=30, ge=1, le=240)


class Activacion(BaseModel):
    pago_ref: str = Field(min_length=1, max_length=120)
    medio: str = Field(min_length=1, max_length=40)
    monto: float = Field(ge=0)
    minutos: Optional[int] = Field(default=None, ge=1, le=240)


class Servicio(BaseModel):
    fuera: bool


class Vinculo(BaseModel):
    codigo: str = Field(pattern=r"^\d{6}$")
    firmware: str = Field(default="", max_length=40)


class Reporte(BaseModel):
    tipo: str = Field(pattern="^(latido|inicio|fin|confirmacion|uso_sin_pago|tapa_abierta|reinicio)$")
    orden_id: Optional[int] = None
    segundos_restantes: Optional[int] = None
    detalle: str = Field(default="", max_length=200)


class PagoSimulado(BaseModel):
    equipo_id: int
    monto: float = Field(ge=0)
    minutos: Optional[int] = Field(default=None, ge=1, le=240)


# ---------------------------------------------------------------- app
def crear_app(ruta_base: str | None = None, token_admin: str | None = None) -> FastAPI:
    base = Base(ruta_base or os.environ.get("MILENIUM_DB", "milenium.db"))
    token = token_admin or os.environ.get("MILENIUM_ADMIN_TOKEN", "")
    if len(token) < 16:
        raise RuntimeError("Definí MILENIUM_ADMIN_TOKEN con al menos 16 caracteres")

    app = FastAPI(title="Milenium 2 · módulos")
    app.state.base = base

    # ---------- autenticación de la app (administrador)
    def admin(authorization: str = Header(default="")):
        if not firmas.iguales(authorization, f"Bearer {token}"):
            raise HTTPException(401, "Falta el token de administrador o es incorrecto")

    # ---------- autenticación del módulo (firma HMAC por pedido)
    async def modulo_firmado(request: Request,
                             x_modulo: str = Header(default=""),
                             x_ts: int = Header(default=0),
                             x_firma: str = Header(default="")):
        m = base.uno("SELECT * FROM modulos WHERE id = ?", (x_modulo,))
        if not m:
            raise HTTPException(401, "Módulo desconocido")
        cuerpo = await request.body()
        esperada = firmas.firma_pedido(m["secreto"], request.method, request.url.path, x_ts, cuerpo)
        if not firmas.iguales(x_firma, esperada):
            base.evento(m["equipo_id"], "firma_invalida", "Pedido con firma incorrecta", alerta=True)
            raise HTTPException(401, "Firma inválida")
        if abs(ahora_ms() - x_ts) > DESFASE_MAX_MS:
            raise HTTPException(401, "Reloj del módulo desfasado")
        if x_ts <= m["ultimo_ts"]:  # cada pedido lleva un ts mayor: un pedido copiado no sirve dos veces
            base.evento(m["equipo_id"], "pedido_repetido", "Se rechazó un pedido repetido", alerta=True)
            raise HTTPException(401, "Pedido repetido")
        base.ejec("UPDATE modulos SET ultimo_ts = ?, ultimo_contacto = ? WHERE id = ?", (x_ts, ahora_ms(), m["id"]))
        return m

    def conectado(m) -> bool:
        return bool(m) and ahora_ms() - m["ultimo_contacto"] < SEGUNDOS_CONECTADO * 1000

    def vista_equipo(e) -> dict:
        m = base.uno("SELECT * FROM modulos WHERE equipo_id = ?", (e["id"],))
        return {
            "id": e["id"], "nombre": e["nombre"], "modo": e["modo"], "precio": e["precio"],
            "minutos": e["minutos"], "estado": e["estado"], "fin_ms": e["fin_ms"],
            "modulo": None if not m else {"id": m["id"], "conectado": conectado(m), "ultimo_contacto": m["ultimo_contacto"], "firmware": m["firmware"]},
        }

    def equipo_o_404(equipo_id: int):
        e = base.uno("SELECT * FROM equipos WHERE id = ?", (equipo_id,))
        if not e:
            raise HTTPException(404, "No existe ese equipo")
        return e

    # ---------- rutas de la app
    @app.post("/api/equipos", dependencies=[Depends(admin)])
    def crear_equipo(d: EquipoNuevo):
        i = base.ejec("INSERT INTO equipos (nombre, modo, precio, minutos) VALUES (?,?,?,?)", (d.nombre, d.modo, d.precio, d.minutos))
        return vista_equipo(equipo_o_404(i))

    @app.get("/api/equipos", dependencies=[Depends(admin)])
    def listar_equipos():
        return [vista_equipo(e) for e in base.q("SELECT * FROM equipos ORDER BY nombre")]

    @app.post("/api/equipos/{equipo_id}/codigo", dependencies=[Depends(admin)])
    def codigo_vinculacion(equipo_id: int):
        equipo_o_404(equipo_id)
        base.ejec("DELETE FROM codigos WHERE equipo_id = ? OR expira_ms < ?", (equipo_id, ahora_ms()))
        while True:
            codigo = f"{secrets.randbelow(1_000_000):06d}"
            if not base.uno("SELECT 1 FROM codigos WHERE codigo = ?", (codigo,)):
                break
        expira = ahora_ms() + VIGENCIA_CODIGO_MS
        base.ejec("INSERT INTO codigos (codigo, equipo_id, expira_ms) VALUES (?,?,?)", (codigo, equipo_id, expira))
        return {"codigo": codigo, "expira_ms": expira}

    @app.post("/api/equipos/{equipo_id}/activar", dependencies=[Depends(admin)])
    def activar(equipo_id: int, d: Activacion):
        return _activar(equipo_id, d.pago_ref, d.medio, d.monto, d.minutos)

    def _activar(equipo_id, pago_ref, medio, monto, minutos):
        e = equipo_o_404(equipo_id)
        if e["estado"] == "fuera":
            raise HTTPException(409, "El equipo está fuera de servicio")
        if e["estado"] == "en_uso" and e["fin_ms"] > ahora_ms():
            raise HTTPException(409, "El equipo ya está funcionando")
        m = base.uno("SELECT * FROM modulos WHERE equipo_id = ?", (equipo_id,))
        if not m:
            raise HTTPException(409, "El equipo no tiene módulo vinculado")
        if not conectado(m):
            raise HTTPException(409, "El módulo del equipo está desconectado")
        if base.uno("SELECT 1 FROM pagos WHERE ref = ?", (pago_ref,)):
            raise HTTPException(409, "Ese pago ya se usó para activar un equipo")
        mins = minutos if (e["modo"] == "minuto" and minutos) else e["minutos"]
        segundos = min(mins * 60, MAX_SEGUNDOS_USO)
        orden = base.ejec("INSERT INTO ordenes (modulo_id, accion, segundos, expira_ms) VALUES (?,?,?,?)",
                          (m["id"], "activar", segundos, ahora_ms() + VIGENCIA_ORDEN_MS))
        base.ejec("INSERT INTO pagos (ref, equipo_id, medio, monto, segundos, ts, orden_id) VALUES (?,?,?,?,?,?,?)",
                  (pago_ref, equipo_id, medio, monto, segundos, ahora_ms(), orden))
        base.evento(equipo_id, "orden_activar", f"{segundos} s · {medio} · ${monto:.2f} · pago {pago_ref}")
        return {"orden_id": orden, "segundos": segundos}

    @app.post("/api/equipos/{equipo_id}/detener", dependencies=[Depends(admin)])
    def detener(equipo_id: int):
        equipo_o_404(equipo_id)
        m = base.uno("SELECT * FROM modulos WHERE equipo_id = ?", (equipo_id,))
        if not m:
            raise HTTPException(409, "El equipo no tiene módulo vinculado")
        orden = base.ejec("INSERT INTO ordenes (modulo_id, accion, segundos, expira_ms) VALUES (?,?,?,?)",
                          (m["id"], "detener", 0, ahora_ms() + VIGENCIA_ORDEN_MS))
        base.evento(equipo_id, "orden_detener")
        return {"orden_id": orden}

    @app.post("/api/equipos/{equipo_id}/servicio", dependencies=[Depends(admin)])
    def servicio(equipo_id: int, d: Servicio):
        e = equipo_o_404(equipo_id)
        if d.fuera and e["estado"] == "en_uso":
            detener(equipo_id)
        base.ejec("UPDATE equipos SET estado = ? WHERE id = ?", ("fuera" if d.fuera else "libre", equipo_id))
        base.evento(equipo_id, "fuera_de_servicio" if d.fuera else "en_servicio")
        return vista_equipo(equipo_o_404(equipo_id))

    @app.post("/api/equipos/{equipo_id}/desvincular", dependencies=[Depends(admin)])
    def desvincular(equipo_id: int):
        equipo_o_404(equipo_id)
        m = base.uno("SELECT id FROM modulos WHERE equipo_id = ?", (equipo_id,))
        if m:
            base.ejec("DELETE FROM ordenes WHERE modulo_id = ?", (m["id"],))
            base.ejec("DELETE FROM modulos WHERE id = ?", (m["id"],))
        base.evento(equipo_id, "modulo_desvinculado")
        return {"ok": True}

    @app.get("/api/eventos", dependencies=[Depends(admin)])
    def eventos(equipo_id: Optional[int] = None, solo_alertas: bool = False, limite: int = 100):
        sql, args = "SELECT * FROM eventos WHERE 1=1", []
        if equipo_id:
            sql += " AND equipo_id = ?"; args.append(equipo_id)
        if solo_alertas:
            sql += " AND alerta = 1"
        sql += " ORDER BY id DESC LIMIT ?"; args.append(min(max(limite, 1), 500))
        return [dict(f) for f in base.q(sql, args)]

    # Pago simulado: hace lo mismo que hará el aviso real de Mercado Pago.
    # Con la cuenta de Mercado Pago se reemplaza por /api/pagos/mercadopago, que
    # tiene que verificar la firma del aviso y consultar el pago antes de activar.
    @app.post("/api/pagos/simulado", dependencies=[Depends(admin)])
    def pago_simulado(d: PagoSimulado):
        ref = "SIM-" + secrets.token_hex(6)
        return {"pago_ref": ref, **_activar(d.equipo_id, ref, "QR Mercado Pago (simulado)", d.monto, d.minutos)}

    # ---------- rutas del módulo
    @app.post("/modulo/vincular")
    def vincular(d: Vinculo):
        c = base.uno("SELECT * FROM codigos WHERE codigo = ?", (d.codigo,))
        if not c or c["expira_ms"] < ahora_ms():
            raise HTTPException(404, "Código inválido o vencido")
        base.ejec("DELETE FROM codigos WHERE codigo = ?", (d.codigo,))  # se usa una sola vez
        viejo = base.uno("SELECT id FROM modulos WHERE equipo_id = ?", (c["equipo_id"],))
        if viejo:  # vincular un módulo nuevo reemplaza al anterior
            base.ejec("DELETE FROM ordenes WHERE modulo_id = ?", (viejo["id"],))
            base.ejec("DELETE FROM modulos WHERE id = ?", (viejo["id"],))
        modulo_id = "mod_" + secrets.token_hex(8)
        secreto = secrets.token_hex(32)
        base.ejec("INSERT INTO modulos (id, equipo_id, secreto, ultimo_contacto, firmware) VALUES (?,?,?,?,?)",
                  (modulo_id, c["equipo_id"], secreto, ahora_ms(), d.firmware))
        base.evento(c["equipo_id"], "modulo_vinculado", f"{modulo_id} · firmware {d.firmware}")
        return {"modulo_id": modulo_id, "secreto": secreto, "equipo_id": c["equipo_id"]}

    @app.get("/modulo/ordenes")
    def ordenes(m=Depends(modulo_firmado)):
        filas = base.q("SELECT * FROM ordenes WHERE modulo_id = ? AND entregada = 0 AND expira_ms > ? ORDER BY id",
                       (m["id"], ahora_ms()))
        salida = []
        for o in filas:
            base.ejec("UPDATE ordenes SET entregada = 1 WHERE id = ?", (o["id"],))
            salida.append({"id": o["id"], "accion": o["accion"], "segundos": o["segundos"], "expira_ms": o["expira_ms"],
                           "firma": firmas.firma_orden(m["secreto"], o["id"], o["accion"], o["segundos"], o["expira_ms"])})
        return {"ordenes": salida, "ahora_ms": ahora_ms()}

    @app.post("/modulo/reporte")
    async def reporte(request: Request, m=Depends(modulo_firmado)):
        try:
            d = Reporte(**json.loads((await request.body()) or b"{}"))
        except Exception:
            raise HTTPException(422, "Reporte con formato incorrecto")
        eq = m["equipo_id"]
        if d.tipo == "inicio":
            fin = ahora_ms() + (d.segundos_restantes or 0) * 1000
            base.ejec("UPDATE equipos SET estado = 'en_uso', fin_ms = ? WHERE id = ? AND estado != 'fuera'", (fin, eq))
            base.evento(eq, "inicio", f"{d.segundos_restantes or 0} s")
        elif d.tipo == "fin":
            base.ejec("UPDATE equipos SET estado = 'libre', fin_ms = 0 WHERE id = ? AND estado = 'en_uso'", (eq,))
            base.evento(eq, "fin", d.detalle)
        elif d.tipo == "confirmacion" and d.orden_id:
            base.ejec("UPDATE ordenes SET confirmada = 1 WHERE id = ? AND modulo_id = ?", (d.orden_id, m["id"]))
        elif d.tipo in ("uso_sin_pago", "tapa_abierta"):
            textos = {"uso_sin_pago": "La máquina funciona sin un pago registrado", "tapa_abierta": "Se abrió la caja del módulo"}
            base.evento(eq, d.tipo, d.detalle or textos[d.tipo], alerta=True)
        elif d.tipo == "reinicio":
            base.evento(eq, "reinicio", d.detalle)
        return {"ok": True}

    return app


if os.environ.get("MILENIUM_ADMIN_TOKEN"):  # para `uvicorn app:app`
    app = crear_app()
