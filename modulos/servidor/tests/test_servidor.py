"""Pruebas de punta a punta: servidor + módulo simulado, sin hardware."""
import pathlib
import sys
import time

import pytest
from fastapi.testclient import TestClient

RAIZ = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ / "servidor"))
sys.path.insert(0, str(RAIZ / "simulador"))

import app as servidor  # noqa: E402
import firmas  # noqa: E402
from modulo_simulado import ModuloSimulado  # noqa: E402

TOKEN = "token-de-prueba-123456"
ADMIN = {"Authorization": f"Bearer {TOKEN}"}


@pytest.fixture
def c(tmp_path):
    return TestClient(servidor.crear_app(str(tmp_path / "t.db"), TOKEN))


def nuevo_equipo(c, **k):
    d = {"nombre": "Lavarropas 1", "modo": "uso", "precio": 3500, "minutos": 40, **k}
    r = c.post("/api/equipos", json=d, headers=ADMIN)
    assert r.status_code == 200, r.text
    return r.json()


def modulo_vinculado(c, equipo_id):
    codigo = c.post(f"/api/equipos/{equipo_id}/codigo", headers=ADMIN).json()["codigo"]
    m = ModuloSimulado(c)
    m.vincular(codigo)
    return m


def test_sin_token_no_entra(c):
    assert c.get("/api/equipos").status_code == 401
    assert c.get("/api/equipos", headers={"Authorization": "Bearer otro-token-cualquiera"}).status_code == 401


def test_vincular_y_ver_conectado(c):
    e = nuevo_equipo(c)
    m = modulo_vinculado(c, e["id"])
    eq = c.get("/api/equipos", headers=ADMIN).json()[0]
    assert eq["modulo"]["id"] == m.modulo_id and eq["modulo"]["conectado"]


def test_codigo_sirve_una_sola_vez_y_vence(c, monkeypatch):
    e = nuevo_equipo(c)
    codigo = c.post(f"/api/equipos/{e['id']}/codigo", headers=ADMIN).json()["codigo"]
    assert c.post("/modulo/vincular", json={"codigo": codigo}).status_code == 200
    assert c.post("/modulo/vincular", json={"codigo": codigo}).status_code == 404
    codigo2 = c.post(f"/api/equipos/{e['id']}/codigo", headers=ADMIN).json()["codigo"]
    real = servidor.ahora_ms
    monkeypatch.setattr(servidor, "ahora_ms", lambda: real() + servidor.VIGENCIA_CODIGO_MS + 1000)
    assert c.post("/modulo/vincular", json={"codigo": codigo2}).status_code == 404


def test_cobro_activa_y_termina(c):
    e = nuevo_equipo(c, minutos=1)
    m = modulo_vinculado(c, e["id"])
    r = c.post(f"/api/equipos/{e['id']}/activar", json={"pago_ref": "P1", "medio": "Efectivo", "monto": 3500}, headers=ADMIN)
    assert r.status_code == 200 and r.json()["segundos"] == 60
    m.ciclo()
    assert m.encendido
    assert c.get("/api/equipos", headers=ADMIN).json()[0]["estado"] == "en_uso"
    m.apaga_en = time.time() - 1  # pasa el tiempo
    m.ciclo()
    assert not m.encendido
    assert c.get("/api/equipos", headers=ADMIN).json()[0]["estado"] == "libre"


def test_por_minuto_usa_los_minutos_pagados(c):
    e = nuevo_equipo(c, nombre="Aspiradora", modo="minuto", precio=500)
    m = modulo_vinculado(c, e["id"])
    r = c.post(f"/api/equipos/{e['id']}/activar", json={"pago_ref": "P2", "medio": "QR", "monto": 2000, "minutos": 4}, headers=ADMIN)
    assert r.json()["segundos"] == 240
    m.ciclo()
    assert 230 < m.apaga_en - time.time() <= 240


def test_mismo_pago_no_activa_dos_veces(c):
    e = nuevo_equipo(c)
    m = modulo_vinculado(c, e["id"])
    body = {"pago_ref": "P3", "medio": "Efectivo", "monto": 1}
    assert c.post(f"/api/equipos/{e['id']}/activar", json=body, headers=ADMIN).status_code == 200
    m.ciclo(); m.apaga_en = time.time() - 1; m.ciclo()
    assert c.post(f"/api/equipos/{e['id']}/activar", json=body, headers=ADMIN).status_code == 409


def test_no_activa_sin_modulo_desconectado_o_fuera_de_servicio(c, monkeypatch):
    e = nuevo_equipo(c)
    body = {"pago_ref": "P4", "medio": "Efectivo", "monto": 1}
    assert c.post(f"/api/equipos/{e['id']}/activar", json=body, headers=ADMIN).status_code == 409  # sin módulo
    modulo_vinculado(c, e["id"])
    c.post(f"/api/equipos/{e['id']}/servicio", json={"fuera": True}, headers=ADMIN)
    assert c.post(f"/api/equipos/{e['id']}/activar", json=body, headers=ADMIN).status_code == 409  # fuera
    c.post(f"/api/equipos/{e['id']}/servicio", json={"fuera": False}, headers=ADMIN)
    real = servidor.ahora_ms
    monkeypatch.setattr(servidor, "ahora_ms", lambda: real() + (servidor.SEGUNDOS_CONECTADO + 5) * 1000)
    r = c.post(f"/api/equipos/{e['id']}/activar", json=body, headers=ADMIN)
    assert r.status_code == 409 and "desconectado" in r.json()["detail"]


def test_firma_falsa_y_pedido_repetido_se_rechazan(c):
    e = nuevo_equipo(c)
    m = modulo_vinculado(c, e["id"])
    ts = int(time.time() * 1000) + 50
    h = {"X-Modulo": m.modulo_id, "X-Ts": str(ts), "X-Firma": "0" * 64}
    assert c.get("/modulo/ordenes", headers=h).status_code == 401
    h["X-Firma"] = firmas.firma_pedido(m.secreto, "GET", "/modulo/ordenes", ts, b"")
    assert c.get("/modulo/ordenes", headers=h).status_code == 200
    assert c.get("/modulo/ordenes", headers=h).status_code == 401  # el mismo pedido copiado
    alertas = c.get("/api/eventos?solo_alertas=true", headers=ADMIN).json()
    assert {a["tipo"] for a in alertas} >= {"firma_invalida", "pedido_repetido"}


def test_modulo_ignora_orden_alterada(c):
    e = nuevo_equipo(c)
    m = modulo_vinculado(c, e["id"])
    ahora = int(time.time() * 1000)
    buena = {"id": 99, "accion": "activar", "segundos": 60, "expira_ms": ahora + 30000}
    buena["firma"] = firmas.firma_orden(m.secreto, 99, "activar", 60, ahora + 30000)
    alterada = {**buena, "segundos": 9999}  # alguien intenta cambiar los minutos
    m.procesar([alterada], ahora)
    assert not m.encendido and m.rechazadas
    vencida = {**buena, "expira_ms": ahora - 1}
    m.procesar([vencida], ahora)
    assert not m.encendido


def test_alertas_uso_sin_pago_y_tapa(c):
    e = nuevo_equipo(c)
    m = modulo_vinculado(c, e["id"])
    m.reportar("uso_sin_pago")
    m.reportar("tapa_abierta")
    tipos = [a["tipo"] for a in c.get("/api/eventos?solo_alertas=true", headers=ADMIN).json()]
    assert "uso_sin_pago" in tipos and "tapa_abierta" in tipos


def test_detener_desde_el_sistema(c):
    e = nuevo_equipo(c)
    m = modulo_vinculado(c, e["id"])
    c.post(f"/api/equipos/{e['id']}/activar", json={"pago_ref": "P5", "medio": "Efectivo", "monto": 1}, headers=ADMIN)
    m.ciclo()
    assert m.encendido
    c.post(f"/api/equipos/{e['id']}/detener", headers=ADMIN)
    m.ciclo()
    assert not m.encendido
    assert c.get("/api/equipos", headers=ADMIN).json()[0]["estado"] == "libre"


def test_pago_simulado_mercadopago(c):
    e = nuevo_equipo(c)
    m = modulo_vinculado(c, e["id"])
    r = c.post("/api/pagos/simulado", json={"equipo_id": e["id"], "monto": 3500}, headers=ADMIN)
    assert r.status_code == 200 and r.json()["pago_ref"].startswith("SIM-")
    m.ciclo()
    assert m.encendido


def test_vincular_otro_modulo_reemplaza_al_anterior(c):
    e = nuevo_equipo(c)
    viejo = modulo_vinculado(c, e["id"])
    nuevo = modulo_vinculado(c, e["id"])
    assert viejo.modulo_id != nuevo.modulo_id
    with pytest.raises(Exception):
        viejo.ciclo()  # el módulo viejo ya no es reconocido


def test_editar_equipo(c):
    e = nuevo_equipo(c)
    r = c.patch(f"/api/equipos/{e['id']}", json={"nombre": "Lavarropas grande", "precio": 9000}, headers=ADMIN)
    assert r.status_code == 200 and r.json()["nombre"] == "Lavarropas grande" and r.json()["precio"] == 9000
    assert r.json()["minutos"] == 40  # lo que no se manda queda igual
    assert c.patch(f"/api/equipos/{e['id']}", json={"precio": 1}).status_code == 401
    assert c.patch("/api/equipos/999", json={"precio": 1}, headers=ADMIN).status_code == 404


def test_la_app_se_abre_desde_el_servidor(c):
    r = c.get("/app/")
    assert r.status_code == 200 and "Milenium 2" in r.text


def test_cors_solo_para_la_pagina_y_la_compu(c):
    pre = {"Access-Control-Request-Method": "GET", "Access-Control-Request-Headers": "authorization"}
    ok = c.options("/api/equipos", headers={"Origin": "https://bsturniolo.github.io", **pre})
    assert ok.headers.get("access-control-allow-origin") == "https://bsturniolo.github.io"
    local = c.options("/api/equipos", headers={"Origin": "http://localhost:5500", **pre})
    assert local.headers.get("access-control-allow-origin") == "http://localhost:5500"
    otro = c.options("/api/equipos", headers={"Origin": "https://sitio-cualquiera.com", **pre})
    assert "access-control-allow-origin" not in otro.headers
