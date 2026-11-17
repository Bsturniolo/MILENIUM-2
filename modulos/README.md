# Módulos para máquinas automáticas

Sistema propio para que las máquinas (lavarropas, cafeteras, aspiradoras, etc.) se enciendan solo cuando el cliente pagó.

> ⚠️ **Falta la parte física.** El software está hecho y probado con un módulo simulado, pero todavía no se armó ninguna placa. Ver [FALTA-PARTE-FISICA.md](FALTA-PARTE-FISICA.md).

## Cómo funciona

1. Se cobra un uso (en caja o con QR de Mercado Pago).
2. El **servidor** deja una orden firmada para el módulo de esa máquina.
3. El **módulo** (una placa ESP32 dentro de la máquina) la verifica, enciende la máquina y cuenta el tiempo él mismo.
4. Al terminar apaga y avisa. También avisa si la máquina funciona sin pago o si abren la caja.

## Carpetas

| Carpeta | Qué hay |
| --- | --- |
| `servidor/` | Servidor en Python (FastAPI + SQLite): equipos, vinculación, órdenes firmadas, alertas |
| `firmware/modulo_milenium/` | Código para la placa ESP32 (Arduino). **No probado en placa real todavía** |
| `simulador/` | Módulo simulado en Python: hace lo mismo que la placa, para probar sin hardware |
| `FALTA-PARTE-FISICA.md` | Materiales, conexiones, prueba de mesa y pendientes |

## Probarlo en la compu

```bash
cd modulos/servidor
python -m venv .venv && source .venv/bin/activate   # en Windows: .venv\Scripts\activate
pip install -r requirements.txt -r requirements-dev.txt
pytest -q                                            # 21 pruebas de punta a punta
MILENIUM_ADMIN_TOKEN=cambiar-por-un-token-largo uvicorn app:app --reload
```

Con el servidor andando, en otra consola:

```bash
# 1. crear un equipo y pedir un código de vinculación
curl -X POST localhost:8000/api/equipos -H "Authorization: Bearer cambiar-por-un-token-largo" \
     -H "Content-Type: application/json" -d '{"nombre":"Lavarropas 1","modo":"uso","precio":3500,"minutos":1}'
curl -X POST localhost:8000/api/equipos/1/codigo -H "Authorization: Bearer cambiar-por-un-token-largo"

# 2. arrancar el módulo simulado con ese código
python ../simulador/modulo_simulado.py --codigo 123456

# 3. simular un pago con QR: el módulo se enciende 1 minuto y se apaga solo
curl -X POST localhost:8000/api/pagos/simulado -H "Authorization: Bearer cambiar-por-un-token-largo" \
     -H "Content-Type: application/json" -d '{"equipo_id":1,"monto":3500}'
```

La documentación de todas las rutas queda en `http://localhost:8000/docs`.

### Usarlo desde la app

1. Abrí la app en `http://localhost:8000/app/` (el servidor la trae incluida). También funciona desde la página de GitHub.
2. En **Equipos → Servidor** poné la dirección del servidor y el token de administrador. Se guardan solo en ese navegador.
3. En **Máquinas**, agregá un equipo y tocá **Vincular módulo**. Con el código que aparece, arrancá el módulo simulado: `python ../simulador/modulo_simulado.py --codigo <código>`.
4. Cuando la tarjeta diga "Módulo conectado", cobrá con QR (simulado): la máquina pasa a "Funcionando" y se apaga sola al terminar.

El servidor solo acepta pedidos de la app desde la página de GitHub y desde la compu (`localhost`). Para otra dirección: `MILENIUM_ORIGENES="https://mi-pagina.com"`.

## Rutas principales

| Ruta | Quién la usa | Para qué |
| --- | --- | --- |
| `POST /api/equipos` · `GET /api/equipos` · `PATCH /api/equipos/{id}` | App | Crear, listar y editar equipos, con su módulo y si está conectado |
| `GET /app/` | Navegador | La app completa, servida por el mismo servidor |
| `POST /api/equipos/{id}/codigo` | App | Código de 6 dígitos para vincular un módulo (vence en 10 min) |
| `POST /api/equipos/{id}/activar` | App | Cobro hecho: encender por el tiempo pagado |
| `POST /api/equipos/{id}/detener` · `/servicio` · `/desvincular` | App | Apagar, poner fuera de servicio, quitar el módulo |
| `GET /api/eventos?solo_alertas=true` | App | Historial y alertas |
| `POST /api/pagos/simulado` | App | Simula el aviso de Mercado Pago (temporal) |
| `POST /tienda/pedido` | Tienda web | Pedido pagado, firmado con la clave de la tienda (ver `docs/TIENDA-WEB.md`) |
| `GET /api/ventas-web` · `POST /api/ventas-web/{id}/registrar` · `/simulada` | App | Traer pedidos web, marcarlos como registrados, simular uno |
| `POST /modulo/vincular` | Módulo | Primera conexión con el código |
| `GET /modulo/ordenes` · `POST /modulo/reporte` | Módulo | Pedidos firmados: órdenes, latidos, inicio, fin y alertas |

## Próximos pasos de software

- Reemplazar el pago simulado por el aviso real de Mercado Pago (verificando su firma y consultando el pago antes de activar).
- Subir el servidor a internet con HTTPS: ya está todo preparado, ver [`docs/SUBIR-A-LA-NUBE.md`](../docs/SUBIR-A-LA-NUBE.md).
