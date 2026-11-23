# Tienda online. Se construye desde esta carpeta:  docker build -t tienda .
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 \
    TIENDA_DB=/datos/tienda.db TIENDA_FOTOS=/datos/fotos

WORKDIR /srv
COPY servidor/requirements.txt servidor/requirements.txt
RUN pip install --no-cache-dir -r servidor/requirements.txt
COPY servidor/app.py servidor/mercadopago.py servidor/
COPY web/ web/

# Corre sin permisos de administrador; la base y las fotos viven en /datos (un volumen que no se borra).
RUN useradd --system --uid 10001 tienda && mkdir -p /datos && chown tienda /datos
USER tienda
VOLUME ["/datos"]
EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/salud', timeout=4)"

WORKDIR /srv/servidor
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers", "--forwarded-allow-ips", "*"]
