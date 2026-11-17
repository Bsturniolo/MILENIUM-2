"""Firmas HMAC compartidas entre el servidor, el módulo y el simulador.

Cada módulo tiene un secreto propio de 32 bytes que se entrega una sola vez al
vincularlo. Con ese secreto:

- el módulo firma cada pedido que hace al servidor (firma_pedido), y
- el servidor firma cada orden que le manda al módulo (firma_orden).

Así nadie que no tenga el secreto puede ni hablar en nombre del módulo ni darle
órdenes, aunque vea el tráfico.
"""
import hashlib
import hmac


def _hmac(secreto_hex: str, mensaje: str) -> str:
    return hmac.new(bytes.fromhex(secreto_hex), mensaje.encode(), hashlib.sha256).hexdigest()


def firma_pedido(secreto_hex: str, metodo: str, ruta: str, ts_ms: int, cuerpo: bytes) -> str:
    """Firma de un pedido del módulo al servidor."""
    resumen = hashlib.sha256(cuerpo or b"").hexdigest()
    return _hmac(secreto_hex, f"{metodo.upper()}\n{ruta}\n{ts_ms}\n{resumen}")


def firma_orden(secreto_hex: str, orden_id: int, accion: str, segundos: int, expira_ms: int) -> str:
    """Firma de una orden del servidor al módulo."""
    return _hmac(secreto_hex, f"{orden_id}|{accion}|{segundos}|{expira_ms}")


def firma_tienda(clave: str, cuerpo: bytes) -> str:
    """Firma de un pedido de la tienda web: HMAC-SHA256 (hex) del cuerpo tal cual se manda."""
    return hmac.new(clave.encode(), cuerpo, hashlib.sha256).hexdigest()


def iguales(a: str, b: str) -> bool:
    return hmac.compare_digest(a or "", b or "")
