"""Pruebas de punta a punta de la tienda, con un Mercado Pago falso y un sistema conectado falso."""
import base64
import hashlib
import hmac
import json
import pathlib
import sys

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "servidor"))
import app as tienda  # noqa: E402
import mercadopago  # noqa: E402

TOKEN = "clave-de-prueba-123456"
ADMIN = {"Authorization": f"Bearer {TOKEN}"}
CLIENTE = {"nombre": "Ana Gómez", "email": "ana@ejemplo.com", "telefono": "2611234567"}


class MPFalso:
    def __init__(self):
        self.pagos = {}
        self.preferencias = []

    def crear_preferencia(self, pedido, url_tienda, url_aviso):
        self.preferencias.append((pedido, url_tienda, url_aviso))
        return {"id": "pref-1", "url": "https://mp.falso/pagar/" + pedido["numero"]}

    def pago(self, pago_id):
        if pago_id not in self.pagos:
            raise mercadopago.ErrorMP("no existe")
        return self.pagos[pago_id]


class SistemaFalso:
    def __init__(self, falla=False):
        self.recibidos = []
        self.falla = falla

    def __call__(self, url, clave, cuerpo):
        if self.falla:
            raise RuntimeError("apagado")
        self.recibidos.append((url, clave, json.loads(cuerpo), hmac.new(clave.encode(), cuerpo, hashlib.sha256).hexdigest()))


def nueva(tmp_path, **k):
    k.setdefault("prueba", True)
    return TestClient(tienda.crear_app(str(tmp_path / "t.db"), admin_token=TOKEN, carpeta_fotos=str(tmp_path / "fotos"),
                                       reintentos_en_fondo=False, **k))


@pytest.fixture
def c(tmp_path):
    return nueva(tmp_path)


def producto(c, **k):
    d = {"codigo": "SKU1", "nombre": "Remera", "precio": 1000, "stock": 5, **k}
    r = c.post("/api/panel/productos", json=d, headers=ADMIN)
    assert r.status_code == 200, r.text
    return r.json()


def comprar(c, pid, cant=1, envio="retiro", **cli):
    return c.post("/api/pedidos", json={"items": [{"producto_id": pid, "cantidad": cant}], "envio_id": envio, "cliente": {**CLIENTE, **cli}})


def test_panel_pide_clave(c):
    assert c.get("/api/panel/productos").status_code == 401
    assert c.get("/api/panel/productos", headers={"Authorization": "Bearer otra-clave-cualquiera"}).status_code == 401


def test_paginas(c):
    assert "<html" in c.get("/").text.lower()
    assert "<html" in c.get("/panel").text.lower()


def test_catalogo_publico_sin_ocultos_ni_costos(c):
    producto(c)
    producto(c, codigo="SKU2", nombre="Oculto", visible=False)
    d = c.get("/api/tienda").json()
    assert [p["nombre"] for p in d["productos"]] == ["Remera"]
    assert "stock" not in d["productos"][0] and d["productos"][0]["disponible"] == 5
    assert d["pagos"] == "simulado"


def test_compra_simulada_descuenta_stock(c):
    p = producto(c)
    r = comprar(c, p["id"], 2)
    assert r.status_code == 200, r.text
    ped = r.json()
    assert ped["total"] == 2000 and ped["numero"] == "W-00001"
    # mientras no paga, el stock queda apartado
    assert c.get("/api/tienda").json()["productos"][0]["disponible"] == 3
    r = c.post(f"/api/pedidos/{ped['numero']}/pago-simulado", json={"t": ped["t"]})
    assert r.json()["estado"] == "pagado"
    assert c.get("/api/panel/productos", headers=ADMIN).json()[0]["stock"] == 3
    # pagar dos veces no descuenta dos veces
    c.post(f"/api/pedidos/{ped['numero']}/pago-simulado", json={"t": ped["t"]})
    assert c.get("/api/panel/productos", headers=ADMIN).json()[0]["stock"] == 3


def test_no_vende_mas_que_el_stock(c):
    p = producto(c, stock=2)
    assert comprar(c, p["id"], 3).status_code == 409
    assert comprar(c, p["id"], 2).status_code == 200
    r = comprar(c, p["id"], 1)  # el anterior lo apartó
    assert r.status_code == 409 and "agotó" in r.json()["detail"]


def test_precio_lo_pone_el_servidor(c):
    p = producto(c)
    r = c.post("/api/pedidos", json={"items": [{"producto_id": p["id"], "cantidad": 1, "precio": 1}], "envio_id": "retiro", "cliente": CLIENTE})
    assert r.json()["total"] == 1000


def test_pedido_ajeno_no_se_ve(c):
    p = producto(c)
    ped = comprar(c, p["id"]).json()
    assert c.get(f"/api/pedidos/{ped['numero']}?t=token-equivocado-xx").status_code == 404
    assert c.get(f"/api/pedidos/{ped['numero']}?t={ped['t']}").json()["estado"] == "esperando_pago"
    assert "cliente" not in c.get(f"/api/pedidos/{ped['numero']}?t={ped['t']}").json()


def test_envio_con_direccion(c):
    cfg = c.get("/api/panel/config", headers=ADMIN).json()
    cfg["envios"].append({"id": "moto", "nombre": "Envío en moto", "precio": 500, "pide_direccion": True})
    assert c.put("/api/panel/config", json=cfg, headers=ADMIN).status_code == 200
    p = producto(c)
    assert comprar(c, p["id"], envio="moto").status_code == 422
    r = comprar(c, p["id"], envio="moto", direccion="San Martín 123, Mendoza")
    assert r.json()["total"] == 1500


def test_sin_mercadopago_ni_prueba_es_manual(tmp_path):
    c = nueva(tmp_path, prueba=False)
    p = producto(c)
    ped = comprar(c, p["id"]).json()
    assert ped["pagos"] == "manual"
    assert c.post(f"/api/pedidos/{ped['numero']}/pago-simulado", json={"t": ped["t"]}).status_code == 404
    r = c.post(f"/api/panel/pedidos/{ped['numero']}/estado", json={"estado": "pagado"}, headers=ADMIN)
    assert r.json()["estado"] == "pagado"
    assert c.get("/api/panel/productos", headers=ADMIN).json()[0]["stock"] == 4


def test_mercadopago_aviso_confirmado_con_la_api(tmp_path):
    mp = MPFalso()
    c = nueva(tmp_path, mp=mp, prueba=False)
    p = producto(c)
    ped = comprar(c, p["id"], 2).json()
    assert ped["pagar_url"].startswith("https://mp.falso/") and ped["pagos"] == "mercadopago"
    assert mp.preferencias[0][2].endswith("/mp/aviso")
    # aviso de un pago que no está aprobado: no cambia nada
    mp.pagos["111"] = {"status": "pending", "external_reference": ped["numero"], "transaction_amount": 2000, "currency_id": "ARS"}
    c.post("/mp/aviso", json={"type": "payment", "data": {"id": "111"}})
    assert c.get(f"/api/pedidos/{ped['numero']}?t={ped['t']}").json()["estado"] == "esperando_pago"
    # pago aprobado por menos plata: no se acepta
    mp.pagos["112"] = {"status": "approved", "external_reference": ped["numero"], "transaction_amount": 10, "currency_id": "ARS"}
    c.post("/mp/aviso", json={"type": "payment", "data": {"id": "112"}})
    assert c.get(f"/api/pedidos/{ped['numero']}?t={ped['t']}").json()["estado"] == "esperando_pago"
    # pago bueno
    mp.pagos["113"] = {"status": "approved", "external_reference": ped["numero"], "transaction_amount": 2000, "currency_id": "ARS", "payment_type_id": "credit_card"}
    c.post("/mp/aviso?type=payment&data.id=113")
    v = c.get(f"/api/pedidos/{ped['numero']}?t={ped['t']}").json()
    assert v["estado"] == "pagado" and "crédito" in v["pago_medio"]
    c.post("/mp/aviso", json={"type": "payment", "data": {"id": "113"}})  # repetido
    assert c.get("/api/panel/productos", headers=ADMIN).json()[0]["stock"] == 3


def test_vuelta_de_mercadopago_confirma_si_el_aviso_no_llego(tmp_path):
    mp = MPFalso()
    c = nueva(tmp_path, mp=mp)
    p = producto(c)
    ped = comprar(c, p["id"]).json()
    mp.pagos["200"] = {"status": "approved", "external_reference": ped["numero"], "transaction_amount": 1000, "currency_id": "ARS"}
    assert c.get(f"/api/pedidos/{ped['numero']}?t={ped['t']}&payment_id=200").json()["estado"] == "pagado"


def test_firma_del_aviso_de_mp():
    sec = "secreto"
    v1 = hmac.new(sec.encode(), b"id:123;request-id:abc;ts:1700;", hashlib.sha256).hexdigest()
    assert mercadopago.firma_aviso_valida(sec, f"ts=1700,v1={v1}", "abc", "123")
    assert not mercadopago.firma_aviso_valida(sec, f"ts=1701,v1={v1}", "abc", "123")


def test_avisa_al_sistema_conectado_con_firma(tmp_path):
    s = SistemaFalso()
    c = nueva(tmp_path, enviar_aviso=s, conectar=("https://milenium.ejemplo/tienda/pedido", "clave-compartida-larga-123"))
    p = producto(c)
    ped = comprar(c, p["id"], 2).json()
    c.post(f"/api/pedidos/{ped['numero']}/pago-simulado", json={"t": ped["t"]})
    assert len(s.recibidos) == 1
    url, clave, cuerpo, _ = s.recibidos[0]
    assert url.endswith("/tienda/pedido") and cuerpo["pedido_id"] == ped["numero"]
    assert cuerpo["items"] == [{"codigo": "SKU1", "nombre": "Remera", "cantidad": 2, "precio": 1000.0}]
    assert cuerpo["total"] == 2000 and cuerpo["cliente"]["email"] == "ana@ejemplo.com"
    assert c.get("/api/panel/pedidos", headers=ADMIN).json()[0]["aviso_estado"] == "ok"


def test_si_el_sistema_no_responde_reintenta(tmp_path):
    s = SistemaFalso(falla=True)
    c = nueva(tmp_path, enviar_aviso=s, conectar=("https://x/tienda/pedido", "clave-compartida-larga-123"))
    p = producto(c)
    ped = comprar(c, p["id"]).json()
    c.post(f"/api/pedidos/{ped['numero']}/pago-simulado", json={"t": ped["t"]})
    v = c.get("/api/panel/pedidos", headers=ADMIN).json()[0]
    assert v["aviso_estado"] == "pendiente" and v["aviso_intentos"] == 1
    s.falla = False
    c.app.state.reintentar_avisos()
    assert c.get("/api/panel/pedidos", headers=ADMIN).json()[0]["aviso_estado"] == "ok"


def test_formato_compatible_con_milenium(tmp_path):
    """El aviso que manda la tienda lo acepta el servidor de Milenium 2 tal cual."""
    import importlib.util
    ruta = pathlib.Path(__file__).resolve().parents[2] / "modulos" / "servidor"
    if not (ruta / "app.py").exists():
        pytest.skip("Milenium 2 no está en esta copia")
    sys.path.insert(0, str(ruta))  # para que encuentre firmas.py
    spec = importlib.util.spec_from_file_location("milenium_app", ruta / "app.py")
    milenium = importlib.util.module_from_spec(spec)
    sys.modules["milenium_app"] = milenium
    spec.loader.exec_module(milenium)
    clave = "clave-compartida-larga-123"
    mil = TestClient(milenium.crear_app(str(tmp_path / "m.db"), "token-milenium-123456", clave))
    enviados = []

    def a_milenium(url, k, cuerpo):
        r = mil.post("/tienda/pedido", content=cuerpo, headers={"X-Firma": hmac.new(k.encode(), cuerpo, hashlib.sha256).hexdigest(), "Content-Type": "application/json"})
        enviados.append(r.status_code)
        if r.status_code != 200:
            raise RuntimeError(r.text)

    c = nueva(tmp_path, enviar_aviso=a_milenium, conectar=("https://m/tienda/pedido", clave))
    p = producto(c)
    ped = comprar(c, p["id"]).json()
    c.post(f"/api/pedidos/{ped['numero']}/pago-simulado", json={"t": ped["t"]})
    assert enviados == [200]
    v = mil.get("/api/ventas-web", headers={"Authorization": "Bearer token-milenium-123456"}).json()
    assert v[0]["pedido_id"] == ped["numero"] and v[0]["total"] == 1000


def test_cancelar_pagado_devuelve_stock(c):
    p = producto(c)
    ped = comprar(c, p["id"], 2).json()
    c.post(f"/api/pedidos/{ped['numero']}/pago-simulado", json={"t": ped["t"]})
    assert c.post(f"/api/panel/pedidos/{ped['numero']}/estado", json={"estado": "enviado"}, headers=ADMIN).json()["estado"] == "enviado"
    c.post(f"/api/panel/pedidos/{ped['numero']}/estado", json={"estado": "cancelado"}, headers=ADMIN)
    assert c.get("/api/panel/productos", headers=ADMIN).json()[0]["stock"] == 5


def test_fotos(c):
    png = base64.b64encode(b"\x89PNG\r\n\x1a\n" + b"0" * 50).decode()
    r = c.post("/api/panel/fotos", json={"data_url": "data:image/png;base64," + png}, headers=ADMIN)
    assert r.status_code == 200
    assert c.get(r.json()["url"]).status_code == 200
    falsa = base64.b64encode(b"<script>").decode()
    assert c.post("/api/panel/fotos", json={"data_url": "data:image/png;base64," + falsa}, headers=ADMIN).status_code == 422
    assert c.get("/fotos/../app.py").status_code == 404


def test_sincronizar_desde_otro_sistema(c):
    producto(c)
    r = c.put("/api/panel/sincronizar", json={"productos": [{"codigo": "SKU1", "nombre": "Remera", "precio": 1200, "stock": 9},
                                                            {"codigo": "NUEVO", "nombre": "Gorra", "precio": 800, "stock": 3}]}, headers=ADMIN)
    assert r.json() == {"actualizados": 1, "creados": 1}
    ps = {p["codigo"]: p for p in c.get("/api/panel/productos", headers=ADMIN).json()}
    assert ps["SKU1"]["precio"] == 1200 and ps["SKU1"]["stock"] == 9
    assert ps["NUEVO"]["visible"] is False  # los nuevos quedan ocultos hasta revisarlos


def test_ventas_y_clientes_solo_con_clave(c):
    p = producto(c)
    comprar(c, p["id"])
    for ruta in ("/api/panel/pedidos", "/api/panel/resumen", "/api/panel/config"):
        assert c.get(ruta).status_code == 401
    assert "Ana" not in c.get("/api/tienda").text


def test_carrito_para_pegar_en_otra_pagina(tmp_path, monkeypatch):
    monkeypatch.setenv("TIENDA_ORIGENES", "https://mipagina.com.ar")
    mp = MPFalso()
    c = nueva(tmp_path, mp=mp)
    assert "attachShadow" in c.get("/tienda.js").text
    r = c.options("/api/pedidos", headers={"Origin": "https://mipagina.com.ar", "Access-Control-Request-Method": "POST",
                                           "Access-Control-Request-Headers": "content-type"})
    assert r.headers.get("access-control-allow-origin") == "https://mipagina.com.ar"
    p = producto(c, stock=10)
    d = {"items": [{"producto_id": p["id"], "cantidad": 1}], "envio_id": "retiro", "cliente": CLIENTE}
    c.post("/api/pedidos", json={**d, "volver": "https://mipagina.com.ar/tienda?x=1"})
    assert mp.preferencias[-1][1] == "https://mipagina.com.ar/tienda"   # vuelve a tu página
    c.post("/api/pedidos", json={**d, "volver": "https://sitio-trucho.com/"})
    assert mp.preferencias[-1][1].startswith("http://testserver/")     # una página no autorizada no
