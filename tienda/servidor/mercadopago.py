"""Todo lo que habla con Mercado Pago (Checkout Pro), sin librerías extra.

Cómo funciona un cobro:
1. La tienda crea una "preferencia" con los productos y el total. Mercado Pago devuelve un link de pago.
2. El cliente paga en la página de Mercado Pago y vuelve a la tienda.
3. Mercado Pago avisa al servidor (/mp/aviso) con el número de pago. El servidor NO le cree al aviso:
   le pregunta a Mercado Pago por ese pago y solo lo da por bueno si está aprobado y el monto coincide.

Documentación oficial: https://www.mercadopago.com.ar/developers/es/docs/checkout-pro
"""
from __future__ import annotations

import hashlib
import hmac
import json
import urllib.error
import urllib.request

URL_API = "https://api.mercadopago.com"


class ErrorMP(Exception):
    pass


class MercadoPago:
    def __init__(self, access_token: str, timeout: float = 20):
        self.token = access_token
        self.timeout = timeout

    def _pedir(self, metodo: str, ruta: str, datos: dict | None = None) -> dict:
        cuerpo = json.dumps(datos).encode() if datos is not None else None
        req = urllib.request.Request(URL_API + ruta, data=cuerpo, method=metodo, headers={
            "Authorization": f"Bearer {self.token}", "Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as r:
                return json.loads(r.read() or b"{}")
        except urllib.error.HTTPError as e:
            raise ErrorMP(f"Mercado Pago respondió {e.code}: {e.read()[:300].decode(errors='replace')}")
        except (urllib.error.URLError, TimeoutError) as e:
            raise ErrorMP(f"No se pudo conectar con Mercado Pago: {e}")

    def crear_preferencia(self, pedido: dict, url_tienda: str, url_aviso: str) -> dict:
        """Devuelve {"id": ..., "url": link de pago}."""
        items = [{"id": i["codigo"] or str(i["producto_id"]), "title": i["nombre"][:250], "quantity": int(i["cantidad"]),
                  "unit_price": float(i["precio"]), "currency_id": "ARS"} for i in pedido["items"]]
        if pedido["envio"] > 0:
            items.append({"id": "envio", "title": pedido["envio_nombre"] or "Envío", "quantity": 1,
                          "unit_price": float(pedido["envio"]), "currency_id": "ARS"})
        volver = f"{url_tienda}?pedido={pedido['numero']}&t={pedido['token']}"
        c = pedido["cliente"]
        r = self._pedir("POST", "/checkout/preferences", {
            "items": items,
            "external_reference": pedido["numero"],
            "notification_url": url_aviso,
            "back_urls": {"success": volver, "pending": volver, "failure": volver},
            "auto_return": "approved",
            "payer": {"name": c.get("nombre", ""), "email": c.get("email", "")},
            "statement_descriptor": "TIENDA",
        })
        return {"id": r.get("id", ""), "url": r.get("init_point", "")}

    def pago(self, pago_id: str) -> dict:
        """Consulta un pago: status, external_reference, transaction_amount, currency_id, payment_type_id."""
        if not str(pago_id).isdigit():
            raise ErrorMP("Número de pago inválido")
        return self._pedir("GET", f"/v1/payments/{pago_id}")


def firma_aviso_valida(secreto: str, x_signature: str, x_request_id: str, data_id: str) -> bool:
    """Verifica la firma del aviso (encabezado x-signature: "ts=...,v1=...").

    Es opcional: aunque no se configure, el servidor igual confirma cada pago preguntándole a Mercado Pago.
    """
    partes = dict(p.split("=", 1) for p in (x_signature or "").split(",") if "=" in p)
    ts, v1 = partes.get("ts", "").strip(), partes.get("v1", "").strip()
    if not ts or not v1:
        return False
    plantilla = f"id:{str(data_id).lower()};request-id:{x_request_id};ts:{ts};"
    esperada = hmac.new(secreto.encode(), plantilla.encode(), hashlib.sha256).hexdigest()
    return hmac.compare_digest(esperada, v1)
