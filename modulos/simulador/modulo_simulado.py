"""Módulo simulado: se comporta como la placa ESP32 pero corre en la compu.

Sirve para probar todo el sistema sin tener todavía la parte física.

Uso por consola (con el servidor corriendo):
    python modulo_simulado.py --servidor http://127.0.0.1:8000 --codigo 123456

Hace lo mismo que el firmware:
- se vincula con el código de 6 dígitos y guarda su id y su secreto,
- cada 2 segundos pide órdenes firmando el pedido,
- verifica la firma de cada orden, que no esté vencida y que no sea repetida,
- maneja su propio temporizador (si se corta internet, igual apaga a tiempo),
- reporta inicio, fin, latidos y alertas.
"""
from __future__ import annotations

import argparse
import json
import pathlib
import sys
import time

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent / "servidor"))
import firmas  # noqa: E402

MAX_SEGUNDOS_LOCAL = 4 * 3600  # el módulo nunca enciende más que esto, diga lo que diga la orden


class ModuloSimulado:
    def __init__(self, cliente, firmware: str = "sim-1.0"):
        self.cliente = cliente      # httpx.Client o TestClient de FastAPI
        self.firmware = firmware
        self.modulo_id = None
        self.secreto = None
        self.ultima_orden = 0       # ids de orden siempre crecientes: una orden vieja no se repite
        self.encendido = False      # salida a la máquina (relé o pulso de ficha)
        self.apaga_en = 0.0
        self.ts_ultimo = 0
        self.rechazadas = []

    # ---------- comunicación
    def _ts(self) -> int:
        ts = int(time.time() * 1000)
        self.ts_ultimo = max(ts, self.ts_ultimo + 1)
        return self.ts_ultimo

    def _firmado(self, metodo: str, ruta: str, datos: dict | None = None):
        cuerpo = json.dumps(datos).encode() if datos is not None else b""
        ts = self._ts()
        h = {"X-Modulo": self.modulo_id, "X-Ts": str(ts),
             "X-Firma": firmas.firma_pedido(self.secreto, metodo, ruta, ts, cuerpo)}
        if datos is not None:
            h["Content-Type"] = "application/json"
        r = self.cliente.request(metodo, ruta, content=cuerpo or None, headers=h)
        r.raise_for_status()
        return r.json()

    def vincular(self, codigo: str):
        r = self.cliente.post("/modulo/vincular", json={"codigo": codigo, "firmware": self.firmware})
        r.raise_for_status()
        d = r.json()
        self.modulo_id, self.secreto = d["modulo_id"], d["secreto"]
        self.reportar("reinicio", detalle="primer arranque")
        return d

    def reportar(self, tipo: str, **extra):
        return self._firmado("POST", "/modulo/reporte", {"tipo": tipo, **extra})

    # ---------- lógica de la placa
    def orden_valida(self, o: dict, ahora_ms: int) -> bool:
        firma = firmas.firma_orden(self.secreto, o["id"], o["accion"], o["segundos"], o["expira_ms"])
        if not firmas.iguales(o.get("firma", ""), firma):
            return False
        if o["expira_ms"] < ahora_ms or o["id"] <= self.ultima_orden:
            return False
        return o["accion"] in ("activar", "detener")

    def procesar(self, ordenes: list, ahora_ms: int):
        for o in ordenes:
            if not self.orden_valida(o, ahora_ms):
                self.rechazadas.append(o)
                continue
            self.ultima_orden = o["id"]
            if o["accion"] == "activar":
                seg = min(int(o["segundos"]), MAX_SEGUNDOS_LOCAL)
                self.encendido, self.apaga_en = True, time.time() + seg
                self.reportar("confirmacion", orden_id=o["id"])
                self.reportar("inicio", orden_id=o["id"], segundos_restantes=seg)
            else:
                self.reportar("confirmacion", orden_id=o["id"])
                self.apagar("detenido desde el sistema")

    def apagar(self, motivo: str):
        if self.encendido:
            self.encendido = False
            self.reportar("fin", detalle=motivo)

    def ciclo(self):
        """Una vuelta del loop de la placa."""
        if self.encendido and time.time() >= self.apaga_en:
            self.apagar("terminó el tiempo pagado")
        d = self._firmado("GET", "/modulo/ordenes")
        self.procesar(d["ordenes"], d["ahora_ms"])


def main():
    import httpx
    p = argparse.ArgumentParser(description="Módulo Milenium simulado")
    p.add_argument("--servidor", default="http://127.0.0.1:8000")
    p.add_argument("--codigo", required=True, help="código de vinculación de 6 dígitos")
    a = p.parse_args()
    m = ModuloSimulado(httpx.Client(base_url=a.servidor, timeout=10))
    d = m.vincular(a.codigo)
    print(f"Vinculado al equipo {d['equipo_id']} como {m.modulo_id}")
    ultimo_latido = 0.0
    while True:
        try:
            m.ciclo()
            if time.time() - ultimo_latido > 30:
                m.reportar("latido"); ultimo_latido = time.time()
            estado = f"ENCENDIDO, faltan {int(m.apaga_en - time.time())} s" if m.encendido else "apagado"
            print(f"\r{estado:40}", end="", flush=True)
        except Exception as e:  # sin conexión: el temporizador local sigue funcionando
            print(f"\nSin conexión ({e}); reintento")
            if m.encendido and time.time() >= m.apaga_en:
                m.encendido = False
        time.sleep(2)


if __name__ == "__main__":
    main()
